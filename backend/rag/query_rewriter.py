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
        r"\bNLP\b": "Natural Language Processing",
        r"\bsem(?:ester)? 1\b": "Semester I",
        r"\bsem(?:ester)? 2\b": "Semester II",
        r"\bsem(?:ester)? 3\b": "Semester III",
        r"\bsem(?:ester)? 4\b": "Semester IV",
        r"\bsem(?:ester)? 5\b": "Semester V",
        r"\bsem(?:ester)? 6\b": "Semester VI",
        r"\bsem(?:ester)? 7\b": "Semester VII",
        r"\bsem(?:ester)? 8\b": "Semester VIII"
    }
    for pattern, replacement in acronyms.items():
        query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)

    return query
