import chromadb


COLLECTION_NAME = "sies_documents"

CHROMA_PATH = "./chroma_db"


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
    """
    Delete the current V4 collection and recreate it.
    Used only during ingestion.
    """

    global collection

    try:
        client.delete_collection(
            name=COLLECTION_NAME
        )
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