"""
Vision-based ingestion for legacy-font Nepali PDFs (e.g. the Krishi Diary).

Why this exists
---------------
The Krishi Diary's text layer is encoded in a tangle of legacy Nepali fonts
(FontasyHimali, Preeti, Shreenath, ...) mixed with real Unicode. Plain text
extraction returns ASCII soup, so we OCR the *rendered* pages with Gemini flash
vision, which returns clean Devanagari Unicode Markdown — tables included.

Token-cost optimisations (Gemini flash is billed per token)
-----------------------------------------------------------
1. Python pre-filter BEFORE any API call — calendar pages and near-blank pages
   are detected from the (garbled but countable) text layer and never sent, so
   we pay zero tokens for them.
2. Model-side SKIP — pages that pass the filter but hold no agricultural text
   return the single token "SKIP" instead of a full transcription.
3. Flat image cost — input tokens don't change between 110–140 DPI, so we render
   at 140 (better OCR) for free.
4. Disk cache — every Gemini result (Markdown or SKIP) is cached per page, so a
   re-run never re-pays for a page already done. The run is fully resumable.

Two phases, deliberately separate so re-chunking never re-pays Gemini:
    Phase 1  transcribe_pdf()   PDF  -> per-page Markdown files   (paid, cached)
    Phase 2  ingest_markdown()  Markdown -> chunks -> Qdrant      (free, re-runnable)

Usage
-----
    # Phase 1 — try a few pages first to eyeball quality + cost:
    python -m rag.ingest_vision transcribe --start 298 --end 303
    # ...then the whole book:
    python -m rag.ingest_vision transcribe
    # Phase 2 — chunk + embed everything transcribed:
    python -m rag.ingest_vision ingest
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import base64
import logging
import re
import time
import uuid
from pathlib import Path

import fitz  # pymupdf
from openai import OpenAI

from config import get_settings
# NOTE: langchain_text_splitters, langchain_qdrant and rag.embeddings all pull in
# heavy TensorFlow/HF deps, so they're imported lazily inside the Phase 2
# functions — Phase 1 transcription starts instantly without loading them.

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_PDF = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "ingest", "agriculture-diary-2082.pdf"
)
DEFAULT_MD_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "output", "diary_md"
)
RENDER_DPI = 140          # input tokens are flat vs DPI, so use a legible one
MAX_OUTPUT_TOKENS = 4000  # bounds worst-case cost per page

# Rough Gemini flash pricing (USD / 1M tokens) — for the running estimate only.
# Verify against Google's current pricing page; these are ballpark.
PRICE_IN_PER_M = 0.30
PRICE_OUT_PER_M = 2.50

_ID_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

TRANSCRIBE_PROMPT = (
    "Transcribe this page into clean GitHub-Flavored Markdown.\n"
    "Rules:\n"
    "- Output ALL prose text and ALL tables. Render tables as Markdown tables "
    "with their header row.\n"
    "- Keep every Nepali word and number EXACTLY as shown, in Devanagari Unicode.\n"
    "- Do NOT transcribe calendars, day/date grids, page numbers, repeated "
    "headers/footers, decorative text, photos or images.\n"
    "- No commentary, no explanations.\n"
    "- If the page contains no agricultural text or table, output exactly: SKIP"
)


# ── Cheap Python pre-filters (no API cost) ────────────────────────────────────
_WEEKDAYS = (
    "sunday", "monday", "tuesday", "wednesday",
    "thursday", "thurday", "friday", "saturday",
)


def is_calendar_page(text: str) -> bool:
    """Calendar pages carry the English weekday names — 4+ means a day grid."""
    low = text.lower()
    return sum(1 for d in _WEEKDAYS if d in low) >= 4


def is_low_content(text: str, min_chars: int = 80) -> bool:
    """Near-blank page (char count is a fine density proxy even when garbled)."""
    return len(text.strip()) < min_chars


# ── Gemini flash vision client ────────────────────────────────────────────────
def _client() -> OpenAI:
    if not settings.google_api_key:
        raise SystemExit("google_api_key not set — put GOOGLE_API_KEY in .env")
    return OpenAI(api_key=settings.google_api_key, base_url=settings.gemini_base_url)


def _transcribe_image(client: OpenAI, png_bytes: bytes) -> tuple[str, int, int]:
    """Return (markdown, prompt_tokens, completion_tokens) for one page image."""
    b64 = base64.b64encode(png_bytes).decode()
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=settings.llm_model_fast,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": TRANSCRIBE_PROMPT},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]}],
                temperature=0,
                max_tokens=MAX_OUTPUT_TOKENS,
            )
            md = (r.choices[0].message.content or "").strip()
            u = r.usage
            return md, u.prompt_tokens, u.completion_tokens
        except Exception as e:
            wait = 2 ** attempt
            logger.warning("Vision call failed (attempt %d): %s — retrying in %ds",
                           attempt + 1, e, wait)
            time.sleep(wait)
    raise RuntimeError("Vision transcription failed after 3 attempts")


# ── Phase 1: PDF -> per-page Markdown (paid, cached, resumable) ───────────────
def transcribe_pdf(
    pdf_path: str = DEFAULT_PDF,
    md_dir: str = DEFAULT_MD_DIR,
    dpi: int = RENDER_DPI,
    start: int = 0,
    end: int | None = None,
) -> None:
    out = Path(md_dir)
    out.mkdir(parents=True, exist_ok=True)
    client = _client()

    doc = fitz.open(pdf_path)
    end = doc.page_count if end is None else min(end, doc.page_count)

    tok_in = tok_out = 0
    n_sent = n_prefiltered = n_model_skip = n_cached = 0

    resume_from = _next_unfinished_page(out, start, end)
    if resume_from > start:
        print(f"Resuming — pages {start}..{resume_from - 1} already done, "
              f"continuing from page {resume_from}.")

    for i in range(start, end):
        cache = out / f"page_{i:04d}.md"
        # A non-empty cache file means this page is finished — skip (no re-pay).
        # Empty/partial files (from a killed write) are ignored so the page is redone.
        if cache.exists() and cache.stat().st_size > 0:
            n_cached += 1
            continue

        page = doc[i]
        text = page.get_text("text")

        # (1) free Python pre-filter — never spend tokens on calendars/blanks
        if is_calendar_page(text) or is_low_content(text):
            n_prefiltered += 1
            continue

        # (2) render + transcribe
        png = page.get_pixmap(dpi=dpi).tobytes("png")
        md, ti, to = _transcribe_image(client, png)
        tok_in += ti
        tok_out += to

        # Atomic write: write to a temp file then rename, so a process killed
        # mid-write never leaves a half-written cache file at the real path.
        if md.upper().startswith("SKIP") or not md:
            _atomic_write(cache, "SKIP")
            n_model_skip += 1
        else:
            _atomic_write(cache, md)
            n_sent += 1

        if (n_sent + n_model_skip) % 10 == 0:
            _print_cost(i, tok_in, tok_out)

    print("\n── Phase 1 done ─────────────────────────────")
    print(f"  transcribed: {n_sent} | model-SKIP: {n_model_skip} | "
          f"pre-filtered (free): {n_prefiltered} | already cached: {n_cached}")
    _print_cost(end - 1, tok_in, tok_out, final=True)


def _atomic_write(path: Path, content: str) -> None:
    """Write via a temp file + rename so a killed process leaves no partial cache."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)  # atomic on the same filesystem


