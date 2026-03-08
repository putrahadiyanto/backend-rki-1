import os
from dotenv import load_dotenv
import re
from groq import AsyncGroq

load_dotenv(override=True)
groq = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))  

async def generate_response(prompt: str) -> dict:
    
    try:
        response = await groq.chat.completions.create(
            model='qwen/qwen3-32b',
            messages=[
                {
                    "role": "user", "content": f"Ringkas informasi berikut dari pernyataan ini {prompt}"
                }
            ],
            temperature=0.7,
            max_tokens=1000
        )
    
        thoughts, answer = split_think_and_answer(response.choices[0].message.content)

        return {
            "thoughts": thoughts,
            "answer": answer
        }
    except Exception as e:
        print(f"Error during response generation: {e}")
        return {
            "thoughts": "",
            "answer": "Sorry, I encountered an error while processing your request."
        }
    
def split_think_and_answer(raw_text: str):
    # Ensure we have a string
    raw_text = str(raw_text or "")

    # Match <think> ... </think> case-insensitively and allow attributes: <think ...>
    thought_pattern = re.compile(r'<think\b[^>]*>(.*?)</think>', re.DOTALL | re.IGNORECASE)
    thought_match = thought_pattern.search(raw_text)
    thought = thought_match.group(1).strip() if thought_match and thought_match.group(1) else ""

    # Remove the <think> block entirely to leave only the answer
    answer = thought_pattern.sub('', raw_text).strip()

    # Normalize None -> empty strings for safe JSON serialization
    if thought is None:
        thought = ""
    if answer is None:
        answer = ""

    return thought, answer


async def generate_chat_response(messages: list[dict]) -> dict:
    """
    Multi-turn chat completion.
    `messages` is a list of {"role": "user"|"assistant", "content": "..."} dicts
    representing the conversation history.
    """
    try:
        response = await groq.chat.completions.create(
            model='qwen/qwen3-32b',
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )
        raw = response.choices[0].message.content
        thoughts, answer = split_think_and_answer(raw)
        return {"thoughts": thoughts, "answer": answer}
    except Exception as e:
        print(f"Error during chat response generation: {e}")
        return {
            "thoughts": "",
            "answer": "Sorry, I encountered an error while processing your request.",
        }