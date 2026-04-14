import os
import secrets
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from app.models.user import User
from app.db.mongodb import get_database

class AuthService:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    ALGORITHM = "HS256"

    def __init__(self):
        self.SECRET_KEY = os.getenv("SECRET_KEY")
        if not self.SECRET_KEY:
            raise RuntimeError("SECRET_KEY environment variable is not set")
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
        self.REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

    def get_password_hash(self, password):
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password, hashed_password):
        return self.pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, data: dict, expires_delta: timedelta | None = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    async def register_user(self, username, password, email):
        db = get_database()
        users_collection = db.get_collection("users")
        if await users_collection.find_one({"$or": [{"username": username}, {"email": email}]}):
            return None
        hashed_password = self.get_password_hash(password)
        user = User(username=username, email=email, hashed_password=hashed_password)
        await users_collection.insert_one(user.model_dump())
        return user

    async def authenticate_user(self, username, password):
        db = get_database()
        users_collection = db.get_collection("users")
        user = await users_collection.find_one({"username": username})
        if not user or not self.verify_password(password, user["hashed_password"]):
            return None
        return user

    async def create_refresh_token(self, username: str) -> str:
        token = secrets.token_urlsafe(64)
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        db = get_database()
        await db.get_collection("refresh_tokens").insert_one({
            "token": token,
            "username": username,
            "expires_at": expires_at,
            "revoked": False,
        })
        return token

    async def refresh_access_token(self, refresh_token: str) -> str:
        db = get_database()
        record = await db.get_collection("refresh_tokens").find_one({"token": refresh_token})
        if not record or record["revoked"]:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked refresh token")
        if record["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
        return self.create_access_token(
            data={"sub": record["username"]},
            expires_delta=timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

    async def revoke_refresh_token(self, refresh_token: str):
        db = get_database()
        await db.get_collection("refresh_tokens").update_one(
            {"token": refresh_token},
            {"$set": {"revoked": True}},
        )

    async def get_current_user(self, token: str):
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                return None
        except JWTError:
            return None
        db = get_database()
        users_collection = db.get_collection("users")
        user = await users_collection.find_one({"username": username})
        return user

    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

    async def get_authenticated_username(self, token: str = Depends(oauth2_scheme)) -> str:
        """FastAPI dependency: validate OAuth2 Bearer token and return the username."""
        if not token:
            raise HTTPException(status_code=401, detail="Missing token")
        user = await self.get_current_user(token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return user["username"]
