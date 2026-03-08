import os
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from app.models.user import User
from app.db.mongodb import get_database

class AuthService:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

    def __init__(self):
        self.SECRET_KEY = os.getenv("SECRET_KEY")
        if not self.SECRET_KEY:
            raise RuntimeError("SECRET_KEY environment variable is not set")

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

    async def get_current_user(self, token: str):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
        db = get_database()
        users_collection = db.get_collection("users")
        user = await users_collection.find_one({"username": username})
        if user is None:
            raise credentials_exception
        return user
