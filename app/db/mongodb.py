import os
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic_settings import BaseSettings

from app.utils.logger import get_logger

# Define the Database class
class Database:
    # MongoDB client instance
    client: AsyncIOMotorClient = None


# Create an instance of the Database class
db = Database()
# Initialize the logger
logger = get_logger()


# Connect to MongoDB using the provided URI
async def connect(self, uri: str):

    # Load MongoDB URI and database name from environment variables
    uri = os.getenv(uri)
    db_name = os.getenv('MONGO_DB_NAME')

    # Attempt to connect to MongoDB
    try:
        db.client = AsyncIOMotorClient(
            uri,
            maxPoolSize=10,
            minPoolSize=1,
        )

        await db.client.admin.command('ping')
        logger.info(f"Successfully connected to MongoDB: {db_name}")
    
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise e

# Disconnect from MongoDB
async def disconnect(self):
    # Close the MongoDB client connection if it exists
    if db.client:
        db.client.close()
        logger.info("Successfully disconnected from MongoDB")

def get_database():
    # Return the MongoDB client instance
    db_name = os.getenv('MONGO_DB_NAME')
    return db.client[db_name]