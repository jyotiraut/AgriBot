"""
Single source of truth for the embedding model and Qdrant client.

Both the embedding model and the Qdrant client are expensive to construct
(the embedding model loads a transformer from disk). They are cached here as
process-wide singletons so ingestion and every retrieval call reuse the same
instances instead of reloading the model on every chat turn.
"""
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient

from config import get_settings


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Return the process-wide embedding model (loaded once)."""
    settings = get_settings()
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": settings.embedding_device},
        encode_kwargs={"normalize_embeddings": settings.embedding_normalize},
    )


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Return the process-wide Qdrant client (created once).

    QDRANT_URL forms:
      http(s)://...  → remote Qdrant server / Qdrant Cloud (QDRANT_API_KEY used)
      anything else  → EMBEDDED local mode: the value is a folder path where
                       Qdrant stores its data (e.g. ./qdrant_local). No server
                       or Docker needed. Note: embedded mode is single-process —
                       stop the API server before running an ingest script.
    """
    settings = get_settings()
    url = settings.QDRANT_URL.strip()
    if url.lower().startswith(("http://", "https://")):
        return QdrantClient(
            url=url,
            api_key=settings.QDRANT_API_KEY or None,
            check_compatibility=False,
        )
    return QdrantClient(path=url)


@lru_cache(maxsize=1)
def get_embedding_dim() -> int:
    """Actual output dimension of the configured embedding model."""
    return len(get_embeddings().embed_query("dimension probe"))
