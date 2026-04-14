# Backend API — Frontend Integration Guide

This document describes the HTTP and WebSocket APIs exposed by the backend, authentication flow, message formats, examples (curl / JS), and operational notes for frontend engineers.

**Base URL**
- Local development (default): `http://localhost:8000`
- WebSocket base: `ws://localhost:8000/ws/chat`

**Quick start (run locally without Docker)**
1. Create a Python virtual environment and activate it:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the `backend` folder (or set env vars in your shell). Required environment variables (example values):

```
SECRET_KEY=changeme123
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=rki_db
GROQ_API_KEY=<your_groq_api_key>
LLM_MAX_CONCURRENCY=5
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

4. Start the server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

OpenAPI docs will be available at `http://localhost:8000/docs`.

**Authentication Flow**
- Login (OAuth2 password grant via `/auth/token`) returns `access_token` (JWT) and `refresh_token`.
- Use `Authorization: Bearer <access_token>` header for protected HTTP endpoints.
- For WebSocket, after opening the socket, send an `authenticate` action with `token` field containing the `access_token`.
- When access token expires, call `/auth/refresh` with the `refresh_token` to obtain a new `access_token`.

---

**HTTP API Endpoints**

All endpoints below are mounted on the app root unless otherwise specified. See `app/api/*` for server code.

**Auth** (`/auth`)
- POST `/auth/register` — register new user
   - Body: `{ "username": "string", "email": "string", "password": "string" }`
   - Response: `{ "message": "User registered successfully" }`

- POST `/auth/token` — login (OAuth2 password grant)
   - Form fields: `username`, `password` (application/x-www-form-urlencoded)
   - Response: `{ "access_token": "<jwt>", "refresh_token": "<refresh>", "token_type": "bearer" }`

- POST `/auth/refresh` — refresh access token
   - Body: `{ "refresh_token": "string" }`
   - Response: `{ "access_token": "<jwt>", "token_type": "bearer" }`

- POST `/auth/logout` — revoke refresh token
   - Body: `{ "refresh_token": "string" }`
   - Response: `{ "message": "Successfully logged out" }`

**Chat session management**
- GET `/sessions` — list sessions (protected)
   - Header: `Authorization: Bearer <access_token>`
   - Response: array of session objects (summary fields: `session_id`, `title`, `created_at`, `updated_at`).

- POST `/sessions` — create a new session (protected)
   - Header: `Authorization: Bearer <access_token>`
   - Body: none
   - Response: `{ "session_id": "<uuid>" }`

- GET `/sessions/{session_id}/history` — get full session messages (protected)
   - Header: `Authorization: Bearer <access_token>`
   - Response: `{ "session_id": "<uuid>", "messages": [ { role, content, timestamp }, ... ] }`
   - Errors: 404 if session not found or not owned by the authenticated user.

- DELETE `/sessions/{session_id}` — delete session (protected)
   - Header: `Authorization: Bearer <access_token>`
   - Response: `{ "deleted": true, "session_id": "<uuid>" }`

---

**WebSocket: Realtime chat**

- URL: `ws://<host>:<port>/ws/chat`
- Message format: text frames containing JSON objects.
- All messages are JSON objects with at minimum an `action` field; additional fields depend on the action.

Supported actions (client -> server):

1. Authenticate (must be sent first)
```json
{ "action": "authenticate", "token": "<access_token>" }
```
- Success response:
```json
{ "action": "authenticated", "username": "<username>" }
```
- Failure: `{ "error": "Invalid or expired token" }`

2. Send message (prompt the LLM and store messages)
```json
{ "action": "send_message", "session_id": "<uuid>", "content": "User question or prompt" }
```
- Server behavior: validates inputs, stores the user message, builds recent context, calls the LLM, stores assistant reply, and returns a `chat_response` message.
- Successful response example:
```json
{
   "action": "chat_response",
   "session_id": "<uuid>",
   "user_message": { "role": "user", "content": "...", "timestamp": "..." },
   "assistant_message": { "role": "assistant", "content": "...", "timestamp": "..." },
   "thoughts": "optional internal thoughts",
   "action": "trigger_minigame",     // optional LLM-invoked tool
   "game_data": { /* optional tool payload */ }
}
```

