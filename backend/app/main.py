from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.router import api_router
from app.core.config import settings
from app.utils.logging import setup_logging

setup_logging()

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

_INSECURE_PREFIXES = ("changeme", "replace_with", "your-secret", "secret", "change_me")
if any(settings.JWT_SECRET_KEY.lower().startswith(p) for p in _INSECURE_PREFIXES):
    logger.warning(
        "SECURITY: JWT_SECRET_KEY is set to an insecure placeholder value. "
        "Generate a strong key: python -c \"import secrets; print(secrets.token_hex(32))\""
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from app.core.database import engine, AsyncSessionLocal
    import app.models  # noqa: F401 — register all ORM models with Base metadata

    # Startup recovery: re-queue documents that were mid-processing on last shutdown
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            from app.models.document import Document
            result = await db.execute(
                select(Document.id).where(
                    Document.status == "processing",
                    Document.is_deleted.is_(False),
                )
            )
            stuck_ids = [row.id for row in result.all()]

        if stuck_ids:
            logger.info("Startup recovery: re-queuing %d stuck documents", len(stuck_ids))
            from app.api.v1.documents import _process_document
            for doc_id in stuck_ids:
                asyncio.create_task(_process_document(doc_id, settings.DATABASE_URL))
    except Exception as exc:
        logger.warning("Startup recovery failed: %s", exc)

    # ChromaDB reconciliation: clean up embeddings for soft-deleted documents
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            from app.models.document import Document
            result = await db.execute(
                select(Document.id).where(Document.is_deleted.is_(True))
            )
            deleted_ids = [str(row.id) for row in result.all()]

        if deleted_ids:
            from app.services.vector_service import reconcile_deleted_documents
            await asyncio.to_thread(reconcile_deleted_documents, deleted_ids)
    except Exception as exc:
        logger.warning("ChromaDB reconciliation failed: %s", exc)

    yield

    await engine.dispose()


app = FastAPI(
    title="Document Intelligence Platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", include_in_schema=False)
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "backend", "version": "1.0.0"})
