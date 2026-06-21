from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Annotated, Any, Optional

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from sse_starlette.sse import EventSourceResponse

from app.core.database import get_db
from app.core.deps import get_current_user, require_editor_or_admin, validate_sse_token
from app.models.document import Document, DocumentChunk, DocumentReview, DocumentVersion
from app.models.user import User
from app.schemas.document import (
    DocumentListResponse,
    DocumentPatchRequest,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
    DocumentVersionResponse,
)
from app.services.audit_service import log_action
from app.utils.file_utils import make_document_dir, resolve_upload_path, validate_upload
from app.schemas.chat import SummarizeRequest, SummarizeResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

_MIME_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

_IMAGE_MIMES = {"image/jpeg", "image/png"}

# Maps processing_step → approximate progress percent
_STEP_PROGRESS: dict[str | None, int] = {
    "queued": 5,
    "extracting": 20,
    "ocr": 30,
    "chunking": 50,
    "embedding": 70,
}


def _compute_progress(step: str | None, doc_status: str) -> int:
    if doc_status == "ready":
        return 100
    if doc_status == "error":
        return 0
    if step and step.startswith("embedding chunk "):
        try:
            parts = step.split(" ")  # ["embedding", "chunk", "X/N"]
            nums = parts[2].split("/")
            return 70 + int(int(nums[0]) / int(nums[1]) * 25)
        except Exception:
            return 70
    return _STEP_PROGRESS.get(step, 10)


# ── Background processing ─────────────────────────────────────────────────────

