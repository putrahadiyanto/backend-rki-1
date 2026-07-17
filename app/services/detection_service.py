import os
import json
import asyncio
import base64
from typing import Optional

from google import genai
from google.genai.errors import ClientError, ServerError

from app.models.detection import DetectionResult
from app.utils.logger import get_logger

logger = get_logger()

VALID_CLASSES = {
    "Otak", "Kepala", "Tenggorokan",
    "Dada_Luar", "Dada_Dalam", "Rusuk",
    "Paru-Paru_Kanan", "Paru-paru_Kiri", "Jantung",
    "Ginjal_Luar", "Ginjal_Dalam", "Hati",
    "Lambung", "Usus", "Penis", "Vagina",
}

CLASS_NAMES = {
    "Otak": "Otak (Brain)",
    "Kepala": "Kepala (Head)",
    "Tenggorokan": "Tenggorokan (Throat)",
    "Dada_Luar": "Dada Luar (Outer Chest)",
    "Dada_Dalam": "Dada Dalam (Inner Chest)",
    "Rusuk": "Rusuk (Ribs)",
    "Paru-Paru_Kanan": "Paru-Paru Kanan (Right Lung)",
    "Paru-paru_Kiri": "Paru-Paru Kiri (Left Lung)",
    "Jantung": "Jantung (Heart)",
    "Ginjal_Luar": "Ginjal Luar (Outer Kidney)",
    "Ginjal_Dalam": "Ginjal Dalam (Inner Kidney)",
    "Hati": "Hati (Liver)",
    "Lambung": "Lambung (Stomach)",
    "Usus": "Usus (Intestines)",
    "Penis": "Penis",
    "Vagina": "Vagina",
}

CLASS_LIST_PROMPT = "\n".join(f"- {cls}" for cls in VALID_CLASSES)

SYSTEM_PROMPT = (
    "You are an image classifier for human organ teaching models (peraga organ tubuh manusia).\n\n"
    "Given the image, determine which organ model is shown. You MUST classify the image "
    "into exactly ONE of these classes:\n\n"
    f"{CLASS_LIST_PROMPT}\n\n"
    'If the image does not clearly show any of these organ models, respond with:\n'
    '{ "class_id": "none", "confidence": "low" }\n\n'
    "Respond ONLY with a JSON object in this exact format:\n"
    '{ "class_id": "<class_name>", "confidence": "high" | "medium" | "low" }'
)


class DetectionService:
    """Classifies organ model images using Gemini with multi-key failover."""

    def __init__(self):
        self._keys: list[str] = []
        self._current_index = 0
        self._load_keys()

    def _load_keys(self):
        """Load all GEMINI_API_KEY_* environment variables."""
        keys = []
        for i in range(1, 10):
            key = os.getenv(f"GEMINI_API_KEY_{i}")
            if key:
                keys.append(key)
        if not keys:
            single = os.getenv("GEMINI_API_KEY")
            if single:
                keys.append(single)
        self._keys = keys
        logger.info(f"Loaded {len(self._keys)} Gemini API key(s)")

    def _get_next_key(self) -> str:
        """Get the current key and advance the index for next call."""
        if not self._keys:
            raise RuntimeError("No Gemini API keys configured")
        key = self._keys[self._current_index]
        self._current_index = (self._current_index + 1) % len(self._keys)
        return key

    def _build_client(self, api_key: str) -> genai.Client:
        """Create a fresh Gemini client with the given key."""
        return genai.Client(api_key=api_key)

    def _call_gemini_sync(self, image_bytes: bytes, mime_type: str) -> dict:
        """Blocking Gemini call — runs in a thread."""
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        contents = [
            {
                "role": "user",
                "parts": [
                    {"text": SYSTEM_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": image_b64,
                        }
                    },
                ],
            }
        ]

        last_error = None
        attempts = 0

        while attempts < len(self._keys):
            api_key = self._get_next_key()
            attempts += 1

            try:
                client = self._build_client(api_key)
                response = client.models.generate_content(
                    model="gemini-3.1-flash-lite",
                    contents=contents,
                    config={"temperature": 0},
                )
                raw_text = response.text.strip()

                if raw_text.startswith("```"):
                    raw_text = raw_text.split("\n", 1)[1]
                    if raw_text.endswith("```"):
                        raw_text = raw_text[: raw_text.rfind("```")]
                    raw_text = raw_text.strip()

                parsed = json.loads(raw_text)
                return parsed

            except (ClientError, ServerError) as e:
                logger.warning(f"Gemini key index failed (attempt {attempts}): {e}")
                last_error = e
                continue
            except json.JSONDecodeError as e:
                logger.error(f"Gemini returned invalid JSON: {raw_text}")
                last_error = e
                continue

        raise RuntimeError(f"All Gemini API keys exhausted. Last error: {last_error}")

    async def detect(self, image_bytes: bytes, mime_type: str) -> DetectionResult:
        """Classify an organ model image. Returns DetectionResult."""
        try:
            parsed = await asyncio.to_thread(self._call_gemini_sync, image_bytes, mime_type)
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Gemini detection failed: {e}")
            raise

        class_id = parsed.get("class_id", "none")
        confidence = parsed.get("confidence", "low")

        if class_id == "none" or class_id not in VALID_CLASSES:
            return DetectionResult(
                status="not_detected",
                class_id=None,
                class_name=None,
                confidence=None,
                description=(
                    "Tidak ada model organ tubuh manusia yang terdeteksi dalam gambar. "
                    "Pastikan gambar menunjukkan model peraga organ tubuh manusia dengan jelas."
                ),
            )

        return DetectionResult(
            status="detected",
            class_id=class_id,
            class_name=CLASS_NAMES.get(class_id, class_id),
            confidence=confidence,
            description=f"Model peraga organ {CLASS_NAMES.get(class_id, class_id)} terdeteksi.",
        )
