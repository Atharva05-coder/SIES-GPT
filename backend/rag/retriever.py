from rag.embeddings import create_embedding
from rag.vector_store import collection


def retrieve_relevant_chunks(
    question: str,
    top_k: int = 10
):

    query_embedding = create_embedding(
        question
    )

    results = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=top_k
    )

    retrieved = []

    documents = results.get(
        "documents",
        [[]]
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]]
    )[0]

    for document, metadata in zip(
        documents,
        metadatas
    ):

        retrieved.append({
            "text": document,
            "metadata": metadata
        })

    return retrieved