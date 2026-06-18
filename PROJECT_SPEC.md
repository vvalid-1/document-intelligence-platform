# Project Specification — Document Intelligence Platform

## 1. Overview

The Document Intelligence Platform (DIP) is a self-hosted, production-ready application that enables users to upload, process, search, review, edit, and sign documents using a multi-agent AI system backed entirely by local LLM inference (Ollama + Qwen). No external AI APIs are used.

---

## 2. Goals

| Goal | Description |
|---|---|
| Data Privacy | All processing happens on-premise; no data leaves the server |
| AI-Powered Workflows | Agents automate review, editing, search, and signing tasks |
| Developer-Friendly | Clean REST API, Docker-based deployment, OpenAPI docs |
| Production-Ready | Authentication, RBAC, audit logs, versioning, error handling |
| Extensible | New agents and document types can be added without rearchitecting |

---

## 3. Functional Requirements

### 3.1 Authentication & Users

- FR-AUTH-01: The very first user to register on the platform automatically receives the Admin role
- FR-AUTH-02: After the first user exists, `POST /auth/register` returns 403. New users must be created via `POST /admin/users` (direct) or invited via `POST /admin/users/invite` (token-based)
- FR-AUTH-03: Users log in with email and password and receive JWT access + refresh tokens
- FR-AUTH-04: Access tokens expire after 30 minutes (configurable); refresh tokens after 7 days
- FR-AUTH-05: Admin users can create users, deactivate users, change roles, and reset passwords
- FR-AUTH-06: Three roles: Admin, Editor, Viewer
- FR-AUTH-07: Password reset is Admin-initiated via `POST /admin/users/{id}/reset-password` — no email flow in v1
- FR-AUTH-08: Admin can generate a one-time invitation token that the invitee uses to self-register with a chosen password
- FR-AUTH-09: Authenticated users can change their own password via `PATCH /auth/me/password`

### 3.2 Document Management

- FR-DOC-01: Upload documents (PDF, DOCX, TXT — see open questions)
- FR-DOC-02: View document list with metadata (name, size, upload date, status, uploader)
- FR-DOC-03: Download original and processed documents
- FR-DOC-04: Delete documents (soft delete with 30-day retention, hard delete by Admin)
- FR-DOC-05: Document versioning — every AI-modified version is saved as a new version
- FR-DOC-06: Editors and Admins can upload; Viewers can only view and search
- FR-DOC-07: Document status lifecycle: uploaded → processing → ready → error

### 3.3 Document Processing

- FR-PROC-01: On upload, extract text from PDFs using PyMuPDF; fall back to pypdf if needed
- FR-PROC-02: For DOCX files, extract text using python-docx
- FR-PROC-03: For TXT files, read content directly with encoding detection
- FR-PROC-04: For scanned PDFs (no selectable text), apply Tesseract OCR via pytesseract
- FR-PROC-05: Chunk extracted text into overlapping segments for vector indexing
- FR-PROC-06: Embed chunks using bge-m3 via Ollama and store in ChromaDB with document metadata
- FR-PROC-07: Extract document metadata (page count, file size, creation date, author if available)
- FR-PROC-08: Processing runs asynchronously (non-blocking upload response)
- FR-PROC-09: Processing status is trackable via API polling or SSE stream

### 3.4 Smart Search & RAG Agent

- FR-SEARCH-01: Full-text keyword search across all documents
- FR-SEARCH-02: Semantic / vector search via ChromaDB embeddings
- FR-SEARCH-03: RAG — given a natural language question, retrieve relevant chunks and generate an answer with cited sources
- FR-SEARCH-04: Search results include document name, page number, chunk excerpt, and similarity score
- FR-SEARCH-05: Filter search by date range, document type, uploader

### 3.5 AI Document Reviewer Agent

- FR-REVIEW-01: Analyze a document for writing quality, clarity, and completeness
- FR-REVIEW-02: Detect potential compliance issues or missing sections
- FR-REVIEW-03: Generate a structured review report (issues list, severity, suggestions)
- FR-REVIEW-04: Review can be triggered manually or as part of an upload workflow
- FR-REVIEW-05: Review results are stored and viewable in the document detail page

### 3.6 AI Document Editor Agent

- FR-EDIT-01: Accept a user instruction (e.g., "summarize this document", "rewrite section 3 formally")
- FR-EDIT-02: Stream the edited text output to the frontend via SSE as it is generated
- FR-EDIT-03: Offer two output modes:
  - **Text-only**: Display the edited content in the UI for the user to copy
  - **Regenerated PDF**: Rebuild a new PDF from the edited text and create a new document version
- FR-EDIT-04: Show a diff view between original and edited text
- FR-EDIT-05: Allow user to accept (→ save version) or reject (→ discard) AI edits
- FR-EDIT-06: Support multiple edit operations: summarize, paraphrase, expand, translate, fix grammar

### 3.7 AI Signature Assistant Agent

Electronic (visual) signatures only. No cryptographic / PKI-based digital signatures in v1.

- FR-SIG-01: Detect existing AcroForm signature fields in PDF documents
- FR-SIG-02: Guide users through filling required signature fields via AI assistant
- FR-SIG-03: Support typed e-signatures (user types their name, rendered as a signature-style font using Pillow)
- FR-SIG-04: Support drawn e-signatures (canvas-based drawing in frontend, submitted as PNG)
- FR-SIG-05: Embed the signature image onto the correct page/position in the PDF using PyMuPDF
- FR-SIG-06: Create a new document version for each signed document
- FR-SIG-07: Generate a signature audit trail (who signed, timestamp, IP address, signature type)
- FR-SIG-08: AI assistant suggests which fields require signatures and in what order

