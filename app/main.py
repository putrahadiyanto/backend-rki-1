from fastapi import FastAPI
from contextlib import asynccontextmanager
import os
from app.db.mongodb import connect, disconnect
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to MongoDB when the application starts
    uri = os.getenv('MONGO_URI')
    await connect(uri)
    yield
    # Disconnect from MongoDB when the application shuts down
    await disconnect()

app = FastAPI(lifespan=lifespan)