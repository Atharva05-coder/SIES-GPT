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

        if is_minor_query and "Multidisciplinary Minor" in clean_text:
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
                return "\n".join(res)

        if is_elective_query:
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
                    return intro + "\n\n".join(results)

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

    if elective_text:
        elective_part = extract_semester_electives(query, [{"text": elective_text}])
        if elective_part:
            table_md += "\n\n" + elective_part

    return table_md


def extract_textbooks_and_references(query: str, retrieved_chunks) -> str | None:
    if not re.search(r"\b(textbooks?|reference books?|references?|recommended books?)\b", query, re.IGNORECASE):
        return None
    if re.search(r"\b(experiments?|labs?|practicals?|modules?|scheme)\b", query, re.IGNORECASE):
        return None

    for item in retrieved_chunks:
        text = item.get("text", "")
        m = re.search(r"(?im)((?:Textbooks|Reference books|Online References):.*?)(?:Course Assessment|End Semester Examination|Syllabus Scheme|Internal Assessment|\Z)", text, re.DOTALL)
        if m:
            block = m.group(1).strip()
            cleaned = re.sub(r"(?im)^(Textbooks|Reference books|Online References):", r"### \1\n", block)
            cleaned = re.sub(r"(?im)\n+(?:Assessment|Scheme|CIAP|ESEP):.*$", "", cleaned)
            return cleaned.strip()

    return None


def generate_answer(question: str, retrieved_chunks, original_question: str = None, yield_callback=None):

    def early_return(ret_text):
        if yield_callback:
            tokens = re.findall(r"\S+|\n|\s+", ret_text)
            for tok in tokens:
                yield_callback({"type": "token", "text": tok})
        return ret_text

    check_query = original_question if original_question else question

    # Fast deterministic extractors (0.005s execution)
    fast_electives = extract_semester_electives(check_query, retrieved_chunks)
    if fast_electives:
        if yield_callback:
            tokens = re.findall(r"\S+|\n|\s+", fast_electives)
            for tok in tokens:
                yield_callback({"type": "token", "text": tok})
        return fast_electives

    fast_structure = extract_semester_program_structure(check_query, retrieved_chunks)
    if fast_structure:
        if yield_callback:
            tokens = re.findall(r"\S+|\n|\s+", fast_structure)
            for tok in tokens:
                yield_callback({"type": "token", "text": tok})
        return fast_structure

    fast_books = extract_textbooks_and_references(check_query, retrieved_chunks)
    if fast_books:
        if yield_callback:
            tokens = re.findall(r"\S+|\n|\s+", fast_books)
            for tok in tokens:
                yield_callback({"type": "token", "text": tok})
        return fast_books

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
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta:
                text = chunk.choices[0].delta.content
                if text:
                    answer_chunks.append(text)
                    yield_callback({"type": "token", "text": text})
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






