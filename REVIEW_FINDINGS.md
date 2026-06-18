# Documentation Review Findings — Document Intelligence Platform

**Review Date:** 2026-06-18  
**Scope:** PROJECT_SPEC.md · ARCHITECTURE.md · DATABASE_SCHEMA.md · API_SPEC.md · TASKS.md · IMPLEMENTATION_PLAN.md  
**Dimensions:** Architecture · Database · Agent Communication · API · Security · Scalability · Maintainability · Docker · Ollama · Qwen3 · ChromaDB

---

## CRITICAL BUGS (Break the system if not fixed)

| ID | Location | Issue | Fix Applied |
|---|---|---|---|
| DB-BUG-01 | DATABASE_SCHEMA.md | `documents.owner_id` declared `NOT NULL` but also `ON DELETE SET NULL` — direct constraint contradiction. PostgreSQL raises a violation when user is deleted. | Changed to `ON DELETE RESTRICT` |
| DB-BUG-02 | DATABASE_SCHEMA.md | `agent_sessions.context_data JSONB` stores full conversation history as unbounded blob. Individual turn queries are impossible; large documents in context will cause massive column bloat. | Added `agent_messages` table |
| API-BUG-01 | API_SPEC.md | `POST /agents/sessions/{id}/chat` response contains full `agent_trace` + `result` — a blocking synchronous contract — but the architecture mandates SSE streaming. These are mutually exclusive. | Redesigned: POST returns `task_id` immediately; SSE delivers results |
| API-BUG-02 | API_SPEC.md | Response example on `/search/ask` shows `"model_used": "qwen2.5:7b"` — stale from before model confirmation. | Fixed to `qwen3:8b` |
| ARCH-BUG-01 | ARCHITECTURE.md | System overview diagram says "HTTPS / REST / WebSocket" — WebSocket was replaced by SSE in final decisions. | Fixed to SSE |

---

## SECURITY ISSUES

| ID | Severity | Issue | Fix Applied |
|---|---|---|---|
| SEC-01 | Critical | File path constructed using user-supplied extension (`original.<ext>`). A filename like `../../etc/passwd.pdf` produces a dangerous path. | Added: allowlist extension extraction + sanitization note |
| SEC-02 | High | No magic-byte validation. Any file renamed to `.pdf` passes type check. | Added to NFRs + TASKS |
| SEC-03 | High | No specification of token storage in browser. `localStorage` is XSS-vulnerable. | Added HttpOnly cookie recommendation to NFRs |
| SEC-04 | Medium | Logout revokes refresh token only. Access token stays valid up to 30 min. | Documented as known limitation with mitigation |
| SEC-05 | High | Browser `EventSource` API cannot send `Authorization` headers. JWT in query param is logged by servers. | Added SSE ticket endpoint (`POST /auth/sse-token`) to API spec + tasks |
| SEC-06 | High | `audit_logs` has no immutability protection. Any DB user can `UPDATE`/`DELETE` records. | Added trigger that raises exception on any mutation |
| SEC-07 | High | Rate limiting deferred to Phase 6. Auth endpoints are brute-force targets from Phase 1. | Moved to Phase 1 in TASKS |
| SEC-08 | Medium | Docker containers run as root by default. | Added non-root USER instruction to IMPLEMENTATION_PLAN |
| SEC-09 | Medium | No input length limit on agent chat messages. 1MB message consumes entire context window. | Added `MAX_CHAT_MESSAGE_CHARS=4000` env var to spec |

---

## DATABASE DESIGN ISSUES

| ID | Severity | Issue | Fix Applied |
|---|---|---|---|
| DB-01 | Critical | Missing `agent_messages` table for conversation turns | Added table |
| DB-02 | High | Missing `user_invitations` table for admin-only registration flow | Added table |
| DB-03 | High | Missing GIN full-text search index on `document_chunks.chunk_text` | Added tsvector column + GIN index |
| DB-04 | Medium | Missing composite indexes for common query patterns | Added 3 composite indexes |
| DB-05 | Medium | No CHECK constraints on VARCHAR status/role columns — any string can be stored | Added CHECK constraints |
| DB-06 | Medium | File paths documented as TEXT without clarifying relative vs absolute | Added explicit note: relative paths only |
| DB-07 | Medium | ChromaDB collection distance metric not specified — defaults to L2, wrong for bge-m3 | Added: `hnsw:space: cosine`, dimension: 1024 |
| DB-08 | Low | `document_versions` has no FK to `agent_tasks` — can't trace which task produced a version | Added `task_id` FK column |
| DB-09 | Low | No CHECK constraint on `signatures.signature_type` | Added CHECK constraint |
| DB-10 | Low | No mechanism or schema for admin-initiated password change | Added `PATCH /admin/users/{id}/password` to API spec |

---

## API DESIGN ISSUES

