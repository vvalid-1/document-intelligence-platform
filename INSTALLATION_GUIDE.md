# Installation Guide — Document Intelligence Platform

> **Everything runs locally. No paid APIs, no cloud dependencies.**
> All AI processing (LLM inference, embeddings, OCR, transcription) happens on your machine inside Docker containers.

---

## Table of Contents

1. [Required Software](#1-required-software)
2. [Install Docker](#2-install-docker)
3. [Install Git](#3-install-git)
4. [Clone the Repository](#4-clone-the-repository)
5. [Environment Variables](#5-environment-variables)
6. [First Startup](#6-first-startup)
7. [Database Migrations](#7-database-migrations)
8. [Ollama & Model Setup](#8-ollama--model-setup)
9. [Verify Everything Is Running](#9-verify-everything-is-running)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Required Software

| Software | Minimum Version | Purpose |
|---|---|---|
| Docker Desktop | 24.x or later | Runs all services in containers |
| Docker Compose | v2 (bundled with Docker Desktop) | Orchestrates multi-container setup |
| Git | 2.x | Cloning the repository |

**You do NOT need to install Python, Node.js, PostgreSQL, or Ollama directly.** All dependencies run inside Docker containers.

### Minimum Hardware

| Resource | Minimum | Recommended |
|---|---|---|
| RAM | 8 GB | 16 GB |
| Disk space | 20 GB free | 40 GB free |
| CPU cores | 4 | 8+ |
| GPU | Not required | NVIDIA GPU speeds up LLM inference significantly |

> Ollama is configured for **CPU-only** by default. The `qwen2.5:3b` model runs on 8 GB RAM. Switching to `qwen3:8b` requires at least 16 GB RAM.

---

## 2. Install Docker

### Windows

1. Download **Docker Desktop for Windows** from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
2. Run the installer — enable the **WSL 2** backend when prompted
3. After installation, open Docker Desktop and wait for the engine to start (whale icon in system tray turns solid)
4. Verify in a terminal:
   ```
   docker --version
   docker compose version
   ```

> Docker Desktop must be **running** before you execute any `docker compose` commands.

### macOS

1. Download **Docker Desktop for Mac** (choose Apple Silicon or Intel based on your chip)
2. Drag to Applications and launch
3. Verify:
   ```
   docker --version
   docker compose version
   ```

### Linux

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

---

## 3. Install Git

### Windows

Download and run the installer from [git-scm.com](https://git-scm.com/download/win). Accept all defaults.

Verify:
```
git --version
```

### macOS

```bash
# Xcode command line tools (includes Git)
xcode-select --install
git --version
```

### Linux (Debian/Ubuntu)

```bash
sudo apt update && sudo apt install -y git
git --version
```

---

## 4. Clone the Repository

```bash
git clone https://github.com/vvalid-1/document-intelligence-platform.git
cd document-intelligence-platform
```

Your working directory is now `document-intelligence-platform/`. All subsequent commands run from this directory.

---

## 5. Environment Variables

The platform is configured via a `.env` file in the project root. A template is provided.

### Step 1 — Copy the template

```bash
cp .env.example .env
```

On Windows (Command Prompt):
```
copy .env.example .env
```

### Step 2 — Generate a secure JWT secret

**This is required.** The backend refuses to start with the placeholder value.

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and paste it as the value of `JWT_SECRET_KEY` in your `.env` file.

### Step 3 — Edit `.env`

Open `.env` in any text editor and set at minimum:

```env
# ─── Database ────────────────────────────────────────────────────────────────
DB_USER=docplat
DB_PASSWORD=change_me_in_production      # change this for any non-local deployment
DB_NAME=docplat

# ─── Ollama ──────────────────────────────────────────────────────────────────
OLLAMA_HOST=http://ollama:11434
OLLAMA_CHAT_MODEL=qwen2.5:3b             # CPU-friendly default
OLLAMA_EMBED_MODEL=bge-m3
OLLAMA_NUM_CTX=4096                      # increase to 8192 if you have 16 GB+ RAM
OLLAMA_NUM_THREAD=4                      # set to your CPU core count

# ─── JWT Authentication ───────────────────────────────────────────────────────
JWT_SECRET_KEY=<paste your generated secret here>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ─── File Storage ─────────────────────────────────────────────────────────────
MAX_FILE_SIZE_MB=50

# ─── Agent Settings ───────────────────────────────────────────────────────────
AGENT_TIMEOUT_SECONDS=300
MAX_CHAT_MESSAGE_CHARS=8000

# ─── Security ─────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS=http://localhost,http://localhost:80

# ─── Observability ────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
```

### Full Variable Reference

| Variable | Default | Description |
|---|---|---|
| `DB_USER` | `docplat` | PostgreSQL username |
| `DB_PASSWORD` | `change_me_in_production` | PostgreSQL password |
| `DB_NAME` | `docplat` | PostgreSQL database name |
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama service URL (do not change for Docker) |
| `OLLAMA_CHAT_MODEL` | `qwen2.5:3b` | LLM used for all AI agents |
| `OLLAMA_EMBED_MODEL` | `bge-m3` | Embedding model for semantic search |
| `OLLAMA_NUM_CTX` | `4096` | Context window size (tokens) |
| `OLLAMA_NUM_THREAD` | `4` | CPU threads allocated to Ollama |
| `OLLAMA_NUM_PREDICT` | `1024` | Max tokens per LLM response |
| `CHROMADB_HOST` | `chromadb` | ChromaDB service host (do not change for Docker) |
| `CHROMADB_PORT` | `8000` | ChromaDB port |
| `JWT_SECRET_KEY` | — | **Required.** Min 32 chars. Generate with `secrets.token_hex(32)` |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `UPLOAD_DIR` | `/app/uploads` | Internal container path for uploaded files |
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload size in megabytes |
| `AGENT_TIMEOUT_SECONDS` | `300` | Seconds before an LLM call is aborted |
| `MAX_CHAT_MESSAGE_CHARS` | `8000` | Character limit per chat message |
| `CHUNK_SIZE` | `500` | Document chunk size for vector indexing |
| `CHUNK_OVERLAP` | `100` | Overlap between consecutive chunks |
| `CORS_ALLOWED_ORIGINS` | `http://localhost,http://localhost:80` | Allowed CORS origins |
| `LOG_LEVEL` | `INFO` | Logging verbosity: DEBUG, INFO, WARNING, ERROR |

---

## 6. First Startup

### Start all services

```bash
docker compose up -d
```

This command:
- Builds the backend (Python/FastAPI) and frontend (Next.js) images
- Starts PostgreSQL, ChromaDB, Ollama, backend, frontend, and Nginx
- Ollama automatically pulls `qwen2.5:3b` and `bge-m3` on first run (see [Section 8](#8-ollama--model-setup))

The first startup takes **5–15 minutes** depending on your internet speed and machine, because Docker must:
1. Download all base images (~3 GB)
2. Build the backend and frontend images
3. Pull the `qwen2.5:3b` model (~2 GB) and `bge-m3` model (~1.2 GB)

### Check service health

```bash
docker compose ps
```

All services should show `healthy` or `running` after startup completes. If any service shows `starting`, wait 1–2 minutes and check again.

### View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f ollama
docker compose logs -f frontend
```

---

## 7. Database Migrations

Migrations must be applied after the first startup and after any code update that includes schema changes.

### Apply all pending migrations

```bash
docker compose exec backend alembic upgrade head
```

### Verify migration status

```bash
docker compose exec backend alembic current
```

### Create a new migration (developers only)

```bash
docker compose exec backend alembic revision --autogenerate -m "describe_change_here"
```

> Migrations are automatically detected from SQLAlchemy model changes. Always review the generated file in `backend/alembic/versions/` before applying.

---

## 8. Ollama & Model Setup

### Automatic model pull (default behaviour)

The Ollama container runs a startup script (`scripts/ollama-entrypoint.sh`) that automatically pulls the required models if they are not already cached:

- `qwen2.5:3b` — chat and AI agent model (~2 GB)
- `bge-m3` — multilingual embedding model (~1.2 GB)

Models are stored in the `ollama_models` Docker named volume and persist across container restarts.

### Monitor model download progress

```bash
docker compose logs -f ollama
```

You will see output like:
```
[ollama-entrypoint] Pulling model 'qwen2.5:3b'...
[ollama-entrypoint] Model 'qwen2.5:3b' pulled successfully.
[ollama-entrypoint] Pulling model 'bge-m3'...
[ollama-entrypoint] All models ready. Keeping Ollama running...
```

### Pull a model manually

```bash
docker compose exec ollama ollama pull qwen2.5:3b
docker compose exec ollama ollama pull bge-m3
```

### List downloaded models

```bash
docker compose exec ollama ollama list
```

### Switch to a larger chat model (optional)

If you have 16 GB+ RAM, you can use a more capable model by updating `.env`:

```env
OLLAMA_CHAT_MODEL=qwen3:8b
OLLAMA_NUM_CTX=8192
```

Then pull the model and restart the backend:

```bash
docker compose exec ollama ollama pull qwen3:8b
docker compose restart backend
```

---

## 9. Verify Everything Is Running

### Access the application

Open your browser and go to:

```
http://localhost
```

### First login

The **first user to register becomes the Admin** automatically. Subsequent users require Admin approval to register.

1. Go to `http://localhost`
2. Click **Register** and create your account
3. You are now logged in as Admin

### API health check

```
http://localhost/api/v1/health
```

Should return:
```json
{"status": "ok"}
```

### Check all container statuses

```bash
docker compose ps
```

Expected output:

| Service | Status |
|---|---|
| nginx | running |
| backend | healthy |
| frontend | running |
| postgres | healthy |
| chromadb | healthy |
| ollama | healthy |

---

## 10. Troubleshooting

### Ollama is taking a long time to start

Model downloads can take 10–20 minutes on a slow connection. Monitor progress:
```bash
docker compose logs -f ollama
```
Do not stop the container mid-download. If interrupted, the pull resumes automatically on next startup.

---

### Backend fails to start — "JWT_SECRET_KEY too weak"

The backend rejects placeholder JWT secrets. Generate a real one:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
Paste the result into `.env` as `JWT_SECRET_KEY`, then restart:
```bash
docker compose restart backend
```

---

### Backend fails to start — database connection refused

PostgreSQL may still be initialising. Wait 30 seconds and check:
```bash
docker compose logs postgres
docker compose restart backend
```

If the error persists, verify `DB_USER`, `DB_PASSWORD`, and `DB_NAME` in `.env` match the values in `docker-compose.yml`.

---

### Port 80 already in use

Another process is using port 80. Either stop that process, or edit `docker-compose.yml` to change the Nginx port:
```yaml
ports:
  - "8080:80"   # change 80 to any free port
```
Then access the app at `http://localhost:8080`.

---

### "no space left on device" error

Docker has run out of disk space. Free space by removing unused images and volumes:
```bash
docker system prune -f
docker volume prune -f   # WARNING: removes ALL unused volumes including model cache
```
After `volume prune`, models must be re-downloaded on next startup.

---

### Frontend shows blank page or 502 Bad Gateway

The backend health check may not have passed yet. Wait 60 seconds then refresh. If it persists:
```bash
docker compose logs backend
docker compose logs nginx
```

---

### ChromaDB health check failing

ChromaDB can be slow to initialise. Check its logs:
```bash
docker compose logs chromadb
```
If it is stuck, restart it:
```bash
docker compose restart chromadb
```

---

### Uploaded files not processing (stuck in "processing" status)

Check backend logs for errors:
```bash
docker compose logs -f backend
```
Common causes:
- Ollama model not yet downloaded — wait for model pull to complete
- File exceeds `MAX_FILE_SIZE_MB` — increase the limit in `.env` and restart backend
- OCR failure on a scanned PDF — ensure the file is a valid PDF or image (JPG/PNG)

---

### Full reset — start from scratch

This destroys all data including uploaded files, the database, and downloaded models.

```bash
docker compose down -v
docker compose up -d
docker compose exec backend alembic upgrade head
```

---

### Useful maintenance commands

```bash
# Stop all services — DATA IS PRESERVED (postgres, chromadb, uploads, models)
docker compose down

# Stop and remove ALL data volumes — DESTRUCTIVE, cannot be undone
docker compose down -v

# Restart a single service without rebuilding (e.g. after .env change)
docker compose restart backend
docker compose restart frontend

# Rebuild and restart after code changes
docker compose up -d --build backend
docker compose up -d --build frontend

# Run backend tests
docker compose exec backend pytest -v

# Run type checking
docker compose exec backend mypy app/

# Open a PostgreSQL shell
docker compose exec postgres psql -U docplat -d docplat

# Open a backend Python shell
docker compose exec backend python
```

---

### Updating the project from GitHub

Use this sequence whenever you pull new code on an existing installation:

```bash
# 1. Pull the latest changes
git pull origin master

# 2. Rebuild images that changed
docker compose up -d --build backend frontend

# 3. Apply any new database migrations
docker compose exec backend alembic upgrade head
```

> **Safe to re-run.** If there are no new migrations, `alembic upgrade head` exits immediately without making changes. If there are no backend code changes, rebuilding the backend image is fast because Docker caches unchanged layers.

> **Frontend-only change?** You only need to rebuild frontend: `docker compose up -d --build frontend`  
> **Backend-only change?** You only need to rebuild backend: `docker compose up -d --build backend`

---

## Support

Report issues at: [github.com/vvalid-1/document-intelligence-platform/issues](https://github.com/vvalid-1/document-intelligence-platform/issues)