### 3.8 Orchestrator Agent

- FR-ORCH-01: Accept a high-level user instruction (e.g., "review and summarize this document")
- FR-ORCH-02: Break the instruction into sub-tasks and delegate to specialist agents
- FR-ORCH-03: Coordinate agent outputs into a unified result
- FR-ORCH-04: Maintain conversation history for multi-turn interactions
- FR-ORCH-05: Return structured results to the frontend with agent attribution

### 3.9 Audit & Logging

- FR-AUDIT-01: Log all document operations (upload, download, delete, edit, sign)
- FR-AUDIT-02: Log all agent invocations with input, output, and duration
- FR-AUDIT-03: Audit log is viewable by Admin only
- FR-AUDIT-04: Export audit log as CSV

---

## 4. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Performance | API response < 200ms for non-AI endpoints |
| Performance | Document processing completes within 10 minutes for files up to 50MB (OCR may take longer) |
| Performance | Agent timeout: 300 seconds max per task; configurable via `AGENT_TIMEOUT_SECONDS` |
| Scalability | Horizontal scaling of backend via Docker replicas (future) |
| Scalability | ChromaDB supports up to ~1M chunks before performance degrades — plan migration path beyond |
| Availability | Services restart automatically on failure (`restart: unless-stopped` in docker-compose) |
| Availability | Backend startup waits for Ollama model readiness before serving agent requests |
| Security | Passwords hashed with bcrypt (cost factor ≥ 12) |
| Security | JWT access tokens: 30-min TTL; refresh tokens: 7-day TTL |
| Security | Access tokens stored in memory (Zustand/JS variable); refresh tokens in HttpOnly Secure cookie |
| Security | File upload: extension allowlist + magic byte validation (file header must match declared MIME) |
| Security | File storage paths are relative only — never absolute; stored extension sanitized from allowlist |
| Security | SQL injection protection via SQLAlchemy ORM (no raw SQL strings) |
| Security | CORS restricted to configured origins via `CORS_ALLOWED_ORIGINS` env var |
| Security | SSE authentication via short-lived (30s) single-use SSE tokens — JWT not passed in URL params |
| Security | Audit log is append-only — DB trigger blocks UPDATE and DELETE |
| Security | Docker containers run as non-root user (UID 1000) |
| Security | Agent chat messages capped at 8000 characters (configurable via `MAX_CHAT_MESSAGE_CHARS`) |
| Security | Rate limiting applied from Phase 1: auth endpoints 10 req/min/IP; agent endpoints 30 req/hr/user |
| Observability | Structured JSON logging; log level configurable via `LOG_LEVEL` env var |
| Observability | Health check endpoint includes per-service and per-model status |
| Observability | SSE processing status includes step name and progress percentage |
| Maintainability | 100% type-annotated Python (mypy-compatible) |
| Maintainability | OpenAPI 3.0 spec auto-generated by FastAPI |
| Maintainability | Docker images built with `.dockerignore` to exclude test files and dev dependencies |

---

## 5. Constraints

- No paid APIs (OpenAI, Anthropic, Cohere, etc.)
- No SaaS vector databases (Pinecone, Weaviate Cloud, etc.)
- LLM inference via Ollama only
- Deployment via Docker Compose (no Kubernetes requirement initially)
- All persistent data stored in Docker volumes

---

## 6. Supported Document Types (Confirmed)

| Type | Extension | Processing |
|---|---|---|
| PDF (text-based) | .pdf | PyMuPDF primary, pypdf fallback |
| PDF (scanned/image) | .pdf | PyMuPDF → detect no text → Tesseract OCR |
| Word | .docx | python-docx |
| Plain Text | .txt | Direct read with chardet encoding detection |

---

## 7. Out of Scope (v1)

- Real-time collaborative editing (Google Docs style)
- Cryptographic / PKI-based digital signatures (electronic-visual only)
- XLSX / spreadsheet processing
- Email notification system
- Mobile application
- SSO / OAuth2 provider integration
- Kubernetes deployment
- Multi-language UI (English only in v1)
- GPU acceleration (CPU-only; Ollama will use CPU threads)

---

## 8. Concurrency & Scale Expectations (v1)

| Metric | Expected Value | Notes |
|---|---|---|
| Concurrent users | 1–5 | Ollama CPU processes one LLM call at a time |
| Documents | Up to ~5,000 | ~1M chunks before ChromaDB degrades |
| Max document size | 50 MB | Configurable via `MAX_FILE_SIZE_MB` |
| Agent response time | 30–300 seconds | CPU-only; user sees streaming tokens |
| Embedding time (50MB PDF) | 5–30 minutes | Depends on chunk count and CPU speed |
| Simultaneous uploads | Up to 10 | Processing is async; all queue in background |

---

## 9. Assumptions

- Ollama runs in CPU-only mode; qwen3:8b requires ~8–10 GB RAM; responses will be slower than GPU
- Embedding model bge-m3 also runs via Ollama on CPU
- Users access the platform via a modern web browser (Chrome, Firefox, Edge)
- Deployment target is both local Docker Desktop (Windows/Mac) and Linux servers
- Maximum file size is 50 MB, configurable via MAX_FILE_SIZE_MB env var
- Tesseract is installed in the backend Docker image via apt-get
- SSE (Server-Sent Events) is used for all streaming agent output
