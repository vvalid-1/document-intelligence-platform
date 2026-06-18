# Database Schema — Document Intelligence Platform

## Design Principles

- All primary keys are UUID v4 (`gen_random_uuid()`)
- All timestamps are `TIMESTAMPTZ` (timezone-aware UTC)
- File paths stored as **relative paths only** — e.g., `{document_id}/original.pdf` — never absolute. The upload root is resolved at runtime from `UPLOAD_DIR` env var. Absolute paths break when volume mount points change.
- Soft-deletes used for documents; hard-delete is Admin-only
- `updated_at` columns are maintained by DB trigger (defined at end of this document)
- All VARCHAR enum-like fields have CHECK constraints to enforce valid values at the DB layer
- Audit log is append-only; an immutability trigger prevents UPDATE/DELETE

---

## PostgreSQL Schema

---

### Table: users

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL DEFAULT 'viewer',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_user_role CHECK (role IN ('admin', 'editor', 'viewer'))
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role  ON users(role);
```

---

### Table: user_invitations

Admin-created invitations allowing new users to register. Required because registration is Admin-only after the first user.

```sql
CREATE TABLE user_invitations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL DEFAULT 'viewer',
    invited_by      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL UNIQUE,   -- SHA-256 of the one-time token
    expires_at      TIMESTAMPTZ NOT NULL,            -- default: NOW() + INTERVAL '7 days'
    accepted_at     TIMESTAMPTZ,                     -- NULL = not yet accepted
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_inv_role CHECK (role IN ('admin', 'editor', 'viewer'))
);

CREATE INDEX idx_invitations_email      ON user_invitations(email);
CREATE INDEX idx_invitations_token_hash ON user_invitations(token_hash);
CREATE INDEX idx_invitations_invited_by ON user_invitations(invited_by);
```

---

### Table: refresh_tokens

```sql
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);
```

---

### Table: sse_tokens

Short-lived (30s) single-use tokens for authenticating SSE connections.
The browser native `EventSource` API cannot send custom headers, so SSE endpoints
accept a `?token=<sse_token>` query parameter instead of the Authorization header.

```sql
CREATE TABLE sse_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,   -- NOW() + INTERVAL '30 seconds'
    used        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sse_tokens_hash ON sse_tokens(token_hash);
```

---

### Table: documents

```sql
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- owner_id is nullable: documents are preserved when a user is deleted
    owner_id        UUID REFERENCES users(id) ON DELETE SET NULL,
    title           VARCHAR(500) NOT NULL,
    original_name   VARCHAR(500) NOT NULL,
    -- Relative path within upload volume: "{document_id}/original.{ext}"
    -- Resolve full path at runtime: UPLOAD_DIR / file_path
    file_path       TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type       VARCHAR(100) NOT NULL,
    page_count      INTEGER,             -- NULL for TXT/DOCX (no page concept)
    chunk_count     INTEGER,             -- set after processing completes
    doc_metadata    JSONB,               -- author, creation_date, word_count, etc.
    status          VARCHAR(30) NOT NULL DEFAULT 'uploaded',
    error_message   TEXT,
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_doc_status CHECK (status IN ('uploaded', 'processing', 'ready', 'error'))
);

-- Single-column indexes for simple lookups
CREATE INDEX idx_documents_owner   ON documents(owner_id);
CREATE INDEX idx_documents_status  ON documents(status);
CREATE INDEX idx_documents_deleted ON documents(is_deleted);

-- Composite index covering the primary list-documents query:
-- WHERE owner_id = ? AND is_deleted = FALSE ORDER BY created_at DESC
CREATE INDEX idx_documents_list ON documents(owner_id, is_deleted, status, created_at DESC);

-- Full-text search on title + original filename
ALTER TABLE documents
    ADD COLUMN search_vector TSVECTOR
    GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(original_name, ''))
    ) STORED;

CREATE INDEX idx_documents_fts ON documents USING GIN(search_vector);
```

---

### Table: document_versions

```sql
CREATE TABLE document_versions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id      UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_number   INTEGER NOT NULL,
    created_by       UUID NOT NULL REFERENCES users(id),
    -- Relative path: "{document_id}/v{version_number}.{ext}"
    file_path        TEXT NOT NULL,
    change_summary   TEXT,
    agent_name       VARCHAR(100),   -- NULL if user-created
    -- FK traces which agent task produced this version
    task_id          UUID REFERENCES agent_tasks(id) ON DELETE SET NULL,
    version_metadata JSONB,          -- edit_operation, token_count, diff_stats, etc.
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(document_id, version_number)
);

