from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.document import Document
from app.models.user import User
from app.schemas.search import SearchGroup, SearchHit, SearchRequest, SearchResponse
from app.services.vector_service import embed_texts, get_document_collection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

_EXCERPT_CHARS = 300


@router.post("", response_model=SearchResponse)
async def global_search(
    body: SearchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SearchResponse:
    try:
        embeddings = await embed_texts([body.query])
        query_embedding = embeddings[0]
    except Exception as exc:
        logger.error("Search embedding failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="EMBED_UNAVAILABLE: could not embed query",
        )

    try:
        collection = await asyncio.to_thread(get_document_collection)
        count = await asyncio.to_thread(collection.count)
        if count == 0:
            return SearchResponse(query=body.query, total_hits=0, total_documents=0, groups=[])

        effective_k = min(body.top_k, count)
        results = await asyncio.to_thread(
            collection.query,
            query_embeddings=[query_embedding],
            n_results=effective_k,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.warning("ChromaDB search failed: %s", exc)
        return SearchResponse(query=body.query, total_hits=0, total_documents=0, groups=[])

    docs_list = results.get("documents", [[]])[0]
    metas_list = results.get("metadatas", [[]])[0]
    dists_list = results.get("distances", [[]])[0]

    raw_hits: list[dict[str, Any]] = []
    seen_doc_ids: set[str] = set()

    for text, meta, dist in zip(docs_list, metas_list, dists_list):
        doc_id = meta.get("document_id", "")
        raw_hits.append(
            {
                "document_id": doc_id,
                "document_title": meta.get("document_title", ""),
                "chunk_index": int(meta.get("chunk_index", 0)),
                "page_number": meta.get("page_number"),
                "text": text,
                "similarity": round(1.0 - float(dist), 4),
            }
        )
        seen_doc_ids.add(doc_id)

    if not raw_hits:
        return SearchResponse(query=body.query, total_hits=0, total_documents=0, groups=[])

    doc_id_uuids = []
    for did in seen_doc_ids:
        try:
            doc_id_uuids.append(uuid.UUID(did))
        except ValueError:
            pass

    if not doc_id_uuids:
        return SearchResponse(query=body.query, total_hits=0, total_documents=0, groups=[])

    doc_q = select(Document.id, Document.title).where(
        Document.id.in_(doc_id_uuids),
        Document.is_deleted.is_(False),
        Document.status == "ready",
    )
    if current_user.role == "viewer":
        doc_q = doc_q.where(Document.owner_id == current_user.id)

    doc_rows = (await db.execute(doc_q)).all()
    allowed_ids: dict[str, str] = {str(row.id): row.title for row in doc_rows}

    filtered = [h for h in raw_hits if h["document_id"] in allowed_ids]

    if not filtered:
        return SearchResponse(query=body.query, total_hits=0, total_documents=0, groups=[])

    groups_map: dict[str, list[dict[str, Any]]] = {}
    for hit in filtered:
        did = hit["document_id"]
        groups_map.setdefault(did, []).append(hit)

    groups: list[SearchGroup] = []
    for doc_id_str, hits in groups_map.items():
        hits_sorted = sorted(hits, key=lambda h: h["similarity"], reverse=True)
        best = hits_sorted[0]["similarity"]

        page_num = hits_sorted[0].get("page_number")
        if isinstance(page_num, (int, float)) and int(page_num) <= 0:
            page_num = None

        search_hits = []
        for h in hits_sorted:
            pn = h.get("page_number")
            if isinstance(pn, (int, float)) and int(pn) <= 0:
                pn = None
            excerpt = h["text"][:_EXCERPT_CHARS]
            if len(h["text"]) > _EXCERPT_CHARS:
                excerpt += "…"
            search_hits.append(
                SearchHit(
                    chunk_index=h["chunk_index"],
                    page_number=pn,
                    excerpt=excerpt,
                    similarity=h["similarity"],
                )
            )

        groups.append(
            SearchGroup(
                document_id=uuid.UUID(doc_id_str),
                document_title=allowed_ids[doc_id_str],
                match_count=len(hits_sorted),
                best_similarity=best,
                hits=search_hits,
            )
        )

    groups.sort(key=lambda g: g.best_similarity, reverse=True)

    return SearchResponse(
        query=body.query,
        total_hits=sum(g.match_count for g in groups),
        total_documents=len(groups),
        groups=groups,
    )
