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

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "fr": "French",
    "ar": "Arabic",
}


class TranslationAgent(BaseAgent):
    AGENT_NAME = "translator"

    def __init__(self) -> None:
        self._system_prompt = self._load_prompt("translation_agent.txt")

    async def run(self, payload: TaskPayload, db: AsyncSession) -> AgentResult:
        task = AgentTask(
            session_id=payload.session_id,
            document_id=payload.document_id,
            agent_name=self.AGENT_NAME,
            task_type=payload.task_type,
            input_payload=payload.input_data,
            status="running",
            model_used=settings.OLLAMA_TRANSLATION_MODEL,
        )
        db.add(task)
        await db.flush()

        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self._translate(payload, task.id, db),
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
            logger.error("TranslationAgent task %s failed: %s", task.id, exc, exc_info=True)
            task.status = "failed"
            task.error_message = str(exc)[:500]
            result = AgentResult(success=False, output_data={}, error=str(exc))

        task.duration_ms = int((time.monotonic() - start) * 1000)
        task.completed_at = datetime.now(UTC)
        result.duration_ms = task.duration_ms
        result.output_data.setdefault("task_id", str(task.id))
        await db.flush()
        return result

    async def _translate(
        self, payload: TaskPayload, task_id: UUID, db: AsyncSession
    ) -> AgentResult:
        document_id: UUID = payload.document_id  # type: ignore[assignment]
        target_language: str = payload.input_data["target_language"]
        translator_id: UUID = UUID(str(payload.input_data["translator_id"]))
        lang_name = LANGUAGE_NAMES.get(target_language, target_language)

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
                error="Document has no text content to translate",
            )

        full_text = "\n\n".join(r.chunk_text for r in rows)

        sys_tokens = self._count_tokens(self._system_prompt)
        lang_instruction = f"Translate the following document into {lang_name}:"
        inst_tokens = self._count_tokens(lang_instruction)
        budget = _CTX_LIMIT - sys_tokens - inst_tokens - 300
        content = self._truncate_to_budget(full_text, max(budget, 200))

        messages = [
            {"role": "system", "content": self._system_prompt},
            {
                "role": "user",
                "content": f"{lang_instruction}\n\n{content}",
            },
        ]

        raw_resp = await self._call_ollama(
            messages, model=settings.OLLAMA_TRANSLATION_MODEL
        )
        raw_text = raw_resp.get("message", {}).get("content", "")
        token_count = raw_resp.get("eval_count") or self._count_tokens(raw_text)

        translated_text = self._strip_think_tags(raw_text).strip()
        if not translated_text:
            translated_text = content

        version_res = await db.execute(
            select(func.coalesce(func.max(DocumentVersion.version_number), 0)).where(
                DocumentVersion.document_id == document_id
            )
        )
        next_version: int = version_res.scalar_one() + 1

        stem_suffix = f"translated_{target_language}"
        txt_rel, pdf_rel = await asyncio.to_thread(
            save_version_files, document_id, next_version, translated_text, stem_suffix
        )

        change_summary = f"Translated to {lang_name}"

        version = DocumentVersion(
            document_id=document_id,
            version_number=next_version,
            created_by=translator_id,
            file_path=pdf_rel,
            change_summary=change_summary,
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            version_metadata={
                "txt_path": txt_rel,
                "pdf_path": pdf_rel,
                "target_language": target_language,
                "language_name": lang_name,
                "model": settings.OLLAMA_TRANSLATION_MODEL,
                "original_chunk_count": len(rows),
            },
        )
        db.add(version)
        await db.flush()

        text_preview = translated_text[:_TEXT_PREVIEW_LEN]

        return AgentResult(
            success=True,
            output_data={
                "version_id": str(version.id),
                "task_id": str(task_id),
                "version_number": next_version,
                "target_language": target_language,
                "language_name": lang_name,
                "txt_path": txt_rel,
                "pdf_path": pdf_rel,
                "text_preview": text_preview,
                "change_summary": change_summary,
            },
            token_count=token_count,
        )
