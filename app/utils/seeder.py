import os
import asyncio
from dotenv import load_dotenv
from app.services.auth_service import AuthService
from app.db.mongodb import connect, disconnect, get_database
from app.utils.logger import get_logger

load_dotenv()

logger = get_logger()

async def seed_admin(standalone: bool = False):
    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")
    email = os.getenv("ADMIN_EMAIL")

    required = {"ADMIN_USERNAME": username, "ADMIN_PASSWORD": password, "ADMIN_EMAIL": email}
    if standalone:
        required["MONGO_URI"] = os.getenv("MONGO_URI")

    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    if standalone:
        await connect(os.getenv("MONGO_URI"))

    db = get_database()
    auth_service = AuthService()

    users_collection = db.get_collection("users")
    if not await users_collection.find_one({"username": username}):
        await auth_service.register_user(username, password, email)
        logger.info(f"Admin user '{username}' created.")
    else:
        logger.info(f"Admin user '{username}' already exists.")

    if standalone:
        await disconnect()

if __name__ == "__main__":
    asyncio.run(seed_admin(standalone=True))
