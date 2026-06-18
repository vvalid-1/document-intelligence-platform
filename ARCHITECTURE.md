# Architecture — Document Intelligence Platform

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                                │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                  Next.js 14 Frontend                          │  │
│   │        (App Router · TypeScript · Tailwind CSS)               │  │
│   └────────────────────────┬─────────────────────────────────────┘  │
└────────────────────────────│────────────────────────────────────────┘
                             │ HTTPS / REST / SSE
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          API LAYER                                   │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                   FastAPI Backend                             │  │
│   │   ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │  │
│   │   │ Auth Router│ │Doc Router│ │Search    │ │Agent Router│  │  │
│   │   │            │ │          │ │Router    │ │            │  │  │
│   │   └────────────┘ └──────────┘ └──────────┘ └────────────┘  │  │
│   └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────────────┐
│  PostgreSQL  │  │    ChromaDB      │  │      Ollama Server        │
│  (Primary DB)│  │  (Vector DB)     │  │   (Local LLM Inference)   │
│              │  │                  │  │                           │
│  · Users     │  │  · Doc Chunks    │  │  · Qwen (Chat/Instruct)   │
│  · Documents │  │  · Embeddings    │  │  · Embedding Model        │
│  · Versions  │  │  · Metadata      │  │                           │
│  · Audit Log │  │                  │  │                           │
│  · Sessions  │  │                  │  │                           │
└──────────────┘  └──────────────────┘  └──────────────────────────┘
          │
          ▼
┌──────────────┐
│ File Storage │
│ (Docker Vol) │
│ · Uploads    │
│ · Processed  │
│ · Exports    │
└──────────────┘
```

---

## 2. Multi-Agent Architecture

The agent system uses a **Hub-and-Spoke** pattern. The Orchestrator Agent is the single entry point and routes work to specialist agents.

```
                        ┌──────────────────────────────┐
                        │      Orchestrator Agent       │
                        │                               │
                        │  · Parses user intent         │
                        │  · Plans sub-tasks            │
                        │  · Delegates to specialists   │
                        │  · Aggregates results         │
                        │  · Manages conversation ctx   │
                        └──────────────┬───────────────┘
                                       │
              ┌────────────────────────┼─────────────────────────┐
              │                        │                         │
              ▼                        ▼                         ▼
┌─────────────────────┐  ┌──────────────────────┐  ┌───────────────────────┐
│  Smart Search &     │  │  Document Reviewer    │  │  Document Editor      │
│  RAG Agent          │  │  Agent                │  │  Agent                │
│                     │  │                       │  │                       │
│ · Semantic search   │  │ · Quality analysis    │  │ · Summarize           │
│ · Keyword search    │  │ · Compliance check    │  │ · Paraphrase          │
│ · RAG Q&A           │  │ · Issue detection     │  │ · Expand/condense     │
│ · Source citation   │  │ · Report generation   │  │ · Grammar fix         │
│ · Chunk retrieval   │  │                       │  │ · Version creation    │
└─────────────────────┘  └──────────────────────┘  └───────────────────────┘
                                                    ┌───────────────────────┐
                                                    │  Signature Assistant  │
                                                    │  Agent                │
                                                    │                       │
                                                    │ · Field detection     │
                                                    │ · Signing guidance    │
                                                    │ · Audit trail         │
                                                    └───────────────────────┘
