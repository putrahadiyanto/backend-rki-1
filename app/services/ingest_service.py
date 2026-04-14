# ===========================================
# Currently not used, used for the index on the ingest service to VectorDB (RAG)
# If later on, there will be implementation of RAG, you can use this
# ===========================================

from markitdown import MarkItDown
import io
from typing import BinaryIO, Union, Any
from datetime import datetime
from app.utils.logger import get_logger
from langchain_text_splitters import MarkdownTextSplitter
from app.db.mongodb import get_database
# import voyageai


logger = get_logger()
# vo = voyageai.Client() # Automatically uses VOYAGE_API_KEY from environment

def convert_pdf_to_markdown(source: Any) -> str:
    """
    Converts a PDF (path or stream) to Markdown text using MarkItDown.
    """
    try:
        # Initialize MarkItDown (Local mode)
        md_engine = MarkItDown()
        
        # Ensure the source is a compatible BinaryIO object if it's a stream.
        # FastAPI's SpooledTemporaryFile might not be recognized directly by MarkItDown.
        if not isinstance(source, str) and hasattr(source, "read"):
            content = source.read()
            source = io.BytesIO(content)

        # Convert pdf to Markdown
        result = md_engine.convert(source, extension=".pdf")
        return result.text_content
    except Exception as e:
        logger.error(f"Failed to convert PDF: {e}")
        raise RuntimeError(f"PDF conversion failed: {str(e)}")

async def store_markdown_chunks(markdown_content: str, source_name: str, metadata: dict):
    """
    Chunks markdown content and stores it in the MongoDB vector store.
    """
    if not markdown_content:
        return

    # 1. Chunk the Markdown content
    # We use MarkdownTextSplitter to respect headers and structure
    splitter = MarkdownTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_text(markdown_content)
    logger.info(f"Split {source_name} into {len(chunks)} chunks")

    # Generate embeddings using Voyage AI
    # result = vo.embed(chunks, model="voyage-4-lite", input_type="document")
    embeddings = result.embeddings


    # 2. Store in MongoDB
    try:
        db = get_database()
        collection = db["document_chunks"]
        
        documents = []
        now = datetime.now()
        for i, chunk in enumerate(chunks):
            documents.append({
                "source": source_name,
                "chunk_index": i,
                "content": chunk,
                "embedding": embeddings[i],
                "metadata": {
                    **metadata,
                    "source": source_name,
                    "chunk_index": i,
                    "created_at": now
                }
            })
        
        if documents:
            await collection.insert_many(documents)
            logger.info(f"Successfully stored {len(documents)} chunks in MongoDB")
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise RuntimeError(f"Failed to store chunks in database: {str(e)}")

async def ingest_pdf(source: Union[str, BinaryIO], filename: str, metadata: dict):
    """
    Core logic to convert PDF and store chunks. 
    Note: MongoDB connection should be managed by the caller (e.g., FastAPI lifespan).
    """

    try:
        # Ensure we are at the start of the file stream
        if hasattr(source, "seek"):
            source.seek(0)
            
        markdown_content = convert_pdf_to_markdown(source)
        
        if not markdown_content or markdown_content.strip() == "":
            raise ValueError("Converted Markdown is empty. The PDF might be a scan or corrupted.")

        # Process and store in MongoDB
        await store_markdown_chunks(markdown_content, filename, metadata)
    except Exception as e:
        logger.error(f"Error in ingest_pdf: {e}")
        raise e
