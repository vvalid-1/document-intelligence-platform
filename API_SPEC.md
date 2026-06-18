# API Specification — Document Intelligence Platform

**Base URL:** `http://localhost:8000/api/v1`
**Auth:** `Authorization: Bearer <access_token>` on all protected routes
**Content-Type:** `application/json` unless uploading files (`multipart/form-data`)

---

## Access Control Matrix

| Role | Can do |
|---|---|
| Admin | Everything |
| Editor | Upload, edit, delete own documents, sign, search all, use agents |
| Viewer | Read, search, download — no upload, no edit, no delete |

**Search visibility:** All users (Admin, Editor, Viewer) can search across **all non-deleted documents on the platform**. Document access is not per-user scoped. If per-user isolation is required, filter by `owner_id` in ChromaDB metadata at query time.

---

## Authentication

### POST /auth/register

Open only when no users exist (first user becomes Admin). After the first user, returns 403 with `{"error":{"code":"REGISTRATION_CLOSED"}}`. Use `POST /admin/users` or `POST /auth/invite/accept` instead.

**Request:**
```json
{
  "email": "admin@example.com",
  "full_name": "System Admin",
  "password": "securePassword123!"
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "email": "admin@example.com",
  "full_name": "System Admin",
  "role": "admin",
  "created_at": "2025-01-01T00:00:00Z"
}
```

**Errors:** 400 (validation), 403 (registration closed — not first user), 409 (email exists)

---

### POST /auth/invite/accept

Accept an admin-issued invitation and set a password.

**Request:**
```json
{
  "token": "<invitation_token_from_email_or_admin>",
  "full_name": "Jane Smith",
  "password": "securePassword123!"
}
```

**Response 201:** Same as /auth/register response.

**Errors:** 400 (validation), 404 (token not found), 410 (token expired or already used)

---

### POST /auth/login

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123!"
}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

> **Token storage guidance:** Store access token in memory (JS variable or Zustand store). Store refresh token in an `HttpOnly; Secure; SameSite=Strict` cookie. Do not store access tokens in `localStorage` (XSS risk).
>
> **Post-logout access token validity:** Access tokens remain cryptographically valid until expiry (30 min) after logout. The refresh token is revoked immediately. This is a known, accepted limitation in v1. For higher security, reduce access token TTL to 5 minutes via `ACCESS_TOKEN_TTL_SECONDS` env var.

**Errors:** 401 (invalid credentials), 403 (account deactivated)

---

### POST /auth/refresh

**Request:**
```json
{ "refresh_token": "eyJ..." }
```

**Response 200:** Same as login response.

---

### POST /auth/logout

Revokes the current refresh token.

**Response 200:**
```json
{ "message": "Logged out successfully" }
```

---

### GET /auth/me

**Response 200:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Jane Smith",
  "role": "editor",
  "is_active": true,
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

### POST /auth/sse-token

Issues a short-lived (30s), single-use token for authenticating SSE connections.
Required because the browser `EventSource` API cannot send `Authorization` headers.
The SSE token is passed as `?token=<sse_token>` in the SSE endpoint URL.

**Auth required:** Yes (valid JWT access token)

**Response 200:**
```json
{
  "sse_token": "opaque-30-char-random-string",
  "expires_in": 30
}
```

**Usage flow:**
1. Client calls `POST /auth/sse-token` with JWT bearer
2. Receives `sse_token`
3. Opens `EventSource("/api/v1/agents/sessions/{id}/stream?token=<sse_token>")`
4. Token is consumed on first SSE connection; any subsequent use returns 401

---

### PATCH /auth/me/password

Change the authenticated user's own password (Admin-initiated reset also uses this via admin endpoint).

**Request:**
```json
{
  "current_password": "oldPassword123!",
  "new_password": "newPassword456!"
}
```

**Response 200:**
```json
{ "message": "Password changed successfully" }
```

---

## Documents

### GET /documents

**Query Params:**

