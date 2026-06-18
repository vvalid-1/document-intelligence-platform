# Tasks — Document Intelligence Platform

## Task Legend

| Symbol | Meaning |
|---|---|
| [ ] | Not started |
| [x] | Completed |
| [~] | In progress |
| [!] | Blocked |

**Priority:** P0 = Critical path / P1 = High / P2 = Medium / P3 = Nice to have

---

## Phase 0 — Project Setup

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-000 | Create directory structure | P0 | scaffold all folders |
| T-001 | Initialize git repository | P0 | .gitignore, initial commit |
| T-002 | Create .env.example file | P0 | all required env vars including AGENT_TIMEOUT_SECONDS, MAX_CHAT_MESSAGE_CHARS |
| T-003 | Create docker-compose.yml | P0 | postgres, chromadb, ollama, backend, frontend, **nginx** |
| T-004 | Create docker-compose.dev.yml | P1 | hot reload overrides; nginx pass-through in dev |
| T-005 | Configure Ollama Docker service | P0 | pull qwen3:8b AND bge-m3 on first start; startup script |
| T-006 | Configure PostgreSQL Docker service | P0 | init script, healthcheck, mem_limit: 512m |
| T-007 | Configure ChromaDB Docker service | P0 | persistent volume, mem_limit: 1g |
| T-008 | Configure Nginx Docker service | P0 | proxy to frontend+backend; SSE config (proxy_buffering off) |
| T-009 | Add Docker resource limits | P0 | mem_limit: 12g for ollama; prevents OOM cascades |
| T-010 | Create .dockerignore for backend | P0 | exclude .venv, __pycache__, .pytest_cache, tests/ |
| T-011 | Create .dockerignore for frontend | P0 | exclude node_modules, .next, *.test.ts |
| T-012 | Create Makefile / task runner | P2 | common dev commands |

---

## Phase 1 — Backend Foundation

### 1.1 FastAPI Application Skeleton

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-100 | Initialize FastAPI app | P0 | main.py, app factory |
| T-101 | Configure pydantic-settings | P0 | load from .env |
| T-102 | Configure SQLAlchemy async engine | P0 | asyncpg driver |
| T-103 | Initialize Alembic | P0 | alembic.ini, env.py |
| T-104 | Create initial DB migration | P0 | all tables from DATABASE_SCHEMA.md |
| T-105 | Configure CORS middleware | P0 | allow frontend origin |
| T-106 | Configure structured JSON logging | P1 | loguru or structlog |
| T-107 | Create health check endpoint | P0 | GET /health — reports DB, ChromaDB, and Ollama model load state |
| T-108 | Configure global exception handler | P0 | uniform error response format |
| T-109 | Implement Ollama model pre-load wait | P0 | on lifespan startup: poll /api/tags every 5s until qwen3:8b + bge-m3 appear; health returns "degraded" during wait |

### 1.2 Authentication and SSE Tokens

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-110 | Create User, UserInvitation ORM models | P0 | |
| T-111 | Create User Pydantic schemas | P0 | |
| T-112 | Implement password hashing (bcrypt, cost ≥ 12) | P0 | |
| T-113 | Implement JWT token generation | P0 | access + refresh |
| T-114 | Implement JWT token validation | P0 | |
| T-115 | Create POST /auth/register (first-user only) | P0 | returns 403 REGISTRATION_CLOSED after first user |
| T-116 | Implement first-user-becomes-admin logic | P0 | atomic count check to prevent race condition |
| T-117 | Create POST /auth/invite/accept | P0 | validates invitation token, creates user |
| T-118 | Create POST /auth/login | P0 | |
| T-119 | Create POST /auth/refresh | P0 | |
| T-120 | Create POST /auth/logout | P0 | revoke refresh token |
| T-121 | Create GET /auth/me | P0 | |
| T-122 | Create PATCH /auth/me/password | P1 | user changes own password |
| T-123 | Implement SSE token endpoint POST /auth/sse-token | P0 | 30s TTL, single-use, stored in sse_tokens table |
| T-124 | Create SSE token validation dependency | P0 | validates token, marks used=TRUE atomically |
| T-125 | Create RBAC dependency | P0 | require_role("admin"), etc. |
| T-126 | Implement slowapi rate limiting for auth endpoints | P0 | 10/min on login; applied in Phase 1 not Phase 6 |
| T-127 | Write auth unit tests | P1 | test first-user logic, invitation flow, SSE tokens |

