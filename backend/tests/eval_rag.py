import random
from rag.vector_store import client
from rag.rag_pipeline import ask_sies_gpt

def main():
    c = client.get_collection('sies_documents')
    all_docs = c.get(include=['documents', 'metadatas'])
    
    docs = all_docs['documents']
    metas = all_docs['metadatas']
    
    # We want to test a few distinct scenarios:
    # 1. A specific Module topic
    # 2. A Lab experiment
    # 3. Textbook/Reference query
    # 4. Assessment/Evaluation query
    # 5. Course outcomes query
    
    test_queries = [
        ("What are the textbooks for Theoretical Computer Science?", 21), # Assuming CEC501 textbooks are around page 21
        ("What are the course outcomes for Software Engineering?", None), # Generic course outcome
        ("What experiments are in the Software Engineering Lab?", None), # Lab request
        ("Explain the concept of Turing Machine as per syllabus", 20), # Module specific
        ("What is the continuous internal assessment practical (CIAP) marks for Database Management System?", None)
    ]
    
    print("Starting Evaluation...\n")
    
    for q, expected_page in test_queries:
        print(f"QUERY: {q}")
        res = ask_sies_gpt(q)
        sources = [s['page'] for s in res['sources']]
        print(f"SOURCES RETRIEVED: {sources}")
        if expected_page and expected_page not in sources:
            print(f"--> FAILURE: Expected page {expected_page} not found!")
        print(f"ANSWER SNIPPET: {res['answer'][:150]}...\n")
        print("-" * 50)

if __name__ == "__main__":
    main()
