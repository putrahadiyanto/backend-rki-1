from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.services.auth_service import AuthService
from datetime import timedelta
from app.models.auth import RegisterForm, RefreshRequest

router = APIRouter()
auth_service = AuthService()

@router.post("/register")
async def register(form_data: RegisterForm):
    user = await auth_service.register_user(form_data.username, form_data.password, form_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )
    return {"message": "User registered successfully"}

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth_service.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    refresh_token = await auth_service.create_refresh_token(user["username"])
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/refresh")
async def refresh(body: RefreshRequest):
    access_token = await auth_service.refresh_access_token(body.refresh_token)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout(body: RefreshRequest):
    await auth_service.revoke_refresh_token(body.refresh_token)
    return {"message": "Successfully logged out"}
