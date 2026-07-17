from pydantic import BaseModel
from typing import Literal, Optional


class DetectionResult(BaseModel):
    status: Literal["detected", "not_detected"]
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    confidence: Optional[Literal["high", "medium", "low"]] = None
    description: str
