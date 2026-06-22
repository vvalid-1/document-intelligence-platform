from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent, TaskPayload, _CTX_LIMIT
from app.core.config import settings
from app.models.agent import AgentTask
from app.models.document import DocumentVersion
from app.services.pdf_service import save_version_files

logger = logging.getLogger(__name__)

_EMPTY_ANALYSIS: dict = {
    "summary": "",
    "key_topics": [],
    "action_items": [],
    "important_dates": [],
    "important_numbers": [],
}


def _parse_analysis(raw: str) -> dict:
    """Extract JSON object from LLM output, with fallback to empty structure."""
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    # Try to find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return _EMPTY_ANALYSIS.copy()


class MediaAnalysisAgent(BaseAgent):
    AGENT_NAME = "media_analysis"

    def __init__(self) -> None:
        self._system_prompt = self._load_prompt("media_analysis_agent.txt")

    async def run(self, payload: TaskPayload, db: AsyncSession) -> AgentResult:
        task = AgentTask(
            session_id=payload.session_id,
            document_id=payload.document_id,
            agent_name=self.AGENT_NAME,
            task_type=payload.task_type,
            input_payload=payload.input_data,
            status="running",
            model_used=settings.OLLAMA_MEDIA_MODEL,
        )
        db.add(task)
        await db.flush()

        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self._analyze(payload, task.id, db),
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
                success=False, output_data={}, error="Agent timed out", timed_out=True
            )
        except Exception as exc:
            logger.error("MediaAnalysisAgent task %s failed: %s", task.id, exc, exc_info=True)
            task.status = "failed"
            task.error_message = str(exc)[:500]
            result = AgentResult(success=False, output_data={}, error=str(exc))

        task.duration_ms = int((time.monotonic() - start) * 1000)
        task.completed_at = datetime.now(UTC)
        result.duration_ms = task.duration_ms
        result.output_data.setdefault("task_id", str(task.id))
        await db.flush()
        return result

    async def _analyze(
        self, payload: TaskPayload, task_id: UUID, db: AsyncSession
    ) -> AgentResult:
        document_id: UUID = payload.document_id  # type: ignore[assignment]
        transcript: str = payload.input_data["transcript"]
        user_id: UUID = UUID(str(payload.input_data["user_id"]))
        duration_seconds: float | None = payload.input_data.get("duration_seconds")
        language: str | None = payload.input_data.get("language")

        sys_tokens = self._count_tokens(self._system_prompt)
        budget = _CTX_LIMIT - sys_tokens - 200
        truncated_transcript = self._truncate_to_budget(transcript, max(budget, 300))

        messages = [
            {"role": "system", "content": self._system_prompt},
            {
                "role": "user",
                "content": f"Analyze this transcript:\n\n{truncated_transcript}",
            },
        ]

        raw_resp = await self._call_ollama(messages, model=settings.OLLAMA_MEDIA_MODEL)
        raw_text = raw_resp.get("message", {}).get("content", "")
        token_count = raw_resp.get("eval_count") or self._count_tokens(raw_text)

        analysis = _parse_analysis(raw_text)

        version_res = await db.execute(
            select(func.coalesce(func.max(DocumentVersion.version_number), 0)).where(
                DocumentVersion.document_id == document_id
            )
        )
        next_version: int = version_res.scalar_one() + 1

        summary_text = analysis.get("summary", "")
        if not summary_text:
            summary_text = truncated_transcript[:2000]

        txt_rel, pdf_rel = await asyncio.to_thread(
            save_version_files, document_id, next_version, transcript, "transcript"
        )

        # Save summary as a separate PDF
        _, summary_pdf_rel = await asyncio.to_thread(
            save_version_files, document_id, next_version, summary_text, "summary"
        )

        version = DocumentVersion(
            document_id=document_id,
            version_number=next_version,
            created_by=user_id,
            file_path=summary_pdf_rel,
            change_summary="Media analysis: transcript + AI summary",
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            version_metadata={
                "transcript": transcript,
                "summary": analysis.get("summary", ""),
                "key_topics": analysis.get("key_topics", []),
                "action_items": analysis.get("action_items", []),
                "important_dates": analysis.get("important_dates", []),
                "important_numbers": analysis.get("important_numbers", []),
                "txt_path": txt_rel,
                "pdf_path": summary_pdf_rel,
                "duration_seconds": duration_seconds,
                "language": language,
                "model": settings.OLLAMA_MEDIA_MODEL,
            },
        )
        db.add(version)
        await db.flush()

        return AgentResult(
            success=True,
            output_data={
                "version_id": str(version.id),
                "task_id": str(task_id),
                "version_number": next_version,
                "summary": analysis.get("summary", ""),
                "key_topics": analysis.get("key_topics", []),
                "action_items": analysis.get("action_items", []),
                "important_dates": analysis.get("important_dates", []),
                "important_numbers": analysis.get("important_numbers", []),
                "duration_seconds": duration_seconds,
                "language": language,
                "txt_path": txt_rel,
                "pdf_path": summary_pdf_rel,
            },
            token_count=token_count,
        )
