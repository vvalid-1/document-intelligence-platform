# Project Status — Document Intelligence Platform

## Current Version: V1.9

**Stack:** FastAPI · Next.js 14 · PostgreSQL · ChromaDB · Ollama (qwen3:8b / qwen2.5:3b / bge-m3) · Docker Compose
**Deployment:** CPU-only · No paid APIs · Fully local

---

## Git

| Item | Value |
|---|---|
| Branch | `master` |
| Remote | `https://github.com/vvalid-1/document-intelligence-platform` |
| HEAD | `2574a42` |

### Recent Commits (newest first)

| Hash | Message |
|---|---|
| `2574a42` | feat(v1.9): Folders / Collections for document organisation |
| `8c2f426` | feat(v1.8): Favorites, Trash Bin, Bulk Actions, Dashboard stats |
| `2ef0f2d` | feat(v1.7): Archive & Restore Documents |
| `5c09c80` | docs: add PROJECT_STATUS.md with V1.6 completion status |
| `414a81e` | feat(v1.6): Global Search across all documents |
| `22d43cc` | feat(v1.5): OCR support for scanned PDFs and images (JPG/JPEG/PNG) |
| `2e8c819` | feat(v1.4): Version Comparison and Diff Viewer |

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

### V1.6 — Global Search (shipped)
- `POST /api/v1/search` — embeds query via bge-m3, queries all ChromaDB chunks (no document filter)
- Groups results by document, ranks groups by best cosine similarity
- Soft-deleted / inaccessible documents filtered via PostgreSQL post-check
- Viewer RBAC: only own documents appear in results
- No LLM call — pure vector retrieval (sub-second)
- `/search` page: large search input, example queries, grouped result cards, similarity bars, expand/collapse, loading skeleton, no-results state
- Search added to sidebar navigation
- 8 backend tests

### V1.7 — Archive & Restore (shipped)
- `POST /documents/{id}/archive` — sets `is_archived=true`, `archived_at=now()`
- `POST /documents/{id}/restore` — clears archive flags
- `GET /documents?archived=true` — archived documents list
- `GET /documents/stats` filters archived docs from active counts
- `GET /search` excludes archived documents from results
- `/archived` page: full archived library with Restore button, pagination
- Archive / Restore button in document list and document detail header
- Amber "archived" banner on document detail
- Archive event in Activity Timeline
- Migration `0004`: `is_archived`, `archived_at` columns + index
- 8 backend tests

### V1.8 — Document Management Experience (shipped)

#### Favorites / Starred Documents
- `POST /documents/{id}/favorite` — stars a document (409 if already starred)
- `POST /documents/{id}/unfavorite` — unstars a document (409 if not starred)
- `GET /documents?favorite=true` — returns only starred documents
- Star icon per row in document list (inline toggle, amber when active)
- Star toggle button in document detail header
- "Starred" filter tab on the Documents page
- `/favorites` page: full starred library with Unstar action, pagination

#### Trash Bin
- `DELETE /documents/{id}` now moves to trash (`is_deleted=true`) — no ChromaDB deletion
- ChromaDB deletion deferred to permanent delete, enabling instant restore
- `GET /documents?trashed=true` — lists documents in trash
- `POST /documents/{id}/untrash` — restores a document from trash
- `DELETE /documents/{id}/permanent` — admin-only hard delete: deletes ChromaDB vectors first, then removes document row from PostgreSQL
- `/trash` page: lists trashed docs, Restore button, "Delete forever" button (visible to all, but backend enforces admin-only)
- Audit actions: `document.trash`, `document.untrash`, `document.permanent_delete`

#### Bulk Actions
- `POST /documents/bulk/archive` — archive up to 50 documents in one call
- `POST /documents/bulk/restore` — restore archived documents
- `POST /documents/bulk/trash` — trash multiple documents
- `POST /documents/bulk/favorite` — star or unstar multiple documents (`value: bool`)
- All bulk routes registered before `/{document_id}/…` routes (prevents UUID parse conflict)
- Documents page: per-row checkboxes, select-all, floating bulk action bar (Archive / Star / Unstar / Trash / Clear)

#### Dashboard Updates
- `GET /documents/stats` now returns `favorites` (starred active docs) and `trash` (trashed docs) counts
- Dashboard shows 7 stat cards (added Starred ★ and Trash 🗑)
- All stat cards are clickable links to the relevant page

#### Infrastructure
- Migration `0005`: `is_favorite` column + index on `documents`
- `vector_service.get_document_collection` and `delete_document_chunks` imported at module level in `documents.py` (enables `patch("app.api.v1.documents.get_document_collection", …)` in tests)
- 19 new backend tests (test_favorites: 6, test_trash: 7, test_bulk: 6) — all passing

### V1.9 — Folders / Collections (shipped — current)

#### Folder Management
- `GET /api/v1/folders` — list user's folders with `doc_count` (admin sees all)
- `POST /api/v1/folders` — create folder (409 if duplicate name per user)
- `PATCH /api/v1/folders/{id}` — rename folder (409 on conflict)
- `DELETE /api/v1/folders/{id}` — delete folder; `ON DELETE SET NULL` automatically unassigns documents
- `GET /api/v1/folders/{id}/documents` — paginated documents inside a folder

