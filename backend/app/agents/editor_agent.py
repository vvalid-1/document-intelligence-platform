from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent, TaskPayload, _CTX_LIMIT
from app.core.config import settings
from app.models.agent import AgentTask
from app.models.document import DocumentChunk, DocumentVersion
from app.services.pdf_service import save_version_files

logger = logging.getLogger(__name__)

_TEXT_PREVIEW_LEN = 500


class EditorAgent(BaseAgent):
    AGENT_NAME = "editor"

    def __init__(self) -> None:
        self._system_prompt = self._load_prompt("editor_agent.txt")

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
                self._apply_edits(payload, task.id, db),
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
            logger.error("EditorAgent task %s failed: %s", task.id, exc, exc_info=True)
            task.status = "failed"
            task.error_message = str(exc)[:500]
            result = AgentResult(success=False, output_data={}, error=str(exc))

        task.duration_ms = int((time.monotonic() - start) * 1000)
        task.completed_at = datetime.now(UTC)
        result.duration_ms = task.duration_ms
        result.output_data.setdefault("task_id", str(task.id))
        await db.flush()
        return result

    # ── Core edit logic ───────────────────────────────────────────────────────

    async def _apply_edits(
        self, payload: TaskPayload, task_id: UUID, db: AsyncSession
    ) -> AgentResult:
        document_id: UUID = payload.document_id  # type: ignore[assignment]
        instruction: str = payload.input_data["instruction"]
        editor_id: UUID = UUID(str(payload.input_data["editor_id"]))

        rows = (
            await db.execute(
                select(DocumentChunk.chunk_text, DocumentChunk.chunk_index)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
            )
        ).all()

        if not rows:
            return AgentResult(
                success=False,
                output_data={"task_id": str(task_id)},
                error="Document has no text content to edit",
            )

        full_text = "\n\n".join(r.chunk_text for r in rows)

        sys_tokens = self._count_tokens(self._system_prompt)
        inst_tokens = self._count_tokens(instruction)
        budget = _CTX_LIMIT - sys_tokens - inst_tokens - 300
        content = self._truncate_to_budget(full_text, max(budget, 200))

        messages = [
            {"role": "system", "content": self._system_prompt},
            {
                "role": "user",
                "content": (
                    f"Document:\n\n{content}\n\n"
                    f"Edit instruction: {instruction}"
                ),
            },
        ]

        raw_resp = await self._call_ollama(messages)
        raw_text = raw_resp.get("message", {}).get("content", "")
        token_count = raw_resp.get("eval_count") or self._count_tokens(raw_text)

        edited_text = self._strip_think_tags(raw_text).strip()
        if not edited_text:
            edited_text = content

        # Determine the next version number
        version_res = await db.execute(
            select(func.coalesce(func.max(DocumentVersion.version_number), 0)).where(
                DocumentVersion.document_id == document_id
            )
        )
        next_version: int = version_res.scalar_one() + 1

        # Save files in a thread (sync I/O)
        txt_rel, pdf_rel = await asyncio.to_thread(
            save_version_files, document_id, next_version, edited_text
        )

        change_summary = instruction[:500]

        version = DocumentVersion(
            document_id=document_id,
            version_number=next_version,
            created_by=editor_id,
            file_path=pdf_rel,
            change_summary=change_summary,
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            version_metadata={
                "txt_path": txt_rel,
                "pdf_path": pdf_rel,
                "model": settings.OLLAMA_CHAT_MODEL,
                "instruction_length": len(instruction),
                "original_chunk_count": len(rows),
            },
        )
        db.add(version)
        await db.flush()

        text_preview = edited_text[:_TEXT_PREVIEW_LEN]

        return AgentResult(
            success=True,
            output_data={
                "version_id": str(version.id),
                "task_id": str(task_id),
                "version_number": next_version,
                "txt_path": txt_rel,
                "pdf_path": pdf_rel,
                "text_preview": text_preview,
                "change_summary": change_summary,
            },
            token_count=token_count,
        )
