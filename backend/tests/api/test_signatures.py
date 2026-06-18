from __future__ import annotations

import base64
import uuid
from pathlib import Path

import fitz
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, Signature

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ── PDF & image helpers ───────────────────────────────────────────────────────

def _make_test_pdf(path: Path, pages: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"Page {i + 1} — test content.", fontsize=12)
    doc.save(str(path))
    doc.close()


def _make_png_b64() -> str:
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10))
    pix.set_rect(pix.irect, (200, 200, 200))
    return base64.b64encode(pix.tobytes("png")).decode()


# ── Auth helpers ──────────────────────────────────────────────────────────────

async def _register_and_login(
    client: AsyncClient,
    email: str = "sig_admin@example.com",
) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Sig Admin", "password": "securepassword1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword1"},
    )
    return resp.json().get("access_token", "")


async def _make_pdf_doc(db: AsyncSession, owner_id: uuid.UUID) -> Document:
    from app.core.config import settings

    doc_id = uuid.uuid4()
    doc_dir = Path(settings.UPLOAD_DIR) / str(doc_id)
    doc_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = doc_dir / "original.pdf"
    _make_test_pdf(pdf_path, pages=2)

    doc = Document(
        id=doc_id,
        owner_id=owner_id,
        title="Signable PDF",
        original_name="doc.pdf",
        file_path=f"{doc_id}/original.pdf",
        file_size_bytes=pdf_path.stat().st_size,
        mime_type="application/pdf",
        status="ready",
        page_count=2,
        chunk_count=1,
    )
    db.add(doc)
    await db.flush()
    return doc


# ── Auth guards ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sign_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/sign",
        json={"signature_type": "typed", "typed_text": "Alice", "x": 100, "y": 200, "page_number": 1},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_signatures_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/documents/{uuid.uuid4()}/signatures")
    assert resp.status_code == 403


# ── Typed signature ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sign_typed_success(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/sign",
        json={
            "signature_type": "typed",
            "typed_text": "Alice Manager",
            "x": 100.0,
            "y": 700.0,
            "page_number": 1,
            "field_name": "Approver",
        },
        headers=headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["document_id"] == str(doc.id)
    assert data["signature_type"] == "typed"
    assert data["page_number"] == 1
    assert data["version_number"] == 1
    assert data["position_data"]["x"] == pytest.approx(100.0)
    assert data["field_name"] == "Approver"
    assert "task_id" not in data  # not in response schema
    assert data["signed_at"] is not None


@pytest.mark.asyncio
async def test_sign_typed_second_page(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/sign",
        json={
            "signature_type": "typed",
            "typed_text": "Bob Director",
            "x": 72.0,
            "y": 750.0,
            "page_number": 2,
        },
        headers=headers,
    )

    assert resp.status_code == 201
    assert resp.json()["page_number"] == 2


# ── Drawn signature ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sign_drawn_success(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/sign",
        json={
            "signature_type": "drawn",
            "image_base64": _make_png_b64(),
            "x": 50.0,
            "y": 750.0,
            "page_number": 1,
        },
        headers=headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["signature_type"] == "drawn"
    assert data["signature_image_path"] is not None


