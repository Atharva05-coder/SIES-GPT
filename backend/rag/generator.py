import re

from openai import OpenAI
import os


def extract_semester_electives(query: str, retrieved_chunks) -> str | None:
    is_elective_query = bool(re.search(r"\b(electives?|elective options?)\b", query, re.IGNORECASE))
    is_minor_query = bool(re.search(r"\b(minors?|mdms?|multidisciplinary minors?)\b", query, re.IGNORECASE))
    
    if not is_elective_query and not is_minor_query:
        return None
    if re.search(r"\b(experiments?|labs?|practicals?|modules?|examination scheme|exam scheme|evaluation|assessment)\b", query, re.IGNORECASE):
        return None

    m = re.search(r"\b(?:sem(?:ester)?|term)\s*([1-8]|I|II|III|IV|V|VI|VII|VIII)\b", query, re.IGNORECASE)
    sem_num = None
    if m:
        val = m.group(1).upper()
        roman = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
        sem_num = roman.get(val, int(val) if val.isdigit() else None)

    for item in retrieved_chunks:
        text = item.get("text", "")
        clean_text = text.replace(
            "General Smart Systems Network and \nSecurity \nArtificial \nIntelligence \nCEPEC5011: \nAdvanced Database \nManagement System \nCEPEC5012: \nInternet of things \nCEPEC5013:  \nEthical Hacking \n \nCEPEC5014: \nData warehouse \nand Mining",
            "General: CEPEC5011: Advanced Database Management System\nSmart Systems: CEPEC5012: Internet of things\nNetwork and Security: CEPEC5013: Ethical Hacking\nArtificial Intelligence: CEPEC5014: Data warehouse and Mining"
        ).replace(
            "General Smart Systems Network and \nSecurity \nArtificial \nIntelligence \nCEPEC6011: \nMachine Vision \nCEPEC6012:   \nRobotics and \nApplications \n \nCEPEC6013: Digital \nForensics \nCEPEC6014: \nNatural Language \nProcessing",
            "General: CEPEC6011: Machine Vision\nSmart Systems: CEPEC6012: Robotics and Applications\nNetwork and Security: CEPEC6013: Digital Forensics\nArtificial Intelligence: CEPEC6014: Natural Language Processing"
        ).replace(
            "General Smart Systems Network and \nSecurity \nArtificial \nIntelligence \nCEPEC7011:  High \nPerformance \nComputing \n \nCEPEC7012: \nFog and Edge \nComputing \nCEPEC7013: \nBlockchain \nTechnology \nCEPEC7014: \nDeep Learning",
            "General: CEPEC7011: High Performance Computing\nSmart Systems: CEPEC7012: Fog and Edge Computing\nNetwork and Security: CEPEC7013: Blockchain Technology\nArtificial Intelligence: CEPEC7014: Deep Learning"
        ).replace(
            "Data Science Smart Systems Network and \nSecurity \nArtificial \nIntelligence \nCEPEC7021: \nAugmented Reality \nand Virtual Reality \nCEPEC7022: \nQuantum \nComputing \nCEPEC7023: \nIntelligent Forensic \n \nCEPEC7024: \nReinforcement \nLearning",
            "Data Science: CEPEC7021: Augmented Reality and Virtual Reality\nSmart Systems: CEPEC7022: Quantum Computing\nNetwork and Security: CEPEC7023: Intelligent Forensic\nArtificial Intelligence: CEPEC7024: Reinforcement Learning"
        )

        elective_output = None
        minor_output = None

        if "Multidisciplinary Minor" in clean_text:
            idx = clean_text.find("Multidisciplinary Minor")
            mdm_part = clean_text[idx:]
            oe_idx = mdm_part.find("Open Elective")
            if oe_idx != -1:
                mdm_part = mdm_part[:oe_idx]
            lines = [l.strip() for l in mdm_part.split("\n") if l.strip()]
            courses = []
            curr_code = None
            curr_name = ""
            code_re = re.compile(r"^(MDM[CL]\d{4}):\s*(.*)$")
            for line in lines:
                m_code = code_re.match(line)
                if m_code:
                    if curr_code:
                        courses.append((curr_code, re.sub(r"\s+", " ", curr_name).strip()))
                    curr_code = m_code.group(1)
                    curr_name = m_code.group(2)
                elif curr_code:
                    curr_name += " " + line
            if curr_code:
                courses.append((curr_code, re.sub(r"\s+", " ", curr_name).strip()))
            if courses:
                roman_map = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}
                sem_str = f"Semester {roman_map.get(sem_num, sem_num)}" if sem_num else "The semester"
                res = [f"### {sem_str} Multidisciplinary Minor (MDM) Options\n"]
                for c, n in courses:
                    res.append(f"- **{c}**: {n}")
                minor_output = "\n".join(res)

        sections = re.split(r"(?i)(Program Elective\s*[-–—]?\s*(?:[I|V|X]+|\d+))", clean_text)
        if len(sections) >= 3:
            results = []
            category_names = []
            for i in range(1, len(sections), 2):
                raw_header = sections[i].strip()
                header = re.sub(r"Program\s+Elective\s*[-–—]?\s*", "Program Elective - ", raw_header, flags=re.IGNORECASE).strip()
                category_names.append(header)
                body = sections[i+1]
                lines = []
                for line in body.split("\n"):
                    line = line.strip()
                    if re.search(r"\b(Multidisciplinary Minor|Open Elective)\b", line, re.IGNORECASE):
                        break
                    m_match = re.match(r"^([^:]+):\s*(CEPEC\d+):\s*(.+)$", line)
                    if m_match:
                        bucket, code, name = m_match.group(1).strip(), m_match.group(2).strip(), m_match.group(3).strip()
                        lines.append(f"- **{bucket}**: {code}: {name}")
                if lines:
                    results.append(f"### {header}\n" + "\n".join(lines))

            if results:
                roman_map = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}
                sem_str = f"Semester {roman_map.get(sem_num, sem_num)}" if sem_num else "The semester"
                intro = f"{sem_str} offers **{'** and **'.join(category_names)}**. Below are the available elective options:\n\n"
                elective_output = intro + "\n\n".join(results)

        if is_minor_query and not is_elective_query:
            if minor_output:
                return minor_output
        elif is_elective_query and not is_minor_query:
            if elective_output:
                return elective_output
        elif is_minor_query and is_elective_query:
            parts = [p for p in [elective_output, minor_output] if p]
            if parts:
                return "\n\n---\n\n".join(parts)
        else:
            parts = [p for p in [elective_output, minor_output] if p]
            if parts:
                return "\n\n---\n\n".join(parts)

    return None


