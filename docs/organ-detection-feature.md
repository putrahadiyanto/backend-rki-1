# Feature Plan: Organ Model Image Detection API

## Overview

Add a new API endpoint that accepts an image of a human organ teaching model (`peraga organ tubuh manusia`), sends it to Google Gemini LLM for classification, and returns the detected organ class.

---

## 1. Detection Classes

The image classes correspond to physical organ models used in biology education.

| Class ID | Organ Name |
|---|---|
| `Otak` | Otak (Brain) |
| `Kepala` | Kepala (Head) |
| `Tenggorokan` | Tenggorokan (Throat) |
| `Dada_Luar` | Dada Luar (Outer Chest) |
| `Dada_Dalam` | Dada Dalam (Inner Chest) |
| `Rusuk` | Rusuk (Ribs) |
| `Paru-Paru_Kanan` | Paru-Paru Kanan (Right Lung) |
| `Paru-paru_Kiri` | Paru-Paru Kiri (Left Lung) |
| `Jantung` | Jantung (Heart) |
| `Ginjal_Luar` | Ginjal Luar (Outer Kidney) |
| `Ginjal_Dalam` | Ginjal Dalam (Inner Kidney) |
| `Hati` | Hati (Liver) |
| `Lambung` | Lambung (Stomach) |
| `Usus` | Usus (Intestines) |
| `Penis` | Penis |
| `Vagina` | Vagina |

---

## 2. API Design

### Endpoint

```
POST /api/detect
```

### Request

- **Content-Type:** `multipart/form-data`
- **Authorization:** `Bearer <access_token>` (required)
- **Body:**
  | Field | Type | Required | Description |
  |---|---|---|---|
  | `file` | `UploadFile` | Yes | Image file (JPEG, PNG, WebP) |

### Response

#### Case 1: Organ Detected (HTTP 200)

```json
{
  "status": "detected",
  "class_id": "Jantung",
  "class_name": "Jantung (Heart)",
  "confidence": "high",
  "description": "Model peraga organ Jantung terdeteksi."
}
```

#### Case 2: No Organ Detected (HTTP 200)

```json
{
  "status": "not_detected",
  "class_id": null,
  "class_name": null,
  "confidence": null,
  "description": "Tidak ada model organ tubuh manusia yang terdeteksi dalam gambar. Pastikan gambar menunjukkan model peraga organ tubuh manusia dengan jelas."
}
```

#### Case 3: Error (HTTP 400/500)

```json
{
  "detail": "File type not supported. Please upload JPEG, PNG, or WebP."
}
```

### Why HTTP 200 for both detected and not_detected?

Using 200 for both cases is the **best practice** for classification endpoints:
- The request was **valid** and processed successfully in both cases.
- "Not detected" is a **valid result**, not an error condition.
- The caller can check `status` field to branch logic.
- Avoids confusion between "bad request" (400) and "no detection" (valid outcome).

---

## 3. Architecture

### New Files to Create

```
app/
├── api/
│   └── detection/
│       └── detect.py           # Route handler
├── services/
│   └── detection_service.py    # Gemini integration + classification logic
└── models/
    └── detection.py            # Pydantic response models
```

### Files to Modify

| File | Change |
|---|---|
| `app/main.py` | Register `detection_router` |
| `.env.example` | Add `GEMINI_API_KEYS` |
| `requirements.txt` | Add `google-genai` |

---

## 4. Multi-Key Rotation Mechanism

### Problem

Gemini API keys have rate limits (RPM, RPD, TPM). A single key can get exhausted under load or temporarily blocked.

### Solution: Key Pool with Automatic Failover

The service maintains a **pool of Gemini API keys** and uses them with automatic fallback on failure.

### Environment Variable

```
# Comma-separated list of Gemini API keys for failover
GEMINI_API_KEY_1=your_first_key
GEMINI_API_KEY_2=your_second_key
GEMINI_API_KEY_3=your_third_key
```

At minimum 1 key is required. Multiple keys are optional but recommended for production.

### How It Works