# ── Validation errors ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sign_typed_missing_text_rejected(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/sign",
        json={"signature_type": "typed", "x": 100, "y": 200, "page_number": 1},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sign_drawn_missing_image_rejected(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/sign",
        json={"signature_type": "drawn", "x": 100, "y": 200, "page_number": 1},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sign_invalid_page_number(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/sign",
        json={"signature_type": "typed", "typed_text": "X", "x": 100, "y": 200, "page_number": 99},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sign_coordinates_outside_page(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/sign",
        json={"signature_type": "typed", "typed_text": "X", "x": 9999, "y": 9999, "page_number": 1},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sign_negative_page_rejected_by_schema(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/sign",
        json={"signature_type": "typed", "typed_text": "X", "x": 100, "y": 200, "page_number": 0},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sign_document_not_found(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    resp = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/sign",
        json={"signature_type": "typed", "typed_text": "X", "x": 100, "y": 200, "page_number": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sign_document_not_ready(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()

    doc_id = uuid.uuid4()
    db.add(Document(
        id=doc_id, owner_id=admin.id, title="Processing",
        original_name="p.pdf", file_path=f"{doc_id}/original.pdf",
        file_size_bytes=100, mime_type="application/pdf", status="processing",
    ))
    await db.flush()

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/sign",
        json={"signature_type": "typed", "typed_text": "X", "x": 100, "y": 200, "page_number": 1},
        headers=headers,
    )
    assert resp.status_code == 409


# ── List and get signatures ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_signatures_empty(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    resp = await client.get(f"/api/v1/documents/{doc.id}/signatures", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_signatures_after_sign(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    # Sign twice
    for i in range(2):
        await client.post(
            f"/api/v1/documents/{doc.id}/sign",
            json={"signature_type": "typed", "typed_text": f"Signer {i}", "x": 100, "y": 700, "page_number": 1},
            headers=headers,
        )

    resp = await client.get(f"/api/v1/documents/{doc.id}/signatures", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_signature_success(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    sign_resp = await client.post(
        f"/api/v1/documents/{doc.id}/sign",
        json={"signature_type": "typed", "typed_text": "Detail Test", "x": 72, "y": 720, "page_number": 1},
        headers=headers,
    )
    sig_id = sign_resp.json()["id"]

    resp = await client.get(f"/api/v1/documents/{doc.id}/signatures/{sig_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sig_id
    assert data["signature_type"] == "typed"


@pytest.mark.asyncio
async def test_get_signature_not_found(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    resp = await client.get(
        f"/api/v1/documents/{doc.id}/signatures/{uuid.uuid4()}",
        headers=headers,
    )
    assert resp.status_code == 404


# ── Audit trail ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sign_creates_audit_log(client: AsyncClient, db: AsyncSession) -> None:
    from app.models.audit import AuditLog

    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    await client.post(
        f"/api/v1/documents/{doc.id}/sign",
        json={"signature_type": "typed", "typed_text": "Audit Test", "x": 100, "y": 700, "page_number": 1},
        headers=headers,
    )

    log_res = await db.execute(
        select(AuditLog).where(
            AuditLog.action == "document.sign",
            AuditLog.resource_id == doc.id,
        )
    )
    log = log_res.scalar_one_or_none()
    assert log is not None
    assert log.details["signature_type"] == "typed"
    assert log.details["page_number"] == 1
    assert "signature_id" in log.details
    assert "version_number" in log.details


# ── Original document unchanged ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sign_preserves_original_document_record(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)
    original_file_path = doc.file_path

    await client.post(
        f"/api/v1/documents/{doc.id}/sign",
        json={"signature_type": "typed", "typed_text": "Verify", "x": 100, "y": 700, "page_number": 1},
        headers=headers,
    )

    await db.refresh(doc)
    assert doc.file_path == original_file_path
    assert doc.status == "ready"


@pytest.mark.asyncio
async def test_sign_creates_version_with_signed_file(client: AsyncClient, db: AsyncSession) -> None:
    from app.models.document import DocumentVersion

    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "sig_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_pdf_doc(db, admin.id)

    sign_resp = await client.post(
        f"/api/v1/documents/{doc.id}/sign",
        json={"signature_type": "typed", "typed_text": "Version Check", "x": 100, "y": 700, "page_number": 1},
        headers=headers,
    )

    version_id = sign_resp.json()["version_id"]
    vr = await db.execute(
        select(DocumentVersion).where(DocumentVersion.id == uuid.UUID(version_id))
    )
    version = vr.scalar_one()
    assert "signed" in version.file_path
    assert version.agent_name == "signature"

    # The signed PDF file must exist on disk
    from app.utils.file_utils import resolve_upload_path
    signed_path = resolve_upload_path(version.file_path)
    assert signed_path.exists()