def extract_semester_program_structure(query: str, retrieved_chunks) -> str | None:
    is_struct_query = bool(
        re.search(r"\b(program structure|curriculum structure|teaching scheme|course structure|subject structure)\b", query, re.IGNORECASE)
        or re.search(r"\b(?:sem(?:ester)?|term)\s*([1-8]|I|II|III|IV|V|VI|VII|VIII)\b.*\b(?:structure|subjects?|courses?|curriculum)\b", query, re.IGNORECASE)
        or re.search(r"\b(?:structure|subjects?|courses?|curriculum)\b.*\b(?:sem(?:ester)?|term)\s*([1-8]|I|II|III|IV|V|VI|VII|VIII)\b", query, re.IGNORECASE)
    )
    if not is_struct_query:
        return None

    if re.search(r"\b(experiments?|labs?|practicals?|modules?|textbooks?|reference books?)\b", query, re.IGNORECASE) and not re.search(r"\b(structure)\b", query, re.IGNORECASE):
        return None

    structure_text = None
    elective_text = None

    for item in retrieved_chunks:
        text = item.get("text", "")
        if "Program Structure for" in text or re.search(r"(?i)Teaching Scheme.*Credits Assigned", text):
            if not structure_text:
                structure_text = text
        if "Program Elective" in text or "Multidisciplinary Minor" in text:
            if not elective_text and "Program Structure for" not in text:
                elective_text = text

    if not structure_text:
        return None

    norm_text = re.sub(r"/\s*\n\s*", "/", structure_text)
    sec_match = re.search(r"(?i)Semester\s+([IVX]+|\d+)\s+(.*?)(?:Examination Scheme|\Z)", norm_text, re.DOTALL)
    if not sec_match:
        return None

    found_sem = sec_match.group(1).upper()
    block = sec_match.group(2)

    lines = [l.strip() for l in block.split("\n") if l.strip()]
    code_pattern = re.compile(r"^((?:FEC|FEL|CEC|CEL|CEPEC|CEPEL|MDMC|MDML|OEC|CEP|CEM)\d+[A-Z0-9/]*)\b")
    
    table_rows = []
    current_code = None
    current_rest = ""
    total_hours_credits = None

    for line in lines:
        if re.search(r"(?i)Course\s*Code|Teaching Scheme|Credits Assigned|Theory Pract|Contact Hours", line):
            continue
        if line.startswith("Total") or " Total " in line:
            total_hours_credits = line
            break

        m_code = code_pattern.search(line)
        if m_code:
            if current_code:
                table_rows.append((current_code, current_rest.strip()))
            current_code = m_code.group(1)
            current_rest = line[m_code.end():].strip()
        elif current_code:
            current_rest += " " + line.strip()

    if current_code:
        table_rows.append((current_code, current_rest.strip()))

    if not table_rows:
        return None

    header = "| Course Code | Course Name | Category | Teaching Scheme (Contact Hours) | Credits Assigned |\n|---|---|---|---|---|\n"
    formatted_rows = []

    for code, rest in table_rows:
        rest = re.sub(r"\s+", " ", rest).strip()
        nums_match = re.search(r"((?:(?:\d+[\*\+\#\&\$]*|--|-)\s*){3,})$", rest)
        if nums_match:
            scheme_raw = nums_match.group(1).strip()
            before_nums = rest[:nums_match.start()].strip()
            cat_match = re.search(r"\b(PCC|BSC|ESC|MDM|PEC|VSEC|AEC|HSSM|MJP|OE|PW|CEP|VEC)(?:\s*\([A-Z0-9-]+\))?$", before_nums)
            if cat_match:
                cat = cat_match.group(0).strip()
                name = before_nums[:cat_match.start()].strip()
            else:
                cat = "--"
                name = before_nums
            nums = scheme_raw.split()
            if len(nums) >= 7:
                th_h, pr_h, tu_h = nums[0], nums[1], nums[2]
                tot_c = nums[-1]
                scheme = f"Theory: {th_h}, Pract.: {pr_h}, Tut.: {tu_h}"
                credits = tot_c
            elif len(nums) >= 4:
                scheme = f"Contact Hours: {' '.join(nums[:-1])}"
                credits = nums[-1]
            else:
                scheme = scheme_raw
                credits = nums[-1] if nums else "--"
        else:
            cat_match = re.search(r"\b(PCC|BSC|ESC|MDM|PEC|VSEC|AEC|HSSM|MJP|OE|PW|CEP|VEC)\b\s+(.*)$", rest)
            if cat_match:
                name = rest[:cat_match.start()].strip()
                cat = cat_match.group(1)
                nums = cat_match.group(2).strip().split()
                if len(nums) >= 7:
                    th_h, pr_h, tu_h = nums[0], nums[1], nums[2]
                    tot_c = nums[-1]
                    scheme = f"Theory: {th_h}, Pract.: {pr_h}, Tut.: {tu_h}"
                    credits = tot_c
                elif len(nums) >= 4:
                    scheme = f"Contact Hours: {' '.join(nums[:-1])}"
                    credits = nums[-1]
                else:
                    scheme = " ".join(nums)
                    credits = nums[-1] if nums else "--"
            else:
                name = rest
                cat = "--"
                scheme = "--"
                credits = "--"

        name = re.sub(r"\s+", " ", name).strip()
        formatted_rows.append(f"| {code} | {name} | {cat} | {scheme} | {credits} |")

    sem_label = f"Semester {found_sem}"
    table_md = f"### {sem_label} Program Structure\n\n" + header + "\n".join(formatted_rows)

    if total_hours_credits:
        clean_tot = re.sub(r"\s+", " ", total_hours_credits).strip()
        tot_parts = clean_tot.split()
        if len(tot_parts) >= 7:
            table_md += f"\n\n**Total Credits Assigned:** {tot_parts[-1]}"

    return table_md



def extract_course_module_outline(query: str, retrieved_chunks) -> str | None:
    if not retrieved_chunks:
        return None
    if not all(item.get("metadata", {}).get("course_outline", False) for item in retrieved_chunks):
        return None
    is_syllabus_query = bool(
        re.search(r"\b(syllabus|curriculum|course content|course outline|modules?|units?)\b", query, re.IGNORECASE)
    )
    if not is_syllabus_query:
        return None
    if re.search(r"\b(how many|how much|count|total number|number of|why|explain|difference between|compare|what is the purpose|prerequisites?)\b", query, re.IGNORECASE):
        return None

    return "\n\n".join(item["text"].strip() for item in retrieved_chunks)


WORD_TO_NUM = {
    "first": 1, "1st": 1, "1": 1, "one": 1,
    "second": 2, "2nd": 2, "2": 2, "two": 2,
    "third": 3, "3rd": 3, "3": 3, "three": 3,
    "fourth": 4, "4th": 4, "4": 4, "four": 4,
    "fifth": 5, "5th": 5, "5": 5, "five": 5,
    "sixth": 6, "6th": 6, "6": 6, "six": 6,
    "seventh": 7, "7th": 7, "7": 7, "seven": 7,
    "eighth": 8, "8th": 8, "8": 8, "eight": 8,
    "ninth": 9, "9th": 9, "9": 9, "nine": 9,
    "tenth": 10, "10th": 10, "10": 10, "ten": 10,
    "eleventh": 11, "11th": 11, "11": 11, "eleven": 11,
    "twelfth": 12, "12th": 12, "12": 12, "twelve": 12,
    "thirteenth": 13, "13th": 13, "13": 13, "thirteen": 13,
    "fourteenth": 14, "14th": 14, "14": 14, "fourteen": 14,
    "fifteenth": 15, "15th": 15, "15": 15, "fifteen": 15,
}


def parse_num_token(tok: str) -> int | None:
    tok = tok.lower().strip()
    if tok in WORD_TO_NUM:
        return WORD_TO_NUM[tok]
    clean = re.sub(r"(?:st|nd|rd|th)$", "", tok)
    if clean.isdigit():
        return int(clean)
    return None


def parse_requested_experiments(query: str, available_keys: list[int] | None = None) -> list[int] | None:
    avail = sorted(available_keys) if available_keys else list(range(1, 51))
    max_k = max(avail) if avail else 10

    # 1. 'last N' / 'final N' experiments
    m_last = re.search(r'\b(?:last|final)\s+(\d+(?:st|nd|rd|th)?|[a-z]+)\s*(?:experiments?|practicals?|tasks?|exp\.?)\b', query, re.I)
    if m_last:
        n = parse_num_token(m_last.group(1))
        if n and n > 0:
            if available_keys:
                return avail[-n:]
            return list(range(max(1, max_k - n + 1), max_k + 1))

    # 2. 'first N' / 'top N' / 'fist N' experiments
    m_first = re.search(r'\b(?:first|fist|top|initial|starting)\s+(\d+(?:st|nd|rd|th)?|[a-z]+)\s*(?:experiments?|practicals?|tasks?|exp\.?)\b', query, re.I)
    if m_first:
        n = parse_num_token(m_first.group(1))
        if n and n > 0:
            if available_keys:
                return avail[:n]
            return list(range(1, n + 1))

    # 3. Range: 'experiments from 2 to 5', 'between 3 and 7'
    m_range = re.search(r'\b(?:experiments?|practicals?|tasks?|exp\.?)?\s*(?:from\s+)?(\d+(?:st|nd|rd|th)?|[a-z]+)\s*(?:to|-|through)\s*(\d+(?:st|nd|rd|th)?|[a-z]+)\b', query, re.I)
    if m_range and ('to' in query.lower() or '-' in query or 'through' in query):
        n1 = parse_num_token(m_range.group(1))
        n2 = parse_num_token(m_range.group(2))
        if n1 and n2:
            return list(range(min(n1, n2), max(n1, n2) + 1))

    # 4. Multiple discrete numbers/ordinals: e.g. '2nd, 5th and 7th experiments', '2nd,5th and 7th'
    m_before = re.search(r'([0-9a-z,\s&/-]+)\s+(?:experiments?|practicals?|tasks?|exp\.?)\b', query, re.I)
    if m_before:
        before_str = m_before.group(1)
        tokens = re.findall(r'\b(\d+(?:st|nd|rd|th)?|[a-z]+)\b', before_str, re.I)
        nums = []
        for t in tokens:
            val = parse_num_token(t)
            if val and 1 <= val <= 50:
                nums.append(val)
        if nums:
            return sorted(list(dict.fromkeys(nums)))

    # Check text after 'experiments': e.g. 'experiments 2, 5 and 7'
    m_after = re.search(r'\b(?:experiments?|practicals?|tasks?|exp\.?)\s*(?:no\.?|#)?\s*([0-9a-z,\s&/-]+)', query, re.I)
    if m_after:
        after_str = m_after.group(1)
        after_str = re.split(r'\b(?:of|in|for|from|with)\b', after_str, flags=re.I)[0]
        tokens = re.findall(r'\b(\d+(?:st|nd|rd|th)?|[a-z]+)\b', after_str, re.I)
        nums = []
        for t in tokens:
            val = parse_num_token(t)
            if val and 1 <= val <= 50:
                nums.append(val)
        if nums:
            return sorted(list(dict.fromkeys(nums)))

    return None


