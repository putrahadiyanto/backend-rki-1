import os
from groq import Groq

groq = Groq()

async def generate_response(prompt: str) -> str:
    
    completion 