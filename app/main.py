from dotenv import load_dotenv

load_dotenv(override=True)

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth.auth import router as auth_router
from app.api.chat.manage_chat import router as crud_chat
from app.api.chat.websocket import router as chat_router
from app.api.detection.detect import router as detection_router
from app.db.mongodb import connect, db, disconnect
from app.utils.seeder import seed_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to MongoDB when the application starts
    uri = os.getenv("MONGO_URI")

    # Connect to the DB
    await connect(uri)

    # Store the database manager in app.state for standard access
    app.state.db = db

    # Run seeder to ensure admin user exists
    await seed_admin()

    yield

    # Disconnect from the DB when the application shuts down
    await disconnect()


app = FastAPI(
    title="RKI Backend API",
    lifespan=lifespan,
)

# app.include_router(voice_router)
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(chat_router)
# include HTTP session management endpoints
app.include_router(crud_chat, prefix="/chat", tags=["chat"])
# app.include_router(ingest_router)
app.include_router(detection_router, prefix="/api", tags=["detection"])


@app.get("/")
async def root():
    return {"message": "Hello World"}