CREATE INDEX idx_doc_versions_document ON document_versions(document_id);
CREATE INDEX idx_doc_versions_task     ON document_versions(task_id);
CREATE INDEX idx_doc_versions_created  ON document_versions(created_at DESC);
```

> **Note:** `agent_tasks` is declared after `document_versions` in migration. Use deferred FK or add the FK in a separate migration step.

---

### Table: document_chunks

Mirrors ChromaDB for relational queries (keyword search, cascade deletes).

```sql
CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chroma_chunk_id VARCHAR(255) NOT NULL,   -- ChromaDB document ID: "{doc_id}_{chunk_index}"
    chunk_index     INTEGER NOT NULL,
    -- page_number for PDFs (1-indexed). For DOCX/TXT: NULL.
    -- Chunk position is tracked via chunk_index; no page concept for non-PDF formats.
    page_number     INTEGER,
    chunk_text      TEXT NOT NULL,
    token_count     INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(document_id, chunk_index)
);

CREATE INDEX idx_chunks_document  ON document_chunks(document_id);
CREATE INDEX idx_chunks_chroma_id ON document_chunks(chroma_chunk_id);

-- Full-text search on chunk content (used by keyword search endpoint)
ALTER TABLE document_chunks
    ADD COLUMN search_vector TSVECTOR
    GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED;

CREATE INDEX idx_chunks_fts ON document_chunks USING GIN(search_vector);
```

---

### Table: agent_sessions

```sql
CREATE TABLE agent_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_name    VARCHAR(255),
    -- Small current-turn context only (last N messages for prompt assembly).
    -- Full history is in agent_messages. This blob must stay bounded; trim to
    -- last 10 messages maximum before each write.
    context_summary JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_user   ON agent_sessions(user_id);
CREATE INDEX idx_sessions_active ON agent_sessions(is_active);
CREATE INDEX idx_sessions_user_active ON agent_sessions(user_id, is_active, created_at DESC);
```

---

### Table: agent_messages

Individual conversation turns within a session. Replaces the unbounded `context_data` JSONB blob.

```sql
CREATE TABLE agent_messages (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    role         VARCHAR(20) NOT NULL,
    -- 'user': input from the human
    -- 'assistant': Orchestrator response to the user
    -- 'tool': output from a specialist agent
    -- 'system': internal orchestration messages
    content      TEXT NOT NULL,
    agent_name   VARCHAR(100),            -- which agent produced this message (NULL for user/system)
    task_id      UUID,                    -- FK added after agent_tasks is created (see below)
    sequence_num INTEGER NOT NULL,        -- monotonic per session; used for ordering
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(session_id, sequence_num),
    CONSTRAINT chk_message_role CHECK (role IN ('user', 'assistant', 'tool', 'system'))
);

CREATE INDEX idx_messages_session  ON agent_messages(session_id);
CREATE INDEX idx_messages_task     ON agent_messages(task_id);
-- Composite: load last N messages for prompt assembly
CREATE INDEX idx_messages_session_seq ON agent_messages(session_id, sequence_num DESC);
```

---

### Table: agent_tasks

```sql
CREATE TABLE agent_tasks (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     UUID NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    document_id    UUID REFERENCES documents(id) ON DELETE SET NULL,
    agent_name     VARCHAR(100) NOT NULL,
    task_type      VARCHAR(100) NOT NULL,
    input_payload  JSONB NOT NULL,
    output_payload JSONB,
    status         VARCHAR(30) NOT NULL DEFAULT 'pending',
    error_message  TEXT,
    duration_ms    INTEGER,
    model_used     VARCHAR(100),
    token_count    INTEGER,
    -- Timeout: backend marks status='failed' with error_message='timeout' after AGENT_TIMEOUT_SECONDS
    timed_out      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at   TIMESTAMPTZ,

    CONSTRAINT chk_task_status  CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    CONSTRAINT chk_agent_name   CHECK (agent_name IN ('orchestrator', 'search_rag', 'reviewer', 'editor', 'signature'))
);

CREATE INDEX idx_tasks_session  ON agent_tasks(session_id);
CREATE INDEX idx_tasks_document ON agent_tasks(document_id);
CREATE INDEX idx_tasks_status   ON agent_tasks(status);
CREATE INDEX idx_tasks_agent    ON agent_tasks(agent_name);
-- Composite: session history ordered by time
CREATE INDEX idx_tasks_session_created ON agent_tasks(session_id, created_at DESC);
```

---

### Deferred FKs (added in separate migration after agent_tasks exists)

```sql
-- document_versions.task_id → agent_tasks.id (declared above without FK to avoid circular dep)
ALTER TABLE document_versions
    ADD CONSTRAINT fk_versions_task
    FOREIGN KEY (task_id) REFERENCES agent_tasks(id) ON DELETE SET NULL;

