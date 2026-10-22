import sys
sys.path.insert(0, r"C:\Users\athar\Downloads\SIES-GPT\backend")
sys.stdout.reconfigure(encoding="utf-8")
from rag.rag_pipeline import ask_sies_gpt

test_suite = [
    ("Commit aa467ea: Sem 6 Program Structure", "Syllabus for sem 6"),
    ("Commit aa467ea: Sem 6 Program Structure (alt)", "give sem 6 syllabus"),
    ("Commit aa467ea: Sem 3 Program Structure", "Show subjects for semester 3"),
    ("Commit 10de03c: Total Program Credits", "Total credits for B.Tech Computer Engineering degree"),
    ("Commit 10de03c: Course Nomenclature", "Give Nomenclature of courses in curriculum"),
    ("Commit 4b14038: Course Prerequisites", "Prerequisites for Operating System"),
    ("Commit 426ad24: Course Modules", "Give me Theoretical Computer Science module wise"),
    ("Commit 426ad24: Semester Electives", "What are the electives for semester 5?"),
    ("Commit 536049d: Mini/Major Projects", "Tell me about mini project in semester 5"),
    ("Commit 3b8719a: Lab Experiments (Single)", "Devops lab 5th experiment"),
    ("Commit 3b8719a / f1b1774: Multi-Lab Experiments", "Give devops lab 5th experiment and Aoa lab 3rd experiment"),
    ("Commit 02a7dea / f1b1774: Multi-Course Syllabus", "Give me Tcs and Ap syllabus module wise"),
    ("Commit 89b937f: DSD & UHV Modules", "Give modules of Universal Human Values"),
    ("Commit 682dd97: Evaluation Scheme", "Evaluation scheme for Database Management System"),
]

print(f"Starting Comprehensive Regression Suite ({len(test_suite)} tests)...\n")
failures = 0
for desc, query in test_suite:
    try:
        res = ask_sies_gpt(query)
        ans = res.get("answer", "")
        sources = res.get("sources", [])
        if not ans or len(ans) < 20:
            print(f"[FAIL] {desc} -> Empty response! Query: '{query}'")
            failures += 1
        else:
            files = set(s.get("filename") for s in sources)
            print(f"[PASS] {desc}")
            print(f"       Query: '{query}'")
            print(f"       Result: {len(ans)} chars | Sources: {list(files)}")
    except Exception as e:
        print(f"[ERROR] {desc} -> Raised Exception: {e}")
        failures += 1

print(f"\n==========================================")
print(f"FINAL RESULT: {len(test_suite) - failures}/{len(test_suite)} PASSED")
print(f"==========================================")