### 1.3 Document Management API

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-130 | Create Document, DocumentVersion ORM models | P0 | |
| T-131 | Create Document Pydantic schemas | P0 | include chunk_count, progress_step fields |
| T-132 | Implement file upload handler | P0 | allowlist extension; magic byte validation; sanitize extension before path construction; save relative path only |
| T-133 | Implement magic byte validation utility | P0 | check file header bytes match declared MIME type; prevent .exe renamed to .pdf |
| T-134 | Implement GET /documents (list) | P0 | pagination, filters, composite index used |
| T-135 | Implement POST /documents/upload | P0 | return stream_url in response |
| T-136 | Implement GET /documents/{id} | P0 | |
| T-137 | Implement PATCH /documents/{id} | P1 | update title |
| T-138 | Implement DELETE /documents/{id} | P0 | soft delete |
| T-139 | Implement GET /documents/{id}/download | P0 | stream file; Content-Disposition header |
| T-140 | Implement GET /documents/{id}/versions | P1 | include task_id in response |
| T-141 | Implement GET /documents/{id}/versions/{vid}/download | P0 | download specific version |
| T-142 | Write document API tests | P1 | magic byte rejection, soft delete, version download |

### 1.4 Admin API

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-150 | Create GET /admin/users | P0 | paginated user list |
| T-151 | Create POST /admin/users | P0 | direct user creation with temporary password |
| T-152 | Create POST /admin/users/invite | P0 | generate one-time invitation token (returned in response, not emailed) |
| T-153 | Create PATCH /admin/users/{id} | P0 | role change, activate/deactivate |
| T-154 | Create POST /admin/users/{id}/reset-password | P0 | admin-initiated password reset |
| T-155 | Create GET /admin/audit-logs | P1 | paginated + filtered by user/action/date |
| T-156 | Create GET /admin/audit-logs/export | P1 | CSV download |
| T-157 | Create GET /admin/stats | P1 | document counts, storage used, agent usage, Ollama model status |

---

## Phase 2 — Document Processing Pipeline

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-200 | Add tesseract-ocr, poppler-utils to Dockerfile via apt | P0 | required before building backend image |
| T-201 | Install PyMuPDF, pypdf, python-docx, pytesseract, chardet | P0 | |
| T-202 | Implement PDF text extraction (PyMuPDF primary, pypdf fallback) | P0 | per-page extraction |
| T-203 | Implement scanned PDF detection | P0 | check char count per page; if < 10 chars → treat as image |
| T-204 | Implement Tesseract OCR for scanned PDFs | P0 | pytesseract page-by-page; 30s timeout per page |
| T-205 | Implement DOCX text extraction (python-docx) | P0 | paragraphs + tables; page_number=NULL |
| T-206 | Implement TXT extraction with encoding detection (chardet) | P0 | page_number=NULL |
| T-207 | Implement PDF metadata extraction (pypdf) | P0 | |
| T-208 | Implement text chunking strategy | P0 | overlapping windows; configurable CHUNK_SIZE, CHUNK_OVERLAP |
| T-209 | Set up ChromaDB Python client | P0 | get_or_create_collection with hnsw:space=cosine |
| T-210 | Implement Ollama embedding client (bge-m3) | P0 | batch embed with retry |
| T-211 | Implement chunk embedding + ChromaDB insert | P0 | batch inserts; update chunk_count on documents |
| T-212 | Create DocumentChunk ORM model + GIN FTS index migration | P0 | search_vector GENERATED column |
| T-213 | Wire processing into background task on upload | P0 | FastAPI BackgroundTasks |
| T-214 | Implement processing status + progress_step updates | P0 | granular step names: extracting, ocr, chunking, embedding |
| T-215 | Implement SSE stream for processing status | P0 | GET /documents/{id}/status/stream; SSE token auth |
| T-216 | Handle processing errors gracefully | P0 | set status=error, log step where failure occurred |
| T-217 | Implement startup recovery for stuck documents | P0 | on backend start: re-queue any documents stuck in 'processing' |
| T-218 | Implement document deletion cleanup | P1 | delete ChromaDB entries FIRST, then soft-delete in PG |
| T-219 | Implement ChromaDB/PG reconciliation check on startup | P1 | find orphaned ChromaDB entries for deleted documents |
| T-220 | Write processing pipeline tests | P1 | mock Ollama embed; chromadb EphemeralClient; mock pytesseract |

