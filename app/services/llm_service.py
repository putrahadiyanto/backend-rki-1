import os
from dotenv import load_dotenv
import re
import json
import asyncio
from groq import AsyncGroq

load_dotenv(override=True)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name" : "trigger_minigame",
            "parameters" : {
                "type" : "object",
                "properties" : {
                    "topic" : {"type" : "string"},
                    "message" : {"type" : "string"},
                    "questions" : {
                        "type" : "array",
                        "items" : {
                            "type" : "object",
                            "properties" : {
                                "question_text" : {"type" : "string"},
                                "answer_options" : {
                                    "type" : "array",
                                    "items" : {"type" : "string"},
                                    "minItems" : 4,
                                    "maxItems" : 4,
                                },  
                                'correct_answer_index' : {"type" : "integer", "minimum" : 0, "maximum" : 3}
                            },
                            "required" : ["question_text", "answer_options", "correct_answer_index"]
                        },
                        "minItems" : 3,
                        "maxItems" : 5
                    }
                },
                "required" : ["topic", "questions", "message"]
            }
        }
    }
]

groq = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))  

async def generate_response(prompt: str, history: list[dict] | None = None) -> dict:
    
    SYSTEM_PROMPT = (
        "Kamu adalah asisten belajar biologi yang ramah, sabar, dan santai — seperti teman belajar, bukan guru kaku. "
        "Jawaban kamu akan diucapkan langsung lewat Text-to-Speech (TTS), jadi ikuti aturan format berikut:\n\n"

        "ATURAN FORMAT (wajib untuk TTS):\n"
        "Tulis hanya kalimat natural seperti orang berbicara. Jangan pakai bullet points, tanda bintang, tanda pagar, "
        "simbol atau emoji apapun. Jangan pakai format markdown sama sekali. Kalau perlu menyebutkan beberapa hal, "
        "gunakan kata penghubung seperti 'pertama... lalu... selanjutnya...'. "
        "Gunakan Bahasa Indonesia yang santai dan mudah dimengerti. "
        "Kalau ada istilah medis, jelaskan langsung artinya dalam kalimat yang sama. "
        "Gunakan analogi sederhana supaya mudah dibayangkan. "
        "Jawaban biasa cukup 2 sampai 3 kalimat. Penjelasan mendalam maksimal 5 sampai 6 kalimat.\n\n"

        "CARA BERSIKAP:\n"
        "Bersikaplah seperti teman yang asik diajak ngobrol."

        "KAPAN MEMICU MINIGAME (trigger_minigame):\n"
        "Picu minigame setelah memberikan penjelasan lengkap tentang suatu topik, atau saat pengguna meminta kuis atau latihan. "
        "JANGAN picu minigame untuk sapaan atau pertanyaan baru tentang topik berbeda. "
        "SETELAH minigame dipicu, JANGAN lanjutkan kuis di dalam chat — minigame sudah ditangani oleh aplikasi secara terpisah. "
        "Setelah trigger_minigame, cukup tunggu pertanyaan berikutnya dari pengguna seperti biasa. "
        "Field 'message' ditulis dalam gaya bicara natural untuk TTS.\n"
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = await asyncio.wait_for(
            groq.chat.completions.create(
                model='qwen/qwen3-32b',
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=4096
            ),
            timeout=30.0
        )

        messages = response.choices[0].message

        if messages.tool_calls:
            tool_call = messages.tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            if function_name == "trigger_minigame":
                return {
                    "action": function_name,
                    "answer": clean_for_tts(function_args["message"]),
                    "game_data": function_args,
                }

        else:
            thoughts, answer = split_think_and_answer(response.choices[0].message.content)
            return {"thoughts": thoughts, "answer": answer}
    except Exception as e:
        print(f"Error during response generation: {e}")
        return {"answer": "Maaf, terjadi kesalahan. Coba lagi ya."}
    
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

    return thought, clean_for_tts(answer)


def clean_for_tts(text: str) -> str:
    """Strip markdown formatting so the text is clean for Text-to-Speech."""
    # Remove bold/italic markers: **, __, *, _
    text = re.sub(r'\*{1,2}|_{1,2}', '', text)
    # Remove markdown headings: ## Heading → Heading
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # Convert bullet/dash list items to a natural lead-in (remove the marker)
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
    # Convert numbered lists "1. ..." → remove the number prefix
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove inline code backticks
    text = re.sub(r'`+', '', text)
    # Collapse multiple blank lines to a single space-separated sentence boundary
    text = re.sub(r'\n{2,}', ' ', text)
    # Replace single newlines with a space
    text = re.sub(r'\n', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()

