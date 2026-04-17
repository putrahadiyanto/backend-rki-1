from fastapi import APIRouter, HTTPException, Depends
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.utils.logger import get_logger

logger = get_logger()

router = APIRouter()
auth_service = AuthService()
chat_service = ChatService()

# Get List Session
@router.get('/sessions')
async def get_sessions(username: str = Depends(auth_service.get_authenticated_username)):
    sessions = await chat_service.get_sessions(username)
    return sessions

# Create Chat Session
@router.post('/sessions')
async def create_session(username: str = Depends(auth_service.get_authenticated_username)):
    session_id = await chat_service.create_session(username)
    return {"session_id": session_id}

# Get Session Chat History
@router.get('/sessions/{session_id}/history')
async def get_history(session_id: str, username: str = Depends(auth_service.get_authenticated_username)):
    session = await chat_service.get_session(session_id, username)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"session_id": session_id, "messages": session.get("messages", [])}

# Delete Session Chat
@router.delete('/sessions/{session_id}')
async def delete_session(session_id: str, username: str = Depends(auth_service.get_authenticated_username)):
    deleted = await chat_service.delete_session(session_id, username)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True, "session_id": session_id}

@router.post('/generate_quiz')
async def generate_quiz(topic: str, username: str = Depends(auth_service.get_authenticated_username)):
    try:
        result = await chat_service.generate_quiz(username, topic)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate quiz")

    return result
