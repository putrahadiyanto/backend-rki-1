# Backend RKI-1

A FastAPI-based backend service integrating speech-to-text, LLM capabilities, document processing, and multi-turn chat for intelligent conversational applications.

## Features

- **FastAPI Framework**: Async web framework with automatic API documentation (Swagger/ReDoc).
- **MongoDB Integration**: Async MongoDB client (Motor) with connection lifecycle management.
- **Speech-to-Text (STT)**: Audio transcription using Groq's Whisper model (whisper-large-v3-turbo).
- **LLM Integration**: Text generation, thinking/answer separation using Groq's language models.
- **Multi-turn Chat**: WebSocket-based chat with persistent session history in MongoDB.
- **Authentication**: JWT-based user registration, login, and token management.
- **Document Processing**: PDF to Markdown conversion and text chunking (for RAG).
- **Containerization**: Docker support for easy building and deployment.

## Prerequisites

- Python 3.8+
- MongoDB
- Docker (optional, for containerized deployment)
- Groq API key

## Installation

### Local Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd backend-rki-1
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   # On macOS/Linux
   source venv/bin/activate
   # On Windows
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and configure the following variables:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   MONGO_URI=mongodb://localhost:27017
   MONGO_DB_NAME=your_database_name
   ```

5. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

### Docker Setup

1. **Build and run with Docker Compose**
   ```bash
   docker-compose up --build
   ```

## Endpoints

### REST API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check |
| `POST` | `/auth/register` | Register a new user (`username`, `email`, `password`) |
| `POST` | `/auth/token` | Login and receive a JWT access token |
| `POST` | `/auth/logout` | Logout (client-side token invalidation) |

### WebSocket

| Path | Description |
|------|-------------|
| `/ws/voice` | Voice assistant — stream audio chunks, receive STT + LLM response |
| `/ws/chat` | Multi-turn chat — JWT auth, session management, persistent history |

#### `/ws/voice` Protocol

1. Connect to `ws://host:8000/ws/voice`
2. Send audio bytes in chunks
3. Send text `"END_OF_SPEECH"` when done
4. Receive JSON: `{"stt": "...", "thinking": "...", "answer": "..."}`

#### `/ws/chat` Protocol

1. Connect to `ws://host:8000/ws/chat`
2. **Authenticate first**: `{"action": "authenticate", "token": "<JWT>"}`
3. Send JSON commands:

| Action | Payload | Response |
|--------|---------|----------|
| `authenticate` | `token` | `{"action": "authenticated", "username": "..."}` |
| `create_session` | — | `{"action": "session_created", "session_id": "..."}` |
| `list_sessions` | — | `{"action": "sessions_list", "sessions": [...]}` |
| `get_history` | `session_id` | `{"action": "chat_history", "messages": [...]}` |
| `send_message` | `session_id`, `content` | `{"action": "chat_response", "user_message": {...}, "assistant_message": {...}, "thinking": "..."}` |
| `delete_session` | `session_id` | `{"action": "session_deleted", "session_id": "..."}` |

### Auto-generated Docs

Once the application is running, visit:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Project Structure

```text
backend-rki-1/
├── app/
│   ├── main.py                # FastAPI entry point & lifespan events
│   ├── api/                   # API Routes (REST and WebSockets)
│   │   ├── auth/auth.py       # Registration, login, logout
│   │   ├── chat/websocket.py  # Multi-turn chat WebSocket
│   │   ├── document/ingest.py # Document processing endpoints
│   │   └── voice/websocket.py # Voice/STT WebSocket
│   ├── db/
│   │   └── mongodb.py         # MongoDB Motor async client
│   ├── models/                # Pydantic data models
│   │   ├── auth.py            # RegisterForm
│   │   ├── chat.py            # ChatSession, ChatMessage
│   │   └── user.py            # User
│   ├── services/              # Business Logic Layer
│   │   ├── auth_service.py    # JWT auth, password hashing
│   │   ├── chat_service.py    # Chat session CRUD, LLM orchestration
│   │   ├── ingest_service.py  # PDF to Markdown, text chunking
│   │   ├── llm_service.py     # Groq LLM integration
│   │   └── stt_service.py     # Speech-to-text with Groq Whisper
│   └── utils/
│       ├── logger.py          # Logging utilities
│       ├── seeder.py          # Admin user seeder
│       └── test_*.py          # Test scripts
├── docker-compose.yaml        # Docker Compose configuration
├── dockerfile                 # Container configuration
└── requirements.txt           # Python dependencies
```