---

## Phase 3 — Agent System

### 3.1 Base Agent Framework

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-300 | Set up Ollama Python SDK client wrapper | P0 | retry (3x exponential backoff); CPU tuning (num_ctx, num_thread from env) |
| T-301 | Implement streaming client method | P0 | yield tokens; detect Ollama model-not-loaded error |
| T-302 | Implement Ollama model readiness check | P0 | poll GET /api/tags until qwen3:8b and bge-m3 appear; used in startup sequence |
| T-303 | Implement agent timeout enforcement | P0 | asyncio.wait_for with AGENT_TIMEOUT_SECONDS; send SSE error event on timeout |
| T-304 | Implement tool call parsing with JSON fallback | P0 | if Ollama tool call parsing fails, retry with explicit JSON output prompt |
| T-305 | Create BaseAgent abstract class | P0 | run(), stream_run(); both enforce timeout |
| T-306 | Create AgentSession, AgentMessage, AgentTask ORM models | P0 | including deferred FK migrations |
| T-307 | Implement agent task persistence | P0 | save inputs, outputs, duration, model_used |
| T-308 | Implement context window size guard | P0 | tokenize prompt; if > OLLAMA_NUM_CTX*0.85 → truncate + warn |
| T-309 | Implement SSE response factory | P0 | sse_event() helper; FastAPI StreamingResponse with text/event-stream |
| T-310 | Create AgentMessage append service | P0 | manages sequence_num; loads recent N messages for prompt context |

### 3.2 Orchestrator Agent

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-320 | Write Orchestrator system prompt | P0 | intent classification; task planning; document-context awareness |
| T-321 | Implement task routing logic | P0 | map intent → agent; handle multi-agent sequences |
| T-322 | Implement multi-turn conversation context | P0 | load last N messages from agent_messages; fit in context window |
| T-323 | Implement result aggregation | P0 | combine specialist outputs into coherent response |
| T-324 | Create GET /agents/sessions | P0 | list sessions with pagination |
| T-325 | Create POST /agents/sessions | P0 | |
| T-326 | Create DELETE /agents/sessions/{id} | P0 | archive session |
| T-327 | Create POST /agents/sessions/{id}/chat | P0 | non-blocking; returns task_id + stream_url immediately |
| T-328 | Create GET /agents/sessions/{id}/stream | P0 | SSE; validates SSE token; streams tokens |
| T-329 | Create GET /agents/sessions/{id}/history | P0 | paginated agent_messages |

### 3.3 Smart Search & RAG Agent

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-330 | Implement semantic search (ChromaDB cosine query) | P0 | use cosine collection created in T-209 |
| T-331 | Implement keyword search (PostgreSQL FTS on chunk_search_vector) | P1 | uses GIN index from T-212 |
| T-332 | Implement hybrid search | P2 | merge semantic + keyword results; re-rank by combined score |
| T-333 | Implement RAG prompt builder | P0 | inject top-k chunks; document length guard |
| T-334 | Implement answer generation with streaming + citations | P0 | sources returned before stream starts |
| T-335 | Create POST /search endpoint | P0 | all search types; access: all authenticated users |
| T-336 | Create POST /search/ask endpoint | P0 | returns task_id + sources + stream_url immediately |
| T-337 | Write search agent tests | P1 | |

