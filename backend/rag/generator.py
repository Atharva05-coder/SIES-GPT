import ollama


def generate_answer(
    question: str,
    retrieved_chunks
):

    context_parts = []

    for item in retrieved_chunks:

        metadata = item["metadata"]

        context_parts.append(
            f"""
SOURCE: {metadata.get("filename")}
PAGE: {metadata.get("page")}

CONTENT:
{item["text"]}
"""
        )

    context = "\n\n".join(
        context_parts
    )


    prompt = f"""
You are SIES GPT, an AI assistant for
SIES Graduate School of Technology.

Answer the user's question using the
SIES document context provided below.

IMPORTANT RULES:

1. Use the retrieved SIES context as
   the primary source of truth.

2. Do not invent SIES-specific information.

3. If the answer cannot be found in
   the retrieved context, say that the
   information could not be found in
   the available SIES documents.

4. Give a clear and well-structured answer.

5. When possible, mention the source
   page from the retrieved context.

SIES DOCUMENT CONTEXT:
======================

{context}

======================

USER QUESTION:
{question}

ANSWER:
"""


    response = ollama.generate(
        model="llama3.2:3b",
        prompt=prompt,
    )

    return response["response"]