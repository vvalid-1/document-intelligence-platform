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
from app.core.deps import get_current_user, require_admin, require_editor_or_admin, validate_sse_token
from app.services.vector_service import delete_document_chunks, get_document_collection
from app.services.transcription_service import transcribe_audio
from app.models.document import Document, DocumentChunk, DocumentReview, DocumentVersion
from app.models.user import User
from app.models.folder import Folder
from app.schemas.document import (
    BulkActionRequest,
    BulkFavoriteRequest,
    BulkMoveRequest,
    DocumentListResponse,
    DocumentPatchRequest,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
    DocumentVersionResponse,
    MediaAnalysisResponse,
    MoveRequest,
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
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".mp4": "video/mp4",
}

_IMAGE_MIMES = {"image/jpeg", "image/png"}
_MEDIA_MIMES = {"audio/mpeg", "audio/wav", "video/mp4"}

# Maps processing_step → approximate progress percent
_STEP_PROGRESS: dict[str | None, int] = {
    "queued": 5,
    "extracting": 20,
    "ocr": 30,
    "transcribing": 20,
    "chunking": 50,
    "embedding": 70,
    "analyzing": 85,
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

        if mime in _MEDIA_MIMES:
            # ── Media pipeline: transcribe → chunk transcript → embed → AI analysis ──
            await _set(processing_step="transcribing")
            transcription = await asyncio.to_thread(transcribe_audio, file_path)
            transcript_text = transcription.text
            duration = transcription.duration_seconds
            language = transcription.language

            doc_metadata = {
                "word_count": len(transcript_text.split()),
                "duration_seconds": duration,
                "language": language,
            }
            chunks = chunk_plain_text(transcript_text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
            await _set(
                processing_step="chunking",
                page_count=None,
                doc_metadata=doc_metadata,
                media_duration_seconds=duration,
            )

            if chunks:
                collection = get_document_collection(chroma_client)
                _BATCH = 50
                all_embeddings_media: list[list[float]] = []
                for batch_start in range(0, len(chunks), _BATCH):
                    batch = chunks[batch_start : batch_start + _BATCH]
                    batch_embeddings = await _embed([c.chunk_text for c in batch])
                    all_embeddings_media.extend(batch_embeddings)
                    done = batch_start + len(batch)
                    await _set(processing_step=f"embedding chunk {done}/{len(chunks)}")

                chroma_ids = [f"{document_id}_{c.chunk_index}" for c in chunks]
                created_str = created_at.isoformat() if created_at else ""
                collection.add(
                    ids=chroma_ids,
                    embeddings=all_embeddings_media,
                    documents=[c.chunk_text for c in chunks],
                    metadatas=[
                        {
                            "document_id": str(document_id),
                            "document_title": title,
                            "mime_type": mime,
                            "page_number": -1,
                            "chunk_index": c.chunk_index,
                            "owner_id": str(owner_id) if owner_id else "",
                            "created_at": created_str,
                        }
                        for c in chunks
                    ],
                )

                async with AsyncSession(engine, expire_on_commit=False) as sess:
                    async with sess.begin():
                        for chunk, chroma_id in zip(chunks, chroma_ids):
                            sess.add(
                                DocumentChunk(
                                    document_id=document_id,
                                    chroma_chunk_id=chroma_id,
                                    chunk_index=chunk.chunk_index,
                                    page_number=None,
                                    chunk_text=chunk.chunk_text,
                                    token_count=chunk.token_count,
                                )
                            )

            # AI analysis (only when there's a transcript and an owner)
            if transcript_text and owner_id:
                await _set(processing_step="analyzing")
                from app.agents.media_agent import MediaAnalysisAgent
                from app.agents.base import TaskPayload as _TaskPayload
                from app.models.agent import AgentSession

                async with AsyncSession(engine, expire_on_commit=False) as sess:
                    async with sess.begin():
                        session_obj = AgentSession(
                            user_id=owner_id,
                            session_name=f"media_analysis:{document_id}",
                            is_active=False,
                        )
                        sess.add(session_obj)
                        await sess.flush()

                        payload = _TaskPayload(
                            task_type="media_analysis",
                            session_id=session_obj.id,
                            user_id=owner_id,
                            document_id=document_id,
                            input_data={
                                "transcript": transcript_text,
                                "user_id": str(owner_id),
                                "duration_seconds": duration,
                                "language": language,
                            },
                        )
                        agent = MediaAnalysisAgent()
                        analysis_result = await agent.run(payload, sess)
                        if not analysis_result.success:
                            logger.warning(
                                "Media analysis failed for doc %s: %s",
                                document_id,
                                analysis_result.error,
                            )

            await _set(
                status="ready",
                processing_step=None,
                chunk_count=len(chunks),
                error_message=None,
            )
            logger.info("Media document %s processed: %d chunks, %.1f s", document_id, len(chunks), duration)
            return

        elif mime == "application/pdf":
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
    archived: bool = False,
    favorite: bool = False,
    trashed: bool = False,
    folder_id: uuid.UUID | None = None,
) -> DocumentListResponse:
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    if trashed:
        base_q = select(Document).where(Document.is_deleted.is_(True))
    else:
        base_q = select(Document).where(
            Document.is_deleted.is_(False),
            Document.is_archived.is_(archived),
        )
        if favorite:
            base_q = base_q.where(Document.is_favorite.is_(True))
        if folder_id is not None:
            base_q = base_q.where(Document.folder_id == folder_id)

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
    base: list = [Document.is_deleted.is_(False), Document.is_archived.is_(False)]
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

    viewer_filter = [Document.owner_id == current_user.id] if current_user.role == "viewer" else []
    favorites = await _count(
        select(func.count(Document.id)).where(
            Document.is_deleted.is_(False),
            Document.is_archived.is_(False),
            Document.is_favorite.is_(True),
            *viewer_filter,
        )
    )
    trash = await _count(
        select(func.count(Document.id)).where(Document.is_deleted.is_(True), *viewer_filter)
    )

    folder_q = select(func.count(Folder.id))
    if current_user.role != "admin":
        folder_q = folder_q.where(Folder.owner_id == current_user.id)
    folders_count = await _count(folder_q)

    media_q = select(func.count(DocumentVersion.id)).join(
        Document, DocumentVersion.document_id == Document.id
    ).where(*base, DocumentVersion.agent_name == "media_analysis")
    media_analyses = await _count(media_q)

    return {
        "total": total,
        "ready": ready,
        "reviews": reviews,
        "edits": edits,
        "signatures": signatures,
        "favorites": favorites,
        "trash": trash,
        "folders": folders_count,
        "media_analyses": media_analyses,
    }


# ── Bulk actions ─────────────────────────────────────────────────────────────
# Routes defined here (before /{document_id}/…) so "bulk" is not parsed as a UUID.

@router.post("/bulk/archive", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def bulk_archive_documents(
    body: BulkActionRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> Response:
    from datetime import UTC, datetime as dt

    q = update(Document).where(
        Document.id.in_(body.ids),
        Document.is_deleted.is_(False),
        Document.is_archived.is_(False),
    )
    if current_user.role == "viewer":
        q = q.where(Document.owner_id == current_user.id)
    await db.execute(q.values(is_archived=True, archived_at=dt.now(UTC)))
    await log_action(
        db,
        action="document.bulk_archive",
        user_id=current_user.id,
        details={"count": len(body.ids)},
        request=request,
    )
    return Response(status_code=204)


@router.post("/bulk/restore", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def bulk_restore_documents(
    body: BulkActionRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> Response:
    q = update(Document).where(
        Document.id.in_(body.ids),
        Document.is_deleted.is_(False),
        Document.is_archived.is_(True),
    )
    if current_user.role == "viewer":
        q = q.where(Document.owner_id == current_user.id)
    await db.execute(q.values(is_archived=False, archived_at=None))
    await log_action(
        db,
        action="document.bulk_restore",
        user_id=current_user.id,
        details={"count": len(body.ids)},
        request=request,
    )
    return Response(status_code=204)


@router.post("/bulk/trash", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def bulk_trash_documents(
    body: BulkActionRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> Response:
    from datetime import UTC, datetime as dt

    q = update(Document).where(
        Document.id.in_(body.ids),
        Document.is_deleted.is_(False),
    )
    if current_user.role == "viewer":
        q = q.where(Document.owner_id == current_user.id)
    await db.execute(q.values(is_deleted=True, deleted_at=dt.now(UTC)))
    await log_action(
        db,
        action="document.bulk_trash",
        user_id=current_user.id,
        details={"count": len(body.ids)},
        request=request,
    )
    return Response(status_code=204)


@router.post("/bulk/favorite", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def bulk_favorite_documents(
    body: BulkFavoriteRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    q = update(Document).where(
        Document.id.in_(body.ids),
        Document.is_deleted.is_(False),
    )
    if current_user.role == "viewer":
        q = q.where(Document.owner_id == current_user.id)
    await db.execute(q.values(is_favorite=body.value))
    await log_action(
        db,
        action="document.bulk_favorite",
        user_id=current_user.id,
        details={"count": len(body.ids), "value": body.value},
        request=request,
    )
    return Response(status_code=204)


@router.post("/bulk/move", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def bulk_move_documents(
    body: BulkMoveRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> Response:
    if body.folder_id is not None:
        folder = await db.execute(select(Folder).where(Folder.id == body.folder_id))
        if folder.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    q = update(Document).where(
        Document.id.in_(body.ids),
        Document.is_deleted.is_(False),
    )
    if current_user.role == "viewer":
        q = q.where(Document.owner_id == current_user.id)
    await db.execute(q.values(folder_id=body.folder_id))
    await log_action(
        db,
        action="document.bulk_move",
        user_id=current_user.id,
        details={"count": len(body.ids), "folder_id": str(body.folder_id) if body.folder_id else None},
        request=request,
    )
    return Response(status_code=204)


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


# ── Move to Trash ─────────────────────────────────────────────────────────────

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> Response:
    from datetime import UTC, datetime

    doc = await _get_doc_or_404(document_id, current_user, db)
    doc.is_deleted = True
    doc.deleted_at = datetime.now(UTC)
    await log_action(
        db,
        action="document.trash",
        user_id=current_user.id,
        resource_type="document",
        resource_id=doc.id,
        request=request,
    )
    return Response(status_code=204)


# ── Archive / Restore ─────────────────────────────────────────────────────────

@router.post("/{document_id}/archive", response_model=DocumentResponse)
async def archive_document(
    document_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> DocumentResponse:
    from datetime import UTC, datetime as dt

    doc = await _get_doc_or_404(document_id, current_user, db)
    if doc.is_archived:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document is already archived")
    doc.is_archived = True
    doc.archived_at = dt.now(UTC)
    await log_action(
        db,
        action="document.archive",
        user_id=current_user.id,
        resource_type="document",
        resource_id=doc.id,
        request=request,
    )
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.post("/{document_id}/restore", response_model=DocumentResponse)
async def restore_document(
    document_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> DocumentResponse:
    doc = await _get_doc_or_404(document_id, current_user, db)
    if not doc.is_archived:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document is not archived")
    doc.is_archived = False
    doc.archived_at = None
    await log_action(
        db,
        action="document.restore",
        user_id=current_user.id,
        resource_type="document",
        resource_id=doc.id,
        request=request,
    )
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


# ── Favorite / Unfavorite ─────────────────────────────────────────────────────

@router.post("/{document_id}/favorite", response_model=DocumentResponse)
async def favorite_document(
    document_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentResponse:
    doc = await _get_doc_or_404(document_id, current_user, db)
    if doc.is_favorite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document is already starred")
    doc.is_favorite = True
    await log_action(
        db,
        action="document.favorite",
        user_id=current_user.id,
        resource_type="document",
        resource_id=doc.id,
        request=request,
    )
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.post("/{document_id}/unfavorite", response_model=DocumentResponse)
async def unfavorite_document(
    document_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentResponse:
    doc = await _get_doc_or_404(document_id, current_user, db)
    if not doc.is_favorite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document is not starred")
    doc.is_favorite = False
    await log_action(
        db,
        action="document.unfavorite",
        user_id=current_user.id,
        resource_type="document",
        resource_id=doc.id,
        request=request,
    )
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


# ── Move to folder ───────────────────────────────────────────────────────────

@router.post("/{document_id}/move", response_model=DocumentResponse)
async def move_document(
    document_id: uuid.UUID,
    body: MoveRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> DocumentResponse:
    doc = await _get_doc_or_404(document_id, current_user, db)

    if body.folder_id is not None:
        folder_res = await db.execute(select(Folder).where(Folder.id == body.folder_id))
        if folder_res.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    doc.folder_id = body.folder_id
    await log_action(
        db,
        action="document.move",
        user_id=current_user.id,
        resource_type="document",
        resource_id=doc.id,
        details={"folder_id": str(body.folder_id) if body.folder_id else None},
        request=request,
    )
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


# ── Untrash (restore from trash) ──────────────────────────────────────────────

@router.post("/{document_id}/untrash", response_model=DocumentResponse)
async def untrash_document(
    document_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> DocumentResponse:
    res = await db.execute(
        select(Document).where(Document.id == document_id, Document.is_deleted.is_(True))
    )
    doc = res.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found in trash")
    doc.is_deleted = False
    doc.deleted_at = None
    await log_action(
        db,
        action="document.untrash",
        user_id=current_user.id,
        resource_type="document",
        resource_id=doc.id,
        request=request,
    )
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


# ── Permanent delete (admin only) ─────────────────────────────────────────────

@router.delete("/{document_id}/permanent", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def permanent_delete_document(
    document_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
) -> Response:
    res = await db.execute(select(Document).where(Document.id == document_id))
    doc = res.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Architecture rule #10: delete ChromaDB FIRST
    try:
        collection = await asyncio.to_thread(get_document_collection)
        await asyncio.to_thread(delete_document_chunks, collection, str(document_id))
    except Exception as exc:
        logger.error("ChromaDB deletion failed for doc %s: %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to delete document embeddings — deletion aborted",
        )

    await log_action(
        db,
        action="document.permanent_delete",
        user_id=current_user.id,
        resource_type="document",
        resource_id=document_id,
        request=request,
    )
    await db.delete(doc)
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


# ── Media Analysis ────────────────────────────────────────────────────────────

@router.get("/{document_id}/media-analysis", response_model=MediaAnalysisResponse)
async def get_media_analysis(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MediaAnalysisResponse:
    doc = await _get_doc_or_404(document_id, current_user, db)

    if doc.mime_type not in _MEDIA_MIMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document is not a media file (MP3/WAV/MP4)",
        )

    res = await db.execute(
        select(DocumentVersion)
        .where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.agent_name == "media_analysis",
        )
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )
    version = res.scalar_one_or_none()

    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media analysis not yet available — document may still be processing",
        )

    meta: dict = version.version_metadata or {}
    return MediaAnalysisResponse(
        version_id=str(version.id),
        transcript=meta.get("transcript", ""),
        summary=meta.get("summary", ""),
        key_topics=meta.get("key_topics", []),
        action_items=meta.get("action_items", []),
        important_dates=meta.get("important_dates", []),
        important_numbers=meta.get("important_numbers", []),
        duration_seconds=meta.get("duration_seconds"),
        language=meta.get("language"),
        txt_path=meta.get("txt_path", ""),
        pdf_path=meta.get("pdf_path", ""),
        created_at=version.created_at,
    )


@router.post("/{document_id}/media-analysis", response_model=MediaAnalysisResponse)
async def retrigger_media_analysis(
    document_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> MediaAnalysisResponse:
    """Re-run AI analysis on an existing transcript (does not re-transcribe)."""
    doc = await _get_doc_or_404(document_id, current_user, db)

    if doc.mime_type not in _MEDIA_MIMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document is not a media file (MP3/WAV/MP4)",
        )

    if doc.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is not ready (status={doc.status})",
        )

    # Find existing transcript from the last media_analysis version
    res = await db.execute(
        select(DocumentVersion)
        .where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.agent_name == "media_analysis",
        )
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )
    existing = res.scalar_one_or_none()

    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No previous media analysis found — upload the file again to trigger transcription",
        )

    meta: dict = existing.version_metadata or {}
    transcript = meta.get("transcript", "")
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No transcript found in existing analysis",
        )

    from app.agents.media_agent import MediaAnalysisAgent
    from app.agents.base import TaskPayload
    from app.models.agent import AgentSession

    session_obj = AgentSession(
        user_id=current_user.id,
        session_name=f"media_reanalysis:{document_id}",
        is_active=False,
    )
    db.add(session_obj)
    await db.flush()

    payload = TaskPayload(
        task_type="media_analysis",
        session_id=session_obj.id,
        user_id=current_user.id,
        document_id=document_id,
        input_data={
            "transcript": transcript,
            "user_id": str(current_user.id),
            "duration_seconds": meta.get("duration_seconds"),
            "language": meta.get("language"),
        },
    )
    agent = MediaAnalysisAgent()
    result = await agent.run(payload, db)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or "Media analysis failed",
        )

    await log_action(
        db,
        action="document.media_reanalysis",
        user_id=current_user.id,
        resource_type="document",
        resource_id=document_id,
        request=request,
    )

    out = result.output_data
    # Fetch the newly created version's created_at
    ver_res = await db.execute(
        select(DocumentVersion).where(DocumentVersion.id == uuid.UUID(out["version_id"]))
    )
    new_version = ver_res.scalar_one()

    return MediaAnalysisResponse(
        version_id=out["version_id"],
        transcript=transcript,
        summary=out.get("summary", ""),
        key_topics=out.get("key_topics", []),
        action_items=out.get("action_items", []),
        important_dates=out.get("important_dates", []),
        important_numbers=out.get("important_numbers", []),
        duration_seconds=out.get("duration_seconds"),
        language=out.get("language"),
        txt_path=out.get("txt_path", ""),
        pdf_path=out.get("pdf_path", ""),
        created_at=new_version.created_at,
    )