### 3.4 Document Reviewer Agent

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-340 | Write Reviewer system prompt | P0 | quality, structure, completeness; sliding window for large docs |
| T-341 | Implement sliding window review for large documents | P0 | process in 3000-token windows; aggregate issues |
| T-342 | Implement review output parser with JSON fallback | P0 | parse structured issues; retry on malformed JSON |
| T-343 | Create DocumentReview ORM model | P0 | |
| T-344 | Create POST /agents/review/{doc_id} | P0 | async; SSE for streaming review commentary |
| T-345 | Create GET /documents/{id}/reviews | P0 | paginated |
| T-346 | Write reviewer agent tests | P1 | |

### 3.5 Document Editor Agent

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-360 | Write Editor system prompt per operation | P0 | summarize, paraphrase, expand, fix_grammar, translate |
| T-361 | Implement streaming edit (text-only mode) | P0 | stream tokens via SSE |
| T-362 | Implement first-N-token truncation for large docs | P0 | include truncation warning in SSE done event |
| T-363 | Implement regenerated PDF mode (ReportLab) | P0 | edited text to new PDF |
| T-364 | Implement version creation on PDF edit | P0 | link task_id FK |
| T-365 | Create POST /agents/edit/{doc_id} | P0 | accepts output_mode: text or pdf |
| T-366 | Create GET /agents/edit/{task_id}/stream | P0 | SSE token auth |
| T-367 | Create GET /agents/tasks/{task_id} | P0 | poll completed result after SSE disconnect |
| T-368 | Write editor agent tests | P1 | |

### 3.6 Signature Assistant Agent

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-370 | Implement PDF AcroForm field detection (PyMuPDF) | P0 | returns field list with page/position |
| T-371 | Write Signature Assistant system prompt | P0 | guides user through fields in order |
| T-372 | Implement typed signature rendering (Pillow) | P0 | name text to PNG at signature-style font |
| T-373 | Implement drawn signature acceptance | P0 | validate base64 PNG; check PNG magic bytes; 500KB max |
| T-374 | Implement signature PNG embedding into PDF | P0 | PyMuPDF overlay on correct page + position |
| T-375 | Implement signed document version creation | P0 | new document_version linked to signature record |
| T-376 | Create Signature ORM model | P0 | stores signer_id, document_id, field_data, timestamp, ip_address |
| T-377 | Create GET /signatures/document/{id}/fields | P0 | list detected AcroForm fields |
| T-378 | Create POST /signatures/document/{id}/sign | P0 | submit typed or drawn signature |
| T-379 | Create GET /signatures/document/{id} | P0 | list signatures on a document |
| T-380 | Write signature service tests | P1 | |

---

## Phase 4 — Frontend

### 4.1 Next.js Setup

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-400 | Initialize Next.js 14 app | P0 | App Router, TypeScript |
| T-401 | Install Tailwind CSS + shadcn/ui | P0 | |
| T-402 | Create API client library | P0 | typed fetch wrapper with auto token refresh |
| T-403 | Create useSSE hook | P0 | fetch POST /auth/sse-token then open stream with ?token= param; reconnect on close; yield events |
| T-404 | Set up Zustand stores | P0 | auth (access token in memory), documents, search |
| T-405 | Auth store: refresh token flow | P0 | intercept 401 responses; call /auth/refresh; retry original request |
| T-406 | Create auth pages (login, register) | P0 | forms with zod validation |
| T-407 | Create invite accept page | P0 | /auth/invite?token= leads to set-password form |
| T-408 | Create main dashboard layout | P0 | sidebar, header, breadcrumb |
| T-409 | Set up route middleware (auth guard) | P0 | middleware.ts; redirect unauthenticated |

### 4.2 Document Pages

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-410 | Document list page | P0 | table with status indicators |
| T-411 | Document upload page | P0 | drag-and-drop, progress bar |
| T-412 | Document detail page | P0 | metadata, versions, reviews |
| T-413 | Document viewer (PDF embed) | P1 | browser PDF render |
| T-414 | Version history UI | P1 | list versions, download each |

### 4.3 Search Pages

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-420 | Search page | P0 | query input, result list |
| T-421 | Search result cards | P0 | excerpt, score, document link |
| T-422 | RAG Q&A panel | P0 | question input, answer display, sources |

