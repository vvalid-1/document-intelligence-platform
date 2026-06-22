# Project Status — Document Intelligence Platform

## Current Version: V1.6

**Stack:** FastAPI · Next.js 14 · PostgreSQL · ChromaDB · Ollama (qwen3:8b / qwen2.5:3b / bge-m3) · Docker Compose
**Deployment:** CPU-only · No paid APIs · Fully local

---

## Git

| Item | Value |
|---|---|
| Branch | `master` |
| Remote | `https://github.com/vvalid-1/document-intelligence-platform` |
| HEAD | `414a81e` |

### Recent Commits (newest first)

| Hash | Message |
|---|---|
| `414a81e` | feat(v1.6): Global Search across all documents |
| `22d43cc` | feat(v1.5): OCR support for scanned PDFs and images (JPG/JPEG/PNG) |
| `2e8c819` | feat(v1.4): Version Comparison and Diff Viewer |
| `d24e8e8` | feat(v1.3): Translation Agent — EN/FR/AR document translation |
| `c61ab6a` | feat: dashboard stats (F3) + dark mode (F4) |
| `48175df` | feat: V1.2 — canvas signature pad + modern UI upgrade |
| `f0f8d3e` | feat: V1.1 UX Upgrade — PDF viewer, chat history, workspace, timeline, greeting |

---

## Completed Features

### V1.0 — Core Platform (shipped)
- User registration and login (JWT auth, bcrypt passwords)
- Document upload: PDF, DOCX, TXT (50 MB limit, magic byte validation)
- Async background processing: extract → chunk → embed → ChromaDB + PostgreSQL
- RAG-based Chat: per-document Q&A with source citations via SSE streaming
- AI Review: automated quality review with scored issues
- AI Edit: natural language editing with version history
- Electronic Signature: typed and drawn (canvas) signatures embedded in PDF
- Soft delete, audit logging, RBAC (admin / editor / viewer)
- SSE auth via ticket (no JWT in URL params)
- Admin panel: user management, hard delete

### V1.1 — UX Upgrade (shipped)
- Inline PDF viewer (PdfPreview component, pdf.js)
- Chat history sidebar with session management
- Document workspace layout
- Activity timeline on document detail page
- Greeting with user's first name on dashboard

### V1.2 — UI Polish + Draw Signature (shipped)
- Canvas-based draw signature (SignatureCanvas component — 124 lines)
- Modern Card, Button, Badge UI components
- Dark mode toggle (persisted to localStorage)
- Dashboard statistics panel

### V1.3 — Translation Agent (shipped)
- EN / FR / AR translation via `qwen2.5:3b` (separate from chat model)
- `POST /documents/{id}/translate` — creates a `DocumentVersion(agent_name="translator")`
- `/documents/{id}/translate` page: language selector, PDF preview, download PDF/TXT
- Arabic RTL text support in preview
- 9 backend tests

### V1.4 — Version Comparison and Diff Viewer (shipped)
- `GET /documents/{id}/text` — returns full text from indexed chunks
- Pure TypeScript LCS diff engine (`lib/diff.ts`) — capped at 3 000 lines, O(N²) bounded
- `/documents/{id}/compare?a=original&b={versionId}` page
- Side-by-side view with synchronized proportional scroll
- Unified diff view with dual line numbers
- Stat chips: +added / −removed / equal lines
- Compare link next to each editor/translator version in document detail

### V1.5 — OCR Support (shipped)
- Scanned PDF pages: already handled by PyMuPDF + pytesseract auto-detect (< 10 chars → OCR)
- New image formats: JPG, JPEG, PNG — magic byte validated, OCR-extracted, chunked, embedded
- `extract_text_image()` in `processing_service.py`
- `processing_step="ocr"` banner: "Running OCR to extract text from image…"
- Tesseract French + Arabic language packs added to Dockerfile
- Upload page accepts image files; Document info shows `image/jpeg` / `image/png`
- 9 backend tests

### V1.6 — Global Search (shipped — current)
- `POST /api/v1/search` — embeds query via bge-m3, queries all ChromaDB chunks (no document filter)
- Groups results by document, ranks groups by best cosine similarity
- Soft-deleted / inaccessible documents filtered via PostgreSQL post-check
- Viewer RBAC: only own documents appear in results
- No LLM call — pure vector retrieval (sub-second)
- `/search` page: large search input, example queries, grouped result cards, similarity bars, expand/collapse, loading skeleton, no-results state
- Search added to sidebar navigation
- 8 backend tests

---

## API Surface (v1)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/auth/register` | First user → admin |
| POST | `/api/v1/auth/login` | Returns JWT |
| POST | `/api/v1/auth/sse-token` | Short-lived SSE ticket |
| GET | `/api/v1/documents` | List documents (paginated) |
| POST | `/api/v1/documents` | Upload document (202) |
| GET | `/api/v1/documents/stats` | Dashboard counts |
| GET | `/api/v1/documents/{id}` | Document detail |
| PATCH | `/api/v1/documents/{id}` | Rename |
| DELETE | `/api/v1/documents/{id}` | Soft delete |
| GET | `/api/v1/documents/{id}/text` | Full extracted text |
| GET | `/api/v1/documents/{id}/status` | Processing status |
| GET | `/api/v1/documents/{id}/status/stream` | SSE processing stream |
| GET | `/api/v1/documents/{id}/versions` | Version list |
| GET | `/api/v1/documents/{id}/versions/{vid}/download` | Download PDF/TXT |
| POST | `/api/v1/documents/{id}/chat` | RAG Q&A (SSE) |
| POST | `/api/v1/documents/{id}/review` | AI review |
| POST | `/api/v1/documents/{id}/edit` | AI edit |
| POST | `/api/v1/documents/{id}/translate` | Translate (EN/FR/AR) |
| POST | `/api/v1/documents/{id}/sign` | Add signature |
| GET | `/api/v1/documents/{id}/signatures` | List signatures |
| POST | `/api/v1/search` | Global cross-document search |
| GET | `/api/v1/admin/users` | List all users |
| PATCH | `/api/v1/admin/users/{id}` | Update role/status |
| DELETE | `/api/v1/admin/users/{id}` | Hard delete user |

