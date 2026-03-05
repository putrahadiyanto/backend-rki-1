import os
from motor.motor_asyncio import AsyncIOMotorClient

from app.utils.logger import get_logger

class Database:
    """
    Manages the MongoDB connection lifecycle.
    """
    def __init__(self):
        self.client: AsyncIOMotorClient = None
        self.logger = get_logger()

    async def connect(self, uri: str):
        """Establish connection to MongoDB."""
        try:
            self.client = AsyncIOMotorClient(
                uri,
                maxPoolSize=10,
                minPoolSize=1,
            )
            # Verify connection
            await self.client.admin.command('ping')
            db_name = os.getenv('MONGO_DB_NAME')
            self.logger.info(f"Successfully connected to MongoDB: {db_name}")
        except Exception as e:
            self.logger.error(f"Failed to connect to MongoDB: {e}")
            raise e

    async def disconnect(self):
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            self.logger.info("Successfully disconnected from MongoDB")

    def get_db(self):
        """Return the database instance."""
        db_name = os.getenv('MONGO_DB_NAME')
        if not self.client:
            raise RuntimeError("MongoDB client is not connected")
        if not db_name:
            raise RuntimeError("MONGO_DB_NAME is not set in environment")
        return self.client[db_name]

# Global instance for the application
db = Database()

# Functional wrappers to maintain compatibility with existing imports
connect = db.connect
disconnect = db.disconnect
get_database = db.get_db