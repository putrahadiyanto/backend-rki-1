import os
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from app.models.user import User
from app.db.mongodb import get_database

class AuthService:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    SECRET_KEY = os.getenv("SECRET_KEY")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

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
        hashed_password = self.get_password_hash(password)
        user = User(username=username, email=email, hashed_password=hashed_password)
        db = get_database()
        users_collection = db.get_collection("users")
        await users_collection.insert_one(user.dict())
        return user

    async def authenticate_user(self, username, password):
        db = get_database()
        users_collection = db.get_collection("users")
        user = await users_collection.find_one({"username": username})
        if not user or not self.verify_password(password, user["hashed_password"]):
            return None
        return user

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