```

### 2.1 Agent Communication Protocol

Each agent:
- Has a dedicated **system prompt** defining its role and capabilities
- Receives a **task payload** (structured dict) from the Orchestrator
- Returns a **result payload** (structured dict) with status, output, and metadata
- Maintains no cross-agent shared state (stateless per invocation)
- Uses **Ollama Python SDK** for LLM calls

The Orchestrator maintains conversation state per user session in PostgreSQL (agent_sessions table).

### 2.2 Agent Tool Interface

Agents can call **tools** (Python functions) that the LLM can invoke via function calling:

| Agent | Available Tools |
|---|---|
| Orchestrator | delegate_to_agent, get_session_history, create_task |
| RAG Agent | search_chromadb, get_document_chunk, keyword_search |
| Reviewer Agent | get_document_text, get_document_metadata |
| Editor Agent | get_document_text, create_version, apply_edit |
| Signature Agent | get_pdf_fields, embed_signature, create_audit_entry |

---

## 3. Backend Layer Detail

```
backend/app/
├── agents/
│   ├── base.py             # BaseAgent class, Ollama client wrapper
│   ├── orchestrator.py     # OrchestratorAgent
│   ├── search_rag.py       # SearchRAGAgent
│   ├── reviewer.py         # ReviewerAgent
│   ├── editor.py           # EditorAgent
│   └── signature.py        # SignatureAgent
├── api/
│   ├── v1/
│   │   ├── auth.py         # /api/v1/auth/*
│   │   ├── documents.py    # /api/v1/documents/*
│   │   ├── search.py       # /api/v1/search/*
│   │   ├── agents.py       # /api/v1/agents/*
│   │   ├── signatures.py   # /api/v1/signatures/*
│   │   └── admin.py        # /api/v1/admin/*
│   └── router.py           # Main router aggregation
├── core/
│   ├── config.py           # Settings (pydantic-settings)
│   ├── security.py         # JWT, bcrypt
│   ├── database.py         # SQLAlchemy engine + session
│   └── deps.py             # FastAPI dependency injection
├── models/                 # SQLAlchemy ORM models
├── schemas/                # Pydantic v2 schemas (request/response)
├── services/               # Business logic layer
│   ├── document_service.py
│   ├── search_service.py
│   ├── vector_service.py   # ChromaDB operations
│   ├── processing_service.py  # PyMuPDF + pypdf pipeline
│   └── signature_service.py
└── utils/
    ├── chunking.py         # Text splitting strategies
    ├── pdf_utils.py        # PDF helpers
    └── logging.py          # Structured logging setup
```

---

## 4. Frontend Layer Detail

```
frontend/
├── app/
│   ├── (auth)/
│   │   ├── login/
│   │   └── register/
│   ├── (dashboard)/
│   │   ├── documents/
│   │   │   ├── page.tsx          # Document list
│   │   │   ├── [id]/page.tsx     # Document detail
│   │   │   └── upload/page.tsx   # Upload flow
│   │   ├── search/page.tsx       # Search interface
│   │   ├── agents/page.tsx       # Agent chat interface
│   │   └── admin/page.tsx        # Admin panel
│   ├── layout.tsx
│   └── globals.css
├── components/
│   ├── ui/                       # shadcn/ui base components
│   ├── document/                 # Document-specific components
│   ├── agent/                    # Agent chat components
│   ├── signature/                # Signature canvas + flow
│   └── layout/                   # Nav, sidebar, header
├── lib/
│   ├── api/                      # Type-safe API client (fetch wrapper)
│   ├── hooks/                    # Custom React hooks
│   ├── stores/                   # Zustand state stores
│   └── types/                    # Shared TypeScript types
└── public/
```

---

## 5. Data Flow: Document Upload & Processing

```
User uploads file (.pdf / .docx / .txt)
      │
      ▼
Frontend (POST /api/v1/documents/upload)
      │
      ▼
FastAPI receives file
├── Validate type (pdf/docx/txt), size (≤ MAX_FILE_SIZE_MB)
├── Save to /uploads/{uuid}/original.<ext>
├── Insert document record (status=processing)
└── Spawn background task
      │
      ▼ (Background — ProcessingService)
      │
      ├─ PDF? ──► PyMuPDF extract text per page
      │              │
      │              ├── Text found? ──► proceed to chunking
      │              └── No text (scanned)? ──► Tesseract OCR per page ──► proceed to chunking
      │
      ├─ DOCX? ──► python-docx extract paragraphs + tables
      │
      └─ TXT? ──► read with chardet encoding detection
      │
      ▼
pypdf: extract metadata (PDF only)
      │
      ▼
Chunking: split into overlapping windows (configurable size/overlap)
      │
      ▼
Embed each chunk: Ollama bge-m3 → float[]
      │
      ▼
Store chunks + embeddings → ChromaDB
      │
      ▼
Update document status → ready
      │
      ▼
User polls GET /api/v1/documents/{id}/status
OR SSE stream GET /api/v1/documents/{id}/status/stream
```

---

## 6. Data Flow: RAG Query with SSE Streaming

```
User submits question
      │
      ▼
POST /api/v1/agents/sessions/{id}/chat
      │
      ▼
Orchestrator Agent
├── Classify intent → search task
└── Delegate → SearchRAGAgent
      │
      ▼
SearchRAGAgent
├── Embed query: Ollama bge-m3 → float[]
├── Query ChromaDB → top-k chunks
└── Build RAG prompt: system + chunks + question
      │
      ▼
Ollama (qwen3:8b) — streaming mode
      │
      ├── token → SSE: data: {"event":"token","content":"The "}
      ├── token → SSE: data: {"event":"token","content":"revenue..."}
      └── done  → SSE: data: {"event":"done","sources":[...]}
      │
      ▼
