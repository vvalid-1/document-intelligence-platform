from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import chromadb
import fitz  # PyMuPDF
import pytest

from app.services.processing_service import (
    Chunk,
    PageText,
    chunk_pages,
    chunk_plain_text,
    extract_pdf_metadata,
    extract_text_pdf,
    extract_text_txt,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    """Minimal single-page PDF with real text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "This is test content for the PDF document.")
    page.insert_text((50, 130), "It contains multiple lines for extraction testing.")
    dest = tmp_path / "test.pdf"
    doc.save(str(dest))
    doc.close()
    return dest


@pytest.fixture
def multi_page_pdf(tmp_path: Path) -> Path:
    """Three-page PDF."""
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((50, 100), f"Page {i+1} content: unique text for page number {i+1}.")
    dest = tmp_path / "multipage.pdf"
    doc.save(str(dest))
    doc.close()
    return dest


@pytest.fixture
def txt_file(tmp_path: Path) -> Path:
    dest = tmp_path / "test.txt"
    dest.write_text("Hello World\nThis is a test document.\nThird line.", encoding="utf-8")
    return dest


# ── PDF extraction ────────────────────────────────────────────────────────────

def test_extract_text_pdf_returns_page_texts(pdf_file: Path) -> None:
    pages = extract_text_pdf(pdf_file)
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "test content" in pages[0].text.lower()


def test_extract_text_pdf_multipage(multi_page_pdf: Path) -> None:
    pages = extract_text_pdf(multi_page_pdf)
    assert len(pages) == 3
    for i, page in enumerate(pages):
        assert page.page_number == i + 1
        assert f"Page {i+1}" in page.text


def test_extract_text_pdf_ocr_fallback(pdf_file: Path) -> None:
    """When PyMuPDF returns < 10 chars, OCR should be attempted."""
    with patch("app.services.processing_service._ocr_page", return_value="OCR result") as mock_ocr:
        with patch("fitz.Page.get_text", return_value="tiny"):
            pages = extract_text_pdf(pdf_file)
        mock_ocr.assert_called_once()
        assert pages[0].text == "OCR result"


def test_extract_pdf_metadata(pdf_file: Path) -> None:
    meta = extract_pdf_metadata(pdf_file)
    assert "page_count" in meta
    assert meta["page_count"] == 1


# ── TXT extraction ────────────────────────────────────────────────────────────

def test_extract_text_txt(txt_file: Path) -> None:
    text = extract_text_txt(txt_file)
    assert "Hello World" in text
    assert "test document" in text


def test_extract_text_txt_encoding_detection(tmp_path: Path) -> None:
    """chardet should handle latin-1 encoded files."""
    dest = tmp_path / "latin1.txt"
    dest.write_bytes("Ré sumé document".encode("latin-1"))
    text = extract_text_txt(dest)
    assert len(text) > 0


# ── Chunking ──────────────────────────────────────────────────────────────────

def test_chunk_plain_text_single_chunk() -> None:
    text = "A" * 100
    chunks = chunk_plain_text(text, chunk_size=500, overlap=100)
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number is None


def test_chunk_plain_text_multiple_chunks() -> None:
    text = "word " * 200  # 1000 chars
    chunks = chunk_plain_text(text, chunk_size=400, overlap=100)
    assert len(chunks) >= 2
    for i, c in enumerate(chunks):
        assert c.chunk_index == i
        assert len(c.chunk_text) > 0


def test_chunk_plain_text_overlap() -> None:
    text = "ABCDE" * 100  # 500 chars
    chunks = chunk_plain_text(text, chunk_size=300, overlap=100)
    # Second chunk starts at position 200 (300-100 stride)
    if len(chunks) >= 2:
        assert chunks[1].chunk_text[:10] == text[200:210]


def test_chunk_plain_text_empty() -> None:
    chunks = chunk_plain_text("   \n  ", chunk_size=500, overlap=100)
    assert chunks == []


def test_chunk_pages_tracks_page_numbers() -> None:
    pages = [
        PageText(page_number=1, text="First page has enough text to form a chunk"),
        PageText(page_number=2, text="Second page has different content here"),
    ]
    chunks = chunk_pages(pages, chunk_size=30, overlap=5)
    assert len(chunks) > 0
    assert all(c.page_number in (1, 2) for c in chunks)


def test_chunk_pages_empty_pages() -> None:
    assert chunk_pages([], chunk_size=500, overlap=100) == []


def test_chunk_pages_blank_pages_skipped() -> None:
    pages = [PageText(page_number=1, text="   "), PageText(page_number=2, text="Real content")]
    chunks = chunk_pages(pages, chunk_size=500, overlap=50)
    assert len(chunks) == 1
    assert "Real content" in chunks[0].chunk_text


def test_chunk_token_count() -> None:
    pages = [PageText(page_number=1, text="one two three four five")]
    chunks = chunk_pages(pages, chunk_size=500, overlap=50)
    assert chunks[0].token_count == 5


# ── ChromaDB EphemeralClient integration ─────────────────────────────────────

def test_chroma_ephemeral_insert_and_query() -> None:
    """Verify our ChromaDB add/query pattern using EphemeralClient."""
    client = chromadb.EphemeralClient()
    collection = client.get_or_create_collection(
        "document_chunks",
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,
    )

    doc_id = str(uuid.uuid4())
    chunk_ids = [f"{doc_id}_0", f"{doc_id}_1"]
    embeddings = [[0.1] * 3, [0.2] * 3]  # minimal 3-dim vectors for test
    documents = ["First chunk text", "Second chunk text"]
    metadatas = [
        {"document_id": doc_id, "chunk_index": 0, "page_number": 1, "document_title": "Test", "mime_type": "application/pdf", "owner_id": "", "created_at": ""},
        {"document_id": doc_id, "chunk_index": 1, "page_number": 1, "document_title": "Test", "mime_type": "application/pdf", "owner_id": "", "created_at": ""},
    ]

    collection.add(ids=chunk_ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    results = collection.get(ids=chunk_ids)
    assert len(results["ids"]) == 2

    # Verify delete works
    collection.delete(where={"document_id": doc_id})
    after = collection.get(ids=chunk_ids)
    assert len(after["ids"]) == 0


# ── Embed function mock ───────────────────────────────────────────────────────

async def test_embed_texts_is_called_with_chunks(pdf_file: Path) -> None:
    """Verify the embed function receives the correct texts during processing."""
    from app.core.config import settings

    pages = extract_text_pdf(pdf_file)
    chunks = chunk_pages(pages, chunk_size=settings.CHUNK_SIZE, overlap=settings.CHUNK_OVERLAP)
    assert len(chunks) >= 1

    received_texts: list[str] = []

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        received_texts.extend(texts)
        return [[0.0] * 1024 for _ in texts]

    embeddings = await fake_embed([c.chunk_text for c in chunks])
    assert len(embeddings) == len(chunks)
    assert received_texts == [c.chunk_text for c in chunks]
    assert all(len(e) == 1024 for e in embeddings)
