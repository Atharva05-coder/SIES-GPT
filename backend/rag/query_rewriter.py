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
        r"\bTCS\b": "Theoretical Computer Science",
        r"\bCOA\b": "Computer Organization and Architecture",
        r"\bAOA\b": "Analysis of Algorithm",
        r"\bDSD\b": "Digital System Design",
        r"\bEG\b": "Engineering Graphics",
        r"\bSPCC\b": "System Programming and Compiler Construction",
        r"\bCNS\b": "Cryptography and Network Security",
        r"\bAM-?3\b": "Applied Mathematics- III",
        r"\bAM-?4\b": "Applied Mathematics- IV",
        r"\bAM-?1\b": "Applied Mathematics-I",
        r"\bAM-?2\b": "Applied Mathematics-II",
        r"\b(?:M-?3|Maths?-?3|Maths?-?III|Math-?3|Math-?III)\b": "Applied Mathematics- III",
        r"\b(?:M-?4|Maths?-?4|Maths?-?IV|Math-?4|Math-?IV)\b": "Applied Mathematics- IV",
        r"\b(?:M-?1|Maths?-?1|Maths?-?I|Math-?1|Math-?I)\b": "Applied Mathematics-I",
        r"\b(?:M-?2|Maths?-?2|Maths?-?II|Math-?2|Math-?II)\b": "Applied Mathematics-II",
        r"\b(?:DSA|DS)\b": "Data Structures",
        r"\bADA\b": "Analysis of Algorithm",
        r"\bDWM\b": "Data warehouse and Mining",
        r"\bEH\b": "Ethical Hacking",
        r"\bMV\b": "Machine Vision",
        r"\bDF\b": "Digital Forensics",
        r"\b(?:ADBMS|ADMS)\b": "Advanced Database Management System",
        r"\bDL\b": "Deep Learning",
        r"\b(?:ARVR|AR/VR)\b": "Augmented Reality and Virtual Reality",
        r"\bQC\b": "Quantum Computing",
        r"\bRL\b": "Reinforcement Learning",
        r"\b(?:BC|BCT)\b": "Blockchain Technology",
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