| Param | Type | Default | Description |
|---|---|---|---|
| page | int | 1 | Page number |
| per_page | int | 20 | Max 100 |
| status | string | all | uploaded \| processing \| ready \| error |
| sort | string | created_at_desc | created_at_desc \| created_at_asc \| title_asc |
| mime_type | string | — | Filter by file type |

**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "title": "Q4 Report.pdf",
      "original_name": "Q4 Report.pdf",
      "status": "ready",
      "file_size_bytes": 524288,
      "page_count": 12,
      "chunk_count": 48,
      "mime_type": "application/pdf",
      "owner": { "id": "uuid", "full_name": "Jane Smith" },
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:05:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "per_page": 20,
  "pages": 3
}
```

---

### POST /documents/upload

**Roles:** Editor, Admin

**Content-Type:** `multipart/form-data`

**File validation (server-side):**
- Allowed extensions: `.pdf`, `.docx`, `.txt`
- Allowed MIME types: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/plain`
- File header (magic bytes) verified against declared MIME type — extension alone is not trusted
- Max size: `MAX_FILE_SIZE_MB` env var (default 50)

**Form fields:**

| Field | Required | Description |
|---|---|---|
| file | Yes | Document file |
| title | No | Display title (defaults to filename without extension) |

**Response 202:**
```json
{
  "id": "uuid",
  "title": "Q4 Report",
  "status": "processing",
  "created_at": "2025-01-01T00:00:00Z",
  "stream_url": "/api/v1/documents/uuid/status/stream"
}
```

**Errors:** 400 (invalid type, magic bytes mismatch), 403 (Viewer role), 413 (size exceeded)

---

### GET /documents/{id}

**Response 200:**
```json
{
  "id": "uuid",
  "title": "Q4 Report",
  "original_name": "Q4 Report.pdf",
  "status": "ready",
  "file_size_bytes": 524288,
  "page_count": 12,
  "chunk_count": 48,
  "mime_type": "application/pdf",
  "doc_metadata": {
    "author": "John Doe",
    "creation_date": "2024-12-01T00:00:00Z"
  },
  "owner": { "id": "uuid", "full_name": "Jane Smith" },
  "version_count": 2,
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:05:00Z"
}
```

---

### PATCH /documents/{id}

Update document title. **Roles:** Owner (Editor/Admin) or any Admin.

**Request:**
```json
{ "title": "Q4 2024 Revenue Report" }
```

**Response 200:** Updated document object (same shape as GET /documents/{id}).

---

### GET /documents/{id}/status

**Response 200:**
```json
{
  "id": "uuid",
  "status": "processing",
  "progress_percent": 45,
  "progress_step": "Embedding chunk 22/48",
  "estimated_seconds_remaining": 180,
  "error_message": null
}
```

---

### DELETE /documents/{id}

Soft-delete. **Roles:** Owner or Admin.

**Response 200:**
```json
{ "message": "Document deleted", "id": "uuid" }
```

---

### GET /documents/{id}/download

Returns the original file. `Content-Disposition: attachment; filename="..."` header included.

---

### GET /documents/{id}/versions

**Response 200:**
```json
{
  "document_id": "uuid",
  "versions": [
    {
      "id": "uuid",
      "version_number": 1,
      "change_summary": "Original upload",
      "agent_name": null,
      "task_id": null,
      "created_by": { "id": "uuid", "full_name": "Jane Smith" },
      "created_at": "2025-01-01T00:00:00Z"
    },
    {
      "id": "uuid",
      "version_number": 2,
      "change_summary": "Summarized by AI Editor Agent",
      "agent_name": "editor",
      "task_id": "uuid",
      "created_by": { "id": "uuid", "full_name": "Jane Smith" },
      "created_at": "2025-01-01T01:00:00Z"
    }
  ]
}
```

---

### GET /documents/{id}/versions/{version_id}/download

Download a specific document version. Same response headers as `/documents/{id}/download`.

---

### GET /documents/{id}/reviews

**Query Params:** `page` (default 1), `per_page` (default 10, max 50)

