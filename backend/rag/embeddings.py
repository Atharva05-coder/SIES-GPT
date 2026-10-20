import os
from openai import OpenAI
from dotenv import load_dotenv

# Load from backend/.env explicitly
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

EMBEDDING_MODEL = os.environ.get("EMBED_MODEL", "bge-m3")

client = OpenAI(
    base_url=os.environ.get("EMBED_BASE_URL", "https://embed.atharva-amrutkar.in/v1"),
    api_key=os.environ.get("EMBED_API_KEY", ""),
    max_retries=0,
    timeout=300.0
)

def create_embedding(text: str):
    """
    Create an embedding using the remote OpenAI-compatible endpoint.
    """
    if not text or not text.strip():
        raise ValueError("Cannot create embedding for empty text.")

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )

    if not response.data:
        raise RuntimeError("The embedding endpoint returned no data.")

    return response.data[0].embedding