Client EventSource reads stream in real time
Frontend renders tokens progressively (ChatGPT-style)
```

---

## 7. Docker Compose Service Map

Nginx is a **required service**, not optional. It is the single public entry point and handles SSL termination in production. In dev, it is a simple pass-through proxy.

```
┌──────────────────────────────────────────────────────────┐
│                   Docker Network: docplat                 │
│                                                           │
│  ┌─────────────────────────────────────────────────┐    │
│  │                nginx (:80 / :443)                │    │
│  │   Routes: / → frontend:3000                      │    │
│  │            /api → backend:8000                   │    │
│  │            /api/v1/.*/stream → backend (SSE,     │    │
│  │              proxy_buffering off, keepalive)      │    │
│  └──────────────────────┬──────────────────────────┘    │
│                          │                                │
│         ┌────────────────┴─────────────────┐            │
│         ▼                                  ▼             │
│  ┌──────────────┐                ┌──────────────┐       │
│  │   frontend   │                │   backend    │       │
│  │   :3000      │                │   :8000      │       │
│  └──────────────┘                └──────────────┘       │
│                                         │                │
│              ┌──────────────────────────┼────────┐      │
│              ▼                          ▼        ▼      │
│  ┌─────────────────┐  ┌─────────────┐  ┌──────────────┐│
│  │    postgres      │  │  chromadb   │  │    ollama    ││
│  │    :5432         │  │  :8001      │  │    :11434    ││
│  │    mem: 512m     │  │  mem: 1g    │  │    mem: 12g  ││
│  └─────────────────┘  └─────────────┘  └──────────────┘│
│                                                           │
│  Named Volumes:                                           │
│  · postgres_data  · chromadb_data  · ollama_models       │
│  · uploads        · nginx_certs (prod only)              │
└──────────────────────────────────────────────────────────┘
```

### Nginx SSE Configuration (critical)

SSE connections must have buffering disabled or tokens won't reach the browser:

```nginx
location ~ ^/api/v1/.*/stream {
    proxy_pass         http://backend:8000;
    proxy_buffering    off;
    proxy_cache        off;
    proxy_read_timeout 600s;          # allow long-running agent calls
    proxy_set_header   Connection     '';
    proxy_http_version 1.1;
    chunked_transfer_encoding on;
}
```

### Docker Resource Limits

Required in `docker-compose.yml` to prevent OOM on low-RAM machines:

```yaml
ollama:
  deploy:
    resources:
      limits:
        memory: 12g
postgres:
  deploy:
    resources:
      limits:
        memory: 512m
chromadb:
  deploy:
    resources:
      limits:
        memory: 1g
```

---

## 8. Ollama Startup & Concurrency

### Model Pre-load Wait

On container startup, the backend must not serve agent requests until both Ollama models are loaded into RAM. qwen3:8b on CPU takes 30–120 seconds to load.

```
Backend startup sequence:
1. Connect to PostgreSQL — fail fast if unavailable
2. Run Alembic migrations
3. Connect to ChromaDB — fail fast if unavailable
4. Poll Ollama GET /api/tags every 5s until both models appear:
   - qwen3:8b in response list → chat model ready
   - bge-m3 in response list → embedding model ready