### 4.4 Agent Chat Interface

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-430 | Session manager UI | P0 | list sessions, create, archive |
| T-431 | Agent chat page | P0 | message thread; SSE streaming tokens |
| T-432 | Agent trace accordion | P1 | which agents ran, timing |
| T-433 | Disconnected task recovery UI | P0 | on reconnect poll GET /agents/tasks/{id}; display stored result |

### 4.5 Signature Flow

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-440 | Signature field detection UI | P0 | highlight fields on PDF |
| T-441 | Typed signature input | P0 | text input + font preview |
| T-442 | Signature drawing canvas | P1 | canvas-based drawing |
| T-443 | Signature confirmation flow | P0 | confirm → submit → download |

### 4.6 Admin Panel

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-450 | User management table | P1 | list, role chip, deactivate toggle |
| T-451 | Create user + invite user flows | P1 | modal forms for POST /admin/users and /admin/users/invite |
| T-452 | Reset password flow | P1 | admin resets any user password |
| T-453 | Audit log viewer | P1 | filterable by user, action, date |
| T-454 | System stats dashboard | P2 | storage, doc counts, agent usage |

---

## Phase 5 — Testing & QA

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-500 | Configure pytest + httpx | P0 | async test client |
| T-501 | Auth test suite | P1 | |
| T-502 | Document API test suite | P1 | |
| T-503 | Processing pipeline test suite | P1 | mock Ollama |
| T-504 | Agent test suite | P1 | mock LLM responses |
| T-505 | Search test suite | P1 | |
| T-506 | Frontend type checking (tsc) | P1 | |
| T-507 | E2E test (Playwright) | P2 | core happy paths |
| T-508 | Load test (locust) | P3 | upload + search |

---

## Phase 6 — DevOps & Production Hardening

| ID | Task | Priority | Notes |
|---|---|---|---|
| T-600 | Production docker-compose | P0 | no dev bind mounts; restart: unless-stopped |
| T-601 | Nginx production config | P0 | now required (was optional); SSL termination; SSE buffering off |
| T-602 | Database backup script | P1 | pg_dump for PostgreSQL + volume copy for ChromaDB + uploads |
| T-603 | Log rotation config | P1 | file-based, daily rotation, 30-day retention |
| T-604 | Docker health check specs | P0 | healthcheck.cmd, interval, timeout, retries for all services |
| T-605 | General rate limiting (non-auth endpoints) | P1 | slowapi: agent chat 30/hr/user, upload 20/hr/user — auth rate limiting already done in Phase 1 T-126 |
| T-606 | Security headers middleware | P1 | HSTS, X-Frame-Options, X-Content-Type-Options, CSP |
| T-607 | Nginx log redaction for SSE token | P1 | redact ?token= from nginx access logs |
| T-608 | Security audit: file upload paths | P0 | verify extension sanitization + magic byte check in prod build |
| T-609 | Disk usage monitoring documentation | P1 | document volume monitoring; UPLOAD_MAX_TOTAL_GB env suggestion |
| T-610 | Write deployment runbook | P1 | fresh server setup; first-user bootstrap; model pull sequence |
| T-611 | Load test (locust) | P3 | 10 concurrent upload + search |

---

## Dependency Map

```
Phase 0 (infra) must complete before any Phase 1 code

Phase 1
  T-100..T-108 (skeleton) → T-109 (Ollama wait) → T-110+ (auth)
  T-109 is also required by T-107 (health check)
  T-110..T-129 (auth) → T-130..T-145 (documents)
  T-130..T-145 (docs) → T-150..T-157 (admin)

Phase 2 requires Phase 1 document upload API to be stable
  T-218 (startup recovery) runs on every backend start — built in Phase 2

Phase 3 requires Phase 2 (ChromaDB populated before agents can search)
  T-304 (agent timeout) required by all agent task runners

Phase 4 requires Phase 1 + Phase 2 + Phase 3 API surface to be stable

Phase 5 → Phase 6 (hardening after all tests pass)
```