#### Assign Documents to Folders
- `POST /documents/{id}/move` — move single document to folder (`folder_id: UUID | null` to remove)
- `POST /documents/bulk/move` — bulk move up to 50 documents (`folder_id: null` removes from folder)
- `GET /documents?folder_id={id}` — filter document list by folder

#### Search Integration
- `POST /search` accepts optional `folder_id` — restricts vector results to that folder's documents

#### Dashboard
- `GET /documents/stats` returns `folders` count
- Dashboard shows 8 stat cards (added Folders 📁, links to `/folders`)

#### Frontend Pages
- `/folders` — folder grid: create, rename, delete, doc count per folder
- `/folders/[id]` — documents inside a folder with "Remove from folder" action
- Documents page: folder filter dropdown, folder badge per row, per-row move-to-folder select, bulk move in bulk bar
- Document detail: folder badge + move-to-folder select in Document Info
- Search page: optional folder filter dropdown
- Sidebar: Folders (📁) nav item

#### Infrastructure
- Alembic migration `0006`: `folders` table + `folder_id` on `documents` (FK with `ON DELETE SET NULL`)
- Unique constraint: `(owner_id, name)` prevents duplicate folder names per user
- `backend/app/models/folder.py` — SQLAlchemy 2.0 async model
- `backend/app/schemas/folder.py` — Pydantic v2 schemas (`FolderCreateRequest`, `FolderRenameRequest`, `FolderResponse`, `FolderListResponse`)
- `frontend/src/lib/api/folders.ts` — API client (`listFolders`, `createFolder`, `renameFolder`, `deleteFolder`, `listFolderDocuments`)
- `apiPatch` helper added to `frontend/src/lib/api/client.ts`
- 8 new backend tests (`test_folders.py`) — all passing; full suite **219/219 passing**
- Frontend build: clean (`✓ Ready in 313ms`, no TypeScript errors)

---

## API Surface (v1)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/auth/register` | First user → admin |
| POST | `/api/v1/auth/login` | Returns JWT |
| POST | `/api/v1/auth/sse-token` | Short-lived SSE ticket |
| GET | `/api/v1/documents` | List documents (`archived`, `favorite`, `trashed`, `folder_id` filters) |
| POST | `/api/v1/documents` | Upload document (202) |
| GET | `/api/v1/documents/stats` | Dashboard counts (total, ready, reviews, edits, signatures, favorites, trash, folders) |
| POST | `/api/v1/documents/bulk/archive` | Bulk archive (≤50 docs) |
| POST | `/api/v1/documents/bulk/restore` | Bulk restore archived |
| POST | `/api/v1/documents/bulk/trash` | Bulk move to trash |
| POST | `/api/v1/documents/bulk/favorite` | Bulk star/unstar |
| POST | `/api/v1/documents/bulk/move` | Bulk move to folder |
| GET | `/api/v1/documents/{id}` | Document detail |
| PATCH | `/api/v1/documents/{id}` | Rename |
| DELETE | `/api/v1/documents/{id}` | Move to trash |
| DELETE | `/api/v1/documents/{id}/permanent` | Hard delete (admin only) |
| POST | `/api/v1/documents/{id}/archive` | Archive |
| POST | `/api/v1/documents/{id}/restore` | Restore from archive |
| POST | `/api/v1/documents/{id}/favorite` | Star |
| POST | `/api/v1/documents/{id}/unfavorite` | Unstar |
| POST | `/api/v1/documents/{id}/untrash` | Restore from trash |
| POST | `/api/v1/documents/{id}/move` | Move to folder (`folder_id: null` removes) |
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
| GET | `/api/v1/folders` | List folders with doc counts |
| POST | `/api/v1/folders` | Create folder |
| PATCH | `/api/v1/folders/{id}` | Rename folder |
| DELETE | `/api/v1/folders/{id}` | Delete folder (204) |
| GET | `/api/v1/folders/{id}/documents` | Documents inside folder |
| POST | `/api/v1/search` | Global search (`folder_id` filter optional) |
| GET | `/api/v1/admin/users` | List all users |
| PATCH | `/api/v1/admin/users/{id}` | Update role/status |
| DELETE | `/api/v1/admin/users/{id}` | Hard delete user |

---

## Frontend Pages