5. Mark application as ready — begin serving requests
```

`GET /health` returns `"status": "degraded"` with model loading status during step 4. The Docker healthcheck on the backend service uses `GET /health` so dependent services wait.

### Ollama Concurrency Model

Ollama on CPU processes **one generation request at a time**. Concurrent agent requests queue internally. This has the following implications:

| Scenario | Behavior |
|---|---|
| 1 active agent call | Normal — streaming tokens to user |
| 2 concurrent agent calls | Second call queues silently in Ollama |
| 3+ concurrent agent calls | All queue; first caller gets full bandwidth |
| Embedding during generation | Embedding request queues behind active generation |

**User-visible impact:** When multiple users use agents simultaneously, responses slow proportionally. For a team of 5 concurrent users, expect 5× slower response times.

**Mitigation:** The SSE stream shows tokens as they arrive. Even a slow stream (2–3 tokens/sec on CPU) feels responsive to the user because they see progress immediately.

### Agent Timeout Policy

Every agent invocation has a hard timeout enforced by the backend:

| Operation | Timeout |
|---|---|
| Embedding request | 60 seconds |
| Chat completion (search, review) | 180 seconds |
| Chat completion (edit, large doc) | 300 seconds |
| OCR (per page) | 30 seconds |

Timeout is configurable via `AGENT_TIMEOUT_SECONDS` env var (applies to chat completions). On timeout:
1. Backend marks `agent_tasks.status = 'failed'`, `timed_out = TRUE`
2. SSE stream sends `{"event":"error","code":"TIMEOUT"}`
3. Audit log records `agent.timed_out`

### Context Window Overflow Strategy

qwen3:8b with `OLLAMA_NUM_CTX=4096` holds approximately 3000 tokens of usable content space. A 50-page PDF produces far more.

**Strategy per agent:**

| Agent | Strategy |
|---|---|
| RAG Search | Retrieve top-k chunks (configurable, default 5). Chunks fit in context by design. |
| Reviewer | Sliding window: process document in 3000-token windows; aggregate issues from all windows into unified report. |
| Editor (summarize) | Send first 3000 tokens of document; note truncation in output. |
| Editor (other ops) | If target section provided: extract section only. Otherwise: send first 3000 tokens. |
| Signature | Does not use LLM for content generation; uses LLM only for field guidance text. |

**Document length warning:** When a document exceeds `OLLAMA_NUM_CTX * 0.75` tokens after text extraction, the API response and UI should display a warning: "This document is large. AI operations will process the first N tokens only."

---

## 9. Security Architecture

```
Request → Nginx → CORS Middleware → Rate Limiter → Auth Middleware → Route Handler
                                                          │
                                       ┌──────────────────┘
                                       ▼
                             JWT Token Verification
                                       │
                             ┌─────────┴────────┐
                             │                  │
                          Valid             Invalid
                             │                  │
                       RBAC Check         401 Unauthorized
                             │
                  ┌──────────┴──────────┐
                  │                     │
             Permitted             Forbidden
                  │                     │
          Route Handler          403 Forbidden
```

### File Upload Security

```
Upload request
    │
    ├── Validate extension is in allowlist (.pdf, .docx, .txt)
    │
    ├── Validate magic bytes match declared type:
    │   - PDF: header must start with %PDF-
    │   - DOCX: header must be PK (ZIP archive — DOCX is a ZIP)
    │   - TXT: no magic bytes; validate UTF-8 or chardet encoding detection
    │
    ├── Validate file size ≤ MAX_FILE_SIZE_MB
    │
    ├── Generate storage path: "{uuid}/original.{allowlisted_ext}"
    │   NEVER use user-provided filename in the path.
    │   Extension is taken from the allowlisted set, not from the filename.
    │
    └── Save to UPLOAD_DIR/{storage_path}
```

### SSE Authentication Flow

```
Client                     Backend
  │                            │
  │  POST /auth/sse-token      │
  │  Authorization: Bearer JWT │
  ├──────────────────────────► │
  │                            ├── Validate JWT
  │                            ├── Generate random 30-char token
  │                            ├── Store SHA-256(token) in sse_tokens table
  │  200 { sse_token: "..." }  │     expires_at = NOW() + 30s
  │ ◄──────────────────────────┤
  │                            │
  │  GET /stream?token=...     │
  ├──────────────────────────► │
  │                            ├── Lookup SHA-256(token) in sse_tokens
  │                            ├── Verify not expired, not used
  │                            ├── Mark used=TRUE
  │  text/event-stream opens   │
  │ ◄──────────────────────────┤
```

**Security note:** The SSE token in the query param appears in Nginx access logs. Nginx log format must be configured to redact the `token` parameter in SSE URLs, or logs must be access-controlled.

---

## 10. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Agent framework | Pure custom (Ollama SDK only) | No LangChain/LangGraph; full control, minimal dependencies |
| Chat model | qwen3:8b via Ollama | Capable 8B model; runs on CPU-only machines |
| Embedding model | bge-m3 via Ollama | Multilingual, high quality, fully local |
| Streaming | SSE (Server-Sent Events) | Simpler than WebSocket for one-directional token streaming |
| OCR | Tesseract (pytesseract) | Open source, installed in Docker image via apt |
| Background tasks | FastAPI BackgroundTasks | Simple, no extra broker; upgrade to Celery if needed |
| State management | PostgreSQL for session state | Persistent, queryable, no Redis dependency in v1 |
| API versioning | URL prefix /api/v1/ | Simple, explicit, easy to add v2 later |
| Frontend state | Zustand | Lightweight, minimal boilerplate vs Redux |
| CSS framework | Tailwind CSS + shadcn/ui | Consistent design system, copy-paste components |
| CPU optimization | Ollama num_ctx tuned low | Reduce memory pressure on CPU; configurable via env |