**Response 200:**
```json
{
  "document_id": "uuid",
  "total": 3,
  "page": 1,
  "per_page": 10,
  "reviews": [
    {
      "id": "uuid",
      "overall_score": 7.5,
      "summary": "Well-structured but missing a conclusion.",
      "issues": [
        {
          "severity": "medium",
          "category": "structure",
          "description": "Missing conclusion section",
          "suggestion": "Add a summary paragraph at the end"
        }
      ],
      "created_at": "2025-01-01T01:00:00Z"
    }
  ]
}
```

---

## Search

### POST /search

Access: All authenticated users. Results include all non-deleted platform documents.

**Request:**
```json
{
  "query": "quarterly revenue Q4 2024",
  "search_type": "semantic",
  "top_k": 10,
  "filters": {
    "document_ids": ["uuid1", "uuid2"],
    "mime_type": "application/pdf",
    "date_from": "2024-01-01",
    "date_to": "2024-12-31"
  }
}
```

**search_type values:** `semantic` | `keyword` | `hybrid`

**Response 200:**
```json
{
  "query": "quarterly revenue Q4 2024",
  "search_type": "semantic",
  "results": [
    {
      "document_id": "uuid",
      "document_title": "Q4 Report.pdf",
      "chunk_text": "Total revenue for Q4 2024 reached $4.2M...",
      "page_number": 3,
      "chunk_index": 14,
      "similarity_score": 0.921,
      "highlight": "Total revenue for Q4 2024 reached <mark>$4.2M</mark>..."
    }
  ],
  "total_results": 7,
  "search_time_ms": 145
}
```

---

### POST /search/ask

RAG question answering with streaming. Returns `task_id` and `stream_url`; client reads tokens via SSE.

**Request:**
```json
{
  "question": "What was the total revenue in Q4 2024?",
  "document_ids": ["uuid1"],
  "top_k": 5
}
```

**Response 202:**
```json
{
  "task_id": "uuid",
  "stream_url": "/api/v1/agents/sessions/{session_id}/stream?task_id=uuid&token=<sse_token>",
  "sources": [
    {
      "document_id": "uuid",
      "document_title": "Q4 Report.pdf",
      "page_number": 3,
      "chunk_text": "Total revenue for Q4 2024 reached $4.2M...",
      "similarity_score": 0.921
    }
  ]
}
```

Sources are returned immediately (retrieval is fast); answer tokens arrive via SSE stream.

---

## Agents

### GET /agents/sessions

List authenticated user's sessions.

**Query Params:** `page` (default 1), `per_page` (default 20), `is_active` (bool, default true)