def parse_requested_modules(query: str, total_modules: int = 6) -> list[int]:
    # 1. 'first N' / 'fist N' / 'top N' / 'initial N' modules
    m_first = re.search(r'\b(?:first|fist|top|initial|starting)\s+(\d+(?:st|nd|rd|th)?|[a-z]+)\s+modules?\b', query, re.I)
    if m_first:
        n = parse_num_token(m_first.group(1))
        if n and 1 <= n <= 10:
            return list(range(1, n + 1))

    # 2. 'last N' / 'final N' modules
    m_last = re.search(r'\b(?:last|final)\s+(\d+(?:st|nd|rd|th)?|[a-z]+)\s+modules?\b', query, re.I)
    if m_last:
        n = parse_num_token(m_last.group(1))
        if n and 1 <= n <= 10:
            return list(range(max(1, total_modules - n + 1), total_modules + 1))

    # 3. Range: 'modules from 1 to 3', 'module 2 to 4'
    m_range = re.search(r'\bmodules?\s*(?:from\s+)?(\d+(?:st|nd|rd|th)?|[a-z]+)\s*(?:to|-|through)\s*(\d+(?:st|nd|rd|th)?|[a-z]+)\b', query, re.I)
    if m_range:
        n1 = parse_num_token(m_range.group(1))
        n2 = parse_num_token(m_range.group(2))
        if n1 and n2:
            return list(range(min(n1, n2), max(n1, n2) + 1))

    # 4. Numbers after 'module(s)': e.g. 'module 3 and 6', 'modules 1, 2, and 4', 'module 2'
    m_after = re.search(r'\bmodules?\s*(?:no\.?|#)?\s*([0-9a-z,\s&/-]+)', query, re.I)
    if m_after:
        after_str = m_after.group(1)
        after_str = re.split(r'\b(?:of|in|for|from|with|and\s+its)\b', after_str, flags=re.I)[0]
        tokens = re.findall(r'\b(\d+(?:st|nd|rd|th)?|[a-z]+)\b', after_str, re.I)
        nums = []
        for t in tokens:
            val = parse_num_token(t)
            if val and 1 <= val <= 10:
                nums.append(val)
        if nums:
            return sorted(list(dict.fromkeys(nums)))

    # 5. Numbers before 'module(s)': e.g. '3rd and 6th module', '2nd module', '2nd, 4th and 5th module'
    m_before = re.search(r'([0-9a-z,\s&/-]+)\s+modules?\b', query, re.I)
    if m_before:
        before_str = m_before.group(1)
        tokens = re.findall(r'\b(\d+(?:st|nd|rd|th)?|[a-z]+)\b', before_str, re.I)
        nums = []
        for t in tokens:
            val = parse_num_token(t)
            if val and 1 <= val <= 10:
                nums.append(val)
        if nums:
            return sorted(list(dict.fromkeys(nums)))

    return []


def extract_specific_course_modules(query: str, retrieved_chunks) -> str | None:
    if not retrieved_chunks:
        return None

    m_unit = re.search(r'\bunit\s*(\d+\.\d+)\b', query, re.I)
    target_code = None
    for item in retrieved_chunks:
        meta = item.get("metadata", {})
        if meta.get("course_code"):
            target_code = meta.get("course_code")
            break

    sections = get_sections_dict()
    if not target_code:
        code_match = re.search(r"\b[A-Z]{2,6}\d{3,4}[A-Z]?\b", query.upper())
        if code_match and code_match.group() in sections:
            target_code = code_match.group()

    if not target_code or target_code not in sections:
        return None

    section = sections[target_code]
    course_name = extract_course_name_from_header(section["header"])
    outlines = section.get("module_outlines", [])

    total_mods = len(outlines) if outlines else 6
    req_modules = parse_requested_modules(query, total_modules=total_mods)

    if not req_modules and not m_unit:
        return None

    # Don't intercept if query is explicitly asking for whole syllabus / overview
    if re.search(r"\b(all modules|full syllabus|complete syllabus|overall syllabus)\b", query, re.I):
        return None

    if m_unit:
        req_unit = m_unit.group(1)
        target_mod_num = int(req_unit.split(".")[0])
        for m in outlines:
            if m.get("number") == target_mod_num:
                m_text = m.get("text", "")
                unit_pat = re.compile(rf"(?is)\*\*Unit\s+{re.escape(req_unit)}\*\*\s*(.*?)(?=\n\s*\*\*Unit\s+\d+\.\d+|\n\s*\*\*Self-learning|\Z)")
                unit_match = unit_pat.search(m_text)
                if unit_match:
                    unit_body = unit_match.group(1).strip()
                    lines = [
                        f"### {target_code}: {course_name}",
                        f"**Module {m['number']}: {m.get('title', '')}**\n",
                        f"**Unit {req_unit}:** {unit_body}",
                    ]
                    return "\n\n".join(lines)

    if not req_modules:
        return None

    matched_modules = [m for m in outlines if m.get("number") in req_modules]
    if not matched_modules:
        sec_text = section.get("text", "")
        for n in req_modules:
            mod_pat = re.compile(rf"(?is)(##?\s*Module\s*{n}[:\s].*?)(?=(?:##?\s*Module\s*\d+|Textbooks|Reference books|Assessment Scheme|Examination Scheme|\Z))")
            m_found = mod_pat.search(sec_text)
            if m_found:
                matched_modules.append({"number": n, "text": m_found.group(1).strip()})

    if not matched_modules:
        return None

def format_self_learning_text(text: str) -> str:
    if not text:
        return ""
    if "**Self-learning Topics:**" in text:
        return text
    return re.sub(
        r"(?i)\s*(?:\.|\b)\s*Self-?Learning(?:\s*topics?)?\s*:\s*",
        r".\n\n**Self-learning Topics:**\n",
        text,
    )


    if len(matched_modules) > 1:
        mod_str = ", ".join(f"Module {m['number']}" for m in matched_modules[:-1]) + f" and Module {matched_modules[-1]['number']}"
    else:
        mod_str = f"Module {matched_modules[0]['number']}"

    header = f"### {target_code}: {course_name} ({mod_str})\n\n"
    module_texts = [format_self_learning_text(m.get("text", "")) for m in matched_modules]
    return header + "\n\n---\n\n".join(module_texts)


def extract_course_all_modules_only(query: str, retrieved_chunks) -> str | None:
    if not retrieved_chunks:
        return None

    if re.search(r"\b(full\s+syllabus|complete\s+syllabus|overall\s+syllabus|entire\s+syllabus|teaching\s+scheme|examination\s+scheme|exam\s+scheme|outcomes?|objectives?|credit\s+distribution|how\s+many\s+credits?)\b", query, re.I):
        return None
    if parse_requested_modules(query) or re.search(r"\bunit\s*\d+(\.\d+)?\b", query, re.I):
        return None

    wants_modules = bool(
        re.search(r"\b(?:only\s+modules?|just\s+modules?|modules?\s+and\s+self-?learning|course\s+modules?|give\s+modules?|what\s+are\s+the\s+modules?|list\s+of\s+modules?|show\s+modules?|modules?\s+of)\b", query, re.I)
        or re.search(r"\bmodules?\b", query, re.I)
    )
    if not wants_modules:
        return None

    target_code = None
    for item in retrieved_chunks:
        meta = item.get("metadata", {})
        if meta.get("course_code"):
            target_code = meta.get("course_code")
            break

    sections = get_sections_dict()
    if not target_code:
        code_match = re.search(r"\b[A-Z]{2,6}\d{3,4}[A-Z]?\b", query.upper())
        if code_match and code_match.group() in sections:
            target_code = code_match.group()

    if not target_code or target_code not in sections:
        return None

    section = sections[target_code]
    course_name = extract_course_name_from_header(section["header"])
    outlines = section.get("module_outlines", [])
    if not outlines:
        return None

    header = f"### {target_code}: {course_name} - Course Modules\n\n"
    module_texts = [format_self_learning_text(m.get("text", "")) for m in outlines]
    return header + "\n\n---\n\n".join(module_texts)


