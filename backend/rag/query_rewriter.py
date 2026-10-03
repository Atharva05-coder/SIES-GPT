import ollama
import re

def reframe_query(query: str) -> str:
    # Hardcoded reliable expansions for small LLM
    acronyms = {
        r"\bCN\b": "Computer Network",
        r"\bDBMS\b": "Database Management System",
        r"\bSE\b": "Software Engineering",
        r"\bML\b": "Machine Learning",
        r"\bAI\b": "Artificial Intelligence",
        r"\bOS\b": "Operating System",
        r"\bIoT\b": "Internet of Things",
        r"\bHPC\b": "High Performance Computing",
        r"\bBDA\b": "Big Data Analytics",
        r"\bNLP\b": "Natural Language Processing"
    }
    for pattern, replacement in acronyms.items():
        query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)

    # BM25 is highly resilient to conversational filler ("What is the..."), 
    # but the 3B LLM often deletes critical keywords when asked to "reframe".
    # Therefore, we bypass the LLM for query rewriting and return the expanded query directly.
    return query
