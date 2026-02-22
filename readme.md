```
backend_rki_1/
├── app/
│   ├── __init__.py
│   ├── main.py              # Entry point: initializes FastAPI and includes routers
│   ├── core/                # Shared configurations
│   │   ├── config.py        # Environment variables (GROQ_API_KEY, MONGO_URI)
│   │   └── security.py      # Auth/Session logic
│   ├── api/                 # API Routes (Routers)
│   │   ├── endpoints/
│   │   │   ├── chat.py      # Main /chat WebSocket or POST endpoint
│   │   │   ├── vision.py    # Endpoint for YOLO prediction results
│   │   │   └── history.py   # CRUD for chat history
│   ├── services/            # Pure Business Logic (The "Brain")
│   │   ├── stt_service.py   # Groq Whisper integration logic
│   │   ├── rag_service.py   # Vector search logic (Retrieve)
│   │   ├── llm_service.py   # Groq LLM orchestration (Prompting)
│   │   └── history_service.py # MongoDB interactions for sessions
│   ├── models/              # Pydantic Schemas (Data Validation)
│   │   ├── chat.py          # Request/Response schemas
│   │   └── history.py       # DB-specific data models
│   ├── db/                  # Database connections
│   │   ├── mongodb.py       # Motor (async) MongoDB client setup
│   │   └── vector_store.py  # Connection to Vector DB (FAISS/Qdrant/Milvus)
│   └── utils/               # Helpers
│       ├── chunking.py      # Logic to process Biology PDFs
│       └── prompts.py       # Biology-specific System Prompts
├── data/                    # For local Vector DB storage or PDF raw data
├── .env                     # API keys and secrets
├── requirements.txt
└── README.md
```