def extract_textbooks_and_references(query: str, retrieved_chunks) -> str | None:
    if not re.search(
        r"\b(textbooks?|text\s*books?|reference\s*books?|references?|recommended\s*books?|online\s*references?|online\s*resources?|books?|reading\s*materials?|recommended\s*reading|bibliography)\b",
        query,
        re.IGNORECASE,
    ):
        return None
    if re.search(r"\b(experiments?|labs?|practicals?|modules?|scheme|outcomes?|objectives?)\b", query, re.IGNORECASE):
        return None

    is_only_online = bool(
        re.search(r"\bonline\s+(?:references?|resources?)\b", query, re.IGNORECASE)
        and not re.search(r"\b(textbooks?|books?|all|both)\b", query, re.IGNORECASE)
    )
    is_only_textbooks = bool(
        re.search(r"\btext\s*books?\b", query, re.IGNORECASE)
        and not re.search(r"\b(references?|reference\s*books?|online|all|both|reading)\b", query, re.IGNORECASE)
    )
    is_only_references = bool(
        re.search(r"\b(reference\s*books?|references?)\b", query, re.IGNORECASE)
        and not re.search(r"\b(text\s*books?|all|both|online)\b", query, re.IGNORECASE)
        and not re.search(r"\brefer\b", query, re.IGNORECASE)
    )

    target_code = None
    for item in retrieved_chunks:
        meta = item.get("metadata", {})
        if meta.get("course_code"):
            target_code = meta.get("course_code")
            break

    sections = get_sections_dict()
    if not target_code:
        code_match = re.search(r"\b[A-Z]{2,6}\d{3,4}[A-Z]?\b", query.upper())
        if code_match and code_match.group() in sections:
            target_code = code_match.group()

    candidate_pages = []
    if target_code and target_code in sections:
        candidate_pages = sections[target_code]["all_pages"]
    else:
        candidate_pages = retrieved_chunks

    course_prefix = ""
    if target_code and target_code in sections:
        cname = extract_course_name_from_header(sections[target_code]["header"])
        course_prefix = f"### {target_code}: {cname} - Recommended Books & References\n\n"

    for item in candidate_pages:
        text = item.get("text", "")
        if not re.search(r"(?i)\b(?:Textbooks|Reference books|References|Online References|Online Resources):", text):
            continue

        clean_text = re.split(r"(?i)\n\s*(?:Course Assessment|End Semester Examination|Internal Assessment|Assessment Scheme|Term Work|CIAP|ESEP):", text)[0]

        tb_match = re.search(r"(?is)(?:Textbooks?|Text books?):\s*(.*?)(?=\n\s*(?:Reference books?|References|Online References|Online Resources):|\Z)", clean_text)
        ref_match = re.search(r"(?is)(?:Reference books?|References):\s*(.*?)(?=\n\s*(?:Textbooks?|Text books?|Online References|Online Resources):|\Z)", clean_text)
        online_match = re.search(r"(?is)(?:Online References|Online Resources):\s*(.*?)(?=\n\s*(?:Textbooks?|Text books?|Reference books?|References):|\Z)", clean_text)

        tb_text = tb_match.group(1).strip() if tb_match else ""
        ref_text = ref_match.group(1).strip() if ref_match else ""
        online_text = online_match.group(1).strip() if online_match else ""

        # Clean any trailing module table fragments or stray page footers
        module_cut = r"(?im)^\s*(?:\d+\.\d+\b|Module\s+\d+|Total\s+\d+|Self-learning|CO\d+)"
        tb_text = re.split(module_cut, tb_text)[0].strip()
        ref_text = re.split(module_cut, ref_text)[0].strip()
        online_text = re.split(module_cut, online_text)[0].strip()

        results = []
        if is_only_textbooks:
            if tb_text:
                results.append(f"### Textbooks\n{tb_text}")
        elif is_only_online:
            if online_text:
                results.append(f"### Online References\n{online_text}")
        elif is_only_references:
            if ref_text:
                results.append(f"### References\n{ref_text}")
            if online_text:
                results.append(f"### Online References\n{online_text}")
        else:
            if tb_text:
                results.append(f"### Textbooks\n{tb_text}")
            if ref_text:
                results.append(f"### References\n{ref_text}")
            if online_text:
                results.append(f"### Online References\n{online_text}")

        if results:
            return course_prefix + "\n\n".join(results)

    return None


def extract_lab_experiments(query: str, retrieved_chunks) -> str | None:
    if not re.search(r"\b(experiments?|practicals?|tasks?|lab experiments?)\b", query, re.IGNORECASE):
        return None
    if re.search(r"\b(examination scheme|exam scheme|evaluation|credit distribution|hours?|module \d+)\b", query, re.IGNORECASE):
        return None

    all_experiments: dict[int, dict] = {}
    last_exp_num = 0
    at_least_count = None

    for item in retrieved_chunks:
        text = item.get("text", "")
        current_num = None
        pending_num = None
        in_experiments_section = False

        m_least = re.search(r"(?i)at\s+least\s+(\d+)\s+experiments", text)
        if m_least and not at_least_count:
            at_least_count = m_least.group(1)

        for raw_line in text.split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            if re.match(r"^(LO\d+|Term Work|Textbooks|Reference books|Online References|Online Resources|Software Tools|Hardware Tools|Lab Outcomes?|Course Outcomes?|Lab Objectives?|Practical Exam)", line, re.IGNORECASE):
                in_experiments_section = False
                current_num = None
                continue

            if re.search(r"(List of Experiments|Suggested List)", line, re.IGNORECASE):
                in_experiments_section = True
                continue

            m = re.match(r"^(\d+)(?:\s+([A-Z].*))?$", line)
            if m and 0 < int(m.group(1)) < 50:
                num = int(m.group(1))
                if num == 1 or num == last_exp_num + 1 or num == last_exp_num + 2:
                    if num in all_experiments and not in_experiments_section:
                        continue
                    if m.group(2):
                        current_num = num
                        last_exp_num = num
                        pending_num = None
                        if current_num not in all_experiments or in_experiments_section:
                            all_experiments[current_num] = {"title": m.group(2), "full": [f"{current_num}. {m.group(2)}"]}
                    else:
                        pending_num = num
                    continue

            if pending_num is not None:
                if re.match(r"^[A-Z]", line):
                    current_num = pending_num
                    last_exp_num = pending_num
                    pending_num = None
                    if current_num not in all_experiments or in_experiments_section:
                        all_experiments[current_num] = {"title": line, "full": [f"{current_num}. {line}"]}
                    continue

            if current_num:
                if current_num in all_experiments:
                    cleaned_line = re.sub(r"^[^\w\s\(\)\[\]\-]+", "-", line)
                    cleaned_line = re.sub(r"[\uFFFD\u2022\x95]", "-", cleaned_line)
                    all_experiments[current_num]["full"].append(cleaned_line)

    if not all_experiments:
        return None

    is_counting = bool(re.search(r"\b(how many|how much|count|total number|number of)\b", query, re.IGNORECASE))
    if is_counting:
        total_listed = len(all_experiments)
        if at_least_count:
            return f"According to the syllabus, students are required to complete at least {at_least_count} experiments from the {total_listed} listed experiments for this lab."
        return f"According to the syllabus, there are {total_listed} experiments listed for this lab."

    avail_keys = sorted(all_experiments.keys())
    req_keys = parse_requested_experiments(query, avail_keys)
    if req_keys is not None:
        target_keys = [k for k in avail_keys if k in req_keys]
    else:
        target_keys = avail_keys

    is_short_list = bool(re.search(r"\blist\b", query, re.IGNORECASE) and not re.search(r"\b(detail|describe|task|all)\b", query, re.IGNORECASE))

    exp_blocks = []
    for k in target_keys:
        raw_lines = all_experiments[k]["full"]
        formatted_lines = []
        for raw_l in raw_lines:
            l_str = raw_l.strip()
            if not l_str:
                continue
            if not formatted_lines:
                formatted_lines.append(l_str)
                continue
            prev = formatted_lines[-1]
            is_list_item = bool(re.match(r"^([-*o\u2022]\s|[a-z]\)|\d+\.|Tasks?:)", l_str, re.IGNORECASE))
            prev_ends_sentence = bool(re.search(r"[\.:;!?]$", prev))
            if not is_list_item and not prev_ends_sentence:
                formatted_lines[-1] = prev + " " + l_str
            else:
                formatted_lines.append(l_str)

        header = re.sub(r"^\d+[\.\)]\s*", "", formatted_lines[0])

        if is_short_list or len(formatted_lines) == 1:
            exp_blocks.append(f"- **Experiment {k}**: {header}")
        else:
            body = "\n".join(formatted_lines[1:])
            exp_blocks.append(f"- **Experiment {k}**: {header}\n\n  {body}")

    if not exp_blocks:
        return None

    if len(target_keys) == 1:
        intro = f"Here is Experiment {target_keys[0]} from the syllabus:\n\n"
    elif target_keys == list(range(min(target_keys), max(target_keys) + 1)) and len(target_keys) < len(avail_keys):
        intro = f"Here are experiments {min(target_keys)} to {max(target_keys)} from the syllabus:\n\n"
    elif len(target_keys) < len(avail_keys):
        s_nums = ", ".join(str(k) for k in target_keys[:-1]) + f" and {target_keys[-1]}"
        intro = f"Here are experiments {s_nums} from the syllabus:\n\n"
    else:
        intro = "Here are the experiments from the syllabus:\n\n"

    return intro + "\n\n".join(exp_blocks)


_sections_cache = None

def get_sections_dict():
    global _sections_cache
    if _sections_cache is None:
        from rag.retriever import _course_sections
        _sections_cache = {s["code"]: s for s in _course_sections()}
    return _sections_cache


def extract_course_name_from_header(header: str) -> str:
    m = re.search(r"(\d{1,3}\s+(?:\d{1,3}|--|-)|--\s+\d{1,2}|\b\d{1,2}\b(?:\s*[\*\+]\s*\d+)?\s*(?:--|-|\d))", header)
    if m:
        raw_name = header[:m.start()]
    else:
        lines = [l.strip() for l in header.split("\n") if l.strip()]
        raw_name = " ".join(lines[:3])
    clean = re.sub(r"\s+", " ", raw_name).strip()
    clean = re.sub(r"[\s\d\-–]+$", "", clean).strip()
    return clean


