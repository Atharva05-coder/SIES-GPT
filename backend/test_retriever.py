from rag.retriever import retrieve_relevant_chunks


question = "What is the Third Year Computer Engineering syllabus?"


results = retrieve_relevant_chunks(
    question,
    top_k=5
)


print("\n================================")
print("RAG RETRIEVAL TEST")
print("================================")


for i, result in enumerate(
    results,
    start=1
):

    metadata = result["metadata"]

    print(
        f"\n========== RESULT {i} =========="
    )

    print(
        "File:",
        metadata.get("filename")
    )

    print(
        "Page:",
        metadata.get("page")
    )

    print(
        "Category:",
        metadata.get("category")
    )

    print("\nTEXT:")

    print(
        result["text"][:1000]
    )