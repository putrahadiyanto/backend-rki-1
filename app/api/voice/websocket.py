from fastapi import WebSocket, APIRouter, WebSocketDisconnect, HTTPException
from app.utils.logger import get_logger
from app.services.auth_service import AuthService
from app.services.llm_service import generate_response
from app.services.stt_service import transcribe_audio

logger = get_logger()

router = APIRouter()
auth_service = AuthService()

@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket, token: str):
    try:
        user = await auth_service.get_current_user(token)
    except HTTPException:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    audio_buffer = bytearray()
    
    try:
        while True:
            # Receive data from Android
            # It can be 'bytes' (audio chunks) or 'text' (control signals)
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                logger.info("Student disconnected")
                break
            except Exception as e:
                # Catch RuntimeError and any other unexpected receive errors
                logger.info(f"WebSocket receive error, closing connection: {e}")
                try:
                    await websocket.close()
                except Exception:
                    pass
                break
            
            if "bytes" in message:
                # Defensive check to prevent buffer overflow
                if len(audio_buffer) + len(message["bytes"]) < 10 * 1024 * 1024:  # 10MB limit
                    audio_buffer.extend(message["bytes"])
                else:
                    logger.warning("Audio buffer exceeded 10MB, resetting buffer") # This is a safety measure to prevent memory issues
                    audio_buffer.clear()
            
            elif "text" in message:
                signal = message["text"]
                
                if signal == "END_OF_SPEECH":
                    # Step 1: STT
                    try:
                        transcribed_text = await transcribe_audio(bytes(audio_buffer))
                    except Exception as e:
                        logger.error(f"Error during transcription: {e}")
                        transcribed_text = ""

                    if transcribed_text:
                        logger.info(f"Transcribed text: {transcribed_text}")
                    
                        # Step 2: LLM (with thinking/answer separation)
                        try:
                            result = await generate_response(transcribed_text)
                        except Exception as e:
                            logger.error(f"Error during response generation: {e}")
                            result = {
                                "thoughts": "",
                                "answer": "Sorry, I encountered an error while processing your request."
                            }
                        
                        # Step 3: Send back to Android
                        await websocket.send_json(
                            {
                                "stt": transcribed_text,
                                "thinking": result["thoughts"],
                                "answer": result["answer"]
                            }
                        )
                    else:
                        await websocket.send_json({
                            "thinking": "",
                            "answer": "Sorry, I couldn't understand the audio. Please try again."
                        })

                    # Reset for next question
                    audio_buffer.clear()
                    
    except WebSocketDisconnect:
        logger.info("Student disconnected")