-- agent_messages.task_id → agent_tasks.id
ALTER TABLE agent_messages
    ADD CONSTRAINT fk_messages_task
    FOREIGN KEY (task_id) REFERENCES agent_tasks(id) ON DELETE SET NULL;
```

---

### Table: document_reviews

```sql
CREATE TABLE document_reviews (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id    UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    task_id        UUID REFERENCES agent_tasks(id) ON DELETE SET NULL,
    reviewer_id    UUID NOT NULL REFERENCES users(id),
    overall_score  NUMERIC(4,2),   -- 0.00 to 10.00
    summary        TEXT,
    issues         JSONB NOT NULL DEFAULT '[]',
    -- [{"severity":"high|medium|low","category":"...","description":"...","suggestion":"..."}]
    metadata       JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_review_score CHECK (overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 10))
);

CREATE INDEX idx_reviews_document ON document_reviews(document_id);
CREATE INDEX idx_reviews_created  ON document_reviews(created_at DESC);
```

---

### Table: signatures

```sql
CREATE TABLE signatures (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id            UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    signed_by              UUID NOT NULL REFERENCES users(id),
    version_id             UUID REFERENCES document_versions(id) ON DELETE SET NULL,
    signature_type         VARCHAR(30) NOT NULL,
    -- signature_image_path: relative path to the PNG image file used for embedding.
    -- Storage: "{document_id}/signatures/{signature_id}.png"
    -- RETENTION: these files must NOT be cleaned up. They are part of the audit trail.
    -- Delete only when the parent document is hard-deleted by Admin.
    signature_image_path   TEXT,
    field_name             VARCHAR(255),   -- AcroForm field name (NULL if free-placement)
    page_number            INTEGER,
    position_data          JSONB,          -- {x, y, width, height} in PDF points
    ip_address             INET,
    user_agent             TEXT,
    signed_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_sig_type CHECK (signature_type IN ('typed', 'drawn'))
);

