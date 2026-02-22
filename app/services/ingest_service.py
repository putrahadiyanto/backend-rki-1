import os
import asyncio
from markitdown import MarkItDown
from sentence_transformers import SentenceTransformer
from motor.motor_asyncio import AsyncIOMotorClient
from langchain_text_splitters import MarkdownTextSplitter


from app.db.mongodb import get_database
from app.utils.logger import get_logger

# model = SentenceTransformer('all-MiniLM-L6-v2')
# client = AsyncIOMotorClient(os.getenv('MONGO_URI'))
# db = client[os.getenv('MONGO_DB_NAME')]
# logger = get_logger()

# async def ingest_pdf(file_path):
    
#     md = MarkItDown()
#     result = md.convert(file_path)
#     markdown_text = result.text_content

#     splitter = MarkdownTextSplitter(chunk_size=1000, chunk_overlap=200)
#     chunks = splitter.split_text(markdown_text)

#     for chunk in chunks:
#         embedding = model.encode(chunk).tolist()
#         await db.text_embeddings.insert_one({
#             'text': chunk,
#             'embedding': embedding,
#             'source': file_path
#         })
        
#     logger.info(f"Successfully ingested {file_path}")

def convert_to_markdown(file_path: str) -> str:
    md = MarkItDown()
    result = md.convert(file_path)
    return result.text_content

if __name__ == "__main__":
    pdf_path = './data/pdf'
    for pdf in os.listdir(pdf_path):
        if pdf.endswith('.pdf'):
            file_path = os.path.join(pdf_path, pdf)
            md = convert_to_markdown(file_path)
            with open(file_path.replace('.pdf', '.md'), 'w', encoding='utf-8') as f:
                f.write(md)
    #         asyncio.run(ingest_pdf(os.path.join(pdf_path, pdf)))