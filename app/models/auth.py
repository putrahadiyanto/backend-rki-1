from pydantic import BaseModel

class RegisterForm(BaseModel):
    username: str
    email: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str
