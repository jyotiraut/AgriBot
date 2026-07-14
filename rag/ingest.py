"""
Document ingestion pipeline for the KrishiMitra knowledge base.

Improvements over the original:
  • Uses the shared, cached embedding model / Qdrant client (rag.embeddings).
  • Collection vector size is derived from the ACTUAL model dimension, so the
    ingest and retrieval sides can never silently disagree.
  • Every chunk carries metadata (source, crop, chunk index) so retrieval can
    be filtered by crop and answers can cite their source.
  • Deterministic point IDs (uuid5 of source + chunk index) make re-ingesting a
    file an UPSERT instead of appending duplicates.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import uuid

import fitz  # pymupdf
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client.http.models import Distance, VectorParams

from config import get_settings
from rag.embeddings import get_embeddings, get_qdrant_client, get_embedding_dim

logger = logging.getLogger(__name__)

# Stable namespace so the same file always maps to the same point IDs.
_ID_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

# Guess the crop a document is about from its filename — used as chunk metadata
# so retrieval can be filtered per crop.
_CROP_HINTS = {
    "potato":      "potato",
    "tomato":      "tomato",
    "cauliflower": "cauliflower",
    "cabbage":     "cabbage",
    "maize":       "maize",
    "paddy":       "paddy",
    "rice":        "paddy",
    "wheat":       "wheat",
    "ginger":      "ginger",
}


def _crop_from_filename(filename: str) -> str:
    low = filename.lower()
    for hint, crop in _CROP_HINTS.items():
        if hint in low:
            return crop
    return "general"


def ingest_document(file_path: str) -> int:
    """Parse, chunk, embed and upsert a single PDF. Returns chunk count."""
    settings = get_settings()
    source = os.path.basename(file_path)
    crop = _crop_from_filename(source)
    logger.info("Parsing %s (crop=%s) using PyMuPDF...", source, crop)

    doc = fitz.open(file_path)
    pages_text = [p.get_text("text").strip() for p in doc if p.get_text("text").strip()]
    full_text = "\n".join(pages_text)
    logger.info("Extracted text from %d pages.", len(doc))

    if not full_text.strip():
        logger.warning("No text extracted from %s. Skipping.", source)
        return 0

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.create_documents([full_text])

    # Attach metadata + build deterministic IDs (same file → same IDs → upsert)
    ids = []
    for i, chunk in enumerate(chunks):
        chunk.metadata.update({"source": source, "crop": crop, "chunk_index": i})
        ids.append(str(uuid.uuid5(_ID_NAMESPACE, f"{source}::{i}")))
    logger.info("Final chunks: %d", len(chunks))

    client = get_qdrant_client()
    dim = get_embedding_dim()
    collection = settings.COLLECTION_NAME

    # Recreate the collection if the stored vector size no longer matches the model
    if client.collection_exists(collection):
        existing_dim = client.get_collection(collection).config.params.vectors.size
        if existing_dim != dim:
            logger.warning(
                "Embedding dim changed (%d → %d). Recreating collection '%s'.",
                existing_dim, dim, collection,
            )
            client.delete_collection(collection)

    if not client.collection_exists(collection):
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection,
        embedding=get_embeddings(),
    )

    batch_size = 32
    for i in range(0, len(chunks), batch_size):
        vector_store.add_documents(chunks[i:i + batch_size], ids=ids[i:i + batch_size])
        logger.info("Uploaded %d/%d chunks", min(i + batch_size, len(chunks)), len(chunks))

    logger.info("Successfully ingested %d chunks from %s.", len(chunks), source)
    return len(chunks)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ingest")
    ingest_dir = os.path.abspath(ingest_dir)

    if not os.path.isdir(ingest_dir):
        raise SystemExit(f"Ingest folder not found: {ingest_dir}")

    total = 0
    for filename in sorted(os.listdir(ingest_dir)):
        if filename.lower().endswith(".pdf"):
            print(f"\nIngesting: {filename}")
            total += ingest_document(os.path.join(ingest_dir, filename))
    print(f"\nDone. Total chunks ingested/updated: {total}")
