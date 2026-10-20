import os
import time
from rag.rag_pipeline import ask_sies_gpt

queries = [
    "List all the Program Elective-V subjects in Semester VIII.",
    "Give the hardware and software tools required for the Deep Learning Lab.",
    "List all the experiments from 3 to 7 for the Internet of Things Lab.",
    "What are the self-learning topics for Module 3 and 4 in the Blockchain Technology course?",
    "Which reference books are suggested for the Fog and Edge Computing course?",
    "Give the detailed syllabus for the subject CEPEC7011.",
    "What are the guidelines and term work marks distribution for Major Project II?",
    "Give the experiments list for the Big Data Analytics Lab."
]

with open("test_results.md", "w", encoding="utf-8") as f:
    f.write("# SIES GPT Deep Query Testing\n\n")

for i, q in enumerate(queries, 1):
    print(f"Testing {i}/{len(queries)}: {q}")
    start = time.time()
    try:
        res = ask_sies_gpt(q)
        ans = res['answer']
        pages = [s['page'] for s in res['sources']]
    except Exception as e:
        ans = f"ERROR: {e}"
        pages = []
    duration = time.time() - start
    
    with open("test_results.md", "a", encoding="utf-8") as f:
        f.write(f"## Query {i}: {q}\n")
        f.write(f"**Retrieved Pages:** {pages}\n")
        f.write(f"**Time Taken:** {duration:.2f}s\n")
        f.write(f"**Response:**\n{ans}\n\n")
        f.write("---\n\n")

print("Testing complete. Results saved to test_results.md")
