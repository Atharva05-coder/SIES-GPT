import ollama


EMBEDDING_MODEL = "nomic-embed-text:latest"


def create_embedding(text: str):
    """
    Create an embedding using Ollama.
    """

    if not text or not text.strip():
        raise ValueError(
            "Cannot create embedding for empty text."
        )

    response = ollama.embed(
        model=EMBEDDING_MODEL,
        input=text
    )

    embeddings = response.get("embeddings")

    if not embeddings:
        raise RuntimeError(
            "Ollama returned no embeddings."
        )

    return embeddings[0]