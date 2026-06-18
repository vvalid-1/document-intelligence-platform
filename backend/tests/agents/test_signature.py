from __future__ import annotations

import base64
import uuid
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import TaskPayload
from app.agents.signature_agent import SignatureAgent
from app.models.document import DocumentVersion, Signature
from app.services.signature_service import (
    apply_typed_signature,
    get_pdf_page_info,
    validate_position,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

# ── PDF helpers ───────────────────────────────────────────────────────────────

def _make_test_pdf(path: Path, pages: int = 2) -> None:
    """Create a minimal multi-page PDF using PyMuPDF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"Page {i + 1} — test document content.", fontsize=12)
    doc.save(str(path))
    doc.close()


def _make_test_png() -> bytes:
    """Create a minimal 10×10 white PNG using PyMuPDF Pixmap."""
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10))
    pix.set_rect(pix.irect, (255, 255, 255))
    return pix.tobytes("png")


# ── signature_service unit tests ──────────────────────────────────────────────

def test_get_pdf_page_info_valid(tmp_path: Path) -> None:
    pdf = tmp_path / "test.pdf"
    _make_test_pdf(pdf, pages=3)
    w, h, total = get_pdf_page_info(pdf, 2)
    assert total == 3
    assert w == pytest.approx(595.0)
    assert h == pytest.approx(842.0)


def test_get_pdf_page_info_page_out_of_range(tmp_path: Path) -> None:
    pdf = tmp_path / "test.pdf"
    _make_test_pdf(pdf, pages=1)
    with pytest.raises(ValueError, match="out of range"):
        get_pdf_page_info(pdf, 5)


def test_get_pdf_page_info_page_zero_invalid(tmp_path: Path) -> None:
    pdf = tmp_path / "test.pdf"
    _make_test_pdf(pdf, pages=1)
    with pytest.raises(ValueError, match="out of range"):
        get_pdf_page_info(pdf, 0)


def test_validate_position_valid() -> None:
    validate_position(100.0, 200.0, 595.0, 842.0)  # should not raise


def test_validate_position_x_out_of_range() -> None:
    with pytest.raises(ValueError, match="x="):
        validate_position(600.0, 200.0, 595.0, 842.0)


def test_validate_position_y_out_of_range() -> None:
    with pytest.raises(ValueError, match="y="):
        validate_position(100.0, 900.0, 595.0, 842.0)


def test_validate_position_negative_x() -> None:
    with pytest.raises(ValueError, match="x="):
        validate_position(-1.0, 200.0, 595.0, 842.0)


def test_validate_position_zero_zero_valid() -> None:
    validate_position(0.0, 0.0, 595.0, 842.0)  # should not raise


def test_apply_typed_signature_creates_file(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    dest = tmp_path / "signed.pdf"
    _make_test_pdf(source, pages=1)
    apply_typed_signature(source, dest, "Jane Doe", 100.0, 700.0, 1)
    assert dest.exists()
    assert dest.stat().st_size > 0
    # Verify it's still a valid PDF
    doc = fitz.open(str(dest))
    assert len(doc) == 1
    doc.close()


def test_apply_typed_signature_text_present(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    dest = tmp_path / "signed.pdf"
    _make_test_pdf(source, pages=1)
    apply_typed_signature(source, dest, "Jane Doe", 100.0, 700.0, 1)
    doc = fitz.open(str(dest))
    text = doc[0].get_text()
    doc.close()
    assert "Jane Doe" in text


def test_apply_typed_signature_second_page(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    dest = tmp_path / "signed.pdf"
    _make_test_pdf(source, pages=2)
    apply_typed_signature(source, dest, "John Smith", 100.0, 200.0, 2)
    doc = fitz.open(str(dest))
    text_p2 = doc[1].get_text()
    doc.close()
    assert "John Smith" in text_p2


# ── SignatureAgent integration tests ──────────────────────────────────────────

async def test_signature_agent_typed_creates_version(db: AsyncSession, tmp_path: Path) -> None:
    session, user_id = await _make_session(db)
    doc_id = await _make_pdf_document(db, user_id, tmp_path)

    agent = SignatureAgent()
    payload = TaskPayload(
        task_type="sign_document",
        session_id=session.id,
        user_id=user_id,
        document_id=doc_id,
        input_data={
            "signer_id": str(user_id),
            "signature_type": "typed",
            "typed_text": "Alice Manager",
            "image_base64": None,
            "x": 100.0,
            "y": 700.0,
            "page_number": 1,
            "field_name": "Approver",
            "ip_address": "127.0.0.1",
            "user_agent": "pytest",
        },
    )
    result = await agent.run(payload, db)

    assert result.success is True
    assert "signature_id" in result.output_data
    assert "version_id" in result.output_data
    assert result.output_data["version_number"] == 1

    # DocumentVersion was created
    version_id = uuid.UUID(result.output_data["version_id"])
    vr = await db.execute(select(DocumentVersion).where(DocumentVersion.id == version_id))
    version = vr.scalar_one()
    assert version.agent_name == "signature"
    assert version.task_id is not None
    assert "signed" in version.file_path

    # Signature record was created
    sig_id = uuid.UUID(result.output_data["signature_id"])
    sr = await db.execute(select(Signature).where(Signature.id == sig_id))
    sig = sr.scalar_one()
    assert sig.signature_type == "typed"
    assert sig.page_number == 1
    assert sig.version_id == version_id
    assert sig.position_data["x"] == pytest.approx(100.0)
    assert sig.field_name == "Approver"
    assert sig.ip_address == "127.0.0.1"


async def test_signature_agent_drawn_creates_version(db: AsyncSession, tmp_path: Path) -> None:
    session, user_id = await _make_session(db)
    doc_id = await _make_pdf_document(db, user_id, tmp_path)

    png_bytes = _make_test_png()
    img_b64 = base64.b64encode(png_bytes).decode()

    agent = SignatureAgent()
    payload = TaskPayload(
        task_type="sign_document",
        session_id=session.id,
        user_id=user_id,
        document_id=doc_id,
        input_data={
            "signer_id": str(user_id),
            "signature_type": "drawn",
            "typed_text": None,
            "image_base64": img_b64,
            "x": 50.0,
            "y": 750.0,
            "page_number": 1,
            "field_name": None,
            "ip_address": None,
            "user_agent": None,
        },
    )
    result = await agent.run(payload, db)

    assert result.success is True

    sig_id = uuid.UUID(result.output_data["signature_id"])
    sr = await db.execute(select(Signature).where(Signature.id == sig_id))
    sig = sr.scalar_one()
    assert sig.signature_type == "drawn"
    assert sig.signature_image_path is not None  # stored image path


async def test_signature_agent_version_number_increments(db: AsyncSession, tmp_path: Path) -> None:
    session, user_id = await _make_session(db)
    doc_id = await _make_pdf_document(db, user_id, tmp_path)

    agent = SignatureAgent()
    for expected_n in [1, 2]:
        payload = TaskPayload(
            task_type="sign_document",
            session_id=session.id,
            user_id=user_id,
            document_id=doc_id,
            input_data={
                "signer_id": str(user_id),
                "signature_type": "typed",
                "typed_text": f"Signer {expected_n}",
                "image_base64": None,
                "x": 100.0,
                "y": 700.0,
                "page_number": 1,
                "field_name": None,
                "ip_address": None,
                "user_agent": None,
            },
        )
        result = await agent.run(payload, db)
        assert result.output_data["version_number"] == expected_n


async def test_signature_agent_invalid_page_fails(db: AsyncSession, tmp_path: Path) -> None:
    session, user_id = await _make_session(db)
    doc_id = await _make_pdf_document(db, user_id, tmp_path, pages=1)

    agent = SignatureAgent()
    payload = TaskPayload(
        task_type="sign_document",
        session_id=session.id,
        user_id=user_id,
        document_id=doc_id,
        input_data={
            "signer_id": str(user_id),
            "signature_type": "typed",
            "typed_text": "Alice",
            "image_base64": None,
            "x": 100.0,
            "y": 200.0,
            "page_number": 99,  # out of range
            "field_name": None,
            "ip_address": None,
            "user_agent": None,
        },
    )
    result = await agent.run(payload, db)

    assert result.success is False
    assert "out of range" in (result.error or "").lower()


async def test_signature_agent_invalid_coordinates_fail(db: AsyncSession, tmp_path: Path) -> None:
    session, user_id = await _make_session(db)
    doc_id = await _make_pdf_document(db, user_id, tmp_path)

    agent = SignatureAgent()
    payload = TaskPayload(
        task_type="sign_document",
        session_id=session.id,
        user_id=user_id,
        document_id=doc_id,
        input_data={
            "signer_id": str(user_id),
            "signature_type": "typed",
            "typed_text": "Alice",
            "image_base64": None,
            "x": 9999.0,  # way outside page
            "y": 9999.0,
            "page_number": 1,
            "field_name": None,
            "ip_address": None,
            "user_agent": None,
        },
    )
    result = await agent.run(payload, db)

    assert result.success is False
    assert "outside" in (result.error or "").lower()


async def test_signature_agent_original_not_modified(db: AsyncSession, tmp_path: Path) -> None:
    """Signing must not overwrite the original file."""
    session, user_id = await _make_session(db)
    doc_id = await _make_pdf_document(db, user_id, tmp_path)

    from app.utils.file_utils import resolve_upload_path
    from sqlalchemy import select as sa_select
    from app.models.document import Document

    dr = await db.execute(sa_select(Document).where(Document.id == doc_id))
    doc = dr.scalar_one()
    original_path = resolve_upload_path(doc.file_path)
    original_mtime = original_path.stat().st_mtime

    agent = SignatureAgent()
    payload = TaskPayload(
        task_type="sign_document",
        session_id=session.id,
        user_id=user_id,
        document_id=doc_id,
        input_data={
            "signer_id": str(user_id),
            "signature_type": "typed",
            "typed_text": "Test Signer",
            "image_base64": None,
            "x": 100.0,
            "y": 700.0,
            "page_number": 1,
            "field_name": None,
            "ip_address": None,
            "user_agent": None,
        },
    )
    await agent.run(payload, db)

    # Original file's mtime must be unchanged
    assert original_path.stat().st_mtime == original_mtime


async def test_signature_agent_non_pdf_no_versions_fails(db: AsyncSession) -> None:
    session, user_id = await _make_session(db)
    doc_id = await _make_txt_document(db, user_id)

    agent = SignatureAgent()
    payload = TaskPayload(
        task_type="sign_document",
        session_id=session.id,
        user_id=user_id,
        document_id=doc_id,
        input_data={
            "signer_id": str(user_id),
            "signature_type": "typed",
            "typed_text": "Test",
            "image_base64": None,
            "x": 100.0,
            "y": 200.0,
            "page_number": 1,
            "field_name": None,
            "ip_address": None,
            "user_agent": None,
        },
    )
    result = await agent.run(payload, db)

    assert result.success is False
    assert "no signable pdf" in (result.error or "").lower()


async def test_signature_agent_task_recorded(db: AsyncSession, tmp_path: Path) -> None:
    from app.models.agent import AgentTask

    session, user_id = await _make_session(db)
    doc_id = await _make_pdf_document(db, user_id, tmp_path)

    agent = SignatureAgent()
    payload = TaskPayload(
        task_type="sign_document",
        session_id=session.id,
        user_id=user_id,
        document_id=doc_id,
        input_data={
            "signer_id": str(user_id),
            "signature_type": "typed",
            "typed_text": "Inspector General",
            "image_base64": None,
            "x": 72.0,
            "y": 720.0,
            "page_number": 1,
            "field_name": "inspector",
            "ip_address": None,
            "user_agent": None,
        },
    )
    result = await agent.run(payload, db)

    task_id = uuid.UUID(result.output_data["task_id"])
    tr = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    task = tr.scalar_one()
    assert task.status == "completed"
    assert task.agent_name == "signature"
    assert task.duration_ms is not None
    # image_base64 must NOT be in input_payload (security: don't persist large blobs)
    assert "image_base64" not in task.input_payload


# ── Fixtures ──────────────────────────────────────────────────────────────────

async def _make_session(db: AsyncSession):
    from app.core.security import hash_password
    from app.models.agent import AgentSession
    from app.models.user import User

    user_id = uuid.uuid4()
    db.add(User(
        id=user_id,
        email=f"signer_{uuid.uuid4().hex[:8]}@example.com",
        full_name="Test Signer",
        hashed_password=hash_password("testpassword1"),
        role="editor",
        is_active=True,
    ))
    await db.flush()

    session = AgentSession(user_id=user_id, is_active=False)
    db.add(session)
    await db.flush()
    return session, user_id


async def _make_pdf_document(
    db: AsyncSession, owner_id: uuid.UUID, tmp_path: Path, pages: int = 2
) -> uuid.UUID:
    from app.models.document import Document

    doc_id = uuid.uuid4()

    # Write an actual PDF to the upload directory
    from app.core.config import settings
    doc_dir = Path(settings.UPLOAD_DIR) / str(doc_id)
    doc_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = doc_dir / "original.pdf"
    _make_test_pdf(pdf_path, pages=pages)

    db.add(Document(
        id=doc_id,
        owner_id=owner_id,
        title="PDF Sign Test",
        original_name="test.pdf",
        file_path=f"{doc_id}/original.pdf",
        file_size_bytes=pdf_path.stat().st_size,
        mime_type="application/pdf",
        status="ready",
        page_count=pages,
        chunk_count=1,
    ))
    await db.flush()
    return doc_id


async def _make_txt_document(db: AsyncSession, owner_id: uuid.UUID) -> uuid.UUID:
    from app.models.document import Document

    doc_id = uuid.uuid4()
    db.add(Document(
        id=doc_id,
        owner_id=owner_id,
        title="TXT Doc",
        original_name="test.txt",
        file_path=f"{doc_id}/original.txt",
        file_size_bytes=100,
        mime_type="text/plain",
        status="ready",
        chunk_count=1,
    ))
    await db.flush()
    return doc_id
