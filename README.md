# Document Intelligence Platform

A production-ready, fully local Document Intelligence Platform powered by multi-agent AI, semantic search, and intelligent document processing — with zero reliance on paid external APIs.

---

## Features

| Feature | Description |
|---|---|
| Multi-Agent AI | Orchestrator routes tasks to Search, Reviewer, Editor, and Signature agents |
| Semantic Chat | RAG pipeline over ChromaDB — ask questions, get cited answers |
| AI Review | Automated quality review: clarity, consistency, completeness, issue list |
| AI Edit | Natural language editing instructions applied by local LLM |
| Signatures | Typed or drawn e-signatures placed at (x, y) on any PDF page |
| Document Versioning | Every AI action creates a new version; originals are never overwritten |
| Full Audit Trail | All actions logged to `audit_logs` with user, timestamp, and details |
| Role-Based Access | Admin · Editor · Viewer roles with fine-grained endpoint guards |
| Fully Local LLM | Ollama + Qwen3:8b for chat/edit/review; bge-m3 for embeddings |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router, TypeScript, Tailwind CSS) |
| Backend | FastAPI 0.115 (Python 3.11, async SQLAlchemy 2.0) |
| Primary DB | PostgreSQL 16 |
| Vector DB | ChromaDB |
| LLM | Ollama — qwen3:8b (chat/edit/review) + bge-m3 (embeddings) |
| OCR | Tesseract (via pytesseract) |
| PDF | PyMuPDF (fitz) |
| Auth | JWT access tokens + opaque refresh tokens |
| Streaming | Server-Sent Events (SSE) |
| Proxy | Nginx |
| Runtime | Docker Compose |

---

## Quick Start

### Prerequisites

- Docker Desktop ≥ 4.x (or Docker Engine + Compose v2 on Linux)
- ≥ 12 GB RAM available to Docker (Ollama + models)
- ≥ 20 GB free disk space (models are ~5 GB each)

### 1. Clone and configure

```bash
git clone <repo-url>
cd document-plat
cp .env.example .env
```

Edit `.env` and set a strong `JWT_SECRET_KEY`:

```bash
# Generate a secure key
python3 -c "import secrets; print(secrets.token_hex(32))"
# Paste the output into .env as JWT_SECRET_KEY=<output>
```

### 2. Pull Ollama models (first-time only)

```bash
docker compose run --rm ollama ollama pull qwen3:8b
docker compose run --rm ollama ollama pull bge-m3
```

> **Time:** ~10–30 minutes on a typical internet connection. Models are cached in a named Docker volume (`ollama_models`) and persist across restarts.

### 3. Start all services

```bash
docker compose up -d
```

### 4. Run database migrations

```bash
docker compose exec backend alembic upgrade head
```

### 5. Create the first admin user

```bash
bash scripts/setup_demo.sh
# Default: admin@example.com / DemoPass123!
# Or: bash scripts/setup_demo.sh your@email.com YourPassword "Your Name"
```

### 6. Open the platform

| Service | URL |
|---|---|
| **Web UI** | http://localhost |
| API Docs (Swagger) | http://localhost/api/docs |
| API Docs (ReDoc) | http://localhost/api/redoc |
| Backend health | http://localhost/health |

---

## Demo Workflow

### Step 1 — Log in

Go to `http://localhost` and sign in with the credentials from Step 5.

### Step 2 — Upload a document

Click **Upload** in the sidebar → drop a PDF, DOCX, or TXT file → click **Upload and process**.

The document moves through `pending → processing → ready`. Processing extracts text, runs OCR if needed, splits into chunks, and indexes embeddings into ChromaDB. For a 10-page PDF this takes ~30 seconds on CPU.

### Step 3 — Chat with the document

Open the document → click **Chat**. Ask anything:
- *"Summarise the key points"*
- *"What are the main obligations in section 3?"*
- *"List all dates mentioned"*

Answers stream token-by-token from the local LLM with source citations.

### Step 4 — AI Review

Click **Review** → **Run AI review**. The reviewer agent reads the full document and returns:
- Clarity / Consistency / Completeness scores (0–100%)
- A prioritised issue list with suggestions

### Step 5 — AI Edit

Click **Edit** → type an instruction:
- *"Fix all grammar and spelling errors"*
- *"Make the tone more professional"*
- *"Add an executive summary at the beginning"*

The editor agent rewrites the document and creates a new version (v1, v2, …). The original is never modified.

### Step 6 — Sign

Click **Sign** → choose **Typed** or **Drawn** → click on the page preview to place the signature → click **Apply signature**. A signed PDF is stored as a new document version.

---

## Environment Variables

