from fastapi import FastAPI
from contextlib import asynccontextmanager
import os
from app.api.voice.websocket import router as voice_router
from app.db.mongodb import connect, disconnect
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to MongoDB when the application starts
    uri = os.getenv('MONGO_URI')

    if not uri:
        raise RuntimeError("MONGO_URI is not set in environment")
    

    await connect(uri)

    yield
    
    # Disconnect from MongoDB when the application shuts down
    await disconnect()

app = FastAPI(
    title = "RKI Backend API",
    lifespan=lifespan
)

app.include_router(voice_router)

@app.get("/")
async def root():
    return {"message": "Hello World"}