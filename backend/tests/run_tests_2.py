import os
import time
from rag.rag_pipeline import ask_sies_gpt

queries = [
    "What are the recommended textbooks for the Computer Network course?",
    "Give me the online references and NPTEL links for the Web Computing Lab.",
    "List the Course Outcomes (COs) for the DevOps syllabus.",
    "How is the term work evaluated for the Professional Communication and Ethics II course?",
    "What are the prerequisites for the Quantitative Analysis subject?",
    "What are the Lab Outcomes for the Software Engineering Lab?"
]

with open("test_results_2.md", "w", encoding="utf-8") as f:
    f.write("# SIES GPT Deep Query Testing - Part 2\n\n")

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
    
    with open("test_results_2.md", "a", encoding="utf-8") as f:
        f.write(f"## Query {i}: {q}\n")
        f.write(f"**Retrieved Pages:** {pages}\n")
        f.write(f"**Time Taken:** {duration:.2f}s\n")
        f.write(f"**Response:**\n{ans}\n\n")
        f.write("---\n\n")

print("Testing complete. Results saved to test_results_2.md")
