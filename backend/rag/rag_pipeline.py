from rag.generator import generate_answer
from rag.retriever import retrieve_relevant_chunks
from rag.query_rewriter import reframe_query

def ask_sies_gpt(question: str, yield_callback=None):
    expanded_question = reframe_query(question)
    print(f"[DEBUG] Original Query: {question}")
    print(f"[DEBUG] Reframed Query: {expanded_question}")
    retrieved_chunks = retrieve_relevant_chunks(expanded_question, top_k=8)
    
    sources = []
    for item in retrieved_chunks:
        metadata = item["metadata"]
        for page in metadata.get("pages", [metadata.get("page")]):
            if page is None:
                continue
            source = {
                "filename": metadata.get("filename"),
                "page": page,
                "url": metadata.get("url"),
            }
            if source not in sources:
                sources.append(source)
                
    if yield_callback:
        yield_callback({"type": "sources", "sources": sources})

    answer = generate_answer(expanded_question, retrieved_chunks, original_question=question, yield_callback=yield_callback)

    return {"answer": answer, "sources": sources}