```
┌─────────────────────────────────────────────┐
│              DetectionService               │
│                                             │
│  keys = [KEY_1, KEY_2, KEY_3]               │
│  current_index = 0                          │
│                                             │
│  detect(image):                             │
│    for key in keys:                         │
│      try:                                   │
│        client = genai.Client(api_key=key)   │
│        result = client.models.generate()    │
│        return result                        │
│      except RateLimitError:                 │
│        log warning, rotate to next key      │
│        continue                             │
│      except Exception:                      │
│        log error, rotate to next key        │
│        continue                             │
│    raise ServiceUnavailable (all keys failed)│
└─────────────────────────────────────────────┘
```

### Key Rotation Strategy

1. **Sequential failover** — Try keys in order. On rate limit (429) or error, move to the next key.
2. **No round-robin** — Keep it simple. The first working key is used until it fails.
3. **In-memory state** — The `current_index` resets on service restart (acceptable for this use case).
4. **No cooldown timer** — Keys are retried on next request cycle. Simple and effective.

### Why not round-robin or least-recently-used?

- **Round-robin** spreads load evenly but adds complexity. For a classification endpoint with moderate traffic, sequential failover is sufficient.
- **LRU** requires tracking last-use timestamps — overkill here.
- The primary goal is **availability**, not load balancing. If one key hits rate limit, the next one takes over immediately.

### Error When All Keys Exhausted

```json
{
  "detail": "Detection service temporarily unavailable. All API keys exhausted. Please try again later."
}
```

HTTP 503 Service Unavailable — signals the client to retry after a delay.

---

## 5. Implementation Plan

### Step 1: Add Dependencies

Add to `requirements.txt`:

```
google-genai>=1.0.0
```

