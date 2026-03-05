from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from app.services.ingest_service import ingest_pdf
from app.utils.logger import get_logger
from pydantic import BaseModel, Field
from datetime import datetime

logger = get_logger()
router = APIRouter()

class IngestMetadata(BaseModel):
    category: str
    kelas_akademik: int
    title: str
    description: str

@router.post("/ingest/pdf")
async def ingest_pdf_endpoint(
    file: UploadFile = File(...),
    metadata: IngestMetadata = Depends()
):
    """
    Endpoint to ingest a PDF document, convert it to Markdown, and store chunks in MongoDB.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    try:
        # Process the PDF using the service
        # Straight use the file stream and filename provided by FastAPI
        await ingest_pdf(file.file, file.filename, metadata.model_dump())
        return {"message": f"Successfully ingested {file.filename}", "title": metadata.title}
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