| ID | Severity | Issue | Fix Applied |
|---|---|---|---|
| API-01 | High | `GET /agents/sessions/{id}/history` — endpoint listed but response body missing | Added full response spec |
| API-02 | High | `GET /documents/{id}/versions/{version_id}/download` — referenced in signature response but not spec'd | Added endpoint |
| API-03 | Medium | `PATCH /documents/{id}` missing — no way to rename a document after upload | Added endpoint |
| API-04 | High | `POST /admin/users` missing — admin can't create users (registration is admin-only after first user) | Added endpoint |
| API-05 | Medium | `GET /admin/users` has no documented response body | Added response schema |
| API-06 | Medium | `GET /agents/sessions` missing — user can't list their sessions | Added endpoint |
| API-07 | Low | `DELETE /agents/sessions/{id}` missing — no way to close a session | Added endpoint |
| API-08 | Medium | `POST /search` access control not documented — can Viewers search all documents? | Added access control note |
| API-09 | Low | `GET /documents/{id}/reviews` has no pagination | Added page/per_page |
| API-10 | Medium | SSE disconnect behavior not documented — what happens to task when client disconnects? | Added behavior documentation |
| API-11 | High | SSE auth: `EventSource` cannot send `Authorization` header — no resolution documented | Added `POST /auth/sse-token` short-lived ticket endpoint |

---

## ARCHITECTURE ISSUES

| ID | Severity | Issue | Fix Applied |
|---|---|---|---|
| ARCH-01 | High | No Nginx in base architecture — ports exposed directly, no SSL termination | Added Nginx to Docker service map |
| ARCH-02 | High | `FastAPI BackgroundTasks`: if process dies mid-processing, document stuck in 'processing' forever — no recovery | Added startup recovery job spec |
| ARCH-03 | High | No agent concurrency control — Ollama queues requests silently on CPU; no documented throughput or queue behavior | Added concurrency section |
| ARCH-04 | High | No agent timeout policy — hanging Ollama call blocks SSE connection indefinitely | Added 300s timeout policy |
| ARCH-05 | High | Backend starts before Ollama model loads (30–120s on CPU) — first API calls fail | Added readiness check spec |
| ARCH-06 | High | Context window overflow strategy missing — 50-page PDF far exceeds num_ctx=4096 | Added sliding window strategy |
| ARCH-07 | Medium | ChromaDB distance metric not specified — defaults to L2, incorrect for bge-m3 | Added cosine metric spec |
| ARCH-08 | Medium | ChromaDB ↔ PostgreSQL deletion is not atomic — inconsistency possible | Added reconciliation strategy |
| ARCH-09 | Medium | RAM requirements not clearly stated — qwen3:8b + bge-m3 + system needs ~12–14GB minimum | Added system requirements section |
| ARCH-10 | Low | DOCX/TXT files have no pages — `page_number` fields are undefined for these formats | Added synthetic chunk numbering note |

---

## SCALABILITY ISSUES

| ID | Severity | Issue | Fix Applied |
|---|---|---|---|
| SCALE-01 | Medium | ChromaDB single instance, no horizontal scaling — scale limit undocumented | Added: max ~1M chunks before degradation |
| SCALE-02 | Medium | SQLAlchemy connection pool size undocumented | Added: pool_size=10, max_overflow=20 |
| SCALE-03 | Medium | Embedding 500+ chunks sequentially during processing gives no ETA to user | Added progress_step to status response |
| SCALE-04 | Low | Upload volume has no disk quota — can fill disk without warning | Added monitoring note |

---

## IMPLEMENTATION PLAN ISSUES

| ID | Severity | Issue | Fix Applied |
|---|---|---|---|
| IMPL-01 | Medium | Phase 0 has no Nginx service — production promotion requires architecture change | Added to Phase 0 |
| IMPL-02 | Medium | No Docker resource limits — Ollama can OOM-kill PostgreSQL on low-RAM machines | Added mem_limit specs |
| IMPL-03 | High | Rate limiting deferred to Phase 6 — auth endpoints unprotected during development | Moved to Phase 1 |
| IMPL-04 | High | Agent timeout not in any phase | Added to Phase 3 |
| IMPL-05 | High | SSE authentication token exchange not in any phase | Added to Phase 3 |
| IMPL-06 | High | Startup recovery for stuck-processing documents not in any phase | Added to Phase 2 |
| IMPL-07 | Medium | Missing .dockerignore files | Added to Phase 0 |

---

## ISSUES NOT REQUIRING DOC CHANGES (Acknowledged Limitations)

- **PyMuPDF AGPL license**: Self-hosted use is acceptable; noted in risk register ✓
- **qwen3:8b slowness on CPU**: Mitigated by SSE streaming + user expectation ✓
- **No real-time collaboration**: Explicitly out of scope ✓
- **No cryptographic signatures**: Explicitly out of scope ✓
- **Single Ollama instance throughput**: Documented in concurrency section (new) ✓

---

## TOTAL FIXES APPLIED

| Category | Issues Found | Fixed in Docs |
|---|---|---|
| Critical bugs | 5 | 5 |
| Security | 9 | 9 |
| Database | 10 | 10 |
| API design | 11 | 11 |
| Architecture | 10 | 10 |
| Scalability | 4 | 4 |
| Implementation plan | 7 | 7 |
| **Total** | **56** | **56** |