---

## Frontend Pages

| Route | Purpose |
|---|---|
| `/login` | Auth |
| `/dashboard` | Stats overview |
| `/documents` | Document library |
| `/documents/upload` | Upload (PDF/DOCX/TXT/JPG/PNG) |
| `/documents/[id]` | Document detail, versions, actions |
| `/documents/[id]/chat` | RAG chat |
| `/documents/[id]/review` | AI review |
| `/documents/[id]/edit` | Natural language edit |
| `/documents/[id]/translate` | Translation (EN/FR/AR) |
| `/documents/[id]/sign` | Signature |
| `/documents/[id]/compare` | Diff viewer |
| `/search` | Global search |

---

## Backend Test Suite

| File | Tests | Coverage |
|---|---|---|
| `test_auth.py` | auth flow, JWT, registration guard | |
| `test_documents.py` | upload validation, magic bytes | |
| `test_chat.py` | session creation, message flow | |
| `test_reviews.py` | review creation, auth guards | |
| `test_edits.py` | edit creation, version creation | |
| `test_signatures.py` | typed + drawn signatures | |
| `test_translations.py` | FR/AR translation, 9 tests | |
| `test_ocr.py` | PNG/JPEG upload, magic bytes, extract fn, 9 tests | |
| `test_search.py` | grouping, RBAC, deleted doc filter, 503 path, 8 tests | |

---

## Known Issues

| Issue | Severity | Notes |
|---|---|---|
| SQLAlchemy asyncpg pool cleanup warnings in tests | Low | Pre-existing noise from pytest-asyncio 0.24 teardown race; tests pass cleanly |
| Only `tesseract-ocr-eng` was installed before V1.5 | Fixed | FR + AR packs added in V1.5 Dockerfile |
| Chat/Review/Edit model was `qwen3:8b` (slow on CPU) | Fixed | Switched to `qwen2.5:3b` — faster on CPU-only |
| Translation `chk_agent_name` constraint | Fixed | Migration `0003` + model updated in V1.3 |
| Backend has no dev bind mount | Known | Every code change requires `docker compose build backend && up -d backend` |
| No rate limiting on `/search` endpoint | Low | Rate limiting exists on other endpoints (slowapi); search should be added before production |
| `Alembic script.py.mako` missing in container | Known | Write migrations manually on host; they bake in at build time |

---

## Pending Features (not yet started)

| ID | Feature | Notes |
|---|---|---|
| V1.7 | Report Generator | Auto-generate summary reports from documents |
| V1.8 | Batch Operations | Select multiple documents for bulk translate/review |
| — | Rate limiting on `/search` | Add slowapi limiter to global search endpoint |
| — | Search pagination | Currently returns top 20; add cursor/page support |
| — | Viewer role UI | Currently no viewer-specific UI restrictions |
| — | Document sharing | Share read-only link without login |
| — | Webhook / notification | Notify when async processing completes |

---

## V1.6 Status: COMPLETE

All deliverables shipped and committed:

- [x] `POST /api/v1/search` endpoint — groups by document, RBAC, no LLM
- [x] `backend/app/schemas/search.py` — `SearchRequest`, `SearchGroup`, `SearchResponse`
- [x] `backend/app/api/v1/search.py` — full implementation
- [x] `backend/tests/api/test_search.py` — 8/8 passing
- [x] `frontend/src/lib/api/search.ts` — API client
- [x] `frontend/src/types/api.ts` — `SearchHit`, `SearchGroup`, `SearchResponse` types
- [x] `frontend/src/app/(app)/search/page.tsx` — full search UI
- [x] `frontend/src/components/layout/Sidebar.tsx` — Search nav item added
- [x] Frontend Docker build: `✓ Compiled successfully`
- [x] Committed: `414a81e` — pushed to `origin/master`

---

## Next Recommended Tasks

1. **V1.7 — Report Generator**: Auto-generate a structured PDF report from one or multiple documents (executive summary, key findings, recommendations). Reuses RAG pipeline + editor-style PDF output.

2. **Rate-limit `/search`**: Add `slowapi` limiter (e.g. 20 req/min per user) to `POST /api/v1/search` — currently unprotected against abuse.

3. **Search pagination**: Add `offset` / `page` to `SearchRequest` and `SearchResponse` so large result sets can be paginated.

4. **Run full test suite**: `docker compose exec backend pytest -v` — confirm all 9 test files pass together before next feature.

5. **Ollama model check**: Verify `qwen2.5:3b` and `bge-m3` are still loaded in the Ollama container (`docker compose exec ollama ollama list`).
