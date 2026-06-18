from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent, TaskPayload, _CTX_LIMIT
from app.core.config import settings
from app.models.agent import AgentTask
from app.models.document import DocumentChunk, DocumentReview

logger = logging.getLogger(__name__)

_VALID_TYPES = frozenset({"grammar", "spelling", "style", "formatting", "clarity", "tone"})
_VALID_SEVERITIES = frozenset({"high", "medium", "low"})
_SEVERITY_DEDUCTIONS = {"high": 1.5, "medium": 0.75, "low": 0.25}


class ReviewerAgent(BaseAgent):
    AGENT_NAME = "reviewer"

    def __init__(self) -> None:
        self._review_prompt = self._load_prompt("reviewer_agent.txt")

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
                self._review_document(payload, task.id, db),
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
            logger.error("ReviewerAgent task %s failed: %s", task.id, exc, exc_info=True)
            task.status = "failed"
            task.error_message = str(exc)[:500]
            result = AgentResult(success=False, output_data={}, error=str(exc))

        task.duration_ms = int((time.monotonic() - start) * 1000)
        task.completed_at = datetime.now(UTC)
        result.duration_ms = task.duration_ms
        result.token_count = task.token_count
        result.output_data.setdefault("task_id", str(task.id))
        await db.flush()
        return result

    # ── Core review logic ─────────────────────────────────────────────────────

    async def _review_document(
        self, payload: TaskPayload, task_id: UUID, db: AsyncSession
    ) -> AgentResult:
        document_id: UUID = payload.document_id  # type: ignore[assignment]
        reviewer_id = UUID(str(payload.input_data["reviewer_id"]))
        focus_areas: list[str] | None = payload.input_data.get("focus_areas")

        rows_result = await db.execute(
            select(DocumentChunk.chunk_text, DocumentChunk.chunk_index)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        rows = rows_result.all()

        if not rows:
            review = DocumentReview(
                document_id=document_id,
                task_id=task_id,
                reviewer_id=reviewer_id,
                overall_score=10.0,
                summary="Document has no extractable text content to review.",
                issues=[],
                metadata_={"chunk_count": 0, "model": settings.OLLAMA_CHAT_MODEL},
            )
            db.add(review)
            await db.flush()
            return AgentResult(
                success=True,
                output_data={"review_id": str(review.id), "task_id": str(task_id)},
                token_count=0,
            )

        full_text = "\n\n".join(r.chunk_text for r in rows)
        system_tokens = self._count_tokens(self._review_prompt)
        budget = _CTX_LIMIT - system_tokens - 600
        content = self._truncate_to_budget(full_text, max(budget, 400))

        system_prompt = self._review_prompt
        if focus_areas:
            valid_areas = [a for a in focus_areas if a in _VALID_TYPES]
            if valid_areas:
                system_prompt += (
                    f"\n\nFocus specifically on these issue types: {', '.join(valid_areas)}. "
                    "Report fewer issues outside these categories."
                )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Review the following document:\n\n{content}"},
        ]

        raw_resp = await self._call_ollama(messages)
        raw_text = raw_resp.get("message", {}).get("content", "")
        token_count = raw_resp.get("eval_count") or self._count_tokens(raw_text)

        parsed = self._extract_review_json(raw_text)
        issues = self._sanitize_issues(parsed.get("issues", []))
        score = self._validate_score(parsed.get("overall_score"), issues)
        summary = str(parsed.get("summary", ""))[:2000].strip() or "Review completed."

        review = DocumentReview(
            document_id=document_id,
            task_id=task_id,
            reviewer_id=reviewer_id,
            overall_score=score,
            summary=summary,
            issues=issues,
            metadata_={
                "chunk_count": len(rows),
                "model": settings.OLLAMA_CHAT_MODEL,
                "focus_areas": focus_areas,
            },
        )
        db.add(review)
        await db.flush()

        return AgentResult(
            success=True,
            output_data={
                "review_id": str(review.id),
                "task_id": str(task_id),
                "overall_score": score,
                "issue_count": len(issues),
            },
            token_count=token_count,
        )

    # ── JSON extraction ───────────────────────────────────────────────────────

    def _extract_review_json(self, raw: str) -> dict[str, Any]:
        text = self._strip_think_tags(raw)

        # Strategy 1: direct parse
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 2: extract from ```json ... ``` block
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 3: find outermost { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except (json.JSONDecodeError, ValueError):
                pass

        logger.warning("ReviewerAgent: could not parse JSON from LLM output; using fallback")
        return {
            "overall_score": None,
            "summary": text[:500] if text else "Review completed.",
            "issues": [],
        }

    # ── Sanitization helpers ──────────────────────────────────────────────────

    def _sanitize_issues(self, raw_issues: list) -> list[dict[str, Any]]:
        if not isinstance(raw_issues, list):
            return []
        clean: list[dict[str, Any]] = []
        for item in raw_issues:
            if not isinstance(item, dict):
                continue
            issue_type = str(item.get("type", "style")).lower().strip()
            if issue_type not in _VALID_TYPES:
                issue_type = "style"
            severity = str(item.get("severity", "low")).lower().strip()
            if severity not in _VALID_SEVERITIES:
                severity = "low"
            clean.append(
                {
                    "type": issue_type,
                    "severity": severity,
                    "location": str(item.get("location", ""))[:200],
                    "description": str(item.get("description", ""))[:500],
                    "suggestion": str(item.get("suggestion", ""))[:500],
                }
            )
        return clean

    def _validate_score(
        self, raw_score: Any, issues: list[dict[str, Any]]
    ) -> float:
        if isinstance(raw_score, (int, float)) and 0.0 <= float(raw_score) <= 10.0:
            return round(float(raw_score), 1)
        # Fallback: compute from issue severities
        deductions = sum(
            _SEVERITY_DEDUCTIONS.get(i.get("severity", "low"), 0.25) for i in issues
        )
        return round(max(0.0, 10.0 - deductions), 1)