async def _process_document(
    document_id: uuid.UUID,
    db_url: str,
    chroma_client: Any = None,
    embed_fn: Any = None,
) -> None:
    """Full pipeline: extract → chunk → embed → store in ChromaDB + PG."""
    from app.services.processing_service import (
        chunk_pages,
        chunk_plain_text,
        extract_pdf_metadata,
        extract_text_docx,
        extract_text_image,
        extract_text_pdf,
        extract_text_txt,
    )
    from app.services.vector_service import embed_texts as _default_embed, get_document_collection
    from app.core.config import settings

    engine = create_async_engine(db_url, poolclass=NullPool)
    _embed = embed_fn or _default_embed

    async def _set(**kwargs: Any) -> None:
        async with AsyncSession(engine, expire_on_commit=False) as sess:
            async with sess.begin():
                await sess.execute(
                    update(Document).where(Document.id == document_id).values(**kwargs)
                )

    try:
        # Load document info
        async with AsyncSession(engine, expire_on_commit=False) as sess:
            res = await sess.execute(select(Document).where(Document.id == document_id))
            doc = res.scalar_one_or_none()
            if doc is None:
                return
            file_path_rel = doc.file_path
            mime = doc.mime_type
            title = doc.title
            owner_id = doc.owner_id
            created_at = doc.created_at

        file_path = resolve_upload_path(file_path_rel)

        # Step 1: Extract
        await _set(processing_step="extracting")

        page_count: Optional[int] = None
        doc_metadata: dict = {}

        if mime == "application/pdf":
            pages = extract_text_pdf(file_path)
            meta = extract_pdf_metadata(file_path)
            page_count = meta.pop("page_count", None)
            doc_metadata = meta
            chunks = chunk_pages(pages, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
        elif "wordprocessingml" in mime:
            text = extract_text_docx(file_path)
            doc_metadata = {"word_count": len(text.split())}
            chunks = chunk_plain_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
        elif mime in _IMAGE_MIMES:
            await _set(processing_step="ocr")
            text = extract_text_image(file_path)
            doc_metadata = {"word_count": len(text.split()), "source": "ocr"}
            chunks = chunk_plain_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
        else:
            text = extract_text_txt(file_path)
            doc_metadata = {"word_count": len(text.split())}
            chunks = chunk_plain_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)

        # Step 2: Chunk (record metadata)
        await _set(processing_step="chunking", page_count=page_count, doc_metadata=doc_metadata)

        if not chunks:
            await _set(status="ready", processing_step=None, chunk_count=0, error_message=None)
            return

        # Step 3: Embed in batches
        collection = get_document_collection(chroma_client)
        _BATCH = 50
        all_embeddings: list[list[float]] = []

        for batch_start in range(0, len(chunks), _BATCH):
            batch = chunks[batch_start : batch_start + _BATCH]
            batch_embeddings = await _embed([c.chunk_text for c in batch])
            all_embeddings.extend(batch_embeddings)
            done = batch_start + len(batch)
            await _set(processing_step=f"embedding chunk {done}/{len(chunks)}")

        # Step 4: Insert into ChromaDB
        chroma_ids = [f"{document_id}_{c.chunk_index}" for c in chunks]
        owner_str = str(owner_id) if owner_id else ""
        created_str = created_at.isoformat() if created_at else ""

        collection.add(
            ids=chroma_ids,
            embeddings=all_embeddings,
            documents=[c.chunk_text for c in chunks],
            metadatas=[
                {
                    "document_id": str(document_id),
                    "document_title": title,
                    "mime_type": mime,
                    "page_number": c.page_number if c.page_number is not None else -1,
                    "chunk_index": c.chunk_index,
                    "owner_id": owner_str,
                    "created_at": created_str,
                }
                for c in chunks
            ],
        )

        # Step 5: Insert DocumentChunk records into PostgreSQL
        async with AsyncSession(engine, expire_on_commit=False) as sess:
            async with sess.begin():
                for chunk, chroma_id in zip(chunks, chroma_ids):
                    sess.add(
                        DocumentChunk(
                            document_id=document_id,
                            chroma_chunk_id=chroma_id,
                            chunk_index=chunk.chunk_index,
                            page_number=chunk.page_number,
                            chunk_text=chunk.chunk_text,
                            token_count=chunk.token_count,
                        )
                    )

        # Done
        await _set(
            status="ready",
            processing_step=None,
            chunk_count=len(chunks),
            error_message=None,
        )
        logger.info("Document %s processed successfully: %d chunks", document_id, len(chunks))

    except Exception as exc:
        logger.error("Document %s processing failed: %s", document_id, exc, exc_info=True)
        try:
            await _set(status="error", processing_step=None, error_message=str(exc)[:500])
        except Exception:
            pass
    finally:
        await engine.dispose()


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> DocumentUploadResponse:
    ext = await validate_upload(file)
    mime = _MIME_MAP.get(ext, "application/octet-stream")

    doc_id = uuid.uuid4()
    doc_dir = make_document_dir(str(doc_id))
    safe_name = f"original{ext}"
    file_path_abs = doc_dir / safe_name
    relative_path = f"{doc_id}/{safe_name}"

    content = await file.read()
    async with aiofiles.open(file_path_abs, "wb") as f:
        await f.write(content)

    doc = Document(
        id=doc_id,
        owner_id=current_user.id,
        title=Path(file.filename or safe_name).stem,
        original_name=file.filename or safe_name,
        file_path=relative_path,
        file_size_bytes=len(content),
        mime_type=mime,
        status="processing",
        processing_step="queued",
    )
    db.add(doc)
    await db.flush()

    await log_action(
        db,
        action="document.upload",
        user_id=current_user.id,
        resource_type="document",
        resource_id=doc_id,
        details={"filename": file.filename, "size": len(content)},
        request=request,
    )

    from app.core.config import settings
    background_tasks.add_task(_process_document, doc_id, settings.DATABASE_URL)

    return DocumentUploadResponse(
        id=doc_id,
        title=doc.title,
        status=doc.status,
        stream_url=f"/api/v1/documents/{doc_id}/status/stream",
    )


# ── Status (polling) ──────────────────────────────────────────────────────────

@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentStatusResponse:
    res = await db.execute(
        select(
            Document.id,
            Document.status,
            Document.processing_step,
            Document.chunk_count,
            Document.error_message,
        ).where(Document.id == document_id, Document.is_deleted.is_(False))
    )
    row = res.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return DocumentStatusResponse(
        id=row.id,
        status=row.status,
        progress_percent=_compute_progress(row.processing_step, row.status),
        progress_step=row.processing_step,
        chunk_count=row.chunk_count,
        error_message=row.error_message,
    )