All variables are documented in `.env.example`. Key variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | PostgreSQL DSN (`postgresql+asyncpg://...`) |
| `JWT_SECRET_KEY` | Yes | — | ≥ 32 chars, cryptographically random |
| `OLLAMA_HOST` | No | `http://ollama:11434` | Ollama service URL |
| `OLLAMA_CHAT_MODEL` | No | `qwen3:8b` | Chat / edit / review model |
| `OLLAMA_EMBED_MODEL` | No | `bge-m3` | Embedding model |
| `OLLAMA_NUM_CTX` | No | `4096` | LLM context window (tokens) |
| `OLLAMA_NUM_THREAD` | No | `4` | CPU threads for Ollama |
| `CHROMADB_HOST` | No | `chromadb` | ChromaDB hostname |
| `CHROMADB_PORT` | No | `8000` | ChromaDB port |
| `UPLOAD_DIR` | No | `/app/uploads` | File storage path |
| `MAX_FILE_SIZE_MB` | No | `50` | Maximum upload size |
| `AGENT_TIMEOUT_SECONDS` | No | `300` | Per-agent LLM timeout |
| `CORS_ALLOWED_ORIGINS` | No | `http://localhost,...` | Comma-separated allowed origins |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` · `INFO` · `WARNING` · `ERROR` |

---

## Project Structure

```
document-plat/
├── backend/
│   ├── app/
│   │   ├── agents/          # BaseAgent + 5 agent classes
│   │   │   ├── base.py      # TaskPayload, AgentResult, _call_ollama
│   │   │   ├── orchestrator_agent.py
│   │   │   ├── rag_agent.py
│   │   │   ├── reviewer_agent.py
│   │   │   ├── editor_agent.py
│   │   │   └── signature_agent.py
│   │   ├── api/v1/          # FastAPI routers
│   │   ├── core/            # config, database, security, deps
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic v2 request/response schemas
│   │   ├── services/        # Business logic (PDF, vector, audit, signature)
│   │   └── utils/           # file_utils, logging
│   ├── alembic/             # DB migrations
│   ├── tests/               # 158 pytest tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js App Router pages
│   │   │   ├── (auth)/login/
│   │   │   └── (app)/       # dashboard, documents, [id]/{chat,review,edit,sign}
│   │   ├── components/      # Button, Input, Badge, Card, Sidebar, AuthGuard
│   │   ├── lib/             # API client, Zustand auth store
│   │   └── types/           # TypeScript API types
│   ├── Dockerfile
│   └── package.json
├── nginx/
│   └── conf.d/default.conf  # Reverse proxy + security headers
├── scripts/
│   ├── setup_demo.sh        # Create first admin user
│   └── ollama-entrypoint.sh # Ollama model auto-pull on first start
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## API Reference

The full interactive API is at `http://localhost/api/docs` (Swagger UI) or `http://localhost/api/redoc`.

### Key endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register (first user → Admin) |
| `POST` | `/api/v1/auth/login` | Login → access + refresh tokens |
| `GET` | `/api/v1/auth/me` | Current user profile |
| `POST` | `/api/v1/documents/` | Upload document (multipart) |
| `GET` | `/api/v1/documents/` | List documents (paginated) |
| `GET` | `/api/v1/documents/{id}` | Document detail |
| `POST` | `/api/v1/chat/sessions` | Create chat session |
| `POST` | `/api/v1/chat/sessions/{id}/messages` | Send message (SSE stream) |
| `POST` | `/api/v1/documents/{id}/review` | Run AI review |
| `POST` | `/api/v1/documents/{id}/edit` | Apply AI edit |
| `POST` | `/api/v1/documents/{id}/sign` | Apply signature |
| `GET` | `/api/v1/documents/{id}/signatures` | List signatures |
| `GET` | `/api/v1/admin/users` | List users (Admin only) |

---

## Common Operations

```bash
# Start all services
docker compose up -d

# Apply DB migrations
docker compose exec backend alembic upgrade head

# Create a new migration
docker compose exec backend alembic revision --autogenerate -m "description"

# Run backend tests
docker compose exec backend pytest -v

# View backend logs
docker compose logs -f backend

# Pull a different Ollama model
docker compose exec ollama ollama pull llama3.2

# Rebuild backend after code changes
docker compose up -d --build backend

# Rebuild frontend after code changes
docker compose up -d --build frontend

# Stop everything
docker compose down

# Stop and remove all data (destructive)
docker compose down -v
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| **Ollama not responding** | Run `docker compose logs ollama` — model may still be downloading |
| **Chat returns "timeout"** | Increase `AGENT_TIMEOUT_SECONDS` in `.env`; Qwen is slow on CPU |
| **Upload fails with 413** | File exceeds `MAX_FILE_SIZE_MB` (default 50 MB) |
| **"Document not ready"** | Wait for status to change from `processing` to `ready` |
| **Login says "Invalid credentials"** | Re-run `bash scripts/setup_demo.sh` to create the first user |
| **Frontend shows blank page** | Check `docker compose logs frontend`; rebuild with `--no-cache` if needed |
| **DB migration error** | Run `docker compose exec backend alembic upgrade head` |

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for system design, agent architecture, and data flows.

See [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for the full PostgreSQL schema.

See [API_SPEC.md](API_SPEC.md) for detailed request/response specifications.

---

## License

MIT
