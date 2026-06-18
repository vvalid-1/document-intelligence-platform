# CLAUDE.md — Document Intelligence Platform

## Project Summary

Full-stack Document Intelligence Platform. FastAPI backend, Next.js 14 frontend, PostgreSQL, ChromaDB vector database, Ollama local LLM (Qwen model), multi-agent architecture, Docker Compose deployment.

**No paid APIs. Everything runs locally.**

---

## Key Files

| File | Purpose |
|---|---|
| `ARCHITECTURE.md` | System design, agent architecture, data flows |
| `DATABASE_SCHEMA.md` | Full PostgreSQL schema + ChromaDB collection specs |
| `API_SPEC.md` | All REST endpoints, request/response schemas |
| `TASKS.md` | Development tasks, phases, and priorities |
| `IMPLEMENTATION_PLAN.md` | Phased build order with rationale |
| `PROJECT_SPEC.md` | Functional and non-functional requirements |

---

## Coding Standards

### Python (Backend)

- Python 3.11+
- Full type annotations on all functions and class attributes
- Pydantic v2 for all schemas (use `model_validator`, `field_validator`)
- SQLAlchemy 2.0 async ORM (use `AsyncSession`, `select()`)
- FastAPI dependency injection for DB sessions, current user, RBAC
- Async all the way — no blocking I/O in route handlers
- No bare `except:` — always catch specific exceptions
- Never log sensitive data (passwords, tokens, PII)

### TypeScript (Frontend)

- Strict mode (`"strict": true` in tsconfig.json)
- No `any` types — use `unknown` and narrow properly
- Use Next.js App Router patterns exclusively (no `pages/`)
- Server Components by default; use `"use client"` only when necessary
- API calls through `lib/api/` client, never raw fetch in components
- Zustand for global state; React state for component-local state

### General

- No comments explaining WHAT the code does — only WHY if non-obvious
- No TODO comments in committed code — create a TASKS.md entry instead
- Keep functions small — one responsibility
- No magic numbers or strings — use named constants or config

---

## Architecture Rules

1. **Agent isolation** — agents never call each other directly; the Orchestrator mediates all delegation
2. **No LangChain** — use Ollama Python SDK directly with custom tool call parsing + JSON fallback
3. **No Redis in v1** — session state in `agent_messages` table; SSE tokens in `sse_tokens` table
4. **Processing is async** — document upload returns 202; processing runs in background
5. **Versioning always** — every AI modification creates a `document_version` record, never overwrites
6. **Soft deletes** — documents never hard-deleted by users; only Admin can hard-delete
7. **Audit everything** — write to `audit_logs` for all document and agent operations
8. **SSE auth via ticket** — never pass JWT in SSE URL param; use `POST /auth/sse-token` short-lived ticket
9. **File paths are relative** — never store absolute paths; resolve from `UPLOAD_DIR` at runtime
10. **Delete ChromaDB first** — on document deletion, delete ChromaDB entries before soft-deleting in PG
11. **Agent timeout is mandatory** — all LLM calls wrapped in `asyncio.wait_for(timeout=AGENT_TIMEOUT_SECONDS)`
12. **Context window guard** — check token count before every LLM call; truncate at 85% of num_ctx
13. **Rate limiting from Phase 1** — never defer rate limiting to production hardening
14. **Magic byte validation** — always validate file header bytes, not just extension or MIME type

---

## Environment Variables

All config via pydantic-settings loaded from `.env`. Never hardcode:
- Database URLs
- JWT secrets
- File paths
- Model names
- Service hostnames

---

## Docker Notes

- `docker compose up -d` starts all services
- `docker compose exec backend alembic upgrade head` runs migrations
- `docker compose exec backend pytest` runs tests
- Backend volume mounts `./backend:/app` in dev mode for hot reload
- Ollama model pulled via `docker compose run ollama ollama pull <model>`
- All data is in named volumes (not bind mounts) in production

---

## Agent System Rules

- Each agent class extends `BaseAgent` in `backend/app/agents/base.py`
- Agents receive a `TaskPayload` dataclass and return an `AgentResult` dataclass
- System prompts live in `backend/app/agents/prompts/` as `.txt` files (not hardcoded in Python)
- All LLM calls go through `BaseAgent._call_ollama()` — never call Ollama SDK directly in a route
- Agent tasks are persisted in `agent_tasks` table before and after execution
- Tool call definitions use the Ollama-compatible format (OpenAI-style tools schema)

---

## Testing Approach

- Unit tests: `pytest` with `httpx.AsyncClient` for API tests
- Mock Ollama responses in tests — never hit real Ollama in CI
- Mock ChromaDB with `chromadb.EphemeralClient()` in tests
- Use PostgreSQL test DB (separate `docplat_test` database)
- Test files mirror source structure: `tests/api/`, `tests/agents/`, `tests/services/`

---

## Common Commands

```bash
# Start all services
docker compose up -d

# Apply DB migrations
docker compose exec backend alembic upgrade head

# Create a new migration
docker compose exec backend alembic revision --autogenerate -m "add_X_table"

# Run backend tests
docker compose exec backend pytest -v

# Run type checking
docker compose exec backend mypy app/

# Pull Ollama model
docker compose exec ollama ollama pull qwen2.5:7b

# View backend logs
docker compose logs -f backend

# Rebuild after code changes (dev)
docker compose up -d --build backend
```

---

## Open Questions

Before implementation begins, answers are needed for the items in the **Open Questions** section below. Do not start Phase 1 code until these are resolved.

---

## Confirmed Tech Decisions

| Decision | Value |
|---|---|
| Chat model | `qwen3:8b` via Ollama |
| Embedding model | `bge-m3` via Ollama |
| Supported file types | PDF (text + OCR), DOCX, TXT |
| OCR library | pytesseract (Tesseract installed in Dockerfile via apt) |
| Streaming | SSE (Server-Sent Events) — no WebSockets |
| Signatures | Electronic/visual only (typed or drawn PNG embedded in PDF) |
| Registration | First user → Admin auto; subsequent → Admin-only |
| Editor output | Both text-only and regenerated PDF |
| GPU | CPU-only — tune Ollama `num_ctx` and `num_thread` via env |
| Max file size | 50 MB default, configurable via `MAX_FILE_SIZE_MB` env var |
| Deployment | Must work on Docker Desktop (Windows/Mac) and Linux servers |

## Environment Variables (Key)

```
OLLAMA_HOST=http://ollama:11434
OLLAMA_CHAT_MODEL=qwen3:8b
OLLAMA_EMBED_MODEL=bge-m3
OLLAMA_NUM_CTX=4096
OLLAMA_NUM_THREAD=4
MAX_FILE_SIZE_MB=50
```

## Forbidden Patterns

- `import openai` — banned
- `import anthropic` — banned
- `from langchain` — banned (use direct Ollama SDK)
- `import langgraph` — banned
- `import crewai` — banned
- Hardcoded model names outside of config
- Synchronous database calls in async route handlers
- Raw SQL strings (use SQLAlchemy ORM)
- `print()` for logging (use the configured logger)
- File I/O outside of `services/` layer
- WebSocket for streaming — use SSE (StreamingResponse with text/event-stream)
