from pydantic import BaseModel, Field
from datetime import datetime, timezone

class User(BaseModel):
    username: str
    email: str
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
