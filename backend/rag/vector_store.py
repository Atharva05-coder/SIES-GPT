import os
import chromadb

COLLECTION_NAME = "sies_documents"

# Ensure the database is always in the backend/ directory, no matter where the script is run from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PATH = os.path.join(os.path.dirname(BASE_DIR), "chroma_db")

client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

def get_collection():
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "description": "SIES GST R24 syllabus RAG index",
            "embedding_model": "nomic-embed-text:latest"
        }
    )

collection = get_collection()

def reset_collection():
    global collection
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "description": "SIES GST R24 syllabus RAG index",
            "embedding_model": "nomic-embed-text:latest"
        }
    )
    return collection
