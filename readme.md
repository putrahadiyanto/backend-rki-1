# Backend RKI-1

A FastAPI-based backend service integrating speech-to-text, LLM capabilities, and document processing for intelligent conversational applications.

## Project Structure

```
backend-rki-1/
├── app/
│   ├── main.py              # FastAPI entry point with MongoDB lifecycle management
│   ├── api/                 # API Routes and Endpoints
│   │   └── vision/
│   │       └── vision.py    # Vision/YOLO endpoint (placeholder)
│   ├── db/
│   │   └── mongodb.py       # MongoDB connection management (Motor async client)
│   ├── services/            # Business Logic Layer
│   │   ├── ingest_service.py    # PDF to Markdown conversion and text ingestion
│   │   ├── llm_service.py       # Groq LLM integration for text generation
│   │   └── stt_service.py       # Speech-to-text using Groq Whisper
│   └── utils/
│       └── logger.py        # Logging utilities
├── docker-compose.yaml      # Docker orchestration
├── dockerfile               # Container configuration
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (not tracked)
└── .env.example             # Environment variables template
```

## Features

- **FastAPI Framework**: Async web framework with automatic API documentation
- **MongoDB Integration**: Async MongoDB client with lifecycle management
- **Speech-to-Text**: Audio transcription using Groq's Whisper model
- **LLM Integration**: Text generation using Groq's language models
- **Document Processing**: PDF to Markdown conversion with MarkItDown
- **Text Chunking**: Markdown text splitting for embeddings and RAG
- **Containerization**: Docker support for easy deployment

## Prerequisites

- Python 3.8+
- MongoDB
- Docker (optional)
- Groq API key

## Installation

### Local Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd backend-rki-1
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your configuration:
   ```
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

## API Documentation

Once the application is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Key Components

### Services

- **STT Service** (`stt_service.py`)
  - Transcribes audio to text using Groq Whisper (whisper-large-v3-turbo)
  - Accepts audio bytes and returns transcription text

- **LLM Service** (`llm_service.py`)
  - Generates text responses using Groq's LLM
  - Handles prompt-based text generation

- **Ingest Service** (`ingest_service.py`)
  - Converts PDF documents to Markdown format
  - Splits text into chunks for embedding
  - Prepares documents for RAG applications

### Database

- **MongoDB** (`mongodb.py`)
  - Async MongoDB client using Motor
  - Connection lifecycle managed through FastAPI lifespan
  - Supports text embeddings and document storage

## Dependencies

```
fastapi==0.129.2          # Web framework
uvicorn==0.41.0           # ASGI server
groq==1.0.0               # Groq API client
motor==3.7.1              # Async MongoDB driver
markitdown==0.1.5         # PDF to Markdown conversion
langchain-text-splitters==1.1.1  # Text chunking
python-multipart==0.0.22  # File upload support
pydantic-settings==2.13.1 # Settings management
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | API key for Groq services | Yes |
| `MONGO_URI` | MongoDB connection string | Yes |
| `MONGO_DB_NAME` | MongoDB database name | Yes |

## Development

### Linting
```bash
flake8 app/
```

### Document Ingestion
To convert PDFs to Markdown:
```bash
python -m app.services.ingest_service
```
Place PDF files in `./data/pdf/` directory.
