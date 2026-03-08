import io
import os
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv(override=True)
groq = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

async def transcribe_audio(audio_data: bytes) -> str:

    # Convert bytes to a file-like object
    audio_file = io.BytesIO(audio_data)
    audio_file.name = "audio.wav"

    # Transcribe the audio using Groq's Whisper model
    try:
        transcription = await groq.audio.transcriptions.create(
            file=audio_file,
            model='whisper-large-v3-turbo',
            temperature=0.0,
            response_format='text'
        )
        return transcription
    except Exception as e:
        print(f"Error during transcription: {e}")
        return ""