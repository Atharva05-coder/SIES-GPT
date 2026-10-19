from collections import OrderedDict
import re
import threading

from rag.generator import generate_answer
from rag.retriever import retrieve_relevant_chunks
from rag.query_rewriter import reframe_query

_CACHE_LOCK = threading.Lock()
_QUERY_CACHE = OrderedDict()
_CACHE_MAX_SIZE = 256

def ask_sies_gpt(question: str, yield_callback=None, cancel_event=None):
    if cancel_event and cancel_event.is_set():
        return {"answer": "", "sources": []}

    norm_key = re.sub(r"\s+", " ", question.strip().lower())

    with _CACHE_LOCK:
        if norm_key in _QUERY_CACHE:
            cached = _QUERY_CACHE[norm_key]
            _QUERY_CACHE.move_to_end(norm_key)
            if yield_callback:
                yield_callback({"type": "sources", "sources": cached["sources"]})
                tokens = re.findall(r"\S+|\n|\s+", cached["answer"])
                for tok in tokens:
                    if cancel_event and cancel_event.is_set():
                        return {"answer": "", "sources": []}
                    yield_callback({"type": "token", "text": tok})
            return cached

    expanded_question = reframe_query(question)
    print(f"[DEBUG] Original Query: {question}")
    print(f"[DEBUG] Reframed Query: {expanded_question}")

    if cancel_event and cancel_event.is_set():
        return {"answer": "", "sources": []}

    retrieved_chunks = retrieve_relevant_chunks(expanded_question, top_k=8)

    if cancel_event and cancel_event.is_set():
        return {"answer": "", "sources": []}
    
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

    if cancel_event and cancel_event.is_set():
        return {"answer": "", "sources": []}

    answer = generate_answer(
        expanded_question,
        retrieved_chunks,
        original_question=question,
        yield_callback=yield_callback,
        cancel_event=cancel_event,
    )

    if cancel_event and cancel_event.is_set():
        return {"answer": "", "sources": []}

    result = {"answer": answer, "sources": sources}

    if answer and len(answer) > 20 and (not cancel_event or not cancel_event.is_set()):
        with _CACHE_LOCK:
            _QUERY_CACHE[norm_key] = result
            if len(_QUERY_CACHE) > _CACHE_MAX_SIZE:
                _QUERY_CACHE.popitem(last=False)

    return result
