from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=20, ge=1, le=50)


class SearchHit(BaseModel):
    chunk_index: int
    page_number: int | None
    excerpt: str
    similarity: float


class SearchGroup(BaseModel):
    document_id: UUID
    document_title: str
    match_count: int
    best_similarity: float
    hits: list[SearchHit]


class SearchResponse(BaseModel):
    query: str
    total_hits: int
    total_documents: int
    groups: list[SearchGroup]