3. Ping
```json
{ "action": "ping" }
```
- Server replies: `{ "action": "pong" }`

4. Errors / unknown actions
- Server replies with `{ "error": "<message>", "available_actions": [ ... ] }`.

**WebSocket auth note**: The WebSocket uses an explicit `authenticate` action with the token. The server maintains `authenticated_user` per connection. If client sends other actions before authentication, the server responds with an error asking to authenticate first.

---

**Data shapes**
- `ChatMessage`:
   - `{ "role": "user"|"assistant", "content": "string", "timestamp": "ISO-8601 string" }`
- `ChatSession`:
   - `{ "session_id": "uuid", "username": "string", "title": "optional", "messages": [ChatMessage], "created_at": "ISO", "updated_at": "ISO" }`

---

**Client examples**

Login (curl):
```bash
curl -X POST \
   -d "username=alice&password=secret" \
   http://localhost:8000/auth/token
```

Create session (fetch):
```js
await fetch('http://localhost:8000/sessions', {
   method: 'POST',
   headers: { 'Authorization': 'Bearer ' + access_token }
});
```

WebSocket example (browser JS):
```js
const ws = new WebSocket('ws://localhost:8000/ws/chat');
ws.onopen = () => {
   ws.send(JSON.stringify({ action: 'authenticate', token: ACCESS_TOKEN }));
   // then send a message
   ws.send(JSON.stringify({ action: 'send_message', session_id: SESSION_ID, content: 'Halo!' }));
};
ws.onmessage = (ev) => {
   const msg = JSON.parse(ev.data);
   console.log('recv', msg);
};
```

---

**Operational notes for frontend**

- Token handling: store `access_token` (short-lived) and `refresh_token` (longer-lived). When requests return 401, try `/auth/refresh` with `refresh_token` to get a new `access_token`.
- WebSocket: authenticate immediately after open. The connection is tied to the authenticated user for the lifetime of the socket.
- Concurrency: the backend serializes operations per `session_id` (in-process async locks) and caps concurrent LLM calls globally with an environment-driven semaphore `LLM_MAX_CONCURRENCY` (default `5`).
   - Result: multiple `send_message` calls against the same `session_id` are processed sequentially. Many concurrent messages across different sessions may be limited by the LLM concurrency cap and therefore may queue briefly.
- Timeouts / keepalives: the app supports an application-level `ping` action. There is no enforced app-side idle timeout by default (the server or reverse proxy might close idle sockets). Consider periodically sending `ping` from the client if necessary.
- Error handling: display server `error` objects to the user as friendly messages. If LLM errors occur, the message returned will include a fallback answer or an error field.

---

**Environment variables of interest**
- `SECRET_KEY` — required for JWT signing
- `MONGO_URI` — connection string to MongoDB
- `MONGO_DB_NAME` — database name
- `GROQ_API_KEY` — key for the LLM provider
- `LLM_MAX_CONCURRENCY` — integer limit for simultaneous LLM calls
- `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`

---

**Notes for integration testing**
- Start a local MongoDB (or use a test DB) before launching the server.
- Use `--reload` for development but use `uvicorn` single worker for local testing of in-process session locks. For multi-worker production, per-session in-memory locks do not synchronize across workers (use Redis locks if you plan to run multiple workers).

---

If you want, I can:
- Add this README into the repository (it is saved at `backend/README.md`).
- Generate a condensed `API.md` or `openapi` examples for the frontend.

Tell me if you'd like the README saved in a different location or want additional example flows (e.g., refresh-token implementation in frontend code).