CREATE INDEX idx_signatures_document  ON signatures(document_id);
CREATE INDEX idx_signatures_user      ON signatures(signed_by);
CREATE INDEX idx_signatures_signed_at ON signatures(signed_at DESC);
```

---

### Table: audit_logs

Append-only. A trigger prevents any UPDATE or DELETE. This is enforced at the DB layer, not just at the application layer.

```sql
CREATE TABLE audit_logs (
    id            BIGSERIAL PRIMARY KEY,
    user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    action        VARCHAR(100) NOT NULL,
    -- Enumerated values (not constrained in DB to allow future extension without migration):
    -- user.register, user.login, user.logout, user.invited, user.role_changed, user.deactivated
    -- document.upload, document.download, document.delete, document.hard_delete
    -- document.version_created, document.signed
    -- agent.invoked, agent.completed, agent.failed, agent.timed_out
    resource_type VARCHAR(50),
    resource_id   UUID,
    details       JSONB,
    ip_address    INET,
    user_agent    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_user     ON audit_logs(user_id);
CREATE INDEX idx_audit_action   ON audit_logs(action);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
-- Composite: most common admin query pattern
CREATE INDEX idx_audit_user_created ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_created  ON audit_logs(created_at DESC);
```

---

## Triggers

### Auto-update `updated_at`

```sql
CREATE OR REPLACE FUNCTION fn_update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION fn_update_updated_at();

CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION fn_update_updated_at();

CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON agent_sessions
    FOR EACH ROW EXECUTE FUNCTION fn_update_updated_at();
```

### Audit log immutability

```sql
CREATE OR REPLACE FUNCTION fn_audit_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only: UPDATE and DELETE are not permitted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_immutable
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION fn_audit_immutable();
```

---

## Alembic Migration Order

To avoid FK circular dependencies, run migrations in this order:

1. `users`
2. `user_invitations`
3. `refresh_tokens`
4. `sse_tokens`
5. `documents`
6. `document_chunks`
7. `agent_sessions`
8. `agent_messages` (without task_id FK)
9. `agent_tasks`
10. `document_versions` (without task_id FK)
11. `document_reviews`
12. `signatures`
13. `audit_logs`
14. Triggers
15. Deferred FKs: `document_versions.task_id`, `agent_messages.task_id`

---

## ChromaDB Collections

### Collection: `document_chunks`

| Field | Type | Description |
|---|---|---|
| id | string | `{document_id}_{chunk_index}` |
| embedding | float[1024] | bge-m3 output — **1024 dimensions** |
| document | string | Chunk text content |
| metadata.document_id | string | UUID |
| metadata.document_title | string | |
| metadata.mime_type | string | `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/plain` |
| metadata.page_number | int or null | 1-indexed for PDFs; `null` for DOCX/TXT |
| metadata.chunk_index | int | Position in document |
| metadata.owner_id | string | UUID |
| metadata.created_at | string | ISO8601 |

**Collection creation (must be explicit):**

```python
collection = client.get_or_create_collection(
    name="document_chunks",
    metadata={"hnsw:space": "cosine"},   # REQUIRED: bge-m3 uses cosine similarity
    embedding_function=None,              # We compute embeddings externally via Ollama
)
```

> **Critical:** Without `hnsw:space: cosine`, ChromaDB defaults to L2 (Euclidean) distance. L2 distance on normalized embeddings produces semantically wrong rankings for text similarity. This must be set at collection creation time and cannot be changed after.

**Embedding dimension:** bge-m3 produces **1024-dimensional** float vectors. This is fixed; do not change the embedding model without recreating the collection.

**Query operations:**

```python
# Semantic search
collection.query(query_embeddings=[...], n_results=10)

# Filtered to one document
collection.query(query_embeddings=[...], n_results=20, where={"document_id": "uuid"})

# On document deletion — delete BEFORE soft-deleting in PostgreSQL
collection.delete(where={"document_id": "uuid"})
```

**ChromaDB / PostgreSQL consistency strategy:**

Deletion must follow this exact order to prevent orphaned embeddings:
1. `collection.delete(where={"document_id": uuid})` — ChromaDB first
2. If step 1 succeeds: `UPDATE documents SET is_deleted=TRUE` — PostgreSQL
3. If step 1 fails: abort; surface error to user; do NOT update PostgreSQL

On backend startup, run a reconciliation check:
- Query ChromaDB for all `document_id` values in the collection
- Cross-reference against PostgreSQL `documents` where `is_deleted=TRUE`
- Delete any ChromaDB entries for soft-deleted documents (cleanup of failed deletes)

---

## DOCX / TXT Page Number Strategy

PDF documents have natural page boundaries. DOCX and TXT files do not.

| Format | page_number in document_chunks | page_count in documents |
|---|---|---|
| PDF | 1-indexed page number | Actual page count |
| DOCX | NULL | NULL |
| TXT | NULL | NULL |

For DOCX/TXT, chunk position is identified by `chunk_index` only. The frontend must handle `page_number = null` gracefully (display "Chunk N" instead of "Page N").

---

## System Requirements (RAM)

| Service | Estimated RAM |
|---|---|
| qwen3:8b (Ollama) | ~8 GB |
| bge-m3 (Ollama) | ~1.5 GB |
| PostgreSQL | ~256 MB |
| ChromaDB | ~512 MB |
| Backend (FastAPI) | ~256 MB |
| Frontend (Next.js SSR) | ~256 MB |
| OS overhead | ~1 GB |
| **Total minimum** | **~12 GB** |
| **Recommended** | **16 GB** |

> On a 16 GB machine, Ollama should be started with `OLLAMA_MAX_LOADED_MODELS=2` to keep both models in memory. Set `mem_limit: 12g` on the Ollama Docker service.

---

## Indexes Summary

| Table | Index Type | Columns | Purpose |
|---|---|---|---|
| users | B-tree unique | email | Login lookup |
| user_invitations | B-tree unique | token_hash | Token validation |
| documents | B-tree composite | owner_id, is_deleted, status, created_at | List query |
| documents | GIN | search_vector | Full-text search on title |
| document_chunks | GIN | search_vector | Keyword search on content |
| document_chunks | B-tree unique | document_id, chunk_index | Dedup |
| agent_sessions | B-tree composite | user_id, is_active, created_at | Session list |
| agent_messages | B-tree composite | session_id, sequence_num DESC | History load |
| agent_tasks | B-tree composite | session_id, created_at DESC | Task history |
| audit_logs | B-tree composite | user_id, created_at DESC | User activity |
| refresh_tokens | B-tree unique | token_hash | Token validation |
| sse_tokens | B-tree unique | token_hash | SSE auth |
