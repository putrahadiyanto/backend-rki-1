from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.services.auth_service import AuthService
from app.services.detection_service import DetectionService
from app.utils.logger import get_logger

logger = get_logger()

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
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="File type not supported. Please upload JPEG, PNG, or WebP.",
        )

    image_bytes = await file.read()

    if len(image_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds {MAX_FILE_SIZE_MB}MB limit.",
        )

    try:
        result = await detection_service.detect(image_bytes, file.content_type)
    except RuntimeError as e:
        logger.error(f"All Gemini keys exhausted: {e}")
        raise HTTPException(
            status_code=503,
            detail="Detection service temporarily unavailable. All API keys exhausted.",
        )
    except Exception as e:
        logger.error(f"Detection failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process detection response.",
        )

    return result.model_dump()