def build_course_full_markdown(target_code: str, section: dict, sections: dict) -> str:
    p1_text = section["all_pages"][0]["text"]
    course_name = extract_course_name_from_header(section["header"])
    text_clean = re.sub(rf"\b{re.escape(target_code)}\b", "", p1_text)

    # 1. Teaching Scheme & Credits
    teaching_scheme = None
    credits_assigned = None
    m_teach = re.search(r"(?is)(?:Teaching\s*Scheme|Theory\s+Practical\s+Tutorial|Credits\s*Assigned).*?(?=\n\s*(?:Examination\s*Scheme|Pre-?requisite|Program\s*Outcomes)|\Z)", text_clean)
    if m_teach:
        block = m_teach.group(0)
        header_match = re.search(r"(?i)(?:Tot\s*al|Total)", block)
        sub_block = block[header_match.end():] if header_match else block
        nums = re.findall(r"(\d+(?:\*?\+?\s*\d+)?|\-{1,2})", sub_block)
        if len(nums) >= 6:
            th_h, pr_h, tu_h = nums[0], nums[1], nums[2]
            th_c, pr_c, tu_c = nums[3], nums[4], nums[5]
            tot_c = nums[6] if len(nums) >= 7 else nums[-1]
            parts_h = []
            if th_h not in ["--", "-", "0"]: parts_h.append(f"{th_h} (Theory)")
            if pr_h not in ["--", "-", "0"]: parts_h.append(f"{pr_h} (Practical)")
            if tu_h not in ["--", "-", "0"]: parts_h.append(f"{tu_h} (Tutorial)")
            teaching_scheme = " + ".join(parts_h) if parts_h else "--"
            credits_assigned = f"{tot_c}"
        elif len(nums) >= 3:
            teaching_scheme = f"{nums[0]} hrs (Theory)" if nums[0] not in ["--", "-"] else "--"
            credits_assigned = f"{nums[-1]}"

    # 2. Examination Scheme
    exam_scheme = None
    m_exam = re.search(r"(?is)Examination\s*Scheme.*?(?=\n\s*(?:Pre-?requisite|Program\s*Outcomes|Course\s*Objectives|Lab\s*Objectives|Exp\.?\s*No|Suggested\s*List|\*|\Z))", text_clean)
    if m_exam:
        block = m_exam.group(0)
        header_end = re.search(r"(?i)(?:ISE\s+MSE|Total)", block)
        sub_block = block[header_end.end():] if header_end else block
        nums = re.findall(r"(\d{2,3}|\-{1,2})", sub_block)
        if len(nums) == 4 and nums[0].isdigit() and nums[1].isdigit() and nums[2].isdigit():
            ise, mse, ese, tot = nums[0], nums[1], nums[2], nums[3]
            exam_scheme = f"ISE ({ise}), MSE ({mse}), ESE ({ese}) | Total: {tot}"
        elif len(nums) >= 5:
            ise, mse, ese = nums[0], nums[1], nums[2]
            ciap, esep = nums[3], nums[4]
            tot = nums[5] if len(nums) >= 6 else (nums[-1] if nums[-1] not in ["--", "-"] else "")
            parts_e = []
            if ise not in ["--", "-"]: parts_e.append(f"ISE ({ise})")
            if mse not in ["--", "-"]: parts_e.append(f"MSE ({mse})")
            if ese not in ["--", "-"]: parts_e.append(f"ESE ({ese})")
            if ciap not in ["--", "-"]: parts_e.append(f"CIAP / Term Work ({ciap})")
            if esep not in ["--", "-"]: parts_e.append(f"ESEP / Practical Exam ({esep})")
            scheme_str = ", ".join(parts_e)
            if tot and tot not in ["--", "-"]:
                scheme_str += f" | Total: {tot}"
            exam_scheme = scheme_str

    # 3. Pre-requisite
    prereq = None
    m_prereq = re.search(r"(?is)Pre-?\s*requisite[s]?\s*:\s*(.*?)(?=\n\s*(?:Program\s*Outcomes?|Course\s*Objectives?|Lab\s*Objectives?)|\Z)", p1_text)
    if m_prereq:
        raw_pr = m_prereq.group(1).strip()
        pr_lines = [re.sub(r"^\d+\.\s*", "", l.strip()) for l in raw_pr.split("\n") if l.strip()]
        if pr_lines:
            prereq = "; ".join(pr_lines)
    if not prereq or prereq.lower() in ["nil", "none", "-", "--", "na", "not applicable"]:
        prereq = "Nil"
    else:
        prereq = re.sub(r"^[:\s]+", "", prereq).strip()

    # 4. Program Outcomes Addressed
    pos = []
    m_pos = re.search(r"(?is)Program\s*Outcomes?\s+(?:Addressed)?\s*(.*?)(?=\n\s*(?:Course\s*Objectives?|Lab\s*Objectives?|Course\s*Outcomes?|Lab\s*Outcomes?)|\Z)", p1_text)
    if m_pos:
        raw_pos = m_pos.group(1).strip()
        for l in raw_pos.split("\n"):
            l = l.strip()
            l_clean = re.sub(r"^\d+\.\s*", "", l)
            if re.match(r"^PO\d+", l_clean, re.IGNORECASE):
                pos.append(l_clean)
            elif pos and not re.search(r"(?i)Course|Lab|Objective|Outcome", l):
                pos[-1] += " " + l

    # Course / Lab distinction
    is_lab = bool(re.search(r"\blab\b", course_name, re.I) or target_code.startswith("CEL") or target_code.startswith("FEL") or target_code.startswith("CEPEL") or target_code.startswith("MDML"))
    obj_title = "Lab Objectives" if is_lab else "Course Objectives"
    out_title = "Lab Outcomes" if is_lab else "Course Outcomes"

    # Objectives
    objs = []
    m_obj = re.search(r"(?is)(?:Course|Lab)\s+Objectives?\s*:\s*(?:The course aims to enable students:)?\s*(.*?)(?=\n\s*(?:Course|Lab)\s+Outcomes?|\Z)", p1_text)
    if m_obj:
        raw_obj = m_obj.group(1).strip()
        for l in raw_obj.split("\n"):
            l = l.strip()
            m_num = re.match(r"^\d+\.\s*(.*)", l)
            if m_num:
                item = re.sub(r"^(?:To\s+)?", "", m_num.group(1).strip())
                if item:
                    item = item[0].upper() + item[1:]
                objs.append(item)
            elif objs and not re.search(r"(?i)Course\s+Outcomes?|Lab\s+Outcomes?", l):
                objs[-1] += " " + l

    # Outcomes
    outs = []
    m_out = re.search(r"(?is)(?:Course|Lab)\s+Outcomes?\s*:\s*(?:Upon completion of this course.*?:)?\s*(.*?)(?=\n\s*(?:Course\s+Code|Teaching\s+Scheme|Module\s+No|Suggested\s+List)|\Z)", p1_text)
    if m_out:
        raw_out = m_out.group(1).strip()
        for l in raw_out.split("\n"):
            l = l.strip()
            m_num = re.match(r"^\d+\.\s*(.*)", l)
            if m_num:
                item = m_num.group(1).strip()
                if item:
                    item = item[0].upper() + item[1:]
                outs.append(item)
            elif outs and not re.search(r"(?i)Teaching\s+Scheme|Course\s+Code", l):
                outs[-1] += " " + l

    # Assemble Markdown Response
    res_lines = []
    res_lines.append(f"**Course Code:** {target_code}  ")
    res_lines.append(f"**Course Name:** {course_name}  ")
    if teaching_scheme:
        res_lines.append(f"**Teaching Scheme:** {teaching_scheme}  ")
    if credits_assigned:
        res_lines.append(f"**Credits Assigned:** {credits_assigned}  ")
    if exam_scheme:
        res_lines.append(f"**Examination Scheme:** {exam_scheme}  ")
    res_lines.append(f"**Pre-requisite:** {prereq}\n")

    if pos:
        res_lines.append("**Program Outcomes Addressed:**")
        for p in pos:
            res_lines.append(f"- {p}")
        res_lines.append("")

    if objs:
        res_lines.append(f"**{obj_title}:**")
        for i, o in enumerate(objs, 1):
            res_lines.append(f"{i}. {o}")
        res_lines.append("")

    if outs:
        res_lines.append(f"**{out_title}:**")
        for i, o in enumerate(outs, 1):
            res_lines.append(f"{i}. {o}")
        res_lines.append("")

    if is_lab:
        exps = extract_lab_experiments("all experiments", section["all_pages"])
        if exps:
            clean_exps = re.sub(r"^Here are (?:the|experiments).*?:\n\n", "", exps, flags=re.I).strip()
            res_lines.append(f"### Suggested List of Experiments\n\n{clean_exps}\n")
    else:
        outlines = section.get("module_outlines", [])
        if outlines:
            res_lines.append("### Course Modules\n")
            for m in outlines:
                res_lines.append(format_self_learning_text(m.get("text", "")))
                res_lines.append("")

    books = extract_textbooks_and_references("all textbooks and references", section["all_pages"])
    if books:
        res_lines.append(f"{books}")

    return "\n".join(res_lines).strip()


def find_paired_course(code: str, name: str, is_target_lab: bool, sections: dict) -> tuple[str, str] | None:
    clean_n = re.sub(r"[\s\-]+(lab|laboratory)$", "", name, flags=re.I).strip()
    for other_code, other_sec in sections.items():
        if other_code == code:
            continue
        other_name = extract_course_name_from_header(other_sec["header"])
        other_clean = re.sub(r"[\s\-]+(lab|laboratory)$", "", other_name, flags=re.I).strip()
        other_is_lab = bool(re.search(r"\blab\b", other_name, re.I) or other_code.startswith("CEL") or other_code.startswith("FEL") or other_code.startswith("CEPEL") or other_code.startswith("MDML"))
        if other_is_lab != is_target_lab:
            c1 = clean_n.rstrip("s").lower()
            c2 = other_clean.rstrip("s").lower()
            if c1 == c2 or (len(c1) > 5 and (c1 in c2 or c2 in c1)):
                return other_code, other_name
    return None


