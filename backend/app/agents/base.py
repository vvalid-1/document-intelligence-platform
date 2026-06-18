from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"

# 85% of configured context window is the hard limit for input tokens
_CTX_LIMIT = int(settings.OLLAMA_NUM_CTX * 0.85)

# One token ≈ 4 characters for English text (rough but consistent approximation)
_CHARS_PER_TOKEN = 4


@dataclass
class TaskPayload:
    task_type: str
    session_id: UUID
    user_id: UUID
    document_id: UUID | None
    input_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    success: bool
    output_data: dict[str, Any]
    error: str | None = None
    token_count: int | None = None
    duration_ms: int | None = None
    timed_out: bool = False


class BaseAgent:
    AGENT_NAME: str = "base"

    def _load_prompt(self, filename: str) -> str:
        return (_PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()

    def _count_tokens(self, text: str) -> int:
        return max(1, len(text) // _CHARS_PER_TOKEN)

    def _truncate_to_budget(self, text: str, budget_tokens: int) -> str:
        """Trim text so it fits within budget_tokens (character-based approximation)."""
        char_limit = budget_tokens * _CHARS_PER_TOKEN
        if len(text) <= char_limit:
            return text
        return text[:char_limit].rsplit(" ", 1)[0]

    def _strip_think_tags(self, text: str) -> str:
        """Strip Qwen3 <think>...</think> reasoning blocks from output."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    async def _call_ollama(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": settings.OLLAMA_CHAT_MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "num_ctx": settings.OLLAMA_NUM_CTX,
                "num_thread": settings.OLLAMA_NUM_THREAD,
                "num_predict": settings.OLLAMA_NUM_PREDICT,
            },
        }
        if tools:
            payload["tools"] = tools

        # httpx timeout slightly longer than asyncio.wait_for so the outer guard wins
        timeout = httpx.Timeout(settings.AGENT_TIMEOUT_SECONDS + 10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{settings.OLLAMA_HOST}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()  # type: ignore[return-value]

    async def _call_ollama_stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        payload: dict[str, Any] = {
            "model": settings.OLLAMA_CHAT_MODEL,
            "messages": messages,
            "stream": True,
            "options": {
                "num_ctx": settings.OLLAMA_NUM_CTX,
                "num_thread": settings.OLLAMA_NUM_THREAD,
                "num_predict": settings.OLLAMA_NUM_PREDICT,
            },
        }
        timeout = httpx.Timeout(settings.AGENT_TIMEOUT_SECONDS + 10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{settings.OLLAMA_HOST}/api/chat",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        break

    async def run(self, payload: TaskPayload, db: AsyncSession) -> AgentResult:
        raise NotImplementedError