**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "session_name": "Document Analysis Session",
      "is_active": true,
      "message_count": 12,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T01:00:00Z"
    }
  ],
  "total": 5,
  "page": 1,
  "per_page": 20
}
```

---

### POST /agents/sessions

**Request:**
```json
{
  "session_name": "Document Analysis Session",
  "document_ids": ["uuid1", "uuid2"]
}
```

**Response 201:**
```json
{
  "session_id": "uuid",
  "session_name": "Document Analysis Session",
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

### DELETE /agents/sessions/{session_id}

Archive/close a session. Sets `is_active=FALSE`. Does not delete messages.

**Response 200:**
```json
{ "message": "Session closed", "session_id": "uuid" }
```

---

### POST /agents/sessions/{session_id}/chat

Send a message. Returns `task_id` **immediately** (non-blocking). Client reads the response via SSE stream.

> **Design note:** This endpoint is intentionally async. It does NOT return the agent's answer. It starts the task and returns a handle. The actual response tokens stream via `GET /agents/sessions/{session_id}/stream`.

**Input limits:** `message` field maximum 8000 characters (enforced server-side). The message + retrieved context + system prompt must fit within `OLLAMA_NUM_CTX` tokens.

**Request:**
```json
{
  "message": "Review document Q4 Report and then summarize the key findings",
  "document_id": "uuid"
}
```

**Response 202:**
```json
{
  "session_id": "uuid",
  "task_id": "uuid",
  "stream_url": "/api/v1/agents/sessions/uuid/stream?task_id=uuid&token=<sse_token>"
}
```

---

### GET /agents/sessions/{session_id}/history

Returns paginated message history.

**Query Params:** `page` (default 1), `per_page` (default 50, max 100)

**Response 200:**
```json
{
  "session_id": "uuid",
  "session_name": "Document Analysis Session",
  "total_messages": 24,
  "page": 1,
  "per_page": 50,
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "Review document Q4 Report and summarize it",
      "agent_name": null,
      "task_id": null,
      "sequence_num": 1,
      "created_at": "2025-01-01T00:00:00Z"
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "I've reviewed the Q4 Report. Overall score: 7.5/10...",
      "agent_name": "orchestrator",
      "task_id": "uuid",
      "sequence_num": 2,
      "created_at": "2025-01-01T00:00:15Z"
    }
  ]
}
```

---

### POST /agents/review/{document_id}

Trigger document review directly. Returns task_id immediately.

**Response 202:**
```json
{
  "task_id": "uuid",
  "status": "pending",
  "stream_url": "/api/v1/agents/sessions/{session_id}/stream?task_id=uuid&token=<sse_token>"
}
```

---

### POST /agents/edit/{document_id}

**Request:**
```json
{
  "operation": "summarize",
  "instructions": "Summarize to 3 bullet points, formal tone",
  "output_mode": "text",
  "target_section": null
}
```

**operation values:** `summarize` | `paraphrase` | `expand` | `fix_grammar` | `translate` | `custom`

**output_mode values:** `text` (no file created) | `pdf` (creates new document version)

**Response 202:**
```json
{
  "task_id": "uuid",
  "status": "pending",
  "stream_url": "/api/v1/agents/edit/uuid/stream?token=<sse_token>"
}
```

---

### GET /agents/tasks/{task_id}

Poll a task. Use when SSE stream was disconnected — task continues running on the server regardless of client connection.

> **SSE disconnect behavior:** If the client disconnects mid-stream, the agent task continues executing on the backend. The final result is stored in `agent_tasks.output_payload`. The client can reconnect to this endpoint to retrieve the completed result, or wait and reconnect the SSE stream (the server re-streams from the last stored token if task is still running, or returns the full result if already complete).

**Response 200:**
```json
{
  "task_id": "uuid",
  "status": "completed",
  "agent_name": "editor",
  "result": {
    "text": "Executive Summary\n\nThis report covers...",
    "pdf_version_id": "uuid or null"
  },
  "duration_ms": 3200,
  "model_used": "qwen3:8b",
  "timed_out": false,
  "completed_at": "2025-01-01T00:00:15Z"
}
```

**Timeout behavior:** If task exceeds `AGENT_TIMEOUT_SECONDS` (default 300), status is set to `"failed"`, `timed_out` is `true`, and the SSE stream sends `{"event":"error","code":"TIMEOUT"}`.

---

## Signatures

### GET /signatures/document/{document_id}/fields

Detects AcroForm signature fields. Only applicable to PDF documents. Returns empty list for DOCX/TXT.

**Response 200:**
```json
{
  "document_id": "uuid",
  "mime_type": "application/pdf",
  "fields": [
    {
      "field_name": "SignatureField1",
      "page_number": 5,
      "position": { "x": 100, "y": 200, "width": 200, "height": 50 },
      "is_required": true,
      "is_signed": false
    }
  ]
}
```

---

### POST /signatures/document/{document_id}/sign

**Request:**
```json
{
  "field_name": "SignatureField1",
  "signature_type": "typed",
  "typed_name": "Jane Smith",
  "signature_image_base64": null
}
```

For drawn signatures: `"signature_type": "drawn"`, provide `signature_image_base64` (PNG, base64-encoded, max 500KB).

**Response 200:**
```json
{
  "signature_id": "uuid",
  "document_id": "uuid",
  "new_version_id": "uuid",
  "signed_at": "2025-01-01T00:00:00Z",
  "download_url": "/api/v1/documents/uuid/versions/uuid/download"
}
```

---

### GET /signatures/document/{document_id}

**Response 200:**
```json
{
  "document_id": "uuid",
  "signatures": [
    {
      "id": "uuid",
      "signed_by": { "id": "uuid", "full_name": "Jane Smith" },
      "signature_type": "typed",
      "field_name": "SignatureField1",
      "page_number": 5,
      "signed_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

---

## Admin

> All routes require `role: admin`

### GET /admin/users

**Query Params:** `page` (default 1), `per_page` (default 20), `role`, `is_active`

**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "email": "user@example.com",
      "full_name": "Jane Smith",
      "role": "editor",
      "is_active": true,
      "created_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 24,
  "page": 1,
  "per_page": 20,
  "pages": 2
}
```

---

### POST /admin/users

Create a user directly (bypasses invitation flow).

**Request:**
```json
{
  "email": "newuser@example.com",
  "full_name": "Bob Jones",
  "role": "editor",
  "temporary_password": "TempPass123!"
}
```

**Response 201:** User object (same as GET /admin/users item).

---

### POST /admin/users/invite

Send an invitation token to a new user.

**Request:**
```json
{
  "email": "newuser@example.com",
  "role": "editor"
}
```

**Response 201:**
```json
{
  "invitation_id": "uuid",
  "email": "newuser@example.com",
  "invitation_token": "opaque-token-string",
  "expires_at": "2025-01-08T00:00:00Z"
}
```

> `invitation_token` is shown once. Admin must share it with the invitee manually (no email in v1).

---

### PATCH /admin/users/{user_id}

Update role or active status.

**Request:**
```json
{
  "role": "editor",
  "is_active": true
}
```

**Response 200:** Updated user object.

---

### POST /admin/users/{user_id}/reset-password

Admin resets a user's password.

**Request:**
```json
{ "new_password": "ResetPassword123!" }
```

**Response 200:**
```json
{ "message": "Password reset successfully" }
```

---

### GET /admin/audit-logs

**Query Params:** `user_id`, `action`, `resource_type`, `date_from`, `date_to`, `page` (default 1), `per_page` (default 50)

**Response 200:**
```json
{
  "items": [
    {
      "id": 1,
      "user_id": "uuid",
      "user_email": "user@example.com",
      "action": "document.upload",
      "resource_type": "document",
      "resource_id": "uuid",
      "details": { "title": "Q4 Report.pdf", "file_size_bytes": 524288 },
      "ip_address": "192.168.1.1",
      "created_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 1243,
  "page": 1,
  "per_page": 50
}
```

---

### GET /admin/audit-logs/export

Returns CSV file download.

---

### GET /admin/stats

**Response 200:**
```json
{
  "total_users": 24,
  "total_documents": 187,
  "total_chunks": 8234,
  "total_agent_tasks": 1243,
  "storage_used_bytes": 524288000,
  "avg_review_score": 7.2,
  "ollama_status": "loaded",
  "ollama_models": ["qwen3:8b", "bge-m3"]
}
```

---

## Health & Utility

### GET /health

**Response 200:**
```json
{
  "status": "healthy",
  "services": {
    "database": "ok",
    "chromadb": "ok",
    "ollama": "ok",
    "ollama_models": {
      "qwen3:8b": "loaded",
      "bge-m3": "loaded"
    }
  },
  "version": "1.0.0"
}
```

**Unhealthy example (Ollama model still loading on startup):**
```json
{
  "status": "degraded",
  "services": {
    "database": "ok",
    "chromadb": "ok",
    "ollama": "ok",
    "ollama_models": {
      "qwen3:8b": "loading",
      "bge-m3": "not_loaded"
    }
  }
}
```

---

## SSE — Server-Sent Events

All SSE endpoints require authentication via a **short-lived SSE token** (not the JWT bearer).

**Flow:**
1. Call `POST /auth/sse-token` with JWT bearer → receive `sse_token` (30s TTL, single-use)
2. Open SSE connection with `?token=<sse_token>` in the URL
3. Token is consumed on first HTTP request to the SSE endpoint

---

### GET /agents/sessions/{session_id}/stream

**URL params:** `?task_id=<uuid>&token=<sse_token>`

**Response** — `Content-Type: text/event-stream`

```
data: {"event":"start","task_id":"uuid","agent":"orchestrator"}

data: {"event":"token","content":"The document shows "}

data: {"event":"token","content":"a revenue growth of 12%..."}

data: {"event":"agent_switch","agent":"search_rag"}

data: {"event":"token","content":"Based on the Q4 report..."}

data: {"event":"sources","sources":[{"document_id":"uuid","page_number":3,"chunk_text":"..."}]}

data: {"event":"done","task_id":"uuid","duration_ms":3200}
```

**On timeout:**
```
data: {"event":"error","code":"TIMEOUT","message":"Agent did not respond within 300 seconds"}
```

**On agent error:**
```
data: {"event":"error","code":"AGENT_FAILED","message":"..."}
```

**Disconnect behavior:** The agent task continues running server-side if the client disconnects. On reconnect, use `GET /agents/tasks/{task_id}` to retrieve the stored result. Partial streaming resume is not supported — the full completed response is returned.

---

### GET /documents/{id}/status/stream

**URL params:** `?token=<sse_token>`

```
data: {"event":"progress","status":"processing","progress_percent":25,"step":"Extracting text"}

data: {"event":"progress","status":"processing","progress_percent":50,"step":"Running OCR on page 3/12"}

data: {"event":"progress","status":"processing","progress_percent":75,"step":"Embedding chunk 36/48"}

data: {"event":"done","status":"ready","document_id":"uuid","chunk_count":48}
```

Stream closes automatically on `ready` or `error`.

---

### GET /agents/edit/{task_id}/stream

**URL params:** `?token=<sse_token>`

```
data: {"event":"token","content":"Executive Summary\n\n"}

data: {"event":"token","content":"This report covers..."}

data: {"event":"done","full_text":"Executive Summary\n\nThis report covers...","pdf_version_id":"uuid or null"}
```

---

## Error Response Format

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document with ID xyz was not found",
    "details": {}
  }
}
```

### Error Codes

| HTTP | Code | Meaning |
|---|---|---|
| 400 | VALIDATION_ERROR | Invalid request body |
| 400 | INVALID_FILE_TYPE | Extension not in allowlist |
| 400 | INVALID_FILE_MAGIC | File header does not match declared type |
| 400 | MESSAGE_TOO_LONG | Agent message exceeds 8000 chars |
| 401 | UNAUTHORIZED | Missing or invalid token |
| 401 | SSE_TOKEN_INVALID | SSE token not found, expired, or already used |
| 403 | FORBIDDEN | Insufficient role |
| 403 | REGISTRATION_CLOSED | First user already exists |
| 404 | NOT_FOUND | Resource not found |
| 409 | EMAIL_EXISTS | Email already registered |
| 410 | INVITATION_EXPIRED | Invitation token expired or used |
| 413 | FILE_TOO_LARGE | Exceeds MAX_FILE_SIZE_MB |
| 422 | UNPROCESSABLE | FastAPI schema validation failure |
| 429 | RATE_LIMITED | Rate limit exceeded |
| 500 | INTERNAL_ERROR | Unexpected server error |
| 503 | DEPENDENCY_UNAVAILABLE | Ollama, ChromaDB, or PostgreSQL unreachable |

---

## Rate Limiting

Rate limiting is applied from **Phase 1** (not deferred to Phase 6).

| Endpoint Group | Limit | Scope |
|---|---|---|
| POST /auth/login | 10 req/min | per IP |
| POST /auth/register | 5 req/min | per IP |
| POST /auth/sse-token | 60 req/min | per user |
| POST /documents/upload | 20 req/hour | per user |
| POST /agents/sessions/*/chat | 30 req/hour | per user |
| POST /search/ask | 30 req/hour | per user |
| POST /search | 60 req/min | per user |
| GET /health | 120 req/min | per IP |
| All others | 120 req/min | per user |
