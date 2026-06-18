# Implementation Plan — Document Intelligence Platform

## Guiding Principles

1. **Vertical slices over horizontal layers** — deliver working features end-to-end, not half a backend then half a frontend
2. **Infrastructure first** — Docker, DB, and LLM connectivity must work before any feature code
3. **Core before smart** — documents must upload and store before agents touch them
4. **Test as you go** — write tests for each phase before moving to the next
5. **Never break the health check** — `/health` endpoint must stay green throughout

---

## Phase 0 — Infrastructure (Days 1–2)

**Goal:** All Docker services running, connected, and healthy. Nginx in place from day one.

### Steps

1. Create project directory structure (all folders as specified in ARCHITECTURE.md)
2. Write `docker-compose.yml` with **six** services:
   - `nginx` (nginx:alpine) — required, not optional; routes `/` → frontend, `/api` → backend; SSE config (proxy_buffering off, proxy_read_timeout 600s)
   - `postgres` (postgres:16-alpine) with healthcheck, `mem_limit: 512m`
   - `chromadb` (chromadb/chroma:latest) with persistent volume, `mem_limit: 1g`
   - `ollama` (ollama/ollama:latest) with `mem_limit: 12g`; no GPU config (CPU-only)
   - `backend` (custom Dockerfile, Python 3.11-slim) — placeholder for now
   - `frontend` (custom Dockerfile, node:20-alpine) — placeholder for now
3. Add `deploy.resources.limits.memory` for each service to prevent OOM cascades
4. Write Ollama startup entrypoint script:
   - Pull `qwen3:8b` on first run (`ollama pull qwen3:8b`)
   - Pull `bge-m3` on first run (`ollama pull bge-m3`)
   - Only pull if not already present (check via `ollama list`)
5. Write `docker-compose.dev.yml` with bind mount overrides for backend and frontend hot reload
6. Create `.env.example` with ALL required variables (including `AGENT_TIMEOUT_SECONDS=300`, `MAX_CHAT_MESSAGE_CHARS=8000`, `OLLAMA_NUM_CTX=4096`)
7. Create `.dockerignore` for backend (`__pycache__`, `.venv`, `tests/`, `.pytest_cache`)
8. Create `.dockerignore` for frontend (`node_modules`, `.next`, `*.test.ts`, `*.spec.ts`)
9. Create placeholder FastAPI app with just `GET /health` (returns 200)
10. Verify: `docker compose up -d` → all containers healthy → Nginx on :80 → `curl localhost/health` returns 200

**Deliverable:** A running 6-service infra stack with Nginx, resource limits, and a passing health check.

---

## Phase 1 — Backend Authentication & Core API (Days 3–5)

**Goal:** A working auth system, document CRUD, SSE tokens, and rate limiting — all from day one.

### Steps

