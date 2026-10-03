import re

import ollama


def generate_answer(question: str, retrieved_chunks, original_question: str = None):
    check_query = original_question if original_question else question
    context_parts = []
    expected_modules = []
    expected_units = []
    expected_self_learning_sections = 0
    expected_semesters = []
    all_experiments = {}
    last_exp_num = 0

    global_hints = []
    
    for item in retrieved_chunks:
        metadata = item["metadata"]
        pages = metadata.get("pages", [metadata.get("page")])
        text = item["text"]

        expected_modules.extend(
            int(number) for number in re.findall(r"(?m)^## Module (\d+):", text)
        )
        expected_units.extend(re.findall(r"(?m)^\*\*Unit (\d+\.\d+)\*\*", text))
        expected_self_learning_sections += len(
            re.findall(r"(?i)\*\*Self-learning topics\*\*", text)
        )
        expected_semesters.extend(metadata.get("semesters", []))
        page_list = ", ".join(str(page) for page in pages if page is not None)
        
        # Python hack for 3B model: Extract references and tools and bubble them up to the absolute top of the prompt!
        if re.search(r"\b(references?|textbooks?|books?|online|software|hardware|tools?)\b", check_query, re.IGNORECASE):
            refs = re.search(r"(?im)((?:Textbooks|Reference books|Online References|Software Tools|Hardware Tools):.*)", text, re.DOTALL)
            if refs:
                global_hints.append(f"REFERENCES/TOOLS FOUND ON PAGE {page_list}:\n{refs.group(1)}")
                
        if re.search(r"\b(experiments?|labs?|practicals?)\b", check_query, re.IGNORECASE):
            # Robustly extract experiments with their full text
            current_num = None
            pending_num = None
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                m = re.match(r'^(\d+)(?:\s+([A-Z].*))?$', line)
                if m and int(m.group(1)) < 50 and int(m.group(1)) > 0:
                    num = int(m.group(1))
                    # Check if it's the next experiment in sequence (allow skipping 1 or 2)
                    if num == 1 or num == last_exp_num + 1 or num == last_exp_num + 2:
                        if m.group(2):
                            current_num = num
                            last_exp_num = num
                            pending_num = None
                            if current_num not in all_experiments:
                                all_experiments[current_num] = {"title": m.group(2), "full": [f"{current_num}. {m.group(2)}"]}
                        else:
                            pending_num = num
                        continue
                
                if pending_num is not None:
                    if re.match(r'^[A-Z]', line):
                        current_num = pending_num
                        last_exp_num = pending_num
                        pending_num = None
                        if current_num not in all_experiments:
                            all_experiments[current_num] = {"title": line, "full": [f"{current_num}. {line}"]}
                        continue
                
                if current_num:
                    if re.match(r'^(LO\d+|Term Work|Textbooks|Reference books|Online References|Software Tools|Hardware Tools|Suggested List)', line, re.IGNORECASE):
                        current_num = None
                    else:
                        all_experiments[current_num]["full"].append(line)

        context_parts.append(
            f"SOURCE: {metadata.get('filename')}\n"
            f"PAGES: {page_list}\n\n"
            f"CONTENT:\n{text}"
        )

    if not all_experiments and re.search(r"\b(experiments?|labs?|practicals?)\b", check_query, re.IGNORECASE):
        # We did not find any experiments
        pass

    found_refs = any("REFERENCES/TOOLS" in h for h in global_hints)
    if not found_refs and re.search(r"\b(references?|textbooks?|books?|online|software|hardware|tools?)\b", check_query, re.IGNORECASE):
        # If the query heavily implies looking for books/tools but we found NONE in the context, return early to prevent 3B hallucination
        return "I could not find the requested books, tools, or references in the provided syllabus pages."

    if all_experiments:
        # Check for range request (e.g., "5 to 11" or "5-11")
        start_idx = 1
        end_idx = 50
        range_match = re.search(r'\b(?:from\s+)?(\d+)\s*(?:to|-)\s*(\d+)\b', check_query, re.IGNORECASE)
        if range_match:
            start_idx = int(range_match.group(1))
            end_idx = int(range_match.group(2))
        
        filtered_experiments = [v for k, v in sorted(all_experiments.items()) if start_idx <= k <= end_idx]
        
        if filtered_experiments:
            if re.search(r"\blist\b", check_query, re.IGNORECASE):
                # User asked for a list (short titles only)
                exp_list_str = "\n".join(f"{k}. {v['title']}" for k, v in sorted(all_experiments.items()) if start_idx <= k <= end_idx)
                return f"Here is the requested list of experiments from the syllabus:\n\n{exp_list_str}"
            else:
                # User asked for experiments (full descriptions)
                exp_full_str = "\n\n".join(re.sub(r'[^\x00-\x7F]+', '-', "\n".join(v['full'])) for k, v in sorted(all_experiments.items()) if start_idx <= k <= end_idx)
                return f"Here are the requested experiments and their full descriptions from the syllabus:\n\n{exp_full_str}"
        
    context = "\n\n".join(context_parts)
    if global_hints:
        context = ">>> CRITICAL HINT: THE USER ASKED FOR REFERENCES. DO NOT SAY THEY ARE MISSING! THEY ARE RIGHT HERE:\n" + "\n\n".join(global_hints) + "\n<<<\n\n" + context
    is_outline_request = any(item["metadata"].get("course_outline", False) for item in retrieved_chunks)
    module_requirement = ""
    if expected_modules and is_outline_request:
        module_requirement = (
            "\nThe selected source modules are: "
            + ", ".join(str(number) for number in expected_modules)
            + ". Include every one exactly once, in this order; do not omit any.\n"
        )

    prompt = f"""
You are SIES GPT, an AI assistant for SIES Graduate School of Technology.

Answer the user's question using only the source context below.

Rules:
1. CRITICAL: DO NOT HALLUCINATE. You are strictly restricted to the SOURCE CONTEXT below. If the text does not contain the specific syllabus, books, or details requested, you MUST reply with "I cannot find this information in the syllabus documents." Do NOT invent book names, module topics, or course objectives using your internal knowledge.
2. Do not invent, rename, reorder, or combine course modules or topics.
3. The context may already be limited to the requested module range. Return
   only modules present in the context; never expand it to omitted modules.
4. For syllabus requests, include every selected module and every listed unit,
   hours, and self-learning section. Preserve order and the user's range.
5. Do not include textbooks, references, or assessments unless asked. If the user DOES ask for them (e.g. 'online references'), you MUST carefully scan the very bottom of the course pages for sections like 'Online References:' or 'Textbooks:'. Do NOT claim they are missing just because they are buried at the bottom of the page.
6. If the requested detail is truly not in the context, politely explain that you cannot find the requested information in the available SIES documents. 
7. Cross-Referencing Electives: If the user asks for electives in a specific semester, find the Semester Structure page (e.g. Semester V) and identify ALL Elective Categories required for that semester (e.g., both 'Program Elective-III' and 'Program Elective-IV' if present). Then, you MUST scan the other pages to find the detailed lists for EVERY category you found. List the ACTUAL SUBJECT NAMES for each category (e.g., "Advanced Database Management System"). Do NOT just output generic placeholders like "CEPEC501X". NEVER list electives from other semesters.
8. Mention the referred source pages exactly once naturally in your response (e.g., 'According to pages 11 and 12...'). Do NOT append a separate 'Sources' or 'References' list at the end of your answer.
9. Lab Experiments: If the user asks for lab experiments, you MUST carefully scan the entire text and extract EVERY SINGLE numbered experiment (there are often 10 to 15+ experiments). DO NOT stop early or skip any. FORMATTING: If the user explicitly asks for an "experiments list", provide ONLY the title or a very short 1-sentence summary of each experiment to save space. If the user just asks for "experiments" (without the word 'list'), provide the full description for each experiment.
10. HINTS: If the provided context starts with a "HINT:" block containing pre-extracted experiments or tools, you MUST copy those exact items into your answer. Do not ignore the hint.{module_requirement}

SOURCE CONTEXT:
======================
{context}
======================

USER QUESTION:
{question}

ANSWER:
"""

    response = ollama.generate(
        model="llama3.2:3b",
        prompt=prompt,
        options={"temperature": 0.0}
    )
    answer = response["response"]

    if expected_modules:
        returned_modules = [
            int(number)
            for number in re.findall(
                r"(?im)^\s*(?:#{1,6}\s*)?(?:\*\*)?Module\s+(\d+)\b",
                answer,
            )
        ]
        returned_units = re.findall(
            r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?Unit\s+(\d+\.\d+)\b",
            answer,
        )
        returned_self_learning_sections = len(
            re.findall(r"(?i)self[- ]learning topics", answer)
        )
        if (
            returned_modules != expected_modules
            or returned_units != expected_units
            or returned_self_learning_sections < expected_self_learning_sections
        ):
            return "\n\n".join(item["text"] for item in retrieved_chunks)

    if expected_semesters:
        roman_semesters = {
            "I": 1,
            "II": 2,
            "III": 3,
            "IV": 4,
            "V": 5,
            "VI": 6,
            "VII": 7,
            "VIII": 8,
        }
        returned_semesters = {
            roman_semesters.get(value.upper(), int(value) if value.isdigit() else 0)
            for value in re.findall(
                r"(?i)\bSemester\s+(VIII|VII|VI|V|IV|III|II|I|[1-8])\b",
                answer,
            )
        }
        if not set(expected_semesters).issubset(returned_semesters):
            return "\n\n".join(item["text"] for item in retrieved_chunks)

    return answer
