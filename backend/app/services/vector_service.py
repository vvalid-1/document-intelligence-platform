from __future__ import annotations

import logging
from typing import Any

import chromadb
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "document_chunks"

_client: chromadb.ClientAPI | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.HttpClient(
            host=settings.CHROMADB_HOST,
            port=settings.CHROMADB_PORT,
        )
    return _client


def get_document_collection(client: chromadb.ClientAPI | None = None) -> chromadb.Collection:
    c = client or get_chroma_client()
    return c.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,
    )


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts using Ollama /api/embed (bge-m3). Returns one float[] per input."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.OLLAMA_HOST}/api/embed",
            json={"model": settings.OLLAMA_EMBED_MODEL, "input": texts},
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]


def delete_document_chunks(collection: chromadb.Collection, document_id: str) -> None:
    """Delete all ChromaDB chunks for a document (call before soft-deleting in PG)."""
    collection.delete(where={"document_id": document_id})


def reconcile_deleted_documents(deleted_doc_ids: list[str]) -> None:
    """Remove any ChromaDB entries that belong to soft-deleted documents.

    Called once on startup to clean up entries that survived a failed deletion.
    """
    if not deleted_doc_ids:
        return
    try:
        c = get_chroma_client()
        col = get_document_collection(c)
        for doc_id in deleted_doc_ids:
            try:
                col.delete(where={"document_id": doc_id})
            except Exception as exc:
                logger.warning("Reconcile: could not delete ChromaDB chunks for %s: %s", doc_id, exc)
    except Exception as exc:
        logger.warning("Reconcile: ChromaDB unavailable: %s", exc)