def _next_unfinished_page(md_dir: Path, start: int, end: int) -> int:
    """First page in [start, end) without a finished (non-empty) cache file."""
    for i in range(start, end):
        f = md_dir / f"page_{i:04d}.md"
        if not (f.exists() and f.stat().st_size > 0):
            return i
    return end


def _print_cost(page_idx: int, tok_in: int, tok_out: int, final: bool = False) -> None:
    cost = tok_in / 1e6 * PRICE_IN_PER_M + tok_out / 1e6 * PRICE_OUT_PER_M
    tag = "TOTAL" if final else f"...page {page_idx}"
    print(f"  [{tag}] in={tok_in:,} out={tok_out:,} tok "
          f"| est ~${cost:.3f} (flash, approx)")


# ── Phase 2: Markdown -> table-aware chunks -> Qdrant (free) ──────────────────
# Common crops in Devanagari, so diary chunks can still be filtered by crop.
_DEVANAGARI_CROP = {
    "आलु": "potato", "गोलभेडा": "tomato", "काउली": "cauliflower",
    "बन्दा": "cabbage", "धान": "paddy", "मकै": "maize", "गहुँ": "wheat",
    "अदुवा": "ginger", "लसुन": "garlic", "प्याज": "onion", "तोरी": "mustard",
    "उखु": "sugarcane", "अलैंची": "cardamom", "चिया": "tea",
}


def _detect_crop(text: str) -> str:
    for dev, crop in _DEVANAGARI_CROP.items():
        if dev in text:
            return crop
    return "general"


