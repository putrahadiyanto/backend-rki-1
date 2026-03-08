from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI
from contextlib import asynccontextmanager
import os
from app.api.voice.websocket import router as voice_router
from app.api.document.ingest import router as ingest_router
from app.db.mongodb import db, connect, disconnect

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to MongoDB when the application starts
    uri = os.getenv('MONGO_URI')

    # Connect to the DB
    await connect(uri)
    # Store the database manager in app.state for standard access
    app.state.db = db
    
    yield

    # Disconnect from the DB when the application shuts down
    await disconnect()

app = FastAPI(
    title = "RKI Backend API",
    lifespan=lifespan
)

app.include_router(voice_router)
app.include_router(ingest_router)

@app.get("/")
async def root():
    return {"message": "Hello World"}