from __future__ import annotations

import asyncio
import base64
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent, TaskPayload
from app.core.config import settings
from app.models.agent import AgentTask
from app.models.document import Document, DocumentVersion, Signature
from app.services.signature_service import (
    apply_drawn_signature,
    apply_typed_signature,
    get_pdf_page_info,
    save_signature_image,
    validate_position,
)
from app.utils.file_utils import make_document_dir, resolve_upload_path

logger = logging.getLogger(__name__)

_PDF_MIME = "application/pdf"


class SignatureAgent(BaseAgent):
    AGENT_NAME = "signature"

    # ── Public entry point ────────────────────────────────────────────────────

    async def run(self, payload: TaskPayload, db: AsyncSession) -> AgentResult:
        task = AgentTask(
            session_id=payload.session_id,
            document_id=payload.document_id,
            agent_name=self.AGENT_NAME,
            task_type=payload.task_type,
            input_payload={
                k: v
                for k, v in payload.input_data.items()
                if k != "image_base64"  # never persist raw image bytes in task payload
            },
            status="running",
            model_used=None,
        )
        db.add(task)
        await db.flush()

        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self._sign_document(payload, task.id, db),
                timeout=settings.AGENT_TIMEOUT_SECONDS,
            )
            task.status = "completed"
            task.output_payload = result.output_data
        except asyncio.TimeoutError:
            task.status = "failed"
            task.timed_out = True
            task.error_message = "Agent timed out"
            result = AgentResult(
                success=False, output_data={}, error="Agent timed out", timed_out=True
            )
        except Exception as exc:
            logger.error("SignatureAgent task %s failed: %s", task.id, exc, exc_info=True)
            task.status = "failed"
            task.error_message = str(exc)[:500]
            result = AgentResult(success=False, output_data={}, error=str(exc))

        task.duration_ms = int((time.monotonic() - start) * 1000)
        task.completed_at = datetime.now(UTC)
        result.duration_ms = task.duration_ms
        result.output_data.setdefault("task_id", str(task.id))
        await db.flush()
        return result

    # ── Core signing logic ────────────────────────────────────────────────────

    async def _sign_document(
        self, payload: TaskPayload, task_id: UUID, db: AsyncSession
    ) -> AgentResult:
        document_id: UUID = payload.document_id  # type: ignore[assignment]
        data = payload.input_data
        signer_id = UUID(str(data["signer_id"]))
        sig_type: str = data["signature_type"]
        x: float = float(data["x"])
        y: float = float(data["y"])
        page_number: int = int(data["page_number"])
        field_name: str | None = data.get("field_name")
        ip_address: str | None = data.get("ip_address")
        user_agent: str | None = data.get("user_agent")

        # Load document
        doc_res = await db.execute(select(Document).where(Document.id == document_id))
        doc = doc_res.scalar_one_or_none()
        if doc is None or doc.is_deleted:
            raise ValueError("Document not found")

        # Find a signable PDF source
        source_rel, source_type = await self._find_source_pdf(doc, db)
        source_path = resolve_upload_path(source_rel)

        if not source_path.exists():
            raise FileNotFoundError(
                f"Source PDF not found on disk: {source_rel}"
            )

        # Validate page and position (sync I/O → thread)
        page_width, page_height, _ = await asyncio.to_thread(
            get_pdf_page_info, source_path, page_number
        )
        validate_position(x, y, page_width, page_height)

        # Determine next version number
        ver_res = await db.execute(
            select(func.coalesce(func.max(DocumentVersion.version_number), 0)).where(
                DocumentVersion.document_id == document_id
            )
        )
        next_version: int = ver_res.scalar_one() + 1

        doc_dir = make_document_dir(str(document_id))
        output_path = doc_dir / f"v{next_version}_signed.pdf"
        output_rel = f"{document_id}/v{next_version}_signed.pdf"

        # Apply signature (sync I/O → thread)
        sig_image_rel: str | None = None

        if sig_type == "typed":
            typed_text: str = data["typed_text"]
            await asyncio.to_thread(
                apply_typed_signature, source_path, output_path, typed_text, x, y, page_number
            )
        else:
            img_b64: str = data["image_base64"]
            # Save image file first
            sig_image_rel = await asyncio.to_thread(
                save_signature_image, document_id, img_b64
            )
            image_bytes = base64.b64decode(img_b64)
            await asyncio.to_thread(
                apply_drawn_signature, source_path, output_path, image_bytes, x, y, page_number
            )

        # Create DocumentVersion
        change_summary = (
            f"Signed ({sig_type}) on page {page_number} at ({x:.1f}, {y:.1f})"
            + (f" — {data.get('typed_text', '')[:80]}" if sig_type == "typed" else "")
        )
        version = DocumentVersion(
            document_id=document_id,
            version_number=next_version,
            created_by=signer_id,
            file_path=output_rel,
            change_summary=change_summary,
            agent_name=self.AGENT_NAME,
            task_id=task_id,
            version_metadata={
                "signature_type": sig_type,
                "page_number": page_number,
                "x": x,
                "y": y,
                "source_type": source_type,
            },
        )
        db.add(version)
        await db.flush()

        # Create Signature record
        sig_record = Signature(
            document_id=document_id,
            signed_by=signer_id,
            version_id=version.id,
            signature_type=sig_type,
            signature_image_path=sig_image_rel,
            field_name=field_name,
            page_number=page_number,
            position_data={
                "x": x,
                "y": y,
                "page_width": page_width,
                "page_height": page_height,
                "source_type": source_type,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(sig_record)
        await db.flush()

        return AgentResult(
            success=True,
            output_data={
                "signature_id": str(sig_record.id),
                "version_id": str(version.id),
                "version_number": next_version,
                "task_id": str(task_id),
                "pdf_path": output_rel,
            },
        )

    # ── Source PDF resolution ─────────────────────────────────────────────────

    async def _find_source_pdf(
        self, doc: Document, db: AsyncSession
    ) -> tuple[str, str]:
        """
        Return (relative_path, source_type) of the best PDF to sign.
        Priority: original PDF → latest version with a PDF path.
        """
        if doc.mime_type == _PDF_MIME:
            return doc.file_path, "original"

        # Look for the most recent version with a pdf_path in its metadata
        res = await db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.version_number.desc())
        )
        versions = res.scalars().all()
        for v in versions:
            meta = v.version_metadata or {}
            pdf_path = meta.get("pdf_path") or (v.file_path if v.file_path.endswith(".pdf") else None)
            if pdf_path:
                return pdf_path, "version"

        raise ValueError(
            "No signable PDF source found. Upload a PDF or generate a PDF version first."
        )