def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def chunk_markdown(md: str, source: str, page: int) -> list:
    """
    Table-aware chunking:
      • Each Markdown table becomes ONE chunk, prefixed with the nearest heading
        so a row like "युरिया | १२० केजी" keeps its crop/section context.
      • Prose is split with RecursiveCharacterTextSplitter (~600 chars).
    """
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    prose_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)
    lines = md.splitlines()
    heading = ""
    chunks: list[Document] = []
    prose_buf: list[str] = []
    i = 0

    def flush_prose():
        text = "\n".join(prose_buf).strip()
        prose_buf.clear()
        if not text:
            return
        for piece in prose_splitter.split_text(text):
            chunks.append(Document(
                page_content=(f"{heading}\n{piece}" if heading else piece),
                metadata={"source": source, "page": page, "type": "prose",
                          "section": heading, "crop": _detect_crop(piece)},
            ))

    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            flush_prose()
            heading = line.lstrip("# ").strip()
            i += 1
        elif _is_table_line(line):
            flush_prose()
            block = []
            while i < len(lines) and (_is_table_line(lines[i]) or not lines[i].strip()):
                if lines[i].strip():
                    block.append(lines[i])
                elif block:          # blank line ends the table
                    break
                i += 1
            table = "\n".join(block).strip()
            if table:
                body = f"{heading}\n{table}" if heading else table
                chunks.append(Document(
                    page_content=body,
                    metadata={"source": source, "page": page, "type": "table",
                              "section": heading, "crop": _detect_crop(table)},
                ))
        else:
            prose_buf.append(line)
            i += 1

    flush_prose()
    return chunks


def ingest_markdown(
    md_dir: str = DEFAULT_MD_DIR,
    source_name: str = "krishi-diary-2082",
) -> int:
    """Read cached page Markdown, chunk table-aware, embed and upsert to Qdrant."""
    md_path = Path(md_dir)
    files = sorted(md_path.glob("page_*.md"))
    if not files:
        raise SystemExit(f"No transcribed pages in {md_dir} — run 'transcribe' first.")

    all_chunks = []
    for f in files:
        content = f.read_text(encoding="utf-8").strip()
        if not content or content == "SKIP":
            continue
        page = int(re.search(r"(\d+)", f.stem).group(1))
        all_chunks.extend(chunk_markdown(content, source_name, page))

    if not all_chunks:
        print("No content chunks produced.")
        return 0

    # Heavy imports (TensorFlow/HF) deferred to here — Phase 1 never pays for them.
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client.http.models import Distance, VectorParams
    from rag.embeddings import get_embeddings, get_qdrant_client, get_embedding_dim

    ids = [str(uuid.uuid5(_ID_NAMESPACE, f"{source_name}::{i}"))
           for i in range(len(all_chunks))]

    client = get_qdrant_client()
    dim = get_embedding_dim()
    collection = settings.COLLECTION_NAME

    if client.collection_exists(collection):
        existing = client.get_collection(collection).config.params.vectors.size
        if existing != dim:
            logger.warning("Embedding dim changed (%d → %d). Recreating '%s'.",
                           existing, dim, collection)
            client.delete_collection(collection)
    if not client.collection_exists(collection):
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    store = QdrantVectorStore(client=client, collection_name=collection,
                              embedding=get_embeddings())
    batch = 32
    for i in range(0, len(all_chunks), batch):
        store.add_documents(all_chunks[i:i + batch], ids=ids[i:i + batch])
        print(f"  embedded {min(i + batch, len(all_chunks))}/{len(all_chunks)} chunks")

    n_tables = sum(1 for c in all_chunks if c.metadata["type"] == "table")
    print(f"\n── Phase 2 done ─────────────────────────────")
    print(f"  {len(all_chunks)} chunks upserted ({n_tables} tables, "
          f"{len(all_chunks) - n_tables} prose) from {len(files)} pages.")
    return len(all_chunks)


# ── CLI ───────────────────────────────────────────────────────────────────────
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Krishi Diary vision ingestion")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("transcribe", help="Phase 1: PDF -> Markdown (paid)")
    t.add_argument("--pdf", default=DEFAULT_PDF)
    t.add_argument("--md-dir", default=DEFAULT_MD_DIR)
    t.add_argument("--dpi", type=int, default=RENDER_DPI)
    t.add_argument("--start", type=int, default=0)
    t.add_argument("--end", type=int, default=None)

    g = sub.add_parser("ingest", help="Phase 2: Markdown -> Qdrant (free)")
    g.add_argument("--md-dir", default=DEFAULT_MD_DIR)
    g.add_argument("--source", default="krishi-diary-2082")

    a = ap.parse_args()
    if a.cmd == "transcribe":
        transcribe_pdf(a.pdf, a.md_dir, a.dpi, a.start, a.end)
    else:
        ingest_markdown(a.md_dir, a.source)


if __name__ == "__main__":
    main()