def extract_course_full_information(query: str, retrieved_chunks) -> str | None:
    if not retrieved_chunks:
        return None

    if re.search(r"\b(program structure|curriculum structure|electives?|minors?|mdms?|credit distribution|semester-?wise credit|how many credits)\b", query, re.IGNORECASE):
        return None
    if re.search(r"\b(?:only\s+)?(textbooks?|text\s*books?|reference\s*books?|references?|books?|reading\s*materials?|recommended\s*reading)\b", query, re.IGNORECASE) and not re.search(r"\b(information|informatin|details?|overview|about)\b", query, re.IGNORECASE):
        return None
    if re.search(r"\b(?:only\s+modules?|just\s+modules?|modules?\s+and\s+self-?learning|course\s+modules?|give\s+modules?|what\s+are\s+the\s+modules?|list\s+of\s+modules?|show\s+modules?|modules?\s+of)\b", query, re.IGNORECASE) and not re.search(r"\b(full\s+syllabus|complete\s+syllabus|overall\s+syllabus)\b", query, re.IGNORECASE):
        return None
    if re.search(r"\b(from\s+\d+|between\s+\d+|first\s+\d+\s+experiments?|\d+(?:st|nd|rd|th)?\s+experiments?)\b", query, re.IGNORECASE):
        return None
    if parse_requested_modules(query) or re.search(r"\bunit\s*\d+(\.\d+)?\b", query, re.IGNORECASE):
        return None

    target_code = None
    for item in retrieved_chunks:
        meta = item.get("metadata", {})
        if meta.get("course_code"):
            target_code = meta.get("course_code")
            break

    sections = get_sections_dict()
    if not target_code:
        code_match = re.search(r"\b[A-Z]{2,6}\d{3,4}[A-Z]?\b", query.upper())
        if code_match and code_match.group() in sections:
            target_code = code_match.group()

    if not target_code or target_code not in sections:
        return None

    section = sections[target_code]
    course_name = extract_course_name_from_header(section["header"])

    # Determine if this query is asking about this course
    clean_q = query.strip()
    clean_course_name = re.sub(r"[\s\-]+(lab|laboratory)$", "", course_name, flags=re.I).strip()

    def norm_name(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r"[\s\-–_]+", " ", s)
        return s.strip()

    norm_q = norm_name(clean_q)
    norm_cname = norm_name(course_name)
    norm_clean_cname = norm_name(clean_course_name)

    is_course_name_query = bool(
        clean_q.lower() == target_code.lower()
        or clean_q.lower() == course_name.lower()
        or clean_q.lower() == clean_course_name.lower()
        or norm_q == norm_cname
        or norm_q == norm_clean_cname
        or norm_q.rstrip("s") in norm_cname.rstrip("s")
        or norm_cname.rstrip("s") in norm_q.rstrip("s")
        or norm_clean_cname.rstrip("s") in norm_q.rstrip("s")
        or norm_q.rstrip("s") in norm_clean_cname.rstrip("s")
        or clean_q.lower().rstrip("s") in course_name.lower().rstrip("s")
        or course_name.lower().rstrip("s") in clean_q.lower().rstrip("s")
        or re.search(rf"\b{re.escape(target_code)}\b", clean_q, re.I)
        or re.search(rf"\b{re.escape(clean_course_name)}\b", clean_q, re.I)
        or (len(norm_clean_cname) >= 3 and re.search(rf"\b{re.escape(norm_clean_cname)}\b", norm_q, re.I))
    )

    is_info_query = bool(
        is_course_name_query
        or re.search(r"\b(information|informatin|info|details?|overview|summary|about|explain the course|explain the lab|tell me about|give|what is)\b", query, re.IGNORECASE)
        or re.search(r"^(?:what is|details? of|info on|explain|give)\s+[A-Za-z0-9\s-]+\??$", clean_q, re.IGNORECASE)
    )
    if not is_info_query:
        return None

    is_lab = bool(re.search(r"\blab\b", course_name, re.I) or target_code.startswith("CEL") or target_code.startswith("FEL") or target_code.startswith("CEPEL") or target_code.startswith("MDML"))
    wants_both = bool(re.search(r"\b(subject\s+and\s+lab|lab\s+and\s+subject|theory\s+and\s+lab|both)\b", query, re.IGNORECASE))

    main_text = build_course_full_markdown(target_code, section, sections)
    paired = find_paired_course(target_code, course_name, is_lab, sections)

    if wants_both and paired:
        paired_code, paired_name = paired
        if paired_code in sections:
            paired_text = build_course_full_markdown(paired_code, sections[paired_code], sections)
            return f"{main_text}\n\n---\n\n{paired_text}"

    if paired:
        paired_code, paired_name = paired
        label_kind = "theory course" if is_lab else "laboratory course"
        main_text += f"\n\n---\n*Note: For the associated {label_kind}, see **{paired_code}: {paired_name}**.*"

    return main_text


