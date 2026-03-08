import os
import asyncio
from dotenv import load_dotenv
from app.services.auth_service import AuthService
from app.db.mongodb import connect, disconnect, get_database

load_dotenv()

async def seed_admin():
    mongo_uri = os.getenv("MONGO_URI")
    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")
    email = os.getenv("ADMIN_EMAIL")

    missing = [k for k, v in {"MONGO_URI": mongo_uri, "ADMIN_USERNAME": username, "ADMIN_PASSWORD": password, "ADMIN_EMAIL": email}.items() if not v]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    await connect(mongo_uri)
    db = get_database()
    auth_service = AuthService()

    users_collection = db.get_collection("users")
    if not await users_collection.find_one({"username": username}):
        await auth_service.register_user(username, password, email)
        print(f"Admin user '{username}' created.")
    else:
        print(f"Admin user '{username}' already exists.")
    await disconnect()

if __name__ == "__main__":
    asyncio.run(seed_admin())
