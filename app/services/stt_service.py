import io
import os
from groq import Groq

groq = Groq()

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