from fastapi import WebSocket, APIRouter, WebSocketDisconnect
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.utils.logger import get_logger
import json

logger = get_logger()
router = APIRouter()
auth_service = AuthService()
chat_service = ChatService()


def _serialize(obj):
    """Make datetime objects JSON-serializable."""
    from datetime import datetime
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()
    authenticated_user: str | None = None

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            action = data.get("action")

            # ── Authentication (must be first action) ────────────
            if action == "authenticate":
                token = data.get("token", "")
                user = await auth_service.get_current_user(token)
                if user:
                    authenticated_user = user["username"]
                    await websocket.send_json({
                        "action": "authenticated",
                        "username": authenticated_user,
                    })
                    logger.info(f"Chat WS authenticated: {authenticated_user}")
                else:
                    await websocket.send_json({"error": "Invalid or expired token"})
                continue

            # ── Guard: require auth for everything else ──────────
            if not authenticated_user:
                await websocket.send_json({
                    "error": "Not authenticated. Send {\"action\": \"authenticate\", \"token\": \"...\"} first."
                })
                continue

            # ── Send message (prompt LLM) ────────────────────────
            elif action == "send_message":
                session_id = data.get("session_id")
                content = data.get("content", "").strip()
                if not session_id or not content:
                    await websocket.send_json({"error": "session_id and content are required"})
                    continue

                try:
                    result = await chat_service.generate_and_store(
                        session_id, authenticated_user, content
                    )
                    await websocket.send_json({
                        "action": "chat_response",
                        "session_id": session_id,
                        **json.loads(json.dumps(result, default=_serialize)),
                    })
                except ValueError as e:
                    await websocket.send_json({"error": str(e)})
                except Exception as e:
                    logger.error(f"Error in send_message: {e}")
                    await websocket.send_json({"error": "Internal server error"})

            elif action == "ping":
                await websocket.send_json({"action": "pong"})
                continue

            # ── Unknown action ───────────────────────────────────
            else:
                await websocket.send_json({
                    "error": f"Unknown action: {action}",
                    "available_actions": [
                        "authenticate", "send_message", "ping",
                    ],
                })

    except WebSocketDisconnect:
        logger.info(f"Chat WS disconnected: {authenticated_user or 'unauthenticated'}")
    except Exception as e:
        logger.error(f"Unexpected error in chat websocket: {e}")
        try:
            await websocket.send_json({"error": "An unexpected server error occurred."})
            await websocket.close()
        except Exception:
            pass