## Key Components

### Services
- **Auth Service** (`auth_service.py`): User registration, password hashing (bcrypt), JWT token management.
- **Chat Service** (`chat_service.py`): Chat session CRUD, message persistence, multi-turn LLM orchestration with system instructions.
- **STT Service** (`stt_service.py`): Transcribes audio bytes to text using Groq Whisper.
- **LLM Service** (`llm_service.py`): Generates responses using Groq's LLMs (single-turn and multi-turn).
- **Ingest Service** (`ingest_service.py`): Converts PDFs to Markdown format, splits text into chunks, and prepares documents for RAG applications.

### Database
- **MongoDB** (`mongodb.py`): Async MongoDB client. Connections are managed through FastAPI's lifespan events in `app/main.py`.
- **Collections**: `users` (user accounts), `chat_sessions` (chat history with embedded messages).

## Developer Guide

### Adding a new REST API Endpoint

1. **Create the Route File**
   Create a new Python file in the appropriate directory (e.g., `app/api/your_feature/routes.py`).

2. **Define the APIRouter and Endpoint**
   ```python
   # app/api/your_feature/routes.py
   from fastapi import APIRouter, HTTPException
   from pydantic import BaseModel

   router = APIRouter()

   class ItemRequest(BaseModel):
       name: str
       description: str

   @router.post("/items")
   async def create_item(item: ItemRequest):
       try:
           # Call a service from app.services
           return {"message": f"Item {item.name} created successfully"}
       except Exception as e:
           raise HTTPException(status_code=500, detail=str(e))
   ```

3. **Register the Router in `app/main.py`**
   ```python
   # app/main.py
   from fastapi import FastAPI
   from app.api.your_feature.routes import router as your_feature_router
   
   app = FastAPI(...)

   # Include your new router
   app.include_router(your_feature_router, prefix="/api/v1/feature", tags=["FeatureName"])
   ```

### Adding a new WebSocket Endpoint

1. **Create the Route File**
   Create a new Python file in the appropriate directory (e.g., `app/api/your_feature/websocket.py`).

2. **Define the APIRouter and WebSocket Endpoint**
   ```python
   # app/api/your_feature/websocket.py
   from fastapi import APIRouter, WebSocket, WebSocketDisconnect
   import logging

   router = APIRouter()
   logger = logging.getLogger(__name__)

   @router.websocket("/ws/feature")
   async def feature_websocket(websocket: WebSocket):
       await websocket.accept()
       try:
           while True:
               # Receive message from client
               message = await websocket.receive_text()
               
               # Process message and send response
               response = f"Processed: {message}"
               await websocket.send_text(response)
       except WebSocketDisconnect:
           logger.info("Client disconnected from /ws/feature")
       except Exception as e:
           logger.error(f"WebSocket error: {e}")
           await websocket.close()
   ```

3. **Register the Router in `app/main.py`**
   ```python
   # app/main.py
   from fastapi import FastAPI
   from app.api.your_feature.websocket import router as your_ws_router
   
   app = FastAPI(...)

   # Include your new websocket router
   app.include_router(your_ws_router)
   ```

## Development Commands

**Run the app locally:**
```bash
uvicorn app.main:app --reload
```

**Run with Docker:**
```bash
docker compose up -d --build
```

**Seed admin user:**
```bash
# Local
python -m app.utils.seeder
# Docker
docker exec backend_fastapi python -m app.utils.seeder
```

**Test chat WebSocket:**
```bash
python -m app.utils.test_chat_websocket
```

**Run local document ingestion script:**
```bash
python -m app.services.ingest_service
```
*(Ensure PDF files are placed in the `./data/pdf/` directory.)*
