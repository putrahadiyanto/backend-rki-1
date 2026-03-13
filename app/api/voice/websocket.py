from fastapi import WebSocket, APIRouter, WebSocketDisconnect
from app.utils.logger import get_logger
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.stt_service import transcribe_audio
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


@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    authenticated_user: str | None = None
    audio_buffer = bytearray()
    
    try:
        while True:
            # Receive data from client
            # It can be 'bytes' (audio chunks) or 'text' (control signals)
            try:
                raw = await websocket.receive()
            except WebSocketDisconnect:
                logger.info(f"Voice WS disconnected: {authenticated_user or 'unauthenticated'}")
                break
            except Exception as e:
                # Catch RuntimeError and any other unexpected receive errors
                logger.info(f"WebSocket receive error, closing connection: {e}")
                try:
                    await websocket.close()
                except Exception:
                    pass
                break

            raw_bytes = raw.get("bytes")
            raw_text = raw.get("text")

            # Handle binary audio data
            if raw_bytes is not None:
                # Defensive check to prevent buffer overflow
                if len(audio_buffer) + len(raw_bytes) < 10 * 1024 * 1024:  # 10MB limit
                    audio_buffer.extend(raw_bytes)
                else:
                    logger.warning("Audio buffer exceeded 10MB, resetting buffer")
                    audio_buffer.clear()
                continue

            # Handle text data (JSON actions)
            if raw_text is not None:
                try:
                    data = json.loads(raw_text)
                except json.JSONDecodeError:
                    await websocket.send_json({"error": "Invalid JSON"})
                    continue

                action = data.get("action")

                # ── Authentication (must be first action) ───────────
                if action == "authenticate":
                    token = data.get("token", "")
                    user = await auth_service.get_current_user(token)
                    if user:
                        authenticated_user = user["username"]
                        await websocket.send_json({
                            "action": "authenticated",
                            "username": authenticated_user,
                        })
                        logger.info(f"Voice WS authenticated: {authenticated_user}")
                    else:
                        await websocket.send_json({"error": "Invalid or expired token"})
                    continue

                # ── Guard: require auth for everything else ─────────
                if not authenticated_user:
                    await websocket.send_json({
                        "error": "Not authenticated. Send {\"action\": \"authenticate\", \"token\": \"...\"} first."
                    })
                    continue

                # ── Create session ──────────────────────────────────
                if action == "create_session":
                    session_id = await chat_service.create_session(authenticated_user)
                    await websocket.send_json({
                        "action": "session_created",
                        "session_id": session_id,
                    })
                    continue

                # ── List sessions ───────────────────────────────────
                elif action == "list_sessions":
                    sessions = await chat_service.get_sessions(authenticated_user)
                    await websocket.send_json({
                        "action": "sessions_list",
                        "sessions": json.loads(json.dumps(sessions, default=_serialize)),
                    })
                    continue

                # ── Get chat history ────────────────────────────────
                elif action == "get_history":
                    session_id = data.get("session_id")
                    if not session_id:
                        await websocket.send_json({"error": "session_id is required"})
                        continue

                    session = await chat_service.get_session(session_id, authenticated_user)
                    if not session:
                        await websocket.send_json({"error": "Session not found"})
                        continue

                    await websocket.send_json({
                        "action": "chat_history",
                        "session_id": session_id,
                        "messages": json.loads(json.dumps(session.get("messages", []), default=_serialize)),
                    })
                    continue

                # ── Process audio ───────────────────────────────────
                elif action == "end_of_speech":
                    session_id = data.get("session_id")
                    if not session_id:
                        await websocket.send_json({"error": "session_id is required"})
                        continue
                    
                    if not audio_buffer:
                        await websocket.send_json({"error": "No audio data received."})
                        continue

                    # Step 1: STT
                    try:
                        transcribed_text = await transcribe_audio(bytes(audio_buffer))
                        logger.info(f"Transcribed '{authenticated_user}': {transcribed_text}")
                    except Exception as e:
                        logger.error(f"Error during transcription: {e}")
                        transcribed_text = ""
                    
                    # Reset buffer after transcription
                    audio_buffer.clear()

                    if not transcribed_text:
                        await websocket.send_json({
                            "action": "stt_failure",
                            "session_id": session_id,
                            "error": "Sorry, I couldn't understand the audio. Please try again."
                        })
                        continue

                    # Step 2: Generate response and store history
                    try:
                        result = await chat_service.generate_and_store(
                            session_id, authenticated_user, transcribed_text
                        )
                        # Add the transcription to the response for the client
                        result["stt"] = transcribed_text
                        
                        await websocket.send_json({
                            "action": "chat_response",
                            **json.loads(json.dumps(result, default=_serialize)),
                        })
                    except ValueError as e:
                        await websocket.send_json({"error": str(e)})
                    except Exception as e:
                        logger.error(f"Error in voice processing: {e}")
                        await websocket.send_json({"error": "Internal server error"})
                    
                    continue

                # ── Delete session ──────────────────────────────────
                elif action == "delete_session":
                    session_id = data.get("session_id")
                    if not session_id:
                        await websocket.send_json({"error": "session_id is required"})
                        continue

                    deleted = await chat_service.delete_session(session_id, authenticated_user)
                    if deleted:
                        await websocket.send_json({
                            "action": "session_deleted",
                            "session_id": session_id,
                        })
                    else:
                        await websocket.send_json({"error": "Session not found"})
                    continue

                # ── Unknown action ──────────────────────────────────
                else:
                    await websocket.send_json({
                        "error": f"Unknown action: {action}",
                        "available_actions": [
                            "authenticate", "create_session", "list_sessions",
                            "get_history", "end_of_speech", "delete_session",
                        ],
                    })

    except WebSocketDisconnect:
        logger.info(f"Voice WS disconnected: {authenticated_user or 'unauthenticated'}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in voice websocket: {e}")
        try:
            # Attempt to inform the client before closing
            await websocket.send_json({"error": "An unexpected server error occurred."})
            await websocket.close()
        except Exception:
            pass # Ignore errors during cleanup