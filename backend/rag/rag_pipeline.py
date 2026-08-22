from rag.retriever import (
    retrieve_relevant_chunks
)

from rag.generator import (
    generate_answer
)


def ask_sies_gpt(question: str):

    # -----------------------------
    # 1. Retrieve relevant chunks
    # -----------------------------

    retrieved_chunks = (
        retrieve_relevant_chunks(
            question,
            top_k=8
        )
    )


    # -----------------------------
    # 2. Generate answer with Gemini
    # -----------------------------

    answer = generate_answer(
        question,
        retrieved_chunks
    )


    # -----------------------------
    # 3. Prepare sources
    # -----------------------------

    sources = []

    for item in retrieved_chunks:

        metadata = item["metadata"]

        source = {
            "filename": metadata.get(
                "filename"
            ),

            "page": metadata.get(
                "page"
            ),

            "url": metadata.get(
                "url"
            )
        }


        if source not in sources:

            sources.append(source)


    return {
        "answer": answer,
        "sources": sources
    }