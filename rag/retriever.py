"""
Qdrant-backed retriever.

Uses the cached embedding model + Qdrant client from rag.embeddings, so the
transformer is loaded once per process instead of on every chat turn.
"""
from functools import lru_cache

from langchain_qdrant import QdrantVectorStore

from config import get_settings
from rag.embeddings import get_embeddings, get_qdrant_client


@lru_cache(maxsize=1)
def get_vector_store() -> QdrantVectorStore:
    settings = get_settings()
    return QdrantVectorStore(
        client=get_qdrant_client(),
        collection_name=settings.COLLECTION_NAME,
        embedding=get_embeddings(),
    )


@lru_cache(maxsize=1)
def get_retriever():
    """
    Return a cached LangChain retriever pointing at Qdrant.

    top_k and an optional score threshold are configurable via settings.
    """
    settings = get_settings()
    search_kwargs = {"k": settings.retriever_top_k}

    if settings.retriever_score_threshold > 0:
        return get_vector_store().as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={
                **search_kwargs,
                "score_threshold": settings.retriever_score_threshold,
            },
        )

    return get_vector_store().as_retriever(search_kwargs=search_kwargs)