# ── Status SSE stream ─────────────────────────────────────────────────────────

@router.get("/{document_id}/status/stream")
async def document_status_stream(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(validate_sse_token)],
) -> EventSourceResponse:
    async def _generate():
        timeout_secs = 600
        elapsed = 0.0
        poll_interval = 0.5

        while elapsed < timeout_secs:
            res = await db.execute(
                select(
                    Document.status,
                    Document.processing_step,
                    Document.chunk_count,
                    Document.error_message,
                ).where(Document.id == document_id, Document.is_deleted.is_(False))
            )
            row = res.first()
            if row is None:
                yield {"event": "error", "data": json.dumps({"code": "NOT_FOUND"})}
                return

            doc_status, step, chunk_count, error_msg = row
            progress = _compute_progress(step, doc_status)

            yield {
                "event": "progress",
                "data": json.dumps(
                    {
                        "status": doc_status,
                        "progress_percent": progress,
                        "step": step or "",
                        "chunk_count": chunk_count,
                        "error_message": error_msg,
                    }
                ),
            }

            if doc_status == "ready":
                yield {
                    "event": "done",
                    "data": json.dumps(
                        {
                            "status": "ready",
                            "document_id": str(document_id),
                            "chunk_count": chunk_count,
                        }
                    ),
                }
                return

            if doc_status == "error":
                yield {
                    "event": "error",
                    "data": json.dumps(
                        {"code": "PROCESSING_FAILED", "message": error_msg or "Unknown error"}
                    ),
                }
                return

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        yield {"event": "error", "data": json.dumps({"code": "TIMEOUT"})}

    return EventSourceResponse(_generate())


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=DocumentListResponse)
async def list_documents(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = 1,
    page_size: int = 20,
) -> DocumentListResponse:
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    base_q = select(Document).where(Document.is_deleted.is_(False))
    if current_user.role == "viewer":
        base_q = base_q.where(Document.owner_id == current_user.id)

    count_res = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total: int = count_res.scalar_one()

    res = await db.execute(
        base_q.order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    docs = res.scalars().all()
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_document_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, int]:
    base: list = [Document.is_deleted.is_(False)]
    if current_user.role == "viewer":
        base.append(Document.owner_id == current_user.id)

    async def _count(stmt) -> int:
        return (await db.execute(stmt)).scalar_one()

    total = await _count(select(func.count(Document.id)).where(*base))
    ready = await _count(select(func.count(Document.id)).where(*base, Document.status == "ready"))

    ver_q = (
        select(func.count(DocumentVersion.id))
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(*base)
    )
    edits = await _count(ver_q.where(DocumentVersion.agent_name == "editor"))
    signatures = await _count(ver_q.where(DocumentVersion.agent_name == "signature"))

    reviews = await _count(
        select(func.count(DocumentReview.id))
        .join(Document, DocumentReview.document_id == Document.id)
        .where(*base)
    )

    return {"total": total, "ready": ready, "reviews": reviews, "edits": edits, "signatures": signatures}


# ── Detail ────────────────────────────────────────────────────────────────────

async def _get_doc_or_404(doc_id: uuid.UUID, user: User, db: AsyncSession) -> Document:
    res = await db.execute(
        select(Document).where(Document.id == doc_id, Document.is_deleted.is_(False))
    )
    doc = res.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if user.role == "viewer" and doc.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return doc


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentResponse:
    doc = await _get_doc_or_404(document_id, current_user, db)
    return DocumentResponse.model_validate(doc)


# ── Patch ─────────────────────────────────────────────────────────────────────

