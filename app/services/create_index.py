from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

mongo_uri = os.getenv("MONGO_URI")
db_name = os.getenv("MONGO_DB_NAME")

if not mongo_uri:
    print("Error: MONGO_URI not found in .env file")
    exit(1)

print(f"Connecting to: {mongo_uri}")

client = MongoClient(mongo_uri)

db = client[db_name]
collection = db["document_chunks"]

# Definisi Index Vektor
index_model = {
    "name": "vector_index",
    "type": "vectorSearch",
    "definition": {
        "fields": [
            {
                "type": "vector",
                "path": "embedding", # Nama field di screenshot kamu
                "numDimensions": 384, # Sesuai Array(384) di screenshot
                "similarity": "cosine"
            }
        ]
    }
}

# Jalankan pembuatan index
try:
    print(f"Creating Search Index on {db_name}.document_chunks...")
    result = db.command("createSearchIndexes", "document_chunks", indexes=[index_model])
    print(f"Success: {result}")
except Exception as e:
    print(f"Failed to create index: {e}")
    print("Note: 'vectorSearch' requires a MongoDB Atlas cluster (M10+ or Serverless).")