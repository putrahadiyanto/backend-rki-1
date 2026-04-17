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

**Quiz Generation** (`/chat/generate_quiz`)
- POST `/chat/generate_quiz` — generate a quiz based on a topic using the latest user session (protected)
   - Header: `Authorization: Bearer <access_token>`
   - Query parameters: `topic` (string, required) — the quiz topic
   - Response: `{ "session_id": "<uuid>", "quiz": { "topic": "...", "message": "...", "questions": [...] } }`
   - Quiz structure:
     ```json
     {
       "topic": "jantung",
       "message": "Pengantar kuis...",
       "questions": [
         {
           "question_text": "Pertanyaan?",
           "answer_options": ["opsi 1", "opsi 2", "opsi 3", "opsi 4"],
           "correct_answer_index": 0
         }
       ]
     }
     ```
   - Behavior: fetches (or creates) the user's latest session, uses recent chat history as context for quiz generation, and calls the LLM to create 3-5 questions focused on the topic.

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

- **LLM Integration**: The backend uses **LangChain** with **Groq** (qwen/qwen3-32b model) for chat responses and quiz generation.
  - Chat responses are generated using `generate_chat_response()` which accepts a user prompt and recent chat history as LangChain message objects.
  - Quiz generation uses `generate_quiz_tool()` which leverages LangChain tool binding to invoke structured quiz generation via the `generate_quiz` tool.
  
- **Quiz generation flow**:
  1. Client calls `POST /chat/generate_quiz?topic=<topic>`
  2. Backend fetches (or creates) user's latest session
  3. Builds recent chat history (up to 20 messages) as context
  4. Calls LLM with a system prompt instructing it to generate 3-5 questions on the topic based only on previously discussed material
  5. Returns structured quiz data with message, questions, and answer options

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
- `GROQ_API_KEY` — API key for Groq LLM provider (qwen/qwen3-32b model)
- `LLM_MAX_CONCURRENCY` — integer limit for simultaneous LLM calls (default: 5)
- `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` — JWT expiration settings

---

**Architecture notes**

**Service Layer** (`app/services/`):
- `auth_service.py` — handles JWT generation, token validation, user registration/login
- `chat_service.py` — manages chat sessions, messages, and orchestrates LLM calls
  - `generate_and_store()` — stores user message, builds chat history context, calls LLM, stores assistant reply
  - `generate_quiz()` — fetches/creates latest session, generates quiz via LLM tool binding
- `llm_service.py` — LLM integration using **LangChain** and **Groq**
  - `generate_chat_response()` — async chat generation with system prompt, history context, and error handling
  - `generate_quiz_tool()` — async quiz generation using LangChain's tool binding to invoke `generate_quiz` tool
  - `QuizFormat` (Pydantic) — enforces quiz structure with 3-5 questions, 4 options each, one correct answer

**Key Dependencies** (new in refactor):
- `langchain-core` — LangChain core library and message types
- `langchain-groq` — Groq LLM integration for LangChain
- `langchain` — main LangChain framework with tools and agent utilities
- `pydantic` — data validation and structured responses

**Data Flow**:
1. Chat message: `WebSocket.send_message` → `ChatService.generate_and_store` → `generate_chat_response` (LLM) → store assistant reply → WebSocket response
2. Quiz generation: `HTTP POST /chat/generate_quiz?topic=X` → `ChatService.generate_quiz` → build history → `generate_quiz_tool` (LLM with tool binding) → return structured quiz

---

**Notes for integration testing**
- Start a local MongoDB (or use a test DB) before launching the server.
- Ensure `GROQ_API_KEY` is set in `.env` or environment (required for LLM calls).
- Use `--reload` for development but use single-worker `uvicorn` for local testing of in-process session locks. For multi-worker production, per-session in-memory locks do not synchronize across workers (use Redis locks if you plan to run multiple workers).

---

**Testing the quiz endpoint**

Via curl:
```bash
curl -X POST \
  -H "Authorization: Bearer <access_token>" \
  "http://localhost:8000/chat/generate_quiz?topic=jantung"
```

Via the CLI test utility:
```bash
python -m app.utils.test_chat_websocket
# Then type: /minigame
# And enter topic: jantung
```