@router.patch("/{document_id}", response_model=DocumentResponse)
async def patch_document(
    document_id: uuid.UUID,
    body: DocumentPatchRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> DocumentResponse:
    doc = await _get_doc_or_404(document_id, current_user, db)
    doc.title = body.title
    await log_action(
        db,
        action="document.update",
        user_id=current_user.id,
        resource_type="document",
        resource_id=doc.id,
        request=request,
    )
    return DocumentResponse.model_validate(doc)


# ── Soft delete ───────────────────────────────────────────────────────────────

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> Response:
    from datetime import UTC, datetime
    from app.services.vector_service import delete_document_chunks, get_document_collection

    doc = await _get_doc_or_404(document_id, current_user, db)

    # Architecture rule #10: delete ChromaDB FIRST, abort if it fails
    try:
        collection = await asyncio.to_thread(get_document_collection)
        await asyncio.to_thread(delete_document_chunks, collection, str(document_id))
    except Exception as exc:
        logger.error("ChromaDB deletion failed for doc %s: %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to delete document embeddings — deletion aborted",
        )

    doc.is_deleted = True
    doc.deleted_at = datetime.now(UTC)
    await log_action(
        db,
        action="document.delete",
        user_id=current_user.id,
        resource_type="document",
        resource_id=doc.id,
        request=request,
    )
    return Response(status_code=204)


# ── Download ──────────────────────────────────────────────────────────────────

@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    doc = await _get_doc_or_404(document_id, current_user, db)
    path = resolve_upload_path(doc.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")
    return FileResponse(path=str(path), filename=doc.original_name, media_type=doc.mime_type)


# ── Original text (for comparison / diff) ────────────────────────────────────

@router.get("/{document_id}/text")
async def get_document_text(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    doc = await _get_doc_or_404(document_id, current_user, db)
    if doc.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is not ready (status={doc.status})",
        )
    rows = (
        await db.execute(
            select(DocumentChunk.chunk_text, DocumentChunk.chunk_index)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
    ).all()
    full_text = "\n\n".join(r.chunk_text for r in rows)
    return {"text": full_text, "chunk_count": len(rows)}


# ── Versions ──────────────────────────────────────────────────────────────────

@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_versions(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[DocumentVersionResponse]:
    await _get_doc_or_404(document_id, current_user, db)
    res = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
    )
    return [DocumentVersionResponse.model_validate(v) for v in res.scalars().all()]


@router.get("/{document_id}/versions/{version_id}/download")
async def download_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    fmt: str = Query(default="pdf", pattern="^(pdf|txt)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    await _get_doc_or_404(document_id, current_user, db)
    res = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == document_id,
        )
    )
    version = res.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    meta: dict = version.version_metadata or {}
    if fmt == "txt" and meta.get("txt_path"):
        file_rel = meta["txt_path"]
    else:
        file_rel = version.file_path

    path = resolve_upload_path(file_rel)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version file not found")

    ext = "txt" if fmt == "txt" else "pdf"
    filename = f"v{version.version_number}_{path.stem}.{ext}"
    return FileResponse(path=str(path), filename=filename, media_type=f"application/{'octet-stream' if fmt == 'txt' else 'pdf'}")


# ── Summarize ─────────────────────────────────────────────────────────────────

@router.post("/{document_id}/summarize", response_model=SummarizeResponse)
async def summarize_document(
    document_id: uuid.UUID,
    body: SummarizeRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SummarizeResponse:
    from app.agents.base import TaskPayload
    from app.agents.rag_agent import RAGAgent
    from app.models.agent import AgentSession

    doc = await _get_doc_or_404(document_id, current_user, db)
    if doc.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is not ready for summarization (status={doc.status})",
        )

    # Create a minimal session to satisfy agent_tasks.session_id NOT NULL
    session = AgentSession(
        user_id=current_user.id,
        session_name=f"summarize:{document_id}",
        is_active=False,
    )
    db.add(session)
    await db.flush()

    agent = RAGAgent()
    payload = TaskPayload(
        task_type="summarize",
        session_id=session.id,
        user_id=current_user.id,
        document_id=document_id,
        input_data={"length": body.length},
    )
    result = await agent.run(payload, db)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or "Summarization failed",
        )

    await log_action(
        db,
        action="document.summarize",
        user_id=current_user.id,
        resource_type="document",
        resource_id=document_id,
        details={"length": body.length, "task_id": result.output_data.get("task_id")},
        request=request,
    )

    return SummarizeResponse(
        document_id=document_id,
        summary=result.output_data["summary"],
        chunk_count=result.output_data["chunk_count"],
        token_count=result.token_count,
        task_id=uuid.UUID(result.output_data["task_id"]),
    )
