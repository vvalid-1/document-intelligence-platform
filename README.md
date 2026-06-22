# Document Intelligence Platform

> **Version 2.0** · Fully local · No paid APIs · CPU-only · Docker Compose

A production-ready Document Intelligence Platform powered by a multi-agent AI system, semantic search, and intelligent document processing. Every AI capability — chat, review, editing, translation, transcription, and signing — runs entirely on your own machine using open-source models via Ollama and Faster-Whisper.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Multi-Agent Architecture](#3-multi-agent-architecture)
4. [Implemented Agents](#4-implemented-agents)
5. [Features](#5-features)
6. [Technology Stack](#6-technology-stack)
7. [Installation](#7-installation)
8. [Docker Setup](#8-docker-setup)
9. [Environment Variables](#9-environment-variables)
10. [Database Migrations](#10-database-migrations)
11. [Ollama Setup](#11-ollama-setup)
12. [Running the Project](#12-running-the-project)
13. [API Overview](#13-api-overview)
14. [Screenshots](#14-screenshots)
15. [Current Version — V2.0](#15-current-version--v20)
16. [Future Improvements](#16-future-improvements)

---

## 1. Project Overview

The Document Intelligence Platform is a self-hosted alternative to cloud-based document AI tools (Notion AI, Adobe Acrobat AI, Microsoft Copilot). It accepts PDF, DOCX, TXT, JPG, PNG, MP3, WAV, and MP4 files, processes them through a pipeline of AI agents, and exposes a modern dark-themed web interface.

**Key principles:**

- **Zero cloud dependency** — no OpenAI, Anthropic, Google, or any paid API
- **Privacy-first** — all data stays on your machine; nothing leaves the Docker network
- **Versioned** — every AI action creates a new document version; originals are never overwritten
- **Audited** — every operation is written to an audit log with user, timestamp, and action type
- **Role-based** — Admin, Editor, and Viewer roles with endpoint-level guards

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          Browser                                │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / SSE
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Nginx (port 80)                             │
│           Reverse proxy · Security headers · Routing           │
└──────────┬───────────────────────────────┬──────────────────────┘
           │ /api/*                         │ /*
           ▼                               ▼
┌──────────────────────┐       ┌──────────────────────┐
│   FastAPI Backend    │       │  Next.js 14 Frontend  │
│   Python 3.11        │       │  TypeScript · Tailwind│
│   Async SQLAlchemy   │       │  App Router · SSE     │
│   Pydantic v2        │       │  Zustand state        │
└──────────┬───────────┘       └──────────────────────┘
           │
    ┌──────┴────────────────────────────┐
    │                                   │
    ▼                                   ▼
┌────────────────┐           ┌──────────────────────┐
│  PostgreSQL 16  │           │   ChromaDB 0.5.23    │
│  Primary store  │           │   Vector embeddings  │
│  Users, docs,   │           │   Semantic search    │
│  versions,      │           │   RAG retrieval      │
│  audit logs     │           └──────────────────────┘
└────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│                   Ollama (CPU-only)                       │
│                                                          │
│   qwen2.5:3b  ──── Chat · Review · Edit · Translate     │
│                    Media Analysis                        │
│                                                          │
│   bge-m3      ──── Embeddings · Semantic search         │
└──────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│               Faster-Whisper (CPU · int8)                │
│               base model · VAD filtering                 │
│               MP3 / WAV / MP4 transcription              │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Multi-Agent Architecture

All agents extend a shared `BaseAgent` class (`backend/app/agents/base.py`). The Orchestrator receives a task, selects the appropriate agent, and returns the result. Agents never call each other directly — all delegation goes through the Orchestrator.

```
                    ┌─────────────────┐
                    │   Orchestrator   │
                    │     Agent        │
                    └────────┬────────┘
                             │ delegates to
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
   │  RAG Agent  │   │  Reviewer   │   │   Editor    │
   │  (Chat)     │   │   Agent     │   │   Agent     │
   └─────────────┘   └─────────────┘   └─────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
   │ Translation │   │  Signature  │   │   Media     │
   │   Agent     │   │   Agent     │   │  Analysis   │
   └─────────────┘   └─────────────┘   │   Agent     │
                                        └─────────────┘
```

**Agent execution contract:**

- Each agent receives a `TaskPayload` dataclass and returns an `AgentResult`
- All LLM calls go through `BaseAgent._call_ollama()` — never directly in route handlers
- Every call is wrapped in `asyncio.wait_for(timeout=AGENT_TIMEOUT_SECONDS)`
- Token count is checked before every LLM call; input is truncated at 85% of `num_ctx`
- System prompts live in `backend/app/agents/prompts/*.txt` — not hardcoded in Python
- Every task is persisted to `agent_tasks` table before and after execution

---

## 4. Implemented Agents

### Chat Agent (RAG Agent)

Answers questions about a specific document using Retrieval-Augmented Generation.

- Embeds the user query with `bge-m3` via Ollama
- Retrieves the top-k semantically similar chunks from ChromaDB
- Feeds chunks + query to `qwen2.5:3b` with a grounding system prompt
- Streams the answer token-by-token to the browser via SSE
- Cites source chunks in the response

**Endpoint:** `POST /api/v1/documents/{id}/chat`

---

### Review Agent

Performs an automated quality review of the full document text.

- Reads the complete document text from indexed chunks
- Instructs `qwen2.5:3b` to evaluate clarity, consistency, and completeness
- Returns a scored issue list: each issue has a severity (high / medium / low), type, description, location, and suggestion
- Returns an `overall_score` (0–100) displayed as an animated SVG ring in the UI

**Endpoint:** `POST /api/v1/documents/{id}/review`

---

### Edit Agent

Applies natural language editing instructions to a document.

- Accepts a free-text instruction (e.g. "Fix all grammar errors", "Make the tone more formal")
- Sends the full document text + instruction to `qwen2.5:3b`
- Creates a new `DocumentVersion` — the original is never modified
- Returns the edited text as both a downloadable PDF and TXT file

**Endpoint:** `POST /api/v1/documents/{id}/edit`

---

### Translation Agent

Translates documents between English, French, and Arabic.

- Sends document text + target language to `qwen2.5:3b`
- Creates a new `DocumentVersion(agent_name="translator")`
- Supports Arabic RTL text rendering in the preview pane
- Returns a downloadable PDF and TXT in the target language

**Endpoint:** `POST /api/v1/documents/{id}/translate`

---

### Signature Agent

Embeds electronic signatures into PDF documents at precise coordinates.

- Supports three input modes: **Typed** text, **Drawn** (canvas), or **Uploaded PNG**
- Accepts `x`, `y` (PDF point coordinates), `page_number`, and optional `field_name`
- Uses PyMuPDF to embed the signature image into the PDF at the given position
- Creates a new `DocumentVersion` with the signed PDF
- The UI includes a clickable A4 page grid for visual placement

**Endpoint:** `POST /api/v1/documents/{id}/sign`

---

### Media Analysis Agent

Transcribes and analyses audio/video files (MP3, WAV, MP4).

- **Transcription:** Faster-Whisper `base` model, CPU-only, `int8` compute, VAD filtering
- **Analysis:** `qwen2.5:3b` extracts summary, key topics, action items, important dates, and important numbers from the transcript
- Transcript chunks are indexed in ChromaDB — media files are searchable via global search
- Processing pipeline: transcribing → chunking → embedding → analyzing → ready
- Transcript stored as TXT and summary stored as PDF in a `DocumentVersion`

**Endpoint:** `GET /api/v1/documents/{id}/media-analysis`  
**Re-run:** `POST /api/v1/documents/{id}/media-analysis`

---

## 5. Features

### Upload

- Accepted formats: **PDF**, **DOCX**, **TXT**, **JPG**, **JPEG**, **PNG**, **MP3**, **WAV**, **MP4**
- Maximum file size: 50 MB (configurable via `MAX_FILE_SIZE_MB`)
- Magic byte validation on all uploads — extension and MIME type alone are not trusted
- Upload returns HTTP 202 immediately; processing runs as a background task
- Status transitions: `pending → processing → ready` (or `error`)
- Real-time processing progress streamed to the UI via SSE

### OCR

- Scanned PDFs with low text density (< 10 characters per page) are automatically OCR-processed using Tesseract
- Image files (JPG, JPEG, PNG) are always OCR-extracted
- Language packs: English, French, Arabic (installed in backend Dockerfile)
- Processing step shown as `"ocr"` in the status stream

### Search

- Global semantic search across all documents using `bge-m3` embeddings in ChromaDB
- No LLM call — pure vector retrieval (sub-second response)
- Results grouped by document, ranked by best cosine similarity score
- Optional folder filter to restrict results to a specific collection
- Soft-deleted and inaccessible documents filtered via PostgreSQL post-check
- Viewer role: only their own documents appear in results

### Version Comparison (Diff Viewer)

- Side-by-side view of any two document versions
- Pure TypeScript LCS diff engine — no external library
- Unified diff view with dual line numbers
- Synchronized proportional scroll between panels
- Stat chips showing added / removed / unchanged line counts

### Folders

- Create named folders to organise documents into collections
- Rename and delete folders (deletion unassigns documents, does not delete them)
- Move documents between folders individually or in bulk (up to 50 at once)
- Filter the document library and search results by folder
- Dashboard shows total folder count with a link

### Favorites (Starred)

- Star/unstar any document with a single click from the document list or detail page
- Starred filter tab on the document library page
- Dedicated `/favorites` page with paginated starred document list
- Bulk star/unstar up to 50 documents at once
- Dashboard shows starred document count with a link

### Archive

- Archive documents to remove them from the active library without deleting them
- Archived documents are excluded from global search results and stats
- Restore archived documents in one click
- Bulk archive and bulk restore supported
- Dedicated `/archived` page with full paginated list

### Trash

- Deleting a document moves it to trash (soft delete) — ChromaDB vectors are preserved for instant restore
- Restore from trash returns the document to the active library
- Permanent delete (Admin only): deletes ChromaDB vectors first, then removes the database row
- Dedicated `/trash` page with Restore and Delete Forever actions
- Dashboard shows trash count with a link

### Media Analysis

- Upload MP3, WAV, or MP4 files and the platform automatically transcribes and analyses them
- Full transcript displayed in a scrollable viewer on the media analysis page
- AI-extracted fields: executive summary, key topics, action items, important dates, important numbers
- Download transcript as TXT or summary as PDF
- Re-analyze button to re-run the AI analysis on an existing transcript
- Media files are fully searchable via global search (transcript indexed in ChromaDB)

### Translation

- Translate any document into **English**, **French**, or **Arabic** with a single click
- Preview the translated text directly in the UI before downloading
- Arabic translation renders with RTL text direction and correct `lang` attribute
- Each translation creates a new document version — original is preserved
- Download the translation as PDF or TXT

### Signature

- Apply electronic signatures to any PDF document
- Three signature modes: Typed text, Drawn (HTML canvas), or Uploaded PNG image
- Click-to-place on an A4 page grid preview, or enter exact PDF point coordinates
- Optional field name label per signature (e.g. "Approver", "Witness")
- Each signature creates a new document version with the signature embedded

---

## 6. Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Frontend framework | Next.js (App Router) | 14 |
| Frontend language | TypeScript | 5.x |
| Frontend styling | Tailwind CSS | 3.x |
| Frontend state | Zustand | 4.x |
| Backend framework | FastAPI | 0.115 |
| Backend language | Python | 3.11 |
| ORM | SQLAlchemy (async) | 2.0 |
| Schema validation | Pydantic | v2 |
| Primary database | PostgreSQL | 16 |
| Vector database | ChromaDB | 0.5.23 |
| Container orchestration | Docker Compose | v2 |
| Reverse proxy | Nginx | alpine |
| LLM runtime | Ollama | latest |
| Chat / Edit / Review model | qwen2.5:3b | via Ollama |
| Embedding model | bge-m3 | via Ollama |
| Transcription | Faster-Whisper | 1.0.3 |
| OCR | Tesseract + pytesseract | 5.x |
| PDF processing | PyMuPDF (fitz) | latest |
| Audio/video decoding | ffmpeg | system |
| Authentication | JWT (HS256) + opaque refresh tokens | — |
| Streaming | Server-Sent Events (SSE) | — |
| Migrations | Alembic | 1.x |

### Faster-Whisper

Faster-Whisper is a reimplementation of OpenAI's Whisper model using CTranslate2. It runs entirely on CPU using `int8` quantisation, making transcription feasible on commodity hardware without a GPU. The `base` model is used by default — it supports automatic language detection and VAD (Voice Activity Detection) filtering to skip silence.

---

## 7. Installation

> For a full step-by-step installation guide including platform-specific instructions, see [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md).

### Prerequisites

| Software | Version |
|---|---|
| Docker Desktop | 24.x or later |
| Docker Compose | v2 (bundled with Docker Desktop) |
| Git | 2.x |

**Minimum hardware:** 8 GB RAM · 4 CPU cores · 20 GB free disk  
**Recommended:** 16 GB RAM · 8 CPU cores · 40 GB free disk

### Quick Start

```bash
# 1. Clone
git clone https://github.com/vvalid-1/document-intelligence-platform.git
cd document-intelligence-platform

# 2. Configure environment
cp .env.example .env
# Generate a JWT secret and paste it into .env as JWT_SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# 3. Start all services (first run takes 10–15 min for model downloads)
docker compose up -d

# 4. Apply database migrations
docker compose exec backend alembic upgrade head

# 5. Open the platform
# http://localhost
# The first user to register becomes Admin automatically
```

---

## 8. Docker Setup

The platform runs as six Docker services orchestrated by Docker Compose:

| Service | Image | Role |
|---|---|---|
| `nginx` | nginx:alpine | Single public entry point on port 80 |
| `backend` | custom build | FastAPI application |
| `frontend` | custom build | Next.js application |
| `postgres` | postgres:16-alpine | Primary relational database |
| `chromadb` | chromadb/chroma:0.5.23 | Vector store |
| `ollama` | ollama/ollama:latest | LLM and embedding inference |

### Persistent volumes

| Volume | Contents |
|---|---|
| `postgres_data` | All PostgreSQL data |
| `chromadb_data` | All ChromaDB vector data |
| `ollama_models` | Downloaded Ollama models |
| `uploads` | Uploaded files + Whisper model cache |

### Common Docker commands

```bash
# Start everything (subsequent starts — no rebuild, no migration needed)
docker compose up -d

# View all service statuses (all 6 should show healthy or running)
docker compose ps

# Follow logs for a specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f ollama
docker compose logs -f postgres
docker compose logs -f chromadb
docker compose logs -f nginx

# Restart a single service without rebuilding (e.g. after .env change)
docker compose restart backend
docker compose restart frontend

# Rebuild and restart after code changes
docker compose up -d --build backend
docker compose up -d --build frontend

# Stop all services — DATA IS PRESERVED (postgres, chromadb, uploads, models)
docker compose down

# Full reset — DESTROYS ALL DATA AND VOLUMES — use with caution
docker compose down -v
```

### Updating from GitHub

Pull the latest code, rebuild any changed images, and apply any new migrations:

```bash
git pull origin master
docker compose up -d --build backend frontend
docker compose exec backend alembic upgrade head
```

> If only documentation or frontend-only changes were pulled, you can skip rebuilding the backend (and vice versa). When in doubt, rebuild both — it is safe to do so.

---

## 9. Environment Variables

Copy `.env.example` to `.env` and edit before first startup.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DB_USER` | No | `docplat` | PostgreSQL username |
| `DB_PASSWORD` | No | `change_me_in_production` | PostgreSQL password |
| `DB_NAME` | No | `docplat` | PostgreSQL database name |
| `JWT_SECRET_KEY` | **Yes** | — | Cryptographically random, min 32 chars. Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token lifetime |
| `OLLAMA_HOST` | No | `http://ollama:11434` | Ollama service URL (do not change for Docker) |
| `OLLAMA_CHAT_MODEL` | No | `qwen2.5:3b` | LLM for chat, review, edit, translate, media analysis |
| `OLLAMA_EMBED_MODEL` | No | `bge-m3` | Embedding model for semantic search |
| `OLLAMA_NUM_CTX` | No | `4096` | Context window in tokens |
| `OLLAMA_NUM_THREAD` | No | `4` | CPU threads for Ollama |
| `OLLAMA_NUM_PREDICT` | No | `1024` | Max tokens per LLM response |
| `CHROMADB_HOST` | No | `chromadb` | ChromaDB hostname |
| `CHROMADB_PORT` | No | `8000` | ChromaDB port |
| `UPLOAD_DIR` | No | `/app/uploads` | File storage path inside container |
| `MAX_FILE_SIZE_MB` | No | `50` | Maximum upload size in MB |
| `AGENT_TIMEOUT_SECONDS` | No | `300` | Per-agent LLM call timeout in seconds |
| `MAX_CHAT_MESSAGE_CHARS` | No | `8000` | Character limit per chat message |
| `CHUNK_SIZE` | No | `500` | Document chunk size for vector indexing |
| `CHUNK_OVERLAP` | No | `100` | Overlap between consecutive chunks |
| `CORS_ALLOWED_ORIGINS` | No | `http://localhost,http://localhost:80` | Allowed CORS origins (comma-separated) |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` · `INFO` · `WARNING` · `ERROR` |

---

## 10. Database Migrations

Migrations are managed by Alembic. They must be applied after first startup and after any update that includes schema changes.

```bash
# Apply all pending migrations
docker compose exec backend alembic upgrade head

# Check current migration version
docker compose exec backend alembic current

# View migration history
docker compose exec backend alembic history

# Create a new migration (developers)
docker compose exec backend alembic revision --autogenerate -m "describe_change_here"
```

### Migration history

| Migration | Description |
|---|---|
| `0001` | Initial schema: users, documents, versions, audit logs, agent tasks, SSE tokens |
| `0002` | Chat sessions and messages |
| `0003` | Translation agent constraint |
| `0004` | Archive columns (`is_archived`, `archived_at`) |
| `0005` | Favorites column (`is_favorite`) |
| `0006` | Folders table + `folder_id` on documents (FK with `ON DELETE SET NULL`) |
| `0007` | Media duration column (`media_duration_seconds`) |

---

## 11. Ollama Setup

Ollama is the LLM runtime. It hosts the `qwen2.5:3b` chat model and the `bge-m3` embedding model, both running on CPU.

### Automatic model pull

On first startup, the Ollama container runs `scripts/ollama-entrypoint.sh` which automatically pulls both models if they are not already cached:

```bash
docker compose logs -f ollama
# Output:
# [ollama-entrypoint] Pulling model 'qwen2.5:3b'...
# [ollama-entrypoint] Model 'qwen2.5:3b' pulled successfully.
# [ollama-entrypoint] Pulling model 'bge-m3'...
# [ollama-entrypoint] All models ready. Keeping Ollama running...
```

Models are stored in the `ollama_models` named volume and persist across container restarts.

### Manual model management

```bash
# Pull a model manually
docker compose exec ollama ollama pull qwen2.5:3b
docker compose exec ollama ollama pull bge-m3

# List downloaded models
docker compose exec ollama ollama list

# Remove a model
docker compose exec ollama ollama rm qwen2.5:3b
```

### Upgrading to a larger model

If you have 16 GB+ RAM and want better output quality:

```bash
# In .env
OLLAMA_CHAT_MODEL=qwen3:8b
OLLAMA_NUM_CTX=8192

# Pull and restart
docker compose exec ollama ollama pull qwen3:8b
docker compose restart backend
```

---

## 12. Running the Project

### Start

```bash
docker compose up -d
```

### Access

| URL | Description |
|---|---|
| `http://localhost` | Web application |
| `http://localhost/api/docs` | Swagger UI (interactive API) |
| `http://localhost/api/redoc` | ReDoc API documentation |
| `http://localhost/api/v1/health` | Backend health check |

### First login

The first user to register via the web UI is automatically assigned the Admin role. All subsequent users require Admin approval.

### Run tests

```bash
# Full test suite (225 tests)
docker compose exec backend pytest -v

# Specific test file
docker compose exec backend pytest tests/api/test_media.py -v

# With coverage
docker compose exec backend pytest --cov=app -v
```

### Type checking

```bash
docker compose exec backend mypy app/
```

---

## 13. API Overview

The full interactive API is available at `http://localhost/api/docs`.

### Authentication

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register (first user → Admin) |
| `POST` | `/api/v1/auth/login` | Login — returns access + refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `GET` | `/api/v1/auth/me` | Current user profile |
| `POST` | `/api/v1/auth/sse-token` | Short-lived SSE ticket (never pass JWT in URL) |

### Documents

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/documents` | List documents (filters: `archived`, `favorite`, `trashed`, `folder_id`) |
| `POST` | `/api/v1/documents` | Upload document — returns 202, processing is async |
| `GET` | `/api/v1/documents/stats` | Dashboard counts |
| `GET` | `/api/v1/documents/{id}` | Document detail |
| `PATCH` | `/api/v1/documents/{id}` | Rename document |
| `DELETE` | `/api/v1/documents/{id}` | Move to trash (soft delete) |
| `DELETE` | `/api/v1/documents/{id}/permanent` | Hard delete — Admin only |
| `POST` | `/api/v1/documents/{id}/archive` | Archive |
| `POST` | `/api/v1/documents/{id}/restore` | Restore from archive |
| `POST` | `/api/v1/documents/{id}/favorite` | Star |
| `POST` | `/api/v1/documents/{id}/unfavorite` | Unstar |
| `POST` | `/api/v1/documents/{id}/untrash` | Restore from trash |
| `POST` | `/api/v1/documents/{id}/move` | Move to folder (`folder_id: null` removes from folder) |
| `GET` | `/api/v1/documents/{id}/text` | Full extracted text |
| `GET` | `/api/v1/documents/{id}/status` | Processing status |
| `GET` | `/api/v1/documents/{id}/status/stream` | SSE processing progress stream |
| `GET` | `/api/v1/documents/{id}/versions` | Version list |
| `GET` | `/api/v1/documents/{id}/versions/{vid}/download` | Download version as PDF or TXT |

### AI Agents

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/documents/{id}/chat` | RAG Q&A — streams SSE tokens |
| `POST` | `/api/v1/documents/{id}/review` | AI quality review |
| `POST` | `/api/v1/documents/{id}/edit` | Natural language edit |
| `POST` | `/api/v1/documents/{id}/translate` | Translate (EN / FR / AR) |
| `POST` | `/api/v1/documents/{id}/sign` | Apply signature |
| `GET` | `/api/v1/documents/{id}/signatures` | List signatures |
| `GET` | `/api/v1/documents/{id}/media-analysis` | Get transcript + AI analysis |
| `POST` | `/api/v1/documents/{id}/media-analysis` | Re-run AI analysis |

### Bulk Actions

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/documents/bulk/archive` | Archive up to 50 documents |
| `POST` | `/api/v1/documents/bulk/restore` | Restore archived documents |
| `POST` | `/api/v1/documents/bulk/trash` | Trash multiple documents |
| `POST` | `/api/v1/documents/bulk/favorite` | Star or unstar multiple documents |
| `POST` | `/api/v1/documents/bulk/move` | Move multiple documents to a folder |

### Folders

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/folders` | List folders with document counts |
| `POST` | `/api/v1/folders` | Create folder |
| `PATCH` | `/api/v1/folders/{id}` | Rename folder |
| `DELETE` | `/api/v1/folders/{id}` | Delete folder |
| `GET` | `/api/v1/folders/{id}/documents` | Documents inside a folder |

### Search & Admin

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/search` | Global semantic search (optional `folder_id` filter) |
| `GET` | `/api/v1/admin/users` | List all users — Admin only |
| `PATCH` | `/api/v1/admin/users/{id}` | Update role or status |
| `DELETE` | `/api/v1/admin/users/{id}` | Hard delete user |

---

## 14. Screenshots

> The platform uses a dark premium design system with glassmorphism cards, indigo/violet gradient accents, SVG icons, shimmer loading states, and smooth hover animations.

| Page | Description |
|---|---|
| **Dashboard** | 9 clickable stat cards (Documents, Ready, Chats, Reviews, Edits, Translations, Signatures, Folders, Media), recent documents table, AI activity feed |
| **Document Library** | Dark table with per-row star toggle, folder badge, bulk checkboxes, filter tabs (All / Starred / Archived / Trash), bulk action bar |
| **Upload** | Drag-and-drop zone with file type pills, animated progress, SVG file type icons |
| **Document Detail** | AI workspace cards per action type, info grid, version history, signature list, activity timeline |
| **Chat** | Split-screen PDF preview + chat with SSE token streaming, typing dots animation, gradient user bubbles |
| **Review** | Animated SVG score ring, severity summary (high/medium/low dots), issue cards with suggestions |
| **Edit** | Instruction input with example chips, emerald result panel with text preview |
| **Translate** | Language selector buttons with flag emoji and active glow, RTL preview for Arabic |
| **Sign** | Mode tabs (Typed/Draw/Upload), clickable A4 grid for placement, indigo coordinate marker |
| **Media Analysis** | Transcript viewer, summary card, section cards per category (topics/actions/dates/numbers) |
| **Search** | Unified search input, grouped results by document, similarity bars, folder filter dropdown |
| **Folders** | Glass folder cards with document count, inline rename form |
| **Favorites / Archived / Trash** | Dark tables with relevant actions per page |

---

## 15. Current Version — V2.0

**Released:** June 2026  
**Git tag:** `master` @ `c10600e`  
**Test suite:** 225 / 225 passing  
**Frontend build:** `✓ Compiled successfully` (no TypeScript errors)

### V2.0 — Meeting & Media Intelligence

The V2.0 release adds full audio and video intelligence to the platform:

- MP3, WAV, and MP4 file upload with magic byte validation
- Automatic transcription using Faster-Whisper (CPU-only, `base` model, VAD filtering, language auto-detection)
- AI analysis of transcripts: executive summary, key topics, action items, important dates, important numbers
- Transcript indexed in ChromaDB — media content is fully searchable via global search
- Re-analyze endpoint for re-running AI analysis without re-transcribing
- Dedicated media analysis page with transcript viewer and section cards

### Full Version History

| Version | Feature |
|---|---|
| V1.0 | Core platform: upload, RAG chat, AI review, AI edit, signature, JWT auth, RBAC, audit log |
| V1.1 | Inline PDF viewer, chat history sidebar, document workspace layout, activity timeline |
| V1.2 | Canvas draw signature, UI component library, dashboard statistics |
| V1.3 | Translation Agent (EN / FR / AR), Arabic RTL support |
| V1.4 | Version Comparison and Diff Viewer (LCS diff, side-by-side + unified views) |
| V1.5 | OCR for scanned PDFs and images (JPG/JPEG/PNG), French and Arabic Tesseract packs |
| V1.6 | Global semantic search across all documents via ChromaDB |
| V1.7 | Archive and restore documents |
| V1.8 | Favorites, Trash Bin, Bulk Actions (archive / restore / trash / star / move) |
| V1.9 | Folders / Collections with document assignment and folder-scoped search |
| **V2.0** | **Meeting & Media Intelligence: MP3/WAV/MP4 transcription + AI analysis** |

---

## 16. Future Improvements

| ID | Feature | Notes |
|---|---|---|
| V2.1 | YouTube URL transcription | Feed a YouTube URL → download audio → Faster-Whisper (no new model needed) |
| V2.2 | Report Generator | Auto-generate a structured PDF report from one or more documents |
| — | Search pagination | Add `offset` / `page` to `SearchRequest` and `SearchResponse` |
| — | Rate limiting on `/search` | Add slowapi limiter (e.g. 20 req/min per user) |
| — | Viewer role UI restrictions | Currently no viewer-specific frontend restrictions |
| — | Document sharing | Share a read-only link without requiring login |
| — | Webhook notifications | Notify when async document processing completes |
| — | Hide "Delete forever" for non-admins | Add front-end role check on the Trash page |
| — | GPU support | Enable Ollama GPU passthrough for faster LLM inference |

---

## Project Structure

```
document-intelligence-platform/
├── backend/
│   ├── app/
│   │   ├── agents/                    # AI agent system
│   │   │   ├── base.py                # BaseAgent, TaskPayload, AgentResult
│   │   │   ├── orchestrator_agent.py
│   │   │   ├── rag_agent.py           # Chat / Q&A
│   │   │   ├── reviewer_agent.py
│   │   │   ├── editor_agent.py
│   │   │   ├── translation_agent.py
│   │   │   ├── signature_agent.py
│   │   │   ├── media_agent.py         # Transcription + AI analysis
│   │   │   └── prompts/               # System prompts as .txt files
│   │   ├── api/v1/                    # FastAPI routers
│   │   ├── core/                      # Config, database, security, deps
│   │   ├── models/                    # SQLAlchemy ORM models
│   │   ├── schemas/                   # Pydantic v2 schemas
│   │   ├── services/                  # PDF, vector, audit, transcription
│   │   └── utils/                     # file_utils, logging
│   ├── alembic/                       # Database migrations (0001–0007)
│   ├── tests/                         # 225 pytest tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/login/
│   │   │   └── (app)/                 # All authenticated pages
│   │   │       ├── dashboard/
│   │   │       ├── documents/
│   │   │       │   ├── upload/
│   │   │       │   └── [id]/
│   │   │       │       ├── chat/
│   │   │       │       ├── review/
│   │   │       │       ├── edit/
│   │   │       │       ├── translate/
│   │   │       │       ├── sign/
│   │   │       │       ├── compare/
│   │   │       │       └── media-analysis/
│   │   │       ├── search/
│   │   │       ├── folders/
│   │   │       ├── favorites/
│   │   │       ├── archived/
│   │   │       └── trash/
│   │   ├── components/
│   │   │   ├── layout/                # Sidebar, AuthGuard
│   │   │   └── ui/                    # Button, Card, Badge, Input, etc.
│   │   ├── lib/
│   │   │   ├── api/                   # API client functions
│   │   │   └── store/                 # Zustand auth store
│   │   └── types/                     # TypeScript API types
│   ├── Dockerfile
│   └── package.json
├── nginx/
│   └── conf.d/default.conf
├── scripts/
│   └── ollama-entrypoint.sh           # Auto-pulls models on first start
├── docker-compose.yml
├── .env.example
├── INSTALLATION_GUIDE.md
├── ARCHITECTURE.md
├── DATABASE_SCHEMA.md
├── API_SPEC.md
└── README.md
```

---

## License

MIT