Using the official `google-genai` SDK (Google's recommended client for Gemini). Direct and lightweight for image classification.

### Step 2: Environment Variables

Add to `.env.example`:

```
# Gemini API Keys (comma-separated for failover, minimum 1 required)
GEMINI_API_KEY_1=your_first_gemini_api_key
GEMINI_API_KEY_2=your_second_gemini_api_key
GEMINI_API_KEY_3=your_third_gemini_api_key
```

### Step 3: Pydantic Models (`app/models/detection.py`)

```python
from pydantic import BaseModel
from typing import Literal, Optional

class DetectionResult(BaseModel):
    status: Literal["detected", "not_detected"]
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    confidence: Optional[Literal["high", "medium", "low"]] = None
    description: str
```

### Step 4: Detection Service (`app/services/detection_service.py`)

Responsibilities:
1. Load all `GEMINI_API_KEY_*` env vars into a list at init.
2. Maintain a `current_index` to track which key to try next.
3. On each `detect()` call:
   a. Iterate through available keys starting from `current_index`.
   b. Create a fresh `genai.Client(api_key=key)` for each attempt.
   c. Encode image to base64, build multimodal prompt, call Gemini.
   d. On success: return parsed `DetectionResult`.
   e. On rate limit / error: log warning, increment key index, try next key.
   f. If all keys fail: raise `ServiceUnavailable`.
4. Parse Gemini JSON response, validate `class_id` against known classes.
5. Return `DetectionResult` with appropriate status.

**Key design decisions:**
- Create a **new client per attempt** rather than sharing one client — avoids stale state.
- Use `temperature=0` for deterministic classification.
- Validate returned `class_id` against the known class list — unknown classes are treated as `not_detected`.
- Run Gemini's blocking `.generate_content()` in `asyncio.to_thread()` for async compatibility.

**Gemini prompt strategy:**

```
You are an image classifier for human organ teaching models (peraga organ tubuh manusia).

Given the image, determine which organ model is shown. You MUST classify the image
into exactly ONE of these classes:

- Otak
- Kepala
- Tenggorokan
- Dada_Luar
- Dada_Dalam
- Rusuk
- Paru-Paru_Kanan
- Paru-paru_Kiri
- Jantung
- Ginjal_Luar
- Ginjal_Dalam
- Hati
- Lambung
- Usus
- Penis
- Vagina

If the image does not clearly show any of these organ models, respond with:
{ "class_id": "none", "confidence": "low" }

Respond ONLY with a JSON object in this exact format:
{ "class_id": "<class_name>", "confidence": "high" | "medium" | "low" }
```

### Step 5: Route Handler (`app/api/detection/detect.py`)

```python
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.services.auth_service import AuthService
from app.services.detection_service import DetectionService

router = APIRouter()
auth_service = AuthService()
detection_service = DetectionService()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_MB = 10

@router.post("/detect")
async def detect_organ(
    file: UploadFile = File(...),
    username: str = Depends(auth_service.get_authenticated_username),
):
    # 1. Validate file type
    # 2. Validate file size
    # 3. Read bytes
    # 4. Call detection_service.detect(image_bytes)
    # 5. Return DetectionResult
```

- **Authentication required** — uses the same `Depends(auth_service.get_authenticated_username)` pattern as other endpoints.
- Validates file type and size before processing.
- Returns `DetectionResult` as JSON.

### Step 6: Register Router in `main.py`

```python
from app.api.detection.detect import router as detection_router

app.include_router(detection_router, prefix="/api", tags=["detection"])
```

---

## 6. Class Name Mapping

A simple lookup for human-readable names (no team member):

```python
CLASS_NAMES = {
    "Otak":            "Otak (Brain)",
    "Kepala":          "Kepala (Head)",
    "Tenggorokan":     "Tenggorokan (Throat)",
    "Dada_Luar":       "Dada Luar (Outer Chest)",
    "Dada_Dalam":      "Dada Dalam (Inner Chest)",
    "Rusuk":           "Rusuk (Ribs)",
    "Paru-Paru_Kanan": "Paru-Paru Kanan (Right Lung)",
    "Paru-paru_Kiri":  "Paru-Paru Kiri (Left Lung)",
    "Jantung":         "Jantung (Heart)",
    "Ginjal_Luar":     "Ginjal Luar (Outer Kidney)",
    "Ginjal_Dalam":    "Ginjal Dalam (Inner Kidney)",
    "Hati":            "Hati (Liver)",
    "Lambung":         "Lambung (Stomach)",
    "Usus":            "Usus (Intestines)",
    "Penis":           "Penis",
    "Vagina":          "Vagina",
}
```

---

## 7. Error Handling

| Scenario | HTTP Status | Response |
|---|---|---|
| Missing/invalid access token | 401 | `{"detail": "Not authenticated"}` |
| Invalid file type (not image) | 400 | `{"detail": "File type not supported. Please upload JPEG, PNG, or WebP."}` |
| File too large (>10MB) | 400 | `{"detail": "File size exceeds 10MB limit."}` |
| No file provided | 422 | FastAPI auto-validation error |
| All Gemini keys exhausted | 503 | `{"detail": "Detection service temporarily unavailable. All API keys exhausted."}` |
| Gemini returns unknown class | 200 | `{"status": "not_detected", ...}` (treat as not detected) |
| Image doesn't contain organ model | 200 | `{"status": "not_detected", ...}` |
| Gemini response parse error | 500 | `{"detail": "Failed to process detection response."}` |

---

## 8. Non-Functional Requirements

- **Async:** All I/O operations (file read, Gemini API call) must be async or run in threads via `asyncio.to_thread()`.
- **Authentication:** Requires valid JWT access token via `Authorization: Bearer <token>` header.
- **File size limit:** 10MB max to prevent abuse and timeout.
- **Timeout:** Gemini API call should have a 30-second timeout per key attempt.
- **Logging:** Log detection requests with file size, key index used, and result for monitoring.

---

## 9. Implementation Order

| Step | Task | Files |
|---|---|---|
| 1 | Create `app/models/detection.py` | New |
| 2 | Create `app/services/detection_service.py` | New |
| 3 | Create `app/api/detection/detect.py` | New |
| 4 | Register router in `app/main.py` | Modify |
| 5 | Add `GEMINI_API_KEY_*` vars to `.env.example` | Modify |
| 6 | Add `google-genai` to `requirements.txt` | Modify |
| 7 | Test with sample organ model images | Manual |

---

## 10. Future Enhancements (Out of Scope)

- Store detection history in MongoDB for analytics.
- Add confidence threshold config (e.g., reject low-confidence results).
- Batch detection endpoint for multiple images.
- Feedback endpoint to correct misclassifications.
- Key cooldown/cooldown timer for rate-limited keys.
