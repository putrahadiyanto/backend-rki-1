from groq import Groq

groq = Groq()

def transcribe_audio(file_path: str) -> str:

    audio = open(file_path, 'rb').read()

    response = groq.audio.transcribe(
        audio=audio,
        model='whisper-1',
        response_format='text'
    )