from pydantic import BaseModel

class RegisterForm(BaseModel):
    username: str
    email: str
    password: str