def generate_answer(question: str, retrieved_chunks, original_question: str = None, yield_callback=None, cancel_event=None):

    def early_return(ret_text):
        if yield_callback:
            tokens = re.findall(r"\S+|\n|\s+", ret_text)
            for tok in tokens:
                if cancel_event and cancel_event.is_set():
                    return ""
                yield_callback({"type": "token", "text": tok})
        return ret_text

    from rag.query_rewriter import reframe_query
    check_query = reframe_query(original_question if original_question else question)

    # Fast deterministic extractors (0.005s execution)
    wants_structure = bool(re.search(r"\b(program structure|curriculum structure|teaching scheme|course structure|subject structure|structure)\b", check_query, re.I))
    wants_electives = bool(re.search(r"\b(electives?|elective options?|minors?|mdms?|multidisciplinary)\b", check_query, re.I))

    if wants_structure and wants_electives:
        fast_structure = extract_semester_program_structure(check_query, retrieved_chunks)
        fast_electives = extract_semester_electives(check_query, retrieved_chunks)
        if fast_structure and fast_electives:
            return early_return(f"{fast_structure}\n\n---\n\n{fast_electives}")
        elif fast_structure:
            return early_return(fast_structure)
        elif fast_electives:
            return early_return(fast_electives)

    if wants_electives:
        fast_electives = extract_semester_electives(check_query, retrieved_chunks)
        if fast_electives:
            return early_return(fast_electives)

    if wants_structure:
        fast_structure = extract_semester_program_structure(check_query, retrieved_chunks)
        if fast_structure:
            return early_return(fast_structure)

    fast_books = extract_textbooks_and_references(check_query, retrieved_chunks)
    if fast_books:
        return early_return(fast_books)

    fast_exps = extract_lab_experiments(check_query, retrieved_chunks)
    if fast_exps:
        return early_return(fast_exps)

    # Specific sub-module or unit queries (e.g. "Give CN 3rd and 6th module", "Module 2 of OS", "Unit 1.1")
    fast_modules = extract_specific_course_modules(check_query, retrieved_chunks)
    if fast_modules:
        return early_return(fast_modules)

    fast_all_modules = extract_course_all_modules_only(check_query, retrieved_chunks)
    if fast_all_modules:
        return early_return(fast_all_modules)

    fast_info = extract_course_full_information(check_query, retrieved_chunks)
    if fast_info:
        return early_return(fast_info)

    fast_outline = extract_course_module_outline(check_query, retrieved_chunks)
    if fast_outline:
        return early_return(fast_outline)

    if re.search(r"\b(credit distribution|credits? distribution|semester-?wise credit)\b", check_query, re.IGNORECASE):
        table_text = """According to page 3 of the syllabus documents, the Semester-wise Credit Distribution Structure for Four Year UG Engineering is as follows:

| Course Category | I | II | III | IV | V | VI | VII | VIII | Total |
|---|---|---|---|---|---|---|---|---|---|
| Basic Science Course (BSC) / ESC | 7 | 6 | - | - | - | - | - | - | 13 |
| Engineering Science Course (ESC) | 9 | 10 | - | - | - | - | - | - | 19 |
| Program Core Course (PCC) | - | - | 17 | 11 | 11 | 10 | 04 | - | 53 |
| Program Elective Course (PEC) | - | - | - | - | 04 | 04 | 07 | - | 15 |
| Multidisciplinary Minor (MDM) | - | 03 | 04 | 04 | 04 | - | - | - | 15 |
| Open Elective (OE) | - | - | - | - | - | - | 03 | 03 | 06 |
| Vocational and Skill Enhancement Course (VSEC) | 01 | 01 | 02 | 02 | - | 02 | - | - | 08 |
| Ability Enhancement Course (HSSM / AEC) | 02 | - | - | 02 | - | - | - | - | 04 |
| Entrepreneurship / Management (HSSM) | - | 02 | 02 | - | - | - | - | - | 04 |
| Indian Knowledge System (IKS) | 02 | - | - | - | - | - | - | - | 02 |
| Value Education Course (VEC) | - | - | - | 02 | - | - | - | - | 02 |
| Research Methodology (RM) | - | - | - | - | - | - | - | 03 | 03 |
| Community Engagement / Field Project (FP) | - | - | 01 | 01 | - | - | - | - | 02 |
| Project | - | - | - | - | 01 | 02 | 02 | 01 | 06 |
| Internship / On Job Training (OJT) | - | - | - | - | - | - | 12 | - | 12 |
| Co-curricular Courses (CC) | 04 | - | - | - | - | - | - | - | 04 |
| **Total Credits (Major)** | **21** | **21** | **22** | **21** | **22** | **22** | **20** | **19** | **168** |"""
        return early_return(table_text)

    if re.search(r"\b(total credits?|total number of credits?|credits? for (?:the )?(?:b\.?tech|degree|program|engineering))\b", check_query, re.IGNORECASE):
        total_text = "According to the syllabus documents (Page 3), the total number of credits required for the B.Tech Computer Engineering program is **168 credits** across all 8 semesters (Sem I: 21, Sem II: 21, Sem III: 22, Sem IV: 21, Sem V: 22, Sem VI: 22, Sem VII: 20, Sem VIII: 19)."
        return early_return(total_text)
    context_parts = []
    expected_modules = []
    expected_units = []
    expected_self_learning_sections = 0
    expected_semesters = []
    all_experiments = {}
    last_exp_num = 0

    global_hints = []
    seen_context_signatures = set()
    
    for item in retrieved_chunks:
        metadata = item["metadata"]
        pages = metadata.get("pages", [metadata.get("page")])
        text = item["text"]
        if metadata.get("page") == 12:
            text = text.replace(
                "General Smart Systems Network and \nSecurity \nArtificial \nIntelligence \nCEPEC5011: \nAdvanced Database \nManagement System \nCEPEC5012: \nInternet of things \nCEPEC5013:  \nEthical Hacking \n \nCEPEC5014: \nData warehouse \nand Mining",
                "General: CEPEC5011: Advanced Database Management System\nSmart Systems: CEPEC5012: Internet of things\nNetwork and Security: CEPEC5013: Ethical Hacking\nArtificial Intelligence: CEPEC5014: Data warehouse and Mining"
            )
        if metadata.get("page") == 14:
            text = text.replace(
                "General Smart Systems Network and \nSecurity \nArtificial \nIntelligence \nCEPEC6011: \nMachine Vision \nCEPEC6012:   \nRobotics and \nApplications \n \nCEPEC6013: Digital \nForensics \nCEPEC6014: \nNatural Language \nProcessing",
                "General: CEPEC6011: Machine Vision\nSmart Systems: CEPEC6012: Robotics and Applications\nNetwork and Security: CEPEC6013: Digital Forensics\nArtificial Intelligence: CEPEC6014: Natural Language Processing"
            )
        if metadata.get("page") == 16:
            text = text.replace(
                "General Smart Systems Network and \nSecurity \nArtificial \nIntelligence \nCEPEC7011:  High \nPerformance \nComputing \n \nCEPEC7012: \nFog and Edge \nComputing \nCEPEC7013: \nBlockchain \nTechnology \nCEPEC7014: \nDeep Learning",
                "General: CEPEC7011: High Performance Computing\nSmart Systems: CEPEC7012: Fog and Edge Computing\nNetwork and Security: CEPEC7013: Blockchain Technology\nArtificial Intelligence: CEPEC7014: Deep Learning"
            )
            text = text.replace(
                "Data Science Smart Systems Network and \nSecurity \nArtificial \nIntelligence \nCEPEC7021: \nAugmented Reality \nand Virtual Reality \nCEPEC7022: \nQuantum \nComputing \nCEPEC7023: \nIntelligent Forensic \n \nCEPEC7024: \nReinforcement \nLearning",
                "Data Science: CEPEC7021: Augmented Reality and Virtual Reality\nSmart Systems: CEPEC7022: Quantum Computing\nNetwork and Security: CEPEC7023: Intelligent Forensic\nArtificial Intelligence: CEPEC7024: Reinforcement Learning"
            )

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
        if re.search(r"\b(references?|textbooks?|books?|online references?|software tools?|hardware tools?|tools?)\b", check_query, re.IGNORECASE):
            refs = re.search(r"(?im)((?:Textbooks|Reference books|Online References|Software Tools|Hardware Tools):.*)", text, re.DOTALL)
            if refs:
                global_hints.append(f"REFERENCES/TOOLS FOUND ON PAGE {page_list}:\n{refs.group(1)}")
                
        if re.search(r"\b(experiments?|labs?|practicals?)\b", check_query, re.IGNORECASE):
            # Robustly extract experiments with their full text
            current_num = None
            pending_num = None
            in_experiments_section = False
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                if re.match(r'^(LO\d+|Term Work|Textbooks|Reference books|Online References|Software Tools|Hardware Tools|Lab Outcomes?|Course Outcomes?|Lab Objectives?)', line, re.IGNORECASE):
                    in_experiments_section = False
                    current_num = None
                    continue
                    
                if re.search(r'(List of Experiments|Suggested List)', line, re.IGNORECASE):
                    in_experiments_section = True
                    continue
                
                m = re.match(r'^(\d+)(?:\s+([A-Z].*))?$', line)
                if m and int(m.group(1)) < 50 and int(m.group(1)) > 0:
                    num = int(m.group(1))
                    if num == 1 or num == last_exp_num + 1 or num == last_exp_num + 2:
                        # Prevent overwriting if we already have this experiment unless it's genuinely new
                        if num in all_experiments and not in_experiments_section:
                            continue
                            
                        if m.group(2):
                            current_num = num
                            last_exp_num = num
                            pending_num = None
                            if current_num not in all_experiments or in_experiments_section:
                                all_experiments[current_num] = {"title": m.group(2), "full": [f"{current_num}. {m.group(2)}"]}
                        else:
                            pending_num = num
                        continue
                
                if pending_num is not None:
                    if re.match(r'^[A-Z]', line):
                        current_num = pending_num
                        last_exp_num = pending_num
                        pending_num = None
                        if current_num not in all_experiments or in_experiments_section:
                            all_experiments[current_num] = {"title": line, "full": [f"{current_num}. {line}"]}
                        continue
                
                if current_num:
                    if current_num in all_experiments:
                        all_experiments[current_num]["full"].append(line)

        course_info = f"<course>{metadata.get('course_name', 'Unknown')}</course>\n" if 'course_name' in metadata else ""
        text_sig = re.sub(r"\s+", " ", text.strip())[:250]
        if text_sig in seen_context_signatures:
            continue
        seen_context_signatures.add(text_sig)
        context_parts.append(
            f"<source_document>\n"
            f"<filename>{metadata.get('filename')}</filename>\n"
            f"<pages>{page_list}</pages>\n"
            f"{course_info}"
            f"<content>\n{text}\n</content>\n"
            f"</source_document>"
        )

    if not all_experiments and re.search(r"\b(experiments?|practicals?|tasks?)\b", check_query, re.IGNORECASE) and not re.search(r"\b(does|do|is|are|which|why|when|who|how|whether|can|what is|tell me about)\b", check_query, re.IGNORECASE):
        return early_return("I could not find any laboratory experiments or practicals listed in the syllabus for this course.")

    found_refs = any("REFERENCES/TOOLS" in h for h in global_hints)
    if not found_refs and re.search(r"\b(references?|textbooks?|books?|online references?|software tools?|hardware tools?|tools?)\b", check_query, re.IGNORECASE) and not re.search(r"\bsoftware engineering\b", check_query, re.IGNORECASE):
        # If the query heavily implies looking for books/tools but we found NONE in the context, return early to prevent 3B hallucination
        return early_return("I could not find the requested books, tools, or references in the provided syllabus pages.")

    is_counting = re.search(r"\b(how many|how much|count|total number|number of)\b", check_query, re.IGNORECASE)
    if is_counting and re.search(r"\b(modules?)\b", check_query, re.IGNORECASE) and expected_modules:
        return early_return(f"According to the syllabus, there are {len(set(expected_modules))} modules listed for this course.")

    if all_experiments:
        # Check for range request (e.g., "5 to 11" or "5-11")
        start_idx = 1
        end_idx = 50
        word_to_num = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
        
        range_match = re.search(r'\b(?:from\s+)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:to|-)\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b', check_query, re.IGNORECASE)
        first_n_match = re.search(r'\bfirst\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b', check_query, re.IGNORECASE)
        single_match = re.search(r'\b(?:experiments?|practicals?|tasks?)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b', check_query, re.IGNORECASE)
        nth_match = re.search(r'\b(\d+)(?:st|nd|rd|th)?\s+(?:experiments?|practicals?|tasks?)\b', check_query, re.IGNORECASE)
        
        def parse_num(n):
            return int(n) if n.isdigit() else word_to_num[n.lower()]

        if range_match:
            start_idx = parse_num(range_match.group(1))
            end_idx = parse_num(range_match.group(2))
        elif first_n_match:
            start_idx = 1
            end_idx = parse_num(first_n_match.group(1))
        elif single_match:
            start_idx = parse_num(single_match.group(1))
            end_idx = start_idx
        elif nth_match:
            start_idx = int(nth_match.group(1))
            end_idx = start_idx
        
        filtered_experiments = [v for k, v in sorted(all_experiments.items()) if start_idx <= k <= end_idx]
        
        is_counting = re.search(r"\b(how many|how much|count|total number|number of)\b", check_query, re.IGNORECASE)

        if is_counting and all_experiments:
            # For counting queries: scan context for the term work requirement and return directly
            total_listed = len(all_experiments)
            required_match = None
            for chunk_text in context_parts:
                m = re.search(r'at least (\d+) experiments', chunk_text, re.IGNORECASE)
                if m:
                    required_match = m.group(1)
                    break
            if required_match:
                return early_return(f"According to the syllabus, students are required to complete at least {required_match} experiments from the {total_listed} listed experiments for this lab.")
            else:
                return early_return(f"According to the syllabus, there are {total_listed} experiments listed for this lab.")

        has_exp_keyword = re.search(r"\b(experiments?|practicals?|tasks?|list)\b", check_query, re.IGNORECASE)
        is_asking_attribute = re.search(r"\b(does|do|is|are|which|why|when|who|how|whether|can|what is|tell me about)\b", check_query, re.IGNORECASE)
        is_explicit_list = re.search(r"\b(what are the|list|give me|show me|all|detail|describe)\b", check_query, re.IGNORECASE)
        
        should_bypass = False
        if has_exp_keyword and not is_counting:
            if is_explicit_list:
                should_bypass = True
            elif not is_asking_attribute:
                should_bypass = True

        if filtered_experiments and should_bypass:
            if re.search(r"\blist\b", check_query, re.IGNORECASE):
                # User asked for a list (short titles only)
                def make_short(title):
                    clean_title = re.sub(r'[^\x00-\x7F]+', '-', title).strip()
                    parts = clean_title.split('.')
                    short = parts[0]
                    if len(short) > 120: short = short[:120] + '...'
                    # Clean trailing commas/punctuation
                    short = re.sub(r'[,;\s]+$', '', short)
                    return short + '.'
                
                exp_list_str = "\n".join(f"- **Experiment {k}:** {re.sub(r'^\\d+[\\.\\)]\\s*', '', make_short(v['title']))}" for k, v in sorted(all_experiments.items()) if start_idx <= k <= end_idx)
                return early_return(f"Here is the requested list of experiments from the syllabus:\n\n{exp_list_str}")
            else:
                # User asked for experiments (full descriptions with tasks)
                exp_blocks = []
                for k, v in sorted(all_experiments.items()):
                    if start_idx <= k <= end_idx:

                        full_desc = re.sub(r'[^\x00-\x7f]+', '-', "\n".join(v['full']))
                        lines = [line.strip() for line in full_desc.split("\n") if line.strip()]
                        formatted_lines = []
                        for line in lines:
                            if not formatted_lines:
                                formatted_lines.append(line)
                                continue
                            prev = formatted_lines[-1]
                            is_list_item = re.match(r'^([-*o]\s|[a-z]\)|\d+\.|Tasks?:)', line, re.IGNORECASE)
                            prev_ends_sentence = re.search(r'[\.:;!?]$', prev)
                            if not is_list_item and not prev_ends_sentence:
                                formatted_lines[-1] = prev + " " + line
                            else:
                                formatted_lines.append(line)
                        
                        # Strip duplicated experiment number
                        header = formatted_lines[0]
                        header = re.sub(r'^\d+[\.\)]\s*', '', header)
                        formatted_lines[0] = header

                        if len(formatted_lines) == 1:
                            exp_blocks.append(f"- **Experiment {k}:** {formatted_lines[0]}")
                        else:
                            header = formatted_lines[0]
                            body = "\n\n  ".join(formatted_lines[1:])
                            exp_blocks.append(f"- **Experiment {k}:** {header}\n\n  {body}")
                exp_full_str = "\n\n".join(exp_blocks)
                return early_return(f"Here are the detailed experiments (including tasks and requirements) from the syllabus:\n\n{exp_full_str}") 
        
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
5. Do not include textbooks, references, or assessments unless asked. If the user DOES ask for them (e.g. 'online references', 'course assessment', 'how is course evaluated', 'examination scheme', 'marks distribution'):
   - Textbooks / References: carefully scan the bottom of the course pages for sections like 'Textbooks:', 'Reference books:', or 'Online References:'. Do NOT claim they are missing just because they are buried at the bottom of the page.
   - Course Evaluation / Assessment: check both the 'Examination Scheme' table (which lists ISE, MSE, ESE, CIAP, ESEP, Total marks) AND any detailed 'Course Assessment:' or 'End Semester Examination:' sections (which detail Term Work/CIAP oral & written marks, test weightage, etc.). Provide the exact, accurate breakdown of marks as given in the syllabus.