| Route | Purpose |
|---|---|
| `/login` | Auth |
| `/dashboard` | Stats overview (8 clickable stat cards) |
| `/documents` | Document library (checkboxes, bulk bar, star toggle, folder filter + badge + move, Starred tab) |
| `/documents/upload` | Upload (PDF/DOCX/TXT/JPG/PNG) |
| `/documents/[id]` | Document detail, versions, actions, star + archive + folder move |
| `/documents/[id]/chat` | RAG chat |
| `/documents/[id]/review` | AI review |
| `/documents/[id]/edit` | Natural language edit |
| `/documents/[id]/translate` | Translation (EN/FR/AR) |
| `/documents/[id]/sign` | Signature |
| `/documents/[id]/compare` | Diff viewer |
| `/search` | Global search (optional folder filter) |
| `/folders` | Folder grid (create, rename, delete, doc count) |
| `/folders/[id]` | Documents inside a folder |
| `/archived` | Archived documents library |
| `/favorites` | Starred documents library |
| `/trash` | Trash bin (Restore + Delete forever) |

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
| `test_archive.py` | archive/restore, list filter, search exclusion, 8 tests | |
| `test_favorites.py` | star/unstar, 409 guard, filter, stats, 6 tests | |
| `test_trash.py` | trash/untrash, permanent delete, stats, 404 path, 7 tests | |
| `test_bulk.py` | bulk archive/restore/trash/favorite, empty body guard, 6 tests | |
| `test_folders.py` | create, duplicate 409, list with count, rename, delete unassigns, move, filter, bulk move, 8 tests | |

**Full suite: 219/219 passing. Frontend build: clean (no TypeScript errors).**

---

## Known Issues

| Issue | Severity | Notes |
|---|---|---|
| SQLAlchemy asyncpg pool cleanup warnings in tests | Low | Pre-existing noise from pytest-asyncio 0.24 teardown race; tests pass cleanly |
| Only `tesseract-ocr-eng` was installed before V1.5 | Fixed | FR + AR packs added in V1.5 Dockerfile |
| Chat/Review/Edit model was `qwen3:8b` (slow on CPU) | Fixed | Switched to `qwen2.5:3b` — faster on CPU-only |
| Translation `chk_agent_name` constraint | Fixed | Migration `0003` + model updated in V1.3 |
| Backend has no dev bind mount | Known | Every code change requires `docker compose build backend && up -d backend` |
| Docker Desktop Windows bind mount lag | Known | File changes don't sync into running container immediately; use `docker cp` for hot-fix or rebuild |
| No rate limiting on `/search` endpoint | Low | Rate limiting exists on other endpoints (slowapi); search should be added before production |
| `Alembic script.py.mako` missing in container | Known | Write migrations manually on host; they bake in at build time |
| Trash page "Delete forever" visible to all roles | Low | Backend enforces admin-only (403 for non-admin); UI does not hide the button for non-admins |

---

## Pending Features (not yet started)

| ID | Feature | Notes |
|---|---|---|
| V2.0 | Report Generator | Auto-generate structured PDF report from one or more documents |
| — | Rate limiting on `/search` | Add slowapi limiter (e.g. 20 req/min per user) to `POST /api/v1/search` |
| — | Search pagination | Add `offset` / `page` to `SearchRequest` and `SearchResponse` |
| — | Viewer role UI | Currently no viewer-specific UI restrictions |
| — | Document sharing | Share read-only link without login |
| — | Webhook / notification | Notify when async processing completes |
| — | Hide "Delete forever" for non-admins | Front-end role check on Trash page |

---

## V1.9 Status: COMPLETE

All deliverables shipped and committed (`2574a42`):

- [x] Alembic migration `0006` — `folders` table + `folder_id` on `documents` (ON DELETE SET NULL)
- [x] `backend/app/models/folder.py` — Folder ORM model
- [x] `backend/app/schemas/folder.py` — Pydantic v2 schemas
- [x] `backend/app/api/v1/folders.py` — full CRUD router (list, create, rename, delete, list-docs)
- [x] `backend/app/api/router.py` — `folders.router` registered
- [x] `POST /documents/{id}/move` and `POST /documents/bulk/move` endpoints
- [x] `GET /documents?folder_id=` filter
- [x] `POST /search` `folder_id` filter
- [x] `GET /documents/stats` returns `folders` count
- [x] `backend/tests/api/test_folders.py` — 8/8 passing
- [x] Full backend suite — 219/219 passing
- [x] `frontend/src/types/api.ts` — `FolderResponse`, `FolderListResponse`, `folder_id` on `DocumentResponse`, `folders` on stats
- [x] `frontend/src/lib/api/folders.ts` — folder API client
- [x] `frontend/src/lib/api/client.ts` — `apiPatch` added
- [x] `frontend/src/lib/api/documents.ts` — `moveDocument`, `bulkMove`, `folder_id` filter
- [x] `frontend/src/lib/api/search.ts` — `folderId` param
- [x] `/folders` page — folder grid with create, rename, delete, doc count
- [x] `/folders/[id]` page — documents inside folder with Remove action
- [x] `/documents` page — folder filter dropdown, folder badge, move select, bulk move
- [x] `/documents/[id]` page — folder badge + move select in Document Info
- [x] `/search` page — optional folder filter dropdown
- [x] `/dashboard` — 8 stat cards (added Folders 📁)
- [x] Sidebar — Folders (📁) nav item
- [x] Frontend Docker rebuild: `✓ Ready in 313ms` (no TypeScript errors)
- [x] Pushed to `origin/master`