1. Install: FastAPI, SQLAlchemy 2.0 async, Alembic, pydantic-settings, bcrypt, python-jose, slowapi, sse-starlette
2. Set up `core/config.py` (pydantic-settings from .env; pool_size=10, max_overflow=20 for SQLAlchemy)
3. Set up `core/database.py` (async engine + session factory with connection pool config)
4. Initialize Alembic; write initial migration for ALL tables from DATABASE_SCHEMA.md in the documented creation order (users → user_invitations → refresh_tokens → sse_tokens → documents → ... → deferred FKs)
5. Implement `core/security.py` (bcrypt cost=12, JWT encode/decode)
6. Build auth routes: `/auth/register` (first-user-only), `/auth/invite/accept`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`, `/auth/me/password`, `/auth/sse-token`
7. Implement SSE token validation dependency (single-use, marks `used=TRUE` atomically)
8. Apply slowapi rate limiting on auth endpoints: 10/min/IP on login
9. Build RBAC dependency (`get_current_user`, `require_role`)
10. Build document routes: upload (with magic byte validation + extension sanitization), list, detail, patch, soft-delete, download, version list, version download
11. Wire audit logging into all document and auth operations
12. Write tests: auth flows including first-user, invitation accept, SSE token; document upload with magic byte rejection

**Deliverable:** Working auth + document CRUD + SSE tokens + rate limiting, with tests passing.

---

## Phase 2 — Document Processing Pipeline (Days 6–8)

**Goal:** Uploaded PDFs/DOCX/TXT are extracted (with OCR fallback), chunked, embedded, and searchable.

### Steps

1. Add to Dockerfile: `RUN apt-get install -y tesseract-ocr tesseract-ocr-eng poppler-utils`
2. Install Python packages: PyMuPDF (fitz), pypdf, python-docx, pytesseract, chardet, Pillow
3. Implement `services/processing_service.py`:
   - `extract_text_pdf(path) → List[PageText]` — PyMuPDF per page; detect if page is image-only → Tesseract OCR
   - `extract_text_docx(path) → str` — python-docx paragraphs + tables
   - `extract_text_txt(path) → str` — chardet detect encoding → read
   - `extract_metadata(path, mime_type) → dict` — pypdf for PDFs
   - `chunk_text(pages, chunk_size, overlap) → List[Chunk]` — configurable, overlap 20%
4. Implement `services/vector_service.py`:
   - ChromaDB client setup with persistent storage
   - `get_or_create_collection(name)`
   - `embed_chunks(texts) → List[float[]]` — POST to Ollama `/api/embed` with bge-m3
   - `insert_chunks(chunks, embeddings, metadata)`
   - `delete_document_chunks(document_id)`
5. Wire `process_document()` into FastAPI `BackgroundTasks` on upload
6. Implement startup recovery in FastAPI lifespan:
   - On startup, query all documents where `status = 'processing'`
   - Re-queue each as a new `BackgroundTask` — handles restart-mid-processing scenario
7. Implement `GET /documents/{id}/status` for polling (includes `progress_step`, `chunk_count`)
8. Implement `GET /documents/{id}/status/stream` as SSE stream (SSE-token-authenticated; yields step events)
9. Add `document_chunks` table and migration (with GIN FTS index on `chunk_text`)
10. Write processing tests (mock Ollama embed, use ChromaDB `EphemeralClient`, mock pytesseract)

**Deliverable:** Uploads trigger async processing; chunks land in ChromaDB; restart recovery works.

---

## Phase 3 — Agent Framework & Base Agents (Days 9–13)

**Goal:** All five agents working, invocable via API.

### 3.1 Base Framework (Day 9)

1. Implement Ollama model readiness check:
   - `await wait_for_models(required=["qwen3:8b","bge-m3"])` — called in FastAPI lifespan startup
   - Polls `GET /api/tags` every 5s; raises `RuntimeError` after 300s
   - `GET /health` returns `"status":"degraded"` during loading
2. Write `OllamaClient` wrapper:
   - `chat(messages, tools=None) → dict` — blocking; wraps in `asyncio.wait_for(timeout=AGENT_TIMEOUT_SECONDS)`
   - `stream_chat(messages) → AsyncGenerator[str, None]` — yields tokens; respects timeout
   - `embed(texts: List[str]) → List[List[float]]` — batch embed with retry
   - Retry: 3 attempts, exponential backoff; log model-not-loaded errors specifically
   - CPU tuning: pass `num_ctx`, `num_thread`, `num_predict` from env config
3. Implement context window guard:
   - `count_tokens(text) → int` (approximate: chars / 3.5 for English)
   - If prompt exceeds `OLLAMA_NUM_CTX * 0.85`: truncate + append `[TRUNCATED — document exceeds context window]`
4. Create ORM models: `AgentSession`, `AgentMessage` (role CHECK, sequence_num), `AgentTask` (timed_out column)
5. Write `BaseAgent` class with timeout enforcement:
   ```
   - async run(task) → AgentResult  (calls _call_ollama; timeout enforced)
   - async stream_run(task) → AsyncGenerator  (streams tokens; timeout enforced)
   - async _call_ollama(messages, tools=None) → dict  (JSON fallback on malformed tool call)
   - async _stream_ollama(messages) → AsyncGenerator
   - async _parse_tool_calls(response) → List[ToolCall]  (retry with JSON prompt on failure)
   - async _persist_task(task, result, duration_ms)
   ```
6. Create `TaskPayload` and `AgentResult` dataclasses
7. Create `sse_event(event: str, data: dict) → str` helper
8. Create `AgentMessageService` with:
   - `append_message(session_id, role, content)` — increments sequence_num atomically
   - `get_context_window(session_id, max_tokens) → List[Message]` — loads recent turns; truncates to stay under `OLLAMA_NUM_CTX * 0.85`
9. Implement per-agent overflow strategies:
   - **RAG Agent**: top-k chunks only; no sliding window needed
   - **Reviewer Agent**: sliding 3000-token windows over document; aggregate issues across windows
   - **Editor Agent**: first `NUM_CTX * 0.75` tokens of document text; append `[TRUNCATED]` warning note
10. Write system prompt loader from `agents/prompts/*.txt`

### 3.2 Orchestrator Agent (Day 10)

1. Write system prompt: intent classification + task planning
2. Implement `OrchestratorAgent.run()`:
   - Parse user message → intent + target documents
   - Select appropriate specialist agent(s)
   - Delegate and await results
   - Aggregate + format final response
3. Create session endpoints (`POST /agents/sessions`, `POST /agents/sessions/{id}/chat`)

### 3.3 Search & RAG Agent (Day 10)

1. Write system prompt: context-aware Q&A
2. Implement `SearchRAGAgent.run()`:
   - Embed query via Ollama
   - Query ChromaDB top-k
   - Build RAG prompt
   - Generate answer with citations
3. Wire into `POST /search` and `POST /search/ask`

### 3.4 Reviewer Agent (Day 11)

1. Write system prompt: document quality analyst
2. Implement `ReviewerAgent.run()`:
   - Get document text from DB
   - Send to LLM with review prompt
   - Parse structured issues list from response
   - Persist to `document_reviews`
3. Wire into `POST /agents/review/{document_id}`

### 3.5 Editor Agent (Day 12)

1. Write system prompts per operation (summarize, paraphrase, expand, fix_grammar, translate)
2. Implement `EditorAgent.stream_run()`:
   - Get document text
   - Stream LLM output token by token via `_stream_ollama()`
   - Accumulate full text when stream ends
3. Implement output_mode branching:
   - `text` mode: return accumulated text (no file written)
   - `pdf` mode: write edited text to new PDF using ReportLab (`reportlab` package) + create `document_version`
4. Wire SSE stream into `GET /agents/edit/{task_id}/stream` (FastAPI `StreamingResponse`)
5. Wire into `POST /agents/edit/{document_id}`
6. Implement async task polling: `GET /agents/tasks/{task_id}`

### 3.6 Signature Assistant Agent (Day 13)

1. Implement PDF signature field detection (PyMuPDF AcroForm parsing)
2. Implement typed signature rendering (Pillow: text → PNG)
3. Implement drawn signature acceptance (base64 PNG → file)
4. Implement signature embedding into PDF (PyMuPDF overlay)
5. Write system prompt: guides user through field completion
6. Create `Signature` ORM model + migration
7. Wire all signature API endpoints

**Deliverable:** All agents operational; agent API fully functional.

---

## Phase 4 — Frontend (Days 14–20)

**Goal:** Full working UI for all features.

### 4.1 Setup (Day 14)

1. `npx create-next-app@latest frontend --typescript --tailwind --app`
2. Install shadcn/ui: `npx shadcn-ui@latest init`
3. Install: Zustand, react-hook-form, zod, @tanstack/react-query
4. Create `lib/api/client.ts` — typed fetch wrapper with auto token refresh (access token in memory; refresh token in HttpOnly cookie via fetch with `credentials: include`)
5. Create `lib/hooks/useSSE.ts` — SSE client hook with SSE token flow:
   - Before opening `EventSource`: call `POST /auth/sse-token` to get short-lived token
   - Open `new EventSource(url + '?token=' + sseToken)`
   - Handles reconnection: fetch new SSE token on each reconnect attempt
   - Returns `{ events, status, error }` where status = 'connecting' | 'open' | 'closed' | 'error'
6. Create auth store (Zustand) with login/logout/token refresh; access token in memory only (never localStorage)
7. Create layout components: Sidebar, Navbar, PageWrapper

### 4.2 Auth Pages (Day 14)

1. Login page (`/login`) — form, validation, redirect on success
2. Register page (`/register`) — form, validation (only usable for first user)
3. Invite accept page (`/auth/invite?token=`) — reads token from query param, shows set-password form, calls `POST /auth/invite/accept`
4. Route middleware (`middleware.ts`) — redirect unauthenticated users to `/login`

### 4.3 Document Pages (Days 15–16)

1. Document list page — table, status badges, pagination, sort/filter
2. Upload page — drag-and-drop zone, progress indicator, status polling
3. Document detail page — metadata, versions list, reviews list, action buttons
4. Implement document download button

### 4.4 Search Page (Day 17)

1. Search input with type selector (semantic / keyword / hybrid)
2. Result cards — excerpt, score, document link, page number
3. RAG Q&A panel — question input, loading state, answer with source citations

### 4.5 Agent Chat Interface (Day 18)

1. Session selector / creator (list, create, archive sessions)
2. Chat thread UI (user messages + agent streaming responses via `useSSE`)
3. Agent trace accordion (which agents ran, what they did, timing)
4. Disconnect recovery: on page load check for pending task_id in session storage; poll `GET /agents/tasks/{id}` until complete; display stored result
5. Message history: on session open, load prior turns from `GET /agents/sessions/{id}/history`

### 4.6 Signature Flow (Day 19)

1. Signature fields overlay on PDF view
2. Field-by-field signing wizard
3. Typed signature modal (input → font preview)
4. Drawing canvas modal (draw → preview)
5. Confirmation and download signed document

### 4.7 Admin Panel (Day 20)

1. User management table (role chips, toggle active/deactivate)
2. Create user modal (`POST /admin/users`) + invite user modal (`POST /admin/users/invite` — copy token to clipboard)
3. Reset password flow — admin clicks Reset on any user row
4. Audit log table with date/action/user filters and CSV export button
5. System stats cards

**Deliverable:** Full UI — all features accessible through the browser.

---

## Phase 5 — Testing & QA (Days 21–23)

1. Complete backend test suite to >80% coverage
2. Fix any bugs surfaced during frontend testing
3. Manual QA walkthrough of all happy paths:
   - Upload → process → search → RAG answer
   - Upload → review → view report
   - Upload → edit (summarize) → download new version
   - Upload → detect fields → sign → download signed
4. Frontend TypeScript strict check (`tsc --noEmit`)
5. API contract check — verify frontend API calls match API_SPEC.md

---

## Phase 6 — Hardening & Deployment Prep (Days 24–25)

**Note:** Rate limiting was implemented in Phase 1. Nginx was implemented in Phase 0. This phase focuses on production-hardening the existing stack.

1. Add security headers middleware (HSTS, X-Frame-Options, X-Content-Type-Options, CSP)
2. Set non-root user in Dockerfiles (`USER 1000:1000` for both backend and frontend)
3. Add general rate limiting for non-auth endpoints (upload, agent chat, search) — auth rate limiting was done in Phase 1
4. Add Nginx log format to redact `?token=` SSE token query param from access logs
5. Audit all file upload paths for path traversal; verify magic byte validation is correct in prod image
6. Write production `docker-compose.prod.yml` (no bind mounts; `restart: unless-stopped`; validate resource limits)
7. Finalize Nginx SSL config (certbot / self-signed; document the steps)
8. Write deployment runbook (fresh server; `git clone`; first-user bootstrap; model pull expected duration)
9. Create database backup script (pg_dump + ChromaDB volume copy + uploads volume)
10. Write disk usage monitoring documentation (alert when uploads volume > 80% capacity)

---

## Timeline Summary

| Phase | Days | Deliverable |
|---|---|---|
| 0 — Infrastructure | 1–2 | All services running |
| 1 — Auth & Core API | 3–5 | Auth + Document CRUD |
| 2 — Processing Pipeline | 6–8 | PDFs chunked & embedded |
| 3 — Agent System | 9–13 | All 5 agents working |
| 4 — Frontend | 14–20 | Full UI |
| 5 — Testing | 21–23 | QA complete |
| 6 — Hardening | 24–25 | Production-ready |

**Total estimate: 25 working days** (for a solo developer; can be parallelized with a team)

---

## Technology Versions (Locked)

| Package | Version | Notes |
|---|---|---|
| Python | 3.11 | |
| FastAPI | 0.115.x | |
| SQLAlchemy | 2.0.x | async mode |
| Alembic | 1.13.x | |
| Pydantic | 2.x | |
| asyncpg | 0.29.x | async PostgreSQL driver |
| PyMuPDF | 1.24.x | fitz |
| pypdf | 4.x | metadata extraction |
| python-docx | 1.x | DOCX extraction |
| pytesseract | 0.3.x | OCR wrapper |
| tesseract-ocr | 5.x | installed via apt in Dockerfile |
| chardet | 5.x | encoding detection for TXT |
| chromadb | 0.5.x | |
| ollama (Python SDK) | 0.3.x | |
| Pillow | 10.x | signature image rendering |
| reportlab | 4.x | PDF generation from edited text |
| sse-starlette | 2.x | SSE response helper for FastAPI |
| slowapi | 0.1.x | rate limiting |
| Node.js | 20 LTS | |
| Next.js | 14.x | App Router |
| Tailwind CSS | 3.x | |
| PostgreSQL | 16 | |
| Ollama | latest | qwen3:8b + bge-m3 |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| qwen3:8b too slow on CPU | High | High | Stream tokens via SSE; tune num_ctx=2048 for simple tasks; set user expectation in UI |
| bge-m3 embedding slow during bulk ingest | Medium | Medium | Batch embed; run in background; show granular progress via SSE |
| Ollama model load time (30–120s on CPU) | High | Medium | Backend startup waits for readiness; health returns "degraded" during load |
| qwen3:8b tool call parsing unreliable | Medium | High | JSON output fallback: if tool call parse fails, retry with explicit "respond in JSON format" instruction |
| FastAPI BackgroundTask lost on restart | Medium | High | Startup recovery: re-queue all documents stuck in 'processing' on every boot |
| ChromaDB/PostgreSQL deletion inconsistency | Low | Medium | Delete ChromaDB first; only soft-delete in PG on success; reconciliation on startup |
| Browser EventSource can't send Auth header | High (by design) | High | SSE token endpoint (30s TTL, single-use) resolves this; SSE token in URL param is short-lived only |
| File upload path traversal / extension spoofing | Medium | Critical | Extension allowlist + magic byte validation implemented in Phase 1 |
| Context window overflow for large documents | High | Medium | Sliding window for Reviewer; first-N-tokens with truncation warning for Editor |
| PyMuPDF AGPL license | Low | Medium | Acceptable for self-hosted deployment; documented in LICENSE notes |
| ChromaDB breaking API changes | Low | Medium | Pin exact version in requirements.txt |
| Tesseract not in Docker image | Low | High | apt-get install in Dockerfile; tested in Phase 0 build |
| Large scanned PDF (50 MB) exhausting RAM during OCR | Medium | High | OCR page-by-page with 30s/page timeout; GC after each page |
| Agent hallucination in document editing | High | Medium | Always create new version; user must confirm before PDF is saved; never overwrite original |
| DOCX complex formatting lost in text extraction | Medium | Low | python-docx extracts paragraphs + tables; UI note: "Formatting not preserved" |
| 16GB RAM insufficient for full stack | Medium | High | Document minimum 16GB; set Docker mem_limits; test on fresh boot |
