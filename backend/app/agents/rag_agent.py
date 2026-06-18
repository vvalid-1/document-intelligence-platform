from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent, TaskPayload, _CTX_LIMIT
from app.core.config import settings
from app.models.agent import AgentTask
from app.models.document import DocumentChunk
from app.services.vector_service import embed_texts, get_document_collection

logger = logging.getLogger(__name__)

_TOP_K_DEFAULT = 5
_EXCERPT_CHARS = 300


class RAGAgent(BaseAgent):
    AGENT_NAME = "search_rag"

    def __init__(self) -> None:
        self._rag_prompt = self._load_prompt("rag_agent.txt")
        self._summarize_prompt = self._load_prompt("summarize_agent.txt")

    # ── Public entry point ────────────────────────────────────────────────────

    async def run(self, payload: TaskPayload, db: AsyncSession) -> AgentResult:
        task = AgentTask(
            session_id=payload.session_id,
            document_id=payload.document_id,
            agent_name=self.AGENT_NAME,
            task_type=payload.task_type,
            input_payload=payload.input_data,
            status="running",
            model_used=settings.OLLAMA_CHAT_MODEL,
        )
        db.add(task)
        await db.flush()

        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self._dispatch(payload, db),
                timeout=settings.AGENT_TIMEOUT_SECONDS,
            )
            task.status = "completed"
            task.output_payload = result.output_data
            task.token_count = result.token_count
        except asyncio.TimeoutError:
            task.status = "failed"
            task.timed_out = True
            task.error_message = "Agent timed out"
            result = AgentResult(
                success=False,
                output_data={},
                error="Agent timed out",
                timed_out=True,
            )
        except Exception as exc:
            logger.error("RAGAgent task %s failed: %s", task.id, exc, exc_info=True)
            task.status = "failed"
            task.error_message = str(exc)[:500]
            result = AgentResult(success=False, output_data={}, error=str(exc))

        task.duration_ms = int((time.monotonic() - start) * 1000)
        task.completed_at = datetime.now(UTC)
        result.duration_ms = task.duration_ms
        result.token_count = task.token_count

        if not hasattr(result, "task_id"):
            object.__setattr__(result, "task_id", task.id)

        result.output_data["task_id"] = str(task.id)
        await db.flush()
        return result

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def _dispatch(self, payload: TaskPayload, db: AsyncSession) -> AgentResult:
        if payload.task_type == "summarize":
            return await self._summarize(payload, db)
        return await self._qa_retrieval(payload, db)

    # ── Q&A Retrieval ─────────────────────────────────────────────────────────

    async def _qa_retrieval(self, payload: TaskPayload, db: AsyncSession) -> AgentResult:
        question: str = payload.input_data["question"]
        doc_ids: list[str] | None = payload.input_data.get("document_ids")
        top_k: int = int(payload.input_data.get("top_k", _TOP_K_DEFAULT))

        chunks = await self._retrieve_chunks(question, doc_ids, top_k)

        if not chunks:
            answer = (
                "I could not find relevant information in the uploaded documents "
                "to answer your question."
            )
            return AgentResult(
                success=True,
                output_data={"answer": answer, "sources": []},
                token_count=0,
            )

        context, sources = self._build_context(chunks)
        user_message = f"Context:\n{context}\n\nQuestion: {question}"

        system_tokens = self._count_tokens(self._rag_prompt)
        user_budget = _CTX_LIMIT - system_tokens - 200  # 200 reserve for answer
        user_message = self._truncate_to_budget(user_message, max(user_budget, 500))

        messages = [
            {"role": "system", "content": self._rag_prompt},
            {"role": "user", "content": user_message},
        ]

        raw = await self._call_ollama(messages)
        raw_answer = raw.get("message", {}).get("content", "")
        answer = self._strip_think_tags(raw_answer)
        token_count = raw.get("eval_count") or self._count_tokens(answer)

        return AgentResult(
            success=True,
            output_data={"answer": answer, "sources": sources},
            token_count=token_count,
        )

    # ── Summarization ─────────────────────────────────────────────────────────

    async def _summarize(self, payload: TaskPayload, db: AsyncSession) -> AgentResult:
        document_id: UUID = payload.document_id  # type: ignore[assignment]
        length: str = payload.input_data.get("length", "medium")

        length_instruction = {
            "short": "Keep the summary under 150 words.",
            "medium": "Aim for 300–500 words.",
            "long": "Be thorough; up to 800 words is acceptable.",
        }.get(length, "Aim for 300–500 words.")

        result = await db.execute(
            select(DocumentChunk.chunk_text, DocumentChunk.chunk_index)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        rows = result.all()
        chunk_count = len(rows)

        if chunk_count == 0:
            return AgentResult(
                success=True,
                output_data={
                    "summary": "Document has no extractable text content.",
                    "chunk_count": 0,
                },
                token_count=0,
            )

        full_text = "\n\n".join(r.chunk_text for r in rows)
        system_tokens = self._count_tokens(self._summarize_prompt)
        budget = _CTX_LIMIT - system_tokens - 300
        content = self._truncate_to_budget(full_text, max(budget, 500))

        system_prompt = f"{self._summarize_prompt}\n\n{length_instruction}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Summarize the following document:\n\n{content}"},
        ]

        raw = await self._call_ollama(messages)
        raw_summary = raw.get("message", {}).get("content", "")
        summary = self._strip_think_tags(raw_summary)
        token_count = raw.get("eval_count") or self._count_tokens(summary)

        return AgentResult(
            success=True,
            output_data={"summary": summary, "chunk_count": chunk_count},
            token_count=token_count,
        )

    # ── Retrieval ─────────────────────────────────────────────────────────────

    async def _retrieve_chunks(
        self,
        query: str,
        document_ids: list[str] | None,
        top_k: int,
    ) -> list[dict[str, Any]]:
        try:
            embeddings = await embed_texts([query])
            query_embedding = embeddings[0]
        except Exception as exc:
            logger.error("Embedding query failed: %s", exc)
            return []

        where_filter: dict | None = None
        if document_ids:
            if len(document_ids) == 1:
                where_filter = {"document_id": document_ids[0]}
            else:
                where_filter = {"document_id": {"$in": document_ids}}

        try:
            collection = await asyncio.to_thread(get_document_collection)
            count = await asyncio.to_thread(collection.count)
            if count == 0:
                return []

            effective_k = min(top_k, count)
            results = await asyncio.to_thread(
                collection.query,
                query_embeddings=[query_embedding],
                n_results=effective_k,
                include=["documents", "metadatas", "distances"],
                **({"where": where_filter} if where_filter else {}),
            )
        except Exception as exc:
            logger.warning("ChromaDB query failed: %s", exc)
            return []

        chunks: list[dict[str, Any]] = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for doc_text, meta, dist in zip(docs, metas, dists):
            chunks.append(
                {
                    "text": doc_text,
                    "document_id": meta.get("document_id", ""),
                    "document_title": meta.get("document_title", ""),
                    "page_number": meta.get("page_number"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "similarity": round(1.0 - float(dist), 4),
                }
            )

        return chunks

    # ── Context builder ───────────────────────────────────────────────────────

    def _build_context(
        self, chunks: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        parts: list[str] = []
        sources: list[dict[str, Any]] = []

        for i, chunk in enumerate(chunks, start=1):
            page = chunk.get("page_number")
            page_str = f" (Page {page})" if page and page > 0 else ""
            header = f'[Source {i}] Document: "{chunk["document_title"]}"{page_str}'
            parts.append(f"{header}\n{chunk['text']}")

            excerpt = chunk["text"][:_EXCERPT_CHARS]
            if len(chunk["text"]) > _EXCERPT_CHARS:
                excerpt += "..."

            sources.append(
                {
                    "source_num": i,
                    "chunk_index": chunk["chunk_index"],
                    "document_id": chunk["document_id"],
                    "document_title": chunk["document_title"],
                    "page_number": chunk.get("page_number"),
                    "excerpt": excerpt,
                    "similarity_score": chunk["similarity"],
                }
            )

        return "\n\n---\n\n".join(parts), sources