6. If the requested detail is truly not in the context, politely explain that you cannot find the requested information in the available SIES documents. 
7. Electives & Minors Formatting: When asked for electives, minors, or elective options in a semester:
   - DO NOT format electives as a table. Tables with courses in cells look messy and unreadable. Instead, use clear markdown subheadings (### Program Elective-X) and clean bullet points for each technology bucket/domain (e.g. - **General**: CEPEC7011: High Performance Computing).
   - First state which Program Elective(s) / MDM categories the semester offers based on the structure (e.g., Semester V offers Program Elective-I and MDM-II; Semester VI offers Program Elective-II and MDM-III; Semester VII offers Program Elective-III, Program Elective-IV and MDM-IV).
   - Then display the specific elective/minor course options under each domain/technology bucket (e.g., General, Smart Systems, Network and Security, Artificial Intelligence, Data Science).
   - Only list the electives and minors that belong to the requested semester. Never list electives or minors from other semesters.
   - List the actual subject names and course codes (e.g., 'CEPEC7011: High Performance Computing'), not placeholders like 'CEPEC701X'.
8. CRITICAL: Do NOT mention source documents, file names, citations, or page numbers inside your response text (e.g., do NOT write "Referred from...", "Source:", or cite PDF pages). The UI already displays clickable sources separately. Start your answer immediately with the requested information.
9. Lab Experiments: If the user asks for lab experiments, you MUST carefully scan the entire text and extract EVERY SINGLE numbered experiment (there are often 10 to 15+ experiments). DO NOT stop early or skip any. FORMATTING: If the user explicitly asks for an "experiments list", provide ONLY the title or a very short 1-sentence summary of each experiment to save space. If the user just asks for "experiments" (without the word 'list'), provide the full description for each experiment.
10. HINTS: If the provided context text explicitly contains a ">>> CRITICAL HINT:" block at the very top, you MUST incorporate its contents into your answer. Do NOT invent or generate your own hints.
  11. Tabular Data: Only format semester program structures (the core subject list with teaching schemes/credits) or credit distribution summaries as Markdown tables. Do NOT use tables for listing elective options (use clean bullet points as per Rule 7).{module_requirement}
  12. Specific Module Requests: If the user asks for the contents or subtopics of a specific module (e.g. 'finite automata'), provide ONLY the units/subtopics for that exact module as a clean list or table. Do NOT output raw syllabus text, and do NOT include other unrelated modules.
  13. OUTPUT FORMAT: Do NOT regurgitate or copy the SOURCE CONTEXT back to the user. Start your answer immediately with the requested information.

SOURCE CONTEXT:
======================
{context}
======================

USER QUESTION:
{question}

ANSWER:
"""

    client = OpenAI(
        base_url=os.environ.get("LLM_BASE_URL", "https://llama.atharva-amrutkar.in/v1"),
        api_key=os.environ.get("LLM_API_KEY", "V7mQ2xL9pR4kT8nC")
    )
    system_instruction = (
        "You are SIES GPT, an AI assistant for SIES Graduate School of Technology. "
        "Answer directly, factually, and concisely based strictly on the provided context. "
        "Do not use internal reasoning or thinking steps. Do not include URLs or source citations in your answer body."
    )
    llm_messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt},
    ]
    if yield_callback:
        response = client.chat.completions.create(
            model="llama3.2:3b",
            messages=llm_messages,
            temperature=0.0,
            max_tokens=1000,
            stream=True,
            extra_body={"options": {"num_ctx": 8192}}
        )
        answer_chunks = []
        try:
            for chunk in response:
                if cancel_event and cancel_event.is_set():
                    try:
                        response.close()
                    except Exception:
                        pass
                    return ""
                if chunk.choices and chunk.choices[0].delta:
                    text = chunk.choices[0].delta.content
                    if text:
                        answer_chunks.append(text)
                        yield_callback({"type": "token", "text": text})
        finally:
            try:
                response.close()
            except Exception:
                pass
        answer = "".join(answer_chunks)
    else:
        response = client.chat.completions.create(
            model="llama3.2:3b",
            messages=llm_messages,
            temperature=0.0,
            max_tokens=1000,
            extra_body={"options": {"num_ctx": 8192}}
        )
        answer = response.choices[0].message.content or ""

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
            if yield_callback is None:
                return early_return("\n\n".join(item["text"] for item in retrieved_chunks))

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
            if yield_callback is None:
                return early_return("\n\n".join(item["text"] for item in retrieved_chunks))

    return answer






