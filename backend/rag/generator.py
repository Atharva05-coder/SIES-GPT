import re

from openai import OpenAI

import os

PROGRAM_ELECTIVES = {
    1: {
        'sem': 'Semester V',
        'title': 'Program Elective - I (CEPEC501X)',
        'credits': 3,
        'options': [
            ('CEPEC5011', 'Advanced Database Management System', 'General'),
            ('CEPEC5012', 'Internet of Things', 'Smart Systems'),
            ('CEPEC5013', 'Ethical Hacking', 'Network and Security'),
            ('CEPEC5014', 'Data Warehouse and Mining', 'Artificial Intelligence')
        ],
        'lab': 'CEPEL501X: Program Elective-I Lab (1 Credit)'
    },
    2: {
        'sem': 'Semester VI',
        'title': 'Program Elective - II (CEPEC601X)',
        'credits': 3,
        'options': [
            ('CEPEC6011', 'Machine Vision', 'General'),
            ('CEPEC6012', 'Robotics and Applications', 'Smart Systems'),
            ('CEPEC6013', 'Digital Forensics', 'Network and Security'),
            ('CEPEC6014', 'Natural Language Processing', 'Artificial Intelligence')
        ],
        'lab': 'CEPEL601X: Program Elective-II Lab (1 Credit)'
    },
    3: {
        'sem': 'Semester VII',
        'title': 'Program Elective - III (CEPEC701X)',
        'credits': 3,
        'options': [
            ('CEPEC7011', 'High Performance Computing', 'General'),
            ('CEPEC7012', 'Fog and Edge Computing', 'Smart Systems'),
            ('CEPEC7013', 'Blockchain Technology', 'Network and Security'),
            ('CEPEC7014', 'Deep Learning', 'Artificial Intelligence')
        ],
        'lab': 'CEPEL701X: Program Elective-III Lab (1 Credit)'
    },
    4: {
        'sem': 'Semester VII',
        'title': 'Program Elective - IV (CEPEC702X)',
        'credits': 3,
        'options': [
            ('CEPEC7021', 'Augmented Reality and Virtual Reality', 'Data Science'),
            ('CEPEC7022', 'Quantum Computing', 'Smart Systems'),
            ('CEPEC7023', 'Intelligent Forensic', 'Network and Security'),
            ('CEPEC7024', 'Reinforcement Learning', 'Artificial Intelligence')
        ],
        'lab': None
    }
}

OPEN_ELECTIVES = {
    1: {
        'sem': 'Semester VII',
        'title': 'Open Elective - I (OEC701X)',
        'credits': 3,
        'options': [
            ('OEC7011', 'Project Management'),
            ('OEC7012', 'Finance Management'),
            ('OEC7013', 'Management Information System'),
            ('OEC7014', 'Entrepreneurship Development and Management'),
            ('OEC7015', 'Operation Research'),
            ('OEC7016', 'Disaster Management and Mitigation Measures'),
            ('OEC7017', 'Product Design')
        ]
    }
}

MDM_TRACKS = [
    ('Machine Learning', 'MDMC4011: Artificial Intelligence', 'MDMC5012: Machine Learning (+ Lab MDML5011)', 'MDMC6013: NLP (+ Lab MDML6012)', 'MDMC7014: Deep Learning (+ Lab MDML7013)'),
    ('Data Science', 'MDMC4021: Statistical Foundation', 'MDMC5022: Data Analytics & Viz (+ Lab MDML5021)', 'MDMC6023: BI (+ Lab MDML6022)', 'MDMC7024: Big Data Analytics (+ Lab MDML7023)'),
    ('Embedded Systems', 'MDMC4031: Microprocessors', 'MDMC5032: Embedded Systems & RTOS (+ Lab MDML5031)', 'MDMC6033: Sensor Tech (+ Lab MDML6032)', 'MDMC7034: IIoT (+ Lab MDML7033)'),
    ('Cyber Security', 'MDMC4041: Computer Networks', 'MDMC5042: Cryptography & Net Sec (+ Lab MDML5041)', 'MDMC6043: Cloud Security (+ Lab MDML6042)', 'MDMC7044: Digital Forensics (+ Lab MDML7043)'),
    ('System Programming', 'MDMC4051: Adv Data Structure', 'MDMC5052: Adv Algorithm (+ Lab MDML5051)', 'MDMC6053: SPCC (+ Lab MDML6052)', 'MDMC7054: Distributed Systems (+ Lab MDML7053)'),
    ('Management', 'MDMC4061: Cost Management', 'MDMC5062: Supply Chain Management', 'MDMC6063: Organization Behaviour & HRM', 'MDMC7064: Marketing Management')
]

PROJECTS = {
    'CEM301': ('Mini Project 1A', 'Semester III', 1, '2# (Practical)', 'CIAP: 25, ESEP: 25 | Total: 50', 'CEP', 'Students undertake a design/development project in small groups (3-4 students) applying foundational engineering skills.'),
    'CEM401': ('Mini Project 1B', 'Semester IV', 1, '2# (Practical)', 'CIAP: 25, ESEP: 25 | Total: 50', 'CEP', 'Continuation of mini project track focusing on application development and implementation using modern tools/frameworks.'),
    'CEM501': ('Mini Project 2', 'Semester V', 1, '2# (Practical)', 'CIAP: 25, ESEP: 25 | Total: 50', 'CEP', 'Domain-specific mini project solving real-world computing, networking, or intelligent system problems.'),
    'CEP601': ('Major Project I', 'Semester VI', 2, '4# (Practical)', 'CIAP: 25, ESEP: 25 | Total: 50', 'MJP', 'Phase 1 of Final Year Capstone Project: Literature survey, problem formulation, system design, and architecture defense.'),
    'CEP701': ('Major Project II', 'Semester VII', 4, '8# (Practical)', 'CIAP: 50, ESEP: 50 | Total: 100', 'MJP', 'Phase 2 of Final Year Capstone Project: Implementation, integration, performance evaluation, and paper publication.'),
    'CEP801': ('Major Project III', 'Semester VIII', 6, '12# (Practical)', 'CIAP: 50, ESEP: 50 | Total: 100', 'MJP', 'Final Capstone Project phase / Industry Internship project with comprehensive evaluation, testing, and deployment.')
}

def extract_total_program_credits(query: str, retrieved_chunks=None) -> str | None:
    has_credits = bool(re.search(r"\b(credits?|how\s+many\s+credits?|total\s+credits?|credit\s+distribution|allocated\s+credits?|assigned\s+credits?)\b", query, re.I))
    if not has_credits:
        return None

    is_overall = bool(
        re.search(r"\b(overall|in\s+total|total|all\s+together|altogether|8\s*sem(?:esters?)?|eight\s*sem(?:esters?)?|all\s*(?:8\s*)?sem(?:esters?)?|4\s*years?|four\s*years?|entire|complete|whole)\b", query, re.I)
        or re.search(r"\b(computer\s+engineering|b\.?tech|b\.?e|degree|program|curriculum|ug\s+engineering)\b", query, re.I)
    )
    if not is_overall:
        return None

    # If query mentions a specific course code or specific individual course (e.g. CN, TCS, FEC101, etc.)
    # let individual course handler handle it
    codes = resolve_all_course_codes_from_query(query)
    if codes:
        return None

    # If query asks about a single specific semester without 'all/8/overall/total', let semester structure handle it
    m_single_sem = re.search(r"\b(?:sem(?:ester)?\s*([1-8]|I{1,3}|IV|V|VI|VII|VIII))\b", query, re.I)
    if m_single_sem and not re.search(r"\b(all|8|eight|total|overall|together)\b", query, re.I):
        return None

    return (
        "### B.Tech Computer Engineering - Total Program Credits & Semester-wise Distribution\n\n"
        "According to the official autonomous curriculum structure (Page 3), the total number of credits required for the **Four-Year B.Tech in Computer Engineering** is **168 Credits** across all 8 semesters.\n\n"
        "#### Semester-wise Credit Breakdown:\n"
        "| Semester | Credits Assigned |\n"
        "|:---:|:---:|\n"
        "| **Semester I** | 21 |\n"
        "| **Semester II** | 21 |\n"
        "| **Semester III** | 22 |\n"
        "| **Semester IV** | 21 |\n"
        "| **Semester V** | 22 |\n"
        "| **Semester VI** | 22 |\n"
        "| **Semester VII** | 20 |\n"
        "| **Semester VIII** | 19 |\n"
        "| **Total Credits (Major)** | **168** |\n\n"
        "---\n\n"
        "#### Category-wise Credit Distribution:\n"
        "| Course Category | Sem I | Sem II | Sem III | Sem IV | Sem V | Sem VI | Sem VII | Sem VIII | Total Credits |\n"
        "|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n"
        "| **Basic Science Course (BSC) / ESC** | 7 | 6 | -- | -- | -- | -- | -- | -- | **13** |\n"
        "| **Engineering Science Course (ESC)** | 9 | 10 | -- | -- | -- | -- | -- | -- | **19** |\n"
        "| **Program Core Course (PCC)** | -- | -- | 17 | 11 | 11 | 10 | 04 | -- | **53** |\n"
        "| **Program Elective Course (PEC)** | -- | -- | -- | -- | 04 | 04 | 07 | -- | **15** |\n"
        "| **Multidisciplinary Minor (MDM)** | -- | 03 | 04 | 04 | 04 | -- | -- | -- | **15** |\n"
        "| **Open Elective (OE)** | -- | -- | -- | -- | -- | -- | 03 | 03 | **06** |\n"
        "| **Vocational & Skill Enhancement (VSEC)** | 01 | 01 | 02 | 02 | -- | 02 | -- | -- | **08** |\n"
        "| **Ability Enhancement Course (HSSM / AEC)** | 02 | -- | -- | 02 | -- | -- | -- | -- | **04** |\n"
        "| **Entrepreneurship / Economics / Management** | -- | 02 | 02 | -- | -- | -- | -- | -- | **04** |\n"
        "| **Indian Knowledge System (IKS)** | 02 | -- | -- | -- | -- | -- | -- | -- | **02** |\n"
        "| **Value Education Course (VEC)** | -- | -- | -- | 02 | -- | -- | -- | -- | **02** |\n"
        "| **Research Methodology (RM)** | -- | -- | -- | -- | -- | -- | -- | 03 | **03** |\n"
        "| **Community Engagement / Field Project (FP)** | -- | -- | 01 | 01 | -- | -- | -- | -- | **02** |\n"
        "| **Major / Mini Project (MJP)** | -- | -- | -- | -- | 01 | 02 | 02 | 01 | **06** |\n"
        "| **Internship / On Job Training (OJT)** | -- | -- | -- | -- | -- | -- | 12 | -- | **12** |\n"
        "| **Co-curricular Courses (CC)** | 04 | -- | -- | -- | -- | -- | -- | -- | **04** |\n"
        "| **Total Credits (Major)** | **21** | **21** | **22** | **21** | **22** | **22** | **20** | **19** | **168** |"
    )

def extract_course_nomenclature(query: str, retrieved_chunks=None) -> str | None:
    if not re.search(r"\b(nomenclature|course\s+nomenclature|abbreviations?\s+in\s+(?:the\s+)?curriculum|curriculum\s+abbreviations?)\b", query, re.I):
        return None
    return (
        "### Nomenclature of Courses in the Curriculum\n\n"
        "| Abbreviation | Title / Category |\n"
        "|:---:|---|\n"
        "| **BSC** | Basic Science Courses |\n"
        "| **ESC** | Engineering Science Courses |\n"
        "| **PCC** | Program Core Courses |\n"
        "| **PEC** | Program Elective Course |\n"
        "| **MDM** | Multidisciplinary Minor |\n"
        "| **OE** | Open Elective |\n"
        "| **VSEC** | Vocational and Skill Enhancement Course |\n"
        "| **AEC** | Ability Enhancement Course |\n"
        "| **IKS** | Indian Knowledge System |\n"
        "| **VEC** | Value Education Course |\n"
        "| **RM** | Research Methodology |\n"
        "| **CEP/FP** | Community Engagement Project / Field Project |\n"
        "| **OJT** | Internship / On Job Training |\n"
        "| **CC** | Cocurricular Courses |\n"
        "| **ISE** | In Semester Examination |\n"
        "| **MSE** | Mid Semester Examination |\n"
        "| **ESE** | End Semester Examination |\n"
        "| **CIAP** | Continuous Internal Assessment Practical |\n"
        "| **ESEP** | End Semester Examination Practical |"
    )

def extract_special_academic_queries(query: str, retrieved_chunks=None) -> str | None:
    q = query.strip()
    # Total program credits / credit distribution
    res_credits = extract_total_program_credits(q, retrieved_chunks)
    if res_credits:
        return res_credits

    # 0. Nomenclature of courses in curriculum
    if re.search(r'\b(nomenclature|course\s+nomenclature|abbreviations?\s+in\s+(?:the\s+)?curriculum|curriculum\s+abbreviations?)\b', q, re.I):
        return extract_course_nomenclature(q, retrieved_chunks)

    # If query asks for structure along with electives or minors, let the combined handler at generate_answer handle it
    if re.search(r'\b(program\s+structure|curriculum\s+structure|course\s+structure|teaching\s+scheme)\b', q, re.I) and re.search(r'\b(electives?|minors?|mdms?)\b', q, re.I):
        return None
    
    # 1. Program Electives (e.g. Program Elective-I, PE 1, PE-2)
    m_pe = re.search(r'\b(?:program\s+elective|pe)\s*[-_ ]?\s*([1-4]|I{1,3}|IV)\b', q, re.I)
    if m_pe:
        rom = {'I': 1, 'II': 2, 'III': 3, 'IV': 4}
        v = m_pe.group(1).upper()
        pe_num = rom.get(v, int(v) if v.isdigit() else None)
        if pe_num in PROGRAM_ELECTIVES:
            pe = PROGRAM_ELECTIVES[pe_num]
            out = [f"### {pe['title']} ({pe['sem']})\n"]
            out.append('| Course Code | Course Name | Technology Bucket | Credits |')
            out.append('|---|---|:---:|:---:|')
            for code, name, bucket in pe['options']:
                out.append(f"| {code} | {name} | {bucket} | {pe['credits']} |")
            if pe['lab']:
                out.append(f"\n**Associated Practical Lab:** {pe['lab']}")
            return '\n'.join(out)

    # 2. Open Electives
    if re.search(r'\b(?:open\s+electives?|oe)\b', q, re.I):
        oe = OPEN_ELECTIVES[1]
        out = [f"### {oe['title']} ({oe['sem']})\n"]
        out.append('| Course Code | Course Name | Credits |')
        out.append('|---|---|:---:|')
        for code, name in oe['options']:
            out.append(f"| {code} | {name} | {oe['credits']} |")
        return '\n'.join(out)

    # 3. MDM / Multidisciplinary Minor Tracks
    if re.search(r'\b(multidisciplinary\s+minors?|mdm\s+tracks?|all\s+minors?|minor\s+tracks?|minors?\s+offered|mdm\s+options?)\b', q, re.I) or (re.search(r'\b(minors?|mdms?)\b', q, re.I) and not re.search(r'\b(?:sem(?:ester)?|term)\b', q, re.I)):
        out = ["### Multidisciplinary Minor (MDM) Tracks (Semester IV – VII)\n"]
        out.append('| Minor Track | Semester IV (SE) | Semester V (TE) | Semester VI (TE) | Semester VII (BE) |')
        out.append('|---|---|---|---|---|')
        for track, s4, s5, s6, s7 in MDM_TRACKS:
            out.append(f"| **{track}** | {s4} | {s5} | {s6} | {s7} |")
        return '\n'.join(out)

    # 4. Semester MDM / Electives Options (e.g. MDM in sem 5, electives of sem 6)
    m_sem = re.search(r'\b(?:sem(?:ester)?|term)\s*([1-8]|I|II|III|IV|V|VI|VII|VIII)\b', q, re.I)
    if m_sem:
        val = m_sem.group(1).upper()
        rom = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8}
        snum = rom.get(val, int(val) if val.isdigit() else None)
        
        # MDM in semester X
        if re.search(r'\b(minors?|mdms?|multidisciplinary)\b', q, re.I):
            idx_map = {4: 1, 5: 2, 6: 3, 7: 4}
            if snum in idx_map:
                col_idx = idx_map[snum]
                out = [f"### Semester {val} Multidisciplinary Minor (MDM) Options\n"]
                out.append('| Track | Course / Lab Code & Name | Category | Credits |')
                out.append('|---|---|:---:|:---:|')
                for t in MDM_TRACKS:
                    out.append(f"| {t[0]} | {t[col_idx]} | MDM | 3 (Theory) / 1 (Lab) |")
                return '\n'.join(out)

        # Electives in semester X
        if re.search(r'\b(electives?|elective options?|pecs?)\b', q, re.I):
            if snum == 5:
                return extract_special_academic_queries('Program Elective-I')
            elif snum == 6:
                return extract_special_academic_queries('Program Elective-II')
            elif snum == 7:
                pe3 = extract_special_academic_queries('Program Elective-III')
                pe4 = extract_special_academic_queries('Program Elective-IV')
                oe1 = extract_special_academic_queries('Open Electives')
                return f"{pe3}\n\n---\n\n{pe4}\n\n---\n\n{oe1}"

    # 5. Projects (Mini Project & Major Project)
    m_proj = re.search(r'\b(mini\s*project\s*(?:1a|1b|2|1|i|ii)?|major\s*project\s*(?:1|2|3|i|ii|iii)?|capstone\s*project|CEM301|CEM401|CEM501|CEP601|CEP701|CEP801)\b', q, re.I)
    if m_proj:
        target_code = None
        qp = q.upper()
        if '1A' in qp or 'CEM301' in qp: target_code = 'CEM301'
        elif '1B' in qp or 'CEM401' in qp: target_code = 'CEM401'
        elif 'MINI PROJECT 2' in qp or 'CEM501' in qp: target_code = 'CEM501'
        elif 'MAJOR PROJECT 1' in qp or 'MAJOR PROJECT I' in qp or 'CEP601' in qp: target_code = 'CEP601'
        elif 'MAJOR PROJECT 2' in qp or 'MAJOR PROJECT II' in qp or 'CEP701' in qp: target_code = 'CEP701'
        elif 'MAJOR PROJECT 3' in qp or 'MAJOR PROJECT III' in qp or 'CEP801' in qp: target_code = 'CEP801'
        
        if target_code and target_code in PROJECTS:
            p = PROJECTS[target_code]
            out = [f"### {target_code}: {p[0]} ({p[1]})\n"]
            out.append(f"- **Course Category:** {p[5]}")
            out.append(f"- **Teaching Scheme:** {p[3]}")
            out.append(f"- **Credits Assigned:** {p[2]}")
            out.append(f"- **Examination Scheme:** {p[4]}")
            out.append(f"- **Course Overview & Scope:** {p[6]}")
            return '\n'.join(out)
        elif re.search(r'\bmini\s*projects?\b', q, re.I):
            out = ["### Overview of Mini Projects (Computer Engineering Curriculum)\n"]
            out.append('| Course Code | Project Title | Semester | Credits | Teaching Scheme | Evaluation |')
            out.append('|---|---|:---:|:---:|---|---|')
            for c in ['CEM301', 'CEM401', 'CEM501']:
                p = PROJECTS[c]
                out.append(f"| {c} | {p[0]} | {p[1]} | {p[2]} | {p[3]} | {p[4]} |")
            return '\n'.join(out)
        elif re.search(r'\bmajor\s*projects?\b', q, re.I):
            out = ["### Overview of Major Projects (Final Year Capstone Project)\n"]
            out.append('| Course Code | Project Title | Semester | Credits | Teaching Scheme | Evaluation |')
            out.append('|---|---|:---:|:---:|---|---|')
            for c in ['CEP601', 'CEP701', 'CEP801']:
                p = PROJECTS[c]
                out.append(f"| {c} | {p[0]} | {p[1]} | {p[2]} | {p[3]} | {p[4]} |")
            return '\n'.join(out)

    # 6. HWM (Health, Wellness and Mindfulness)
    if re.search(r'\b(hwm|health\s*,?\s*wellness|mindfulness|FEL106)\b', q, re.I):
        sections = get_sections_dict()
        if 'FEL106' in sections:
            if re.search(r'\b(modules?|units?)\b', q, re.I) and not re.search(r'\b(full|complete|overall)\b', q, re.I):
                return extract_course_all_modules_only('FEL106 modules', retrieved_chunks)
            return build_course_full_markdown('FEL106', sections['FEL106'], sections)

    # 7. UHV (Universal Human Values) and Induction
    if re.search(r'\b(uhv|universal\s+human\s+values?|induction\s+cum|induction\s+program|value\s+education|FEL107|CEL404)\b', q, re.I):
        sections = get_sections_dict()
        wants_sem1 = bool(re.search(r'\b(sem\s*1|sem(?:ester)?\s*i\b|first\s*year|fe|induction|FEL107)\b', q, re.I))
        wants_sem4 = bool(re.search(r'\b(sem\s*4|sem(?:ester)?\s*iv\b|second\s*year|se|value\s*education|vec|CEL404)\b', q, re.I))
        wants_modules = bool(re.search(r'\b(modules?|units?)\b', q, re.I) and not re.search(r'\b(full|complete|overall)\b', q, re.I))

        if wants_sem1 and not wants_sem4:
            if 'FEL107' in sections:
                if wants_modules:
                    return extract_course_all_modules_only('FEL107 modules', retrieved_chunks)
                return build_course_full_markdown('FEL107', sections['FEL107'], sections)
        elif wants_sem4 and not wants_sem1:
            if 'CEL404' in sections:
                if wants_modules:
                    return extract_course_all_modules_only('CEL404 modules', retrieved_chunks)
                return build_course_full_markdown('CEL404', sections['CEL404'], sections)
        else:
            out = ["### Universal Human Values (UHV) in Computer Engineering Curriculum\n"]
            out.append("In the Autonomous curriculum, Universal Human Values is offered across two stages:\n")
            out.append("1. **Semester I (FE):** FEL107 – Induction cum Universal Human Values")
            out.append("2. **Semester IV (SE):** CEL404 – Value Education Course (UHV)\n")
            if wants_modules:
                m1 = extract_course_all_modules_only('FEL107 modules', retrieved_chunks) or ""
                m4 = extract_course_all_modules_only('CEL404 modules', retrieved_chunks) or ""
                out.append(f"#### 1. Semester I: FEL107 – Induction cum Universal Human Values\n\n{m1}\n\n---\n\n#### 2. Semester IV: CEL404 – Value Education Course (UHV)\n\n{m4}")
            else:
                c1 = build_course_full_markdown('FEL107', sections['FEL107'], sections) if 'FEL107' in sections else ""
                c4 = build_course_full_markdown('CEL404', sections['CEL404'], sections) if 'CEL404' in sections else ""
                out.append(f"#### 1. Semester I: FEL107 – Induction cum Universal Human Values\n\n{c1}\n\n---\n\n#### 2. Semester IV: CEL404 – Value Education Course (UHV)\n\n{c4}")
            return '\n'.join(out)

    return None

def extract_semester_electives(query: str, retrieved_chunks=None) -> str | None:
    cleaned = re.sub(r"\b(program\s+structure|curriculum\s+structure|course\s+structure|subject\s+structure|teaching\s+scheme|structure)\b", "", query, flags=re.I)
    return extract_special_academic_queries(cleaned, retrieved_chunks)

_sem_struct_cache = None

def get_sem_struct_pages():
    global _sem_struct_cache
    if _sem_struct_cache is None:
        import json
        from pathlib import Path
        data_dir = Path(__file__).resolve().parents[1] / "data"
        _sem_struct_cache = {}
        fy_path = data_dir / "fy_sy_ce_270426_structured.json"
        if fy_path.exists():
            with open(fy_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                pages = d.get("pages", [])
                if len(pages) > 9:
                    _sem_struct_cache["I"] = pages[5].get("text", "")
                    _sem_struct_cache["1"] = pages[5].get("text", "")
                    _sem_struct_cache["II"] = pages[6].get("text", "")
                    _sem_struct_cache["2"] = pages[6].get("text", "")
                    _sem_struct_cache["III"] = pages[7].get("text", "")
                    _sem_struct_cache["3"] = pages[7].get("text", "")
                    _sem_struct_cache["IV"] = pages[8].get("text", "")
                    _sem_struct_cache["4"] = pages[8].get("text", "")
        te_path = data_dir / "te_ce_r24_1_structured.json"
        if te_path.exists():
            with open(te_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                pages = d.get("pages", [])
                if len(pages) > 17:
                    _sem_struct_cache["V"] = pages[10].get("text", "")
                    _sem_struct_cache["5"] = pages[10].get("text", "")
                    _sem_struct_cache["VI"] = pages[12].get("text", "")
                    _sem_struct_cache["6"] = pages[12].get("text", "")
                    _sem_struct_cache["VII"] = pages[14].get("text", "")
                    _sem_struct_cache["7"] = pages[14].get("text", "")
                    _sem_struct_cache["VIII"] = pages[16].get("text", "")
                    _sem_struct_cache["8"] = pages[16].get("text", "")
    return _sem_struct_cache

def extract_semester_program_structure(query: str, retrieved_chunks) -> str | None:

    from rag.query_rewriter import reframe_query

    norm_q = reframe_query(query)

    sem_map = {

        "1": "I", "1st": "I", "i": "I", "first": "I",

        "2": "II", "2nd": "II", "ii": "II", "second": "II",

        "3": "III", "3rd": "III", "iii": "III", "third": "III",

        "4": "IV", "4th": "IV", "iv": "IV", "fourth": "IV",

        "5": "V", "5th": "V", "v": "V", "fifth": "V",

        "6": "VI", "6th": "VI", "vi": "VI", "sixth": "VI",

        "7": "VII", "7th": "VII", "vii": "VII", "seventh": "VII",

        "8": "VIII", "8th": "VIII", "viii": "VIII", "eighth": "VIII",

    }

    m_sem = re.search(r"\b(?:semester|sem|term)\s*([1-8](?:st|nd|rd|th)?|[ivx]+)\b", norm_q, re.I)

    if not m_sem:

        m_sem = re.search(r"\b([1-8](?:st|nd|rd|th)?|[ivx]+)\s*(?:semester|sem|term)\b", norm_q, re.I)

    target_sem = sem_map.get(m_sem.group(1).lower()) if m_sem else None

    # Check if this is a program structure or semester syllabus query

    is_struct_query = bool(

        re.search(r"\b(program structure|curriculum structure|teaching scheme|course structure|subject structure)\b", norm_q, re.I)

        or (target_sem and re.search(r"\b(syllabus|curriculum|structure|subjects?|courses?|teaching scheme|credits?)\b", norm_q, re.I))

    )

    if not is_struct_query:

        return None

    # If query mentions a specific course and does NOT say 'all subjects/courses/structure', let course handler handle it

    target_code = resolve_course_code_from_query(norm_q, retrieved_chunks)

    if target_code and not re.search(r"\b(program structure|curriculum structure|course structure|all subjects|all courses|teaching scheme)\b", norm_q, re.I):

        return None

    if re.search(r"\b(experiments?|labs?|practicals?|modules?|textbooks?|reference books?)\b", norm_q, re.I) and not re.search(r"\b(structure|syllabus)\b", norm_q, re.I):

        return None

    # Find raw page text for requested semester

    structure_text = None

    if target_sem:

        pages_dict = get_sem_struct_pages()

        if target_sem in pages_dict:

            structure_text = pages_dict[target_sem]

    if not structure_text:

        for item in retrieved_chunks:

            text = item.get("text", "")

            if "Program Structure for" in text or re.search(r"(?i)Teaching Scheme.*Credits Assigned", text):

                if target_sem and f"Semester {target_sem}" in text:

                    structure_text = text

                    break

                elif not structure_text:

                    structure_text = text

    if not structure_text:

        return None

    norm_text = re.sub(r"/\s*\n\s*", "/", structure_text)

    # Determine semester header

    sem_header = target_sem

    if not sem_header:

        m_hdr = re.search(r"(?i)Semester\s+([IVX]+|\d+)", norm_text)

        sem_header = m_hdr.group(1).upper() if m_hdr else "Current"

    sec_match = re.search(rf"(?i)Semester\s+{sem_header}\s+(.*?)(?:Examination Scheme|\Z)", norm_text, re.DOTALL)

    if not sec_match:

        sec_match = re.search(r"(?i)Semester\s+([IVX]+|\d+)\s+(.*?)(?:Examination Scheme|\Z)", norm_text, re.DOTALL)

        if not sec_match:

            return None

        sem_header = sec_match.group(1).upper()

    block = sec_match.group(2) if sec_match.lastindex >= 2 else sec_match.group(1)

    lines = [l.strip() for l in block.split("\n") if l.strip()]

    code_pattern = re.compile(r"^((?:FEC|FEL|CEC|CEL|CEPEC|CEPEL|MDMC|MDML|OEC|CEP|CEM)\d+[A-Z0-9/]*)\b")

    table_rows = []

    current_code = None

    current_rest = ""

    total_credits = None

    for line in lines:

        if re.search(r"(?i)Course\s*Code|Teaching Scheme|Credits Assigned|Theory Pract|Contact Hours", line):

            continue

        if line.startswith("Total") or " Total " in line:

            m_tot = re.search(r"(\d+[\*\+\#\&\$]*)$", line.strip())

            if m_tot:

                total_credits = m_tot.group(1).strip()

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

    out = [f"### Semester {sem_header} Program Structure\n"]

    out.append("| Course Code | Course Name | Category | Teaching Scheme (Contact Hours) | Credits Assigned |")

    out.append("|---|---|:---:|---|:---:|")

    calc_total = 0.0

    for code, rest in table_rows:

        rest = re.sub(r"\s+", " ", rest).strip()

        # Support decimals like 2.5 or 0.5 in scheme numbers

        nums_match = re.search(r"((?:(?:\d+(?:\.\d+)?[\*\+\#\&\$]*|--|-)\s*){3,})$", rest)

        if nums_match:

            scheme_raw = nums_match.group(1).strip()

            before_nums = rest[:nums_match.start()].strip()

            cat_match = re.search(r"\b(PCC|BSC|ESC|MDM|PEC|VSEC|AEC|HSSM|MJP|OE|PW|CEP|VEC|CC)(?:\s*\([A-Z0-9-]+\))?$", before_nums)

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

                scheme = "Theory/Pract: " + " ".join(nums[:-1])

                credits = nums[-1]

            else:

                scheme = scheme_raw

                credits = nums[-1] if nums else "--"

        else:

            name = rest

            cat = "--"

            scheme = "--"

            credits = "--"

        name = re.sub(r"\s{2,}", " ", name).strip(" -:\n")

        clean_c = re.sub(r"[^\d.]", "", credits)

        try:

            calc_total += float(clean_c)

        except Exception:

            pass

        out.append(f"| {code} | {name} | {cat} | {scheme} | {credits} |")

    tot_str = total_credits if total_credits else (f"{int(calc_total)}" if calc_total.is_integer() else f"{calc_total}")

    out.append(f"\n**Total Credits Assigned:** {tot_str}")

    return "\n".join(out)

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

def extract_specific_course_modules(query: str, retrieved_chunks) -> str | None:

    if not retrieved_chunks:

        return None

    m_unit = re.search(r'\bunit\s*(\d+\.\d+)\b', query, re.I)

    sections = get_sections_dict()

    target_code = resolve_course_code_from_query(query, retrieved_chunks)

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

    if len(matched_modules) > 1:

        mod_str = ", ".join(f"Module {m['number']}" for m in matched_modules[:-1]) + f" and Module {matched_modules[-1]['number']}"

    else:

        mod_str = f"Module {matched_modules[0]['number']}"

    header = f"### {target_code}: {course_name} ({mod_str})\n\n"

    module_texts = [format_self_learning_text(m.get("text", "")) for m in matched_modules]

    return header + "\n\n---\n\n".join(module_texts)

def extract_course_module_count(query: str, retrieved_chunks=None) -> str | None:
    from rag.outline_formatter import extract_module_outlines
    is_counting = bool(
        re.search(r"\b(how\s+many|how\s+much|count|total\s+number|number\s+of)\b", query, re.I)
        and re.search(r"\bmodules?\b", query, re.I)
    )
    if not is_counting:
        return None

    if re.search(r"\b(experiments?|practicals?|credits?|marks?|hours?|teaching\s+scheme)\b", query, re.I) and not re.search(r"\bhow\s+many\s+modules\b", query, re.I):
        return None

    target_codes = resolve_all_course_codes_from_query(query, retrieved_chunks)
    if not target_codes:
        return None

    sections = get_sections_dict()
    blocks = []
    for target_code in target_codes:
        if target_code not in sections:
            continue
        sec = sections[target_code]
        cname = extract_course_name_from_header(sec["header"])
        outlines = extract_module_outlines(sec["pages"])
        if not outlines:
            continue
        total_mods = len(outlines)
        out = [f"According to the syllabus, there are {total_mods} modules in {cname} ({target_code}):\n"]
        for o in outlines:
            first_line = o["text"].split("\n")[0].replace("## ", "")
            out.append(f"- {first_line}")
        blocks.append("\n".join(out))

    if not blocks:
        return None
    return "\n\n==============================\n\n".join(blocks)

def extract_course_all_modules_only(query: str, retrieved_chunks) -> str | None:

    if not retrieved_chunks:

        return None

    if re.search(r"\b(how\s+many|how\s+much|count|total\s+number|number\s+of|full\s+syllabus|complete\s+syllabus|overall\s+syllabus|entire\s+syllabus|teaching\s+scheme|examination\s+scheme|exam\s+scheme|outcomes?|objectives?|credit\s+distribution|how\s+many\s+credits?)\b", query, re.I):

        return None

    if parse_requested_modules(query) or re.search(r"\bunit\s*\d+(\.\d+)?\b", query, re.I):

        return None

    wants_modules = bool(

        re.search(r"\b(?:only\s+modules?|just\s+modules?|modules?\s+and\s+self-?learning|course\s+modules?|give\s+modules?|what\s+are\s+the\s+modules?|list\s+of\s+modules?|show\s+modules?|modules?\s+of)\b", query, re.I)

        or re.search(r"\b(modules?|chapters?|topics?\s+covered|topics?\s+in|course\s+content|course\s+outline)\b", query, re.I)

    )

    if not wants_modules:

        return None

    sections = get_sections_dict()

    target_codes = resolve_all_course_codes_from_query(query, retrieved_chunks)

    if not target_codes:

        return None

    results = []
    seen_titles = set()
    for target_code in target_codes:
        if target_code not in sections:
            continue
        section = sections[target_code]
        course_name = extract_course_name_from_header(section["header"])
        clean_title = re.sub(r"\s+", " ", course_name).strip().lower()
        if clean_title in seen_titles:
            continue
        seen_titles.add(clean_title)
        outlines = section.get("module_outlines", [])
        if not outlines:
            continue
        header = f"### {target_code}: {course_name} - Course Modules\n\n"
        module_texts = [format_self_learning_text(m.get("text", "")) for m in outlines]
        results.append(header + "\n\n---\n\n".join(module_texts))

    if not results:

        return None

    return "\n\n==============================\n\n".join(results)

def extract_textbooks_and_references(query: str, retrieved_chunks) -> str | None:

    has_book_kw = bool(re.search(

        r"\b(textbooks?|text\s*books?|reference\s*books?|references?|recommended\s*books?|online\s*references?|online\s*resources?|books?|reading\s*materials?|recommended\s*reading|bibliography)\b",

        query,

        re.IGNORECASE,

    ))

    has_online_study_kw = bool(

        re.search(r"\b(where\s+(?:can\s+i|to)\s+study|study\s+online|learn\s+online|online\s+material|online\s+links?|online\s+sources?)\b", query, re.IGNORECASE)

        or (re.search(r"\bonline\b", query, re.IGNORECASE) and re.search(r"\b(study|learn|courses?|videos?|nptel|coursera|material|resources?|links?|references?|where)\b", query, re.IGNORECASE))

    )

    if not has_book_kw and not has_online_study_kw:

        return None

    if re.search(r"\b(experiments?|labs?|practicals?|modules?|scheme|outcomes?|objectives?)\b", query, re.IGNORECASE):

        return None

    is_only_online = bool(

        (has_online_study_kw or re.search(r"\bonline\b", query, re.IGNORECASE))

        and not re.search(r"\b(textbooks?|text\s*books?|reference\s*books?|books?|all\s+references|both)\b", query, re.IGNORECASE)

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

    sections = get_sections_dict()

    target_code = resolve_course_code_from_query(query, retrieved_chunks)

    candidate_pages = []

    if target_code and target_code in sections:

        candidate_pages = sections[target_code]["all_pages"]

    else:

        candidate_pages = retrieved_chunks

    course_prefix = ""

    if target_code and target_code in sections:

        cname = extract_course_name_from_header(sections[target_code]["header"])

        if is_only_online:

            course_prefix = f"### {target_code}: {cname} - Online References\n\n"

        elif is_only_textbooks:

            course_prefix = f"### {target_code}: {cname} - Textbooks\n\n"

        elif is_only_references:

            course_prefix = f"### {target_code}: {cname} - References\n\n"

        else:

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

                results.append(tb_text)

        elif is_only_online:

            if online_text:

                results.append(online_text)

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

            clean_res = "\n\n".join(results)

            clean_res = re.sub(r"[^\x00-\x7F]+", '"', clean_res)

            return course_prefix + clean_res

    return None

def extract_lab_experiments(query: str, retrieved_chunks, course_code: str | None = None, course_name: str | None = None) -> str | None:

    if not re.search(r"\b(experiments?|practicals?|tasks?|lab experiments?|exps?|exp\.?|pracs?|prac\.?)\b", query, re.IGNORECASE):

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

    if not course_code and retrieved_chunks:
        for item in retrieved_chunks:
            meta = item.get("metadata", {})
            if meta.get("course_code"):
                course_code = meta["course_code"]
                break
    if course_code and not course_name:
        sections = get_sections_dict()
        if course_code in sections:
            course_name = extract_course_name_from_header(sections[course_code]["header"])

    header_prefix = f"### {course_code}: {course_name}\n\n" if (course_code and course_name) else ""

    is_counting = bool(re.search(r"\b(how many|how much|count|total number|number of)\b", query, re.IGNORECASE))

    if is_counting:

        total_listed = len(all_experiments)

        if at_least_count:

            return f"{header_prefix}According to the syllabus, students are required to complete at least {at_least_count} experiments from the {total_listed} listed experiments for this lab."

        return f"{header_prefix}According to the syllabus, there are {total_listed} experiments listed for this lab."

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

    return header_prefix + intro + "\n\n".join(exp_blocks)

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

# Master dictionary mapping course acronyms to course codes for all FY/SY/TE theory and lab courses

ACRONYM_TO_COURSE_CODE = {

    # FE Sem 1

    "AM1": "FEC101", "AM-1": "FEC101", "M1": "FEC101", "MATHS1": "FEC101", "MATHS-1": "FEC101",

    "AP1": "FEC1021", "AP-1": "FEC1021", "AP": "FEC1021", "AP LAB": "FEL1011", "AP1 LAB": "FEL1011",

    "AC1": "FEC1022", "AC-1": "FEC1022", "AC": "FEC1022", "AC LAB": "FEL1012", "AC1 LAB": "FEL1012",

    "BEE": "FEC103", "BEEE": "FEC103", "BEE LAB": "FEL102", "BEEE LAB": "FEL102",

    "CP": "FEC104", "CP LAB": "FEL103",

    "AMRD": "FEC105", "AMRD LAB": "FEL104",

    "EW1": "FEL105", "EW 1": "FEL105", "EW-1": "FEL105", "EW-I": "FEL105", "EW I": "FEL105",
    "WORKSHOP 1": "FEL105", "WORKSHOP I": "FEL105", "WORKSHOP-1": "FEL105", "WORKSHOP-I": "FEL105",
    "ENGINEERING WORKSHOP 1": "FEL105", "ENGINEERING WORKSHOP I": "FEL105",
    "ENGINEERING WORKSHOP-1": "FEL105", "ENGINEERING WORKSHOP-I": "FEL105",
    "ENGINEERING WORKSHOP - 1": "FEL105", "ENGINEERING WORKSHOP - I": "FEL105",
    "ENGINEERING WORKSHOP -1": "FEL105", "ENGINEERING WORKSHOP -I": "FEL105",
    "ENGINEERING WORKSHOP": "FEL105", "HWM": "FEL106", "UHV1": "FEL107",

    # FE Sem 2

    "AM2": "FEC201", "AM-2": "FEC201", "M2": "FEC201", "MATHS2": "FEC201", "MATHS-2": "FEC201",

    "AP2": "FEC2021", "AP2 LAB": "FEL2011",

    "AC2": "FEC2022", "AC2 LAB": "FEL2012",

    "EG": "FEC203", "EG LAB": "FEL202",

    "DSD": "FEC204", "DSD LAB": "FEL203",

    "PCT": "FEC205", "PCT LAB": "FEL204",

    "OOPM": "FEL205", "OOPM LAB": "FEL205", "OOP LAB": "FEL205",

    "EW2": "FEL206", "EW 2": "FEL206", "EW-2": "FEL206", "EW-II": "FEL206", "EW II": "FEL206",
    "WORKSHOP 2": "FEL206", "WORKSHOP II": "FEL206", "WORKSHOP-2": "FEL206", "WORKSHOP-II": "FEL206",
    "ENGINEERING WORKSHOP 2": "FEL206", "ENGINEERING WORKSHOP II": "FEL206",
    "ENGINEERING WORKSHOP-2": "FEL206", "ENGINEERING WORKSHOP-II": "FEL206",
    "ENGINEERING WORKSHOP - 2": "FEL206", "ENGINEERING WORKSHOP - II": "FEL206",
    "ENGINEERING WORKSHOP -2": "FEL206", "ENGINEERING WORKSHOP -II": "FEL206", "IKS": "FEL207",

    # SE Sem 3

    "AM3": "CEC301", "AM-3": "CEC301", "M3": "CEC301", "MATHS3": "CEC301", "MATHS-3": "CEC301",

    "DS": "CEC302", "DSA": "CEC302", "DS LAB": "CEL301", "DSA LAB": "CEL301",

    "DSGT": "CEC303", "DBMS": "CEC304", "DBMS LAB": "CEL302",

    "COA": "CEC305", "COA LAB": "CEL303",

    "EE": "CEC306", "SPP": "CEL304", "PYTHON LAB": "CEL304", "PYTHON": "CEL304",

    "MP1A": "CEM301", "MP 1A": "CEM301",

    # SE Sem 4

    "AM4": "CEC401", "AM-4": "CEC401", "M4": "CEC401", "MATHS4": "CEC401", "MATHS-4": "CEC401",

    "OS": "CEC402", "OS LAB": "CEL401",

    "AOA": "CEC403", "ADA": "CEC403", "AOA LAB": "CEL402", "ADA LAB": "CEL402",

    "CTD": "CEC404", "WT": "CEL403", "WT LAB": "CEL403", "WEB TECH LAB": "CEL403",

    "VEC": "CEL404", "UHV": "CEL404", "MP1B": "CEM401", "MP 1B": "CEM401",

    # TE Sem 5

    "TCS": "CEC501", "THEORETICAL COMPUTER SCIENCE": "CEC501",

    "SE": "CEC502", "SE LAB": "CEC502", "SOFTWARE ENGINEERING": "CEC502",

    "CN": "CEC503", "CN LAB": "CEL502", "COMPUTER NETWORK": "CEC503", "COMPUTER NETWORKS": "CEC503",

    "DEVOPS": "CEL501", "DEVOPS LAB": "CEL501", "DOL": "CEL501",

    "ICS": "CEL503", "ICS LAB": "CEL503",

    "MP2": "CEM501", "MP 2": "CEM501",

    # Electives Sem 5

    "ADBMS": "CEPEC5011", "ADBMS LAB": "CEPEL5011",

    "IOT": "CEPEC5012", "IOT LAB": "CEPEL5012",

    "EH": "CEPEC5013", "EH LAB": "CEPEL5013",

    "DWM": "CEPEC5014", "DWM LAB": "CEPEL5014",

    # Minors Sem 5

    "DAV": "MDMC5022", "DAV LAB": "MDML5021",

    "ESR": "MDMC5032", "ESR LAB": "MDML5031",

    "SCM": "MDMC5062",

    # TE Sem 6

    "SPCC": "CEC601", "SPCC LAB": "CEC601", "SYSTEM PROGRAMMING AND COMPILER CONSTRUCTION": "CEC601",

    "CNS": "CEC602", "CNS LAB": "CEC602", "CRYPTOGRAPHY": "CEC602", "CRYPTOGRAPHY AND NETWORK SECURITY": "CEC602", "NETWORK SECURITY": "CEC602",

    "AISC": "CEC603", "AI": "CEC603", "ARTIFICIAL INTELLIGENCE": "CEC603", "ARTIFICIAL INTELLIGENCE AND SOFT COMPUTING": "CEC603",

    "CI LAB": "CEL601", "CIL": "CEL601",

    "CC LAB": "CEL602", "CLOUD LAB": "CEL602", "CLOUD COMPUTING LAB": "CEL602",

    "MPI": "CEP601", "MAJOR PROJECT 1": "CEP601",

    # Electives Sem 6

    "MV": "CEPEC6011", "MV LAB": "CEPEL6011",

    "RA": "CEPEC6012", "RA LAB": "CEPEL6012", "ROBOTICS": "CEPEC6012", "ROBOTICS LAB": "CEPEL6012",

    "DF": "CEPEC6013", "DF LAB": "CEPEL6013",

    "NLP": "CEPEC6014", "NLP LAB": "CEPEL6014", "NATURAL LANGUAGE PROCESSING": "CEPEC6014",

    # Minors Sem 6

    "DMBI": "MDMC6023", "DMBI LAB": "MDML6022",

    "ST": "MDMC6033", "ST LAB": "MDML6032",

    "OBHRM": "MDMC6063", "OB": "MDMC6063"

}

def _ensure_lab_acronyms():
    sections = get_sections_dict()
    for code, sec in sections.items():
        cname = extract_course_name_from_header(sec["header"]).upper().strip()
        if "LAB" in cname:
            if cname not in ACRONYM_TO_COURSE_CODE:
                ACRONYM_TO_COURSE_CODE[cname] = code
            cname_clean = re.sub(r"\s*-\s*", " ", cname).strip()
            if cname_clean not in ACRONYM_TO_COURSE_CODE:
                ACRONYM_TO_COURSE_CODE[cname_clean] = code
            cname_noskill = re.sub(r"^SKILL\s+LAB\s*", "", cname_clean).strip()
            if cname_noskill and cname_noskill not in ACRONYM_TO_COURSE_CODE:
                ACRONYM_TO_COURSE_CODE[cname_noskill] = code

def resolve_all_course_codes_from_query(query: str, retrieved_chunks=None) -> list[str]:
    _ensure_lab_acronyms()
    sections = get_sections_dict()
    matches: list[tuple[int, int, str]] = []  # (start, end, code)
    q_upper = query.upper()

    # 1. Check explicit course codes in query (e.g. CEC501, FEC204)
    explicit_codes: set[str] = set()
    for m in re.finditer(r"\b[A-Z]{2,6}\d{3,4}[A-Z0-9/]*\b", q_upper):
        code = m.group()
        if code in sections:
            matches.append((m.start(), m.end(), code))
            explicit_codes.add(code)

    # 2. Check acronyms & aliases in query (longest alias key first)
    for acr in sorted(ACRONYM_TO_COURSE_CODE.keys(), key=len, reverse=True):
        pattern = rf"\b{re.escape(acr)}\b"
        for m in re.finditer(pattern, q_upper):
            target = ACRONYM_TO_COURSE_CODE[acr]
            if target in sections:
                start, end = m.start(), m.end()
                if not any(max(start, ms) < min(end, me) for ms, me, _ in matches):
                    matches.append((start, end, target))

    # 3. Search course name in sections with robust token normalization
    def _normalize_tokens(s: str) -> str:
        s = s.lower()
        s = re.sub(r"\(.*?\)", "", s)
        s = re.sub(r"[-_/\s]+", " ", s)
        s = re.sub(r"\bviii\b", "8", s)
        s = re.sub(r"\bvii\b", "7", s)
        s = re.sub(r"\bvi\b", "6", s)
        s = re.sub(r"\bv\b", "5", s)
        s = re.sub(r"\biv\b", "4", s)
        s = re.sub(r"\biii\b", "3", s)
        s = re.sub(r"\bii\b", "2", s)
        s = re.sub(r"\bi\b", "1", s)
        return " ".join(s.split())

    is_sem2 = bool(re.search(r"\b(?:sem(?:ester)?\s*(?:2|ii|two)|2nd\s*sem(?:ester)?|second\s*sem(?:ester)?)\b", query, re.I))

    # Group codes by normalized course name
    cname_to_codes: dict[str, list[str]] = {}
    for code, sec in sections.items():
        cname = extract_course_name_from_header(sec["header"])
        cname_norm = _normalize_tokens(cname)
        if len(cname_norm) > 4:
            cname_to_codes.setdefault(cname_norm, []).append(code)

    q_norm = _normalize_tokens(query)
    norm_matches: list[tuple[int, int, str]] = []
    already_matched_codes = {c for _, _, c in matches}

    for cname_norm in sorted(cname_to_codes.keys(), key=len, reverse=True):
        pattern = rf"\b{re.escape(cname_norm)}\b"
        for m in re.finditer(pattern, q_norm):
            start, end = m.start(), m.end()
            if any(max(start, ms) < min(end, me) for ms, me, _ in norm_matches):
                continue

            codes = cname_to_codes[cname_norm]
            # Disambiguate if multiple codes share the same course name (e.g. FEC1021 vs FEC2021)
            if len(codes) == 1:
                chosen_code = codes[0]
            else:
                if is_sem2:
                    sem2_candidates = [c for c in codes if re.match(r"^[A-Z]{2,4}2", c)]
                    chosen_code = sem2_candidates[0] if sem2_candidates else codes[0]
                else:
                    sem1_candidates = [c for c in codes if re.match(r"^[A-Z]{2,4}1", c)]
                    chosen_code = sem1_candidates[0] if sem1_candidates else codes[0]

            norm_matches.append((start, end, chosen_code))
            if chosen_code not in already_matched_codes:
                matches.append((start, end, chosen_code))
                already_matched_codes.add(chosen_code)

    if matches:
        matches.sort(key=lambda x: x[0])
        seen_codes = set()
        seen_titles = set()
        res = []
        for _, _, c in matches:
            if c not in sections or c in seen_codes:
                continue
            cname = extract_course_name_from_header(sections[c]["header"])
            cname_clean = _normalize_tokens(cname)
            if cname_clean in seen_titles and c not in explicit_codes:
                continue
            seen_codes.add(c)
            seen_titles.add(cname_clean)
            res.append(c)
        return res

    # 4. Fallback to retrieved chunks metadata
    if retrieved_chunks:
        for item in retrieved_chunks:
            meta = item.get("metadata", {})
            if meta.get("course_code") and meta["course_code"] in sections:
                return [meta["course_code"]]
    return []

def resolve_course_code_from_query(query: str, retrieved_chunks=None) -> str | None:
    codes = resolve_all_course_codes_from_query(query, retrieved_chunks)
    return codes[0] if codes else None

THEORY_TO_LAB_MAP = {
    'CEC503': 'CEL502',      # Computer Network -> Computer Network Lab
    'CEC402': 'CEL401',      # Operating System -> Operating System Lab
    'CEC403': 'CEL402',      # Analysis of Algorithm -> Analysis of Algorithm Lab
    'CEC302': 'CEL301',      # Data Structures -> Data Structure Lab
    'CEC304': 'CEL302',      # DBMS -> DBMS Lab
    'CEC305': 'CEL303',      # COA -> COA Lab
    'CEPEC5011': 'CEPEL5011', # Advance DBMS -> Advance DBMS Lab
    'CEPEC5012': 'CEPEL5012', # IoT -> IoT Lab
    'CEPEC5013': 'CEPEL5013', # Ethical Hacking -> Ethical Hacking Lab
    'CEPEC5014': 'CEPEL5014', # Data Warehouse and Mining -> Data Warehouse and Mining Lab
    'CEPEC6011': 'CEPEL6011', # Machine Vision -> Machine Vision Lab
    'CEPEC6012': 'CEPEL6012', # Robotics and Applications -> Robotics and Applications Lab
    'CEPEC6013': 'CEPEL6013', # Digital Forensics -> Digital Forensics Lab
    'CEPEC6014': 'CEPEL6014', # NLP -> NLP Lab
    'FEC1021': 'FEL1011',    # Applied Physics I -> Applied Physics Lab
    'FEC2021': 'FEL2011',    # Applied Physics II -> Applied Physics Lab
    'FEC1022': 'FEL1012',    # Applied Chemistry I -> Applied Chemistry Lab
    'FEC2022': 'FEL2012',    # Applied Chemistry II -> Applied Chemistry Lab
    'FEC103': 'FEL102',      # BEEE -> BEEE Lab
    'FEC104': 'FEL103',      # C - Programming -> C - Programming Lab
    'FEC105': 'FEL104',      # AMRD -> AMRD Lab
    'FEC203': 'FEL202',      # Engineering Graphics -> Engineering Graphics Lab
    'FEC204': 'FEL203',      # Digital System Design -> Digital System Design Lab
    'FEC205': 'FEL204',      # PCT -> PCT Lab
    'MDMC5022': 'MDML5021',  # Data Analytics & Visualization -> DAV Lab
    'MDMC5032': 'MDML5031',  # Embedded Systems & RTOS -> ESR Lab
    'MDMC6033': 'MDML6032',  # Sensor Technology -> Sensor Technology Lab
}

def extract_academic_query_dispatch(query: str, retrieved_chunks=None) -> str | None:
    has_exp_kw = bool(re.search(r'\b(experiments?|practicals?|tasks?|pracs?|exps?|lab experiments?)\b', query, re.I))
    has_mod_kw = bool(re.search(r'\b(modules?|units?)\b', query, re.I))
    
    if not (has_exp_kw or has_mod_kw):
        return None

    if re.search(r'\b(program structure|curriculum structure|teaching scheme|all subjects|all courses|credit distribution|total credits?)\b', query, re.I):
        return None

    # If pure module query without experiments, only intercept if there are multiple courses with specific module numbers (e.g. "CN module 2 and TCS module 4")
    if not has_exp_kw and has_mod_kw:
        if not re.search(r'(\d+|unit\s*\d+\.\d+)', query, re.I):
            return None

    all_codes = resolve_all_course_codes_from_query(query, retrieved_chunks)
    if not all_codes:
        return None

    sections = get_sections_dict()

    # Split query into clauses by conjunctions, coordinators, or punctuation
    raw_clauses = [c.strip() for c in re.split(r'\s*(?:and\s+also|as\s+well\s+as|along\s+with|\band\b|[,;&])\s*', query, flags=re.I) if c.strip()]
    
    # If there are multiple courses but conjunction splitting did not create multiple clauses, split by course positions
    if len(all_codes) > 1 and len(raw_clauses) < len(all_codes):
        q_lower = query.lower()
        pos_list = []
        for c in all_codes:
            if c not in sections:
                continue
            cname = extract_course_name_from_header(sections[c]['header']).lower()
            p = q_lower.find(c.lower())
            if p == -1:
                for acr, target in ACRONYM_TO_COURSE_CODE.items():
                    if target == c:
                        p_acr = q_lower.find(acr.lower())
                        if p_acr != -1:
                            p = p_acr
                            break
            if p == -1:
                p = q_lower.find(cname)
            if p != -1:
                pos_list.append((p, c))
        pos_list.sort(key=lambda x: x[0])
        if len(pos_list) == len(all_codes):
            new_clauses = []
            for i in range(len(pos_list)):
                start_p = pos_list[i][0]
                end_p = pos_list[i+1][0] if i + 1 < len(pos_list) else len(query)
                new_clauses.append(query[start_p:end_p].strip())
            if len(new_clauses) >= len(all_codes):
                raw_clauses = new_clauses

    course_to_clause = {}
    for cl in raw_clauses:
        cl_codes = resolve_all_course_codes_from_query(cl, retrieved_chunks)
        for c in cl_codes:
            if c not in course_to_clause:
                course_to_clause[c] = cl
    for c in all_codes:
        if c not in course_to_clause:
            course_to_clause[c] = query

    results = []
    seen_output_keys = set()

    for c in all_codes:
        if c not in sections:
            continue
        cl = course_to_clause.get(c, query)
        sec = sections[c]
        cname = extract_course_name_from_header(sec['header'])
        is_lab = c.startswith(('FEL', 'CEL', 'CEPEL', 'MDML')) or 'lab' in cname.lower() or 'lab' in sec['header'].lower()

        # If clause asks for experiments but code was resolved to theory, map to lab if possible
        if not is_lab and (has_exp_kw and not re.search(r'\b(modules?|units?)\b', cl, re.I)):
            lab_c = THEORY_TO_LAB_MAP.get(c)
            if lab_c and lab_c in sections:
                c = lab_c
                sec = sections[c]
                cname = extract_course_name_from_header(sec['header'])
                is_lab = True

        if c in seen_output_keys:
            continue
        seen_output_keys.add(c)

        if is_lab:
            cl_for_exp = cl
            if not re.search(r'\b(experiments?|practicals?|tasks?|pracs?|exps?)\b', cl_for_exp, re.I):
                cl_for_exp = cl_for_exp + " experiments"
            if not re.search(r'(\d+|first|last|all|list|how\s+many|count|total)', cl_for_exp, re.I):
                cl_for_exp = "all experiments"
            
            exp_text = extract_lab_experiments(cl_for_exp, sec['all_pages'], course_code=c, course_name=cname)
            if exp_text:
                results.append(exp_text.strip())
        else:
            # Theory course
            cl_for_mod = cl
            if not re.search(r'\b(modules?|units?)\b', cl_for_mod, re.I):
                cl_for_mod = cl_for_mod + " modules"
            if re.search(r'(\d+|unit\s*\d+\.\d+)', cl_for_mod, re.I):
                mod_text = extract_specific_course_modules(cl_for_mod, sec['all_pages'])
                if mod_text:
                    results.append(mod_text.strip())
            else:
                mod_text = extract_course_all_modules_only(cl_for_mod, sec['all_pages'])
                if mod_text:
                    results.append(mod_text.strip())

    if results:
        return "\n\n---\n\n".join(results)
    return None

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

        nums = re.findall(r"(?:(?<=\s)|(?<=^))(\d+(?:\.\d+)?(?:[*+#&]?\s*\+?\s*[*+#&]?\s*\d+(?:\.\d+)?)?[*+#&]?|\-{1,2})(?=\s|$)", sub_block)

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

        nums = re.findall(r"(?:(?<=\s)|(?<=^))(\d{1,3}|\-{1,2})(?=\s|$)", sub_block)

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

    res_lines.append(f"- **Course Code:** {target_code}")

    res_lines.append(f"- **Course Name:** {course_name}")

    if teaching_scheme:

        res_lines.append(f"- **Teaching Scheme:** {teaching_scheme}")

    if credits_assigned:

        res_lines.append(f"- **Credits Assigned:** {credits_assigned}")

    if exam_scheme:

        res_lines.append(f"- **Examination Scheme:** {exam_scheme}")

    res_lines.append(f"- **Pre-requisite:** {prereq}\n")

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

    if re.search(r"\b(prereq\w*|pre-req\w*|requirement\w*)\b", query, re.I) and not re.search(r"\b(full\s+syllabus|complete\s+syllabus|overall\s+syllabus)\b", query, re.IGNORECASE):

        return None

    if not retrieved_chunks:

        return None

    if re.search(r"\b(program structure|curriculum structure|electives?|minors?|mdms?|credit distribution|semester-?wise credit|how many credits)\b", query, re.IGNORECASE):

        return None

    if re.search(r"\b(?:only\s+)?(textbooks?|text\s*books?|reference\s*books?|references?|books?|reading\s*materials?|recommended\s*reading)\b", query, re.IGNORECASE) and not re.search(r"\b(information|informatin|details?|overview|about)\b", query, re.IGNORECASE):

        return None

    if re.search(r"\b(?:only\s+modules?|just\s+modules?|modules?\s+and\s+self-?learning|course\s+modules?|give\s+modules?|what\s+are\s+the\s+modules?|list\s+of\s+modules?|show\s+modules?|modules?\s+of)\b", query, re.IGNORECASE) and not re.search(r"\b(full\s+syllabus|complete\s+syllabus|overall\s+syllabus)\b", query, re.IGNORECASE):

        return None

    if re.search(r"\b(from\s+\d+|between\s+\d+|first\s+\d+\s+(?:experiments?|exps?|pracs?)|last\s+\d+\s+(?:experiments?|exps?|pracs?)|\d+(?:st|nd|rd|th)?\s+(?:experiments?|exps?|pracs?))\b", query, re.IGNORECASE):

        return None

    if parse_requested_modules(query) or re.search(r"\bunit\s*\d+(\.\d+)?\b", query, re.IGNORECASE):

        return None

    if re.search(r"\b(evaluat(?:ion|e)|assessment|term\s*work|ciap|esep|bifurcat(?:ion)?)\b", query, re.I):

        return None

    sections = get_sections_dict()

    target_codes = resolve_all_course_codes_from_query(query, retrieved_chunks)

    if not target_codes:

        return None

    if len(target_codes) > 1:
        multi_parts = []
        seen_titles = set()
        for code in target_codes:
            if code in sections:
                cname = extract_course_name_from_header(sections[code]["header"])
                clean_title = re.sub(r"\s+", " ", cname).strip().lower()
                if clean_title in seen_titles:
                    continue
                seen_titles.add(clean_title)
                multi_parts.append(build_course_full_markdown(code, sections[code], sections))
        if multi_parts:
            return "\n\n==============================\n\n".join(multi_parts)
        return None

    target_code = target_codes[0]

    if target_code not in sections:

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

def extract_end_semester_examination_pattern(query: str, retrieved_chunks) -> str | None:

    # Check if query asks for ESE / end semester examination pattern

    ese_kw = bool(re.search(r"\b(ese|end\s*sem(?:ester)?(?:\s*exam(?:ination)?)?|question\s*paper\s*pattern|exam(?:ination)?\s*pattern)\b", query, re.I))

    if not ese_kw:

        return None

    # Do not intercept if query is asking specifically for modules, textbooks, or lab experiments

    if re.search(r"\b(modules?|chapters?|units?|textbooks?|experiments?|practicals?|lab\b)", query, re.I):

        return None

    sections = get_sections_dict()

    # Helper to find if an explicit course is in query

    def find_course_in_q(q: str):

        code_match = re.search(r"\b[A-Z]{2,6}\d{3,4}[A-Z]?\b", q.upper())

        if code_match and code_match.group() in sections:

            return code_match.group()

        q_low = q.lower()

        best = None

        best_len = 0

        for code, sec in sections.items():

            cname = extract_course_name_from_header(sec["header"]).lower()

            cname_clean = re.sub(r"\(.*?\)", "", cname).strip()

            if len(cname_clean) > 4 and cname_clean in q_low:

                if len(cname_clean) > best_len:

                    best = code

                    best_len = len(cname_clean)

        return best

    target_code = resolve_course_code_from_query(query, retrieved_chunks)

    if target_code and target_code in sections:

        sec = sections[target_code]

        course_name = extract_course_name_from_header(sec["header"])

        # Check if exam scheme summary exists on page 0

        scheme_summary = ""

        p1_text = sec["all_pages"][0]["text"]

        text_clean = re.sub(rf"\b{re.escape(target_code)}\b", "", p1_text)

        m_exam = re.search(r"(?is)Examination\s*Scheme.*?(?=\n\s*(?:Pre-?requisite|Program\s*Outcomes|Course\s*Objectives|Lab\s*Objectives|Exp\.?\s*No|Suggested\s*List|\*|\Z))", text_clean)

        if m_exam:

            block = m_exam.group(0)

            header_end = re.search(r"(?i)(?:ISE\s+MSE|Total)", block)

            sub_block = block[header_end.end():] if header_end else block

            nums = re.findall(r"(?:(?<=\s)|(?<=^))(\d{1,3}|\-{1,2})(?=\s|$)", sub_block)

            if len(nums) == 4 and nums[0].isdigit() and nums[1].isdigit() and nums[2].isdigit():

                scheme_summary = f"- **Examination Scheme:** ISE ({nums[0]}), MSE ({nums[1]}), ESE ({nums[2]}) | **Total:** {nums[3]} marks\n"

            elif len(nums) >= 5:

                ise, mse, ese = nums[0], nums[1], nums[2]

                ciap, esep = nums[3], nums[4]

                tot = nums[5] if len(nums) >= 6 else "100"

                parts = []

                if ise not in ["--", "-"]: parts.append(f"ISE ({ise})")

                if mse not in ["--", "-"]: parts.append(f"MSE ({mse})")

                if ese not in ["--", "-"]: parts.append(f"ESE ({ese})")

                if ciap not in ["--", "-", "0"]: parts.append(f"CIAP ({ciap})")

                if esep not in ["--", "-", "0"]: parts.append(f"ESEP ({esep})")

                scheme_summary = f"- **Examination Scheme:** {', '.join(parts)} | **Total:** {tot} marks\n"

        full_text = "\n".join(p.get("text", "") for p in sec.get("all_pages", []))

        idx = full_text.find("End Semester Examination:")

        ese_text = ""

        if idx != -1:

            block = full_text[idx:idx + 700]

            lines = [l.strip() for l in block.split("\n") if l.strip()]

            res_lines = []

            for l in lines[1:]:

                if re.match(r"^[1-6]\.0\s+[A-Z]", l) or "Textbooks:" in l or "Reference" in l or "Online References" in l or "CIAP" in l:

                    break

                clean_l = re.sub(r"^[\$\uf0b7\•\-\*]\s*", "", l).strip()

                if clean_l:

                    res_lines.append(clean_l)

            if res_lines:

                ese_text = "\n".join(f"- {l}" if not re.match(r"^\d+\.", l) else l for l in res_lines)

        if ese_text or scheme_summary:

            body = f"{scheme_summary}{ese_text}".strip()

            return (

                f"### End Semester Examination (ESE) Pattern - {target_code}: {course_name}\n\n"

                f"{body}"

            )

    # Generic ESE pattern (when no specific course is mentioned in query)

    return (

        "### End Semester Examination (ESE) Pattern & Question Paper Structure\n\n"

        "According to the syllabus guidelines, the End Semester Examination (ESE) pattern for theoretical courses is as follows:\n\n"

        "- **Duration:** 03 hours\n"

        "- **Total Marks:** 80 marks (scaled to 60 marks)\n"

        "- **Internal Assessment:** In-Semester Evaluation (ISE 20 marks) + Mid-Semester Examination (MSE 20 marks) | Total: 100 marks\n\n"

        "**Question Paper Pattern:**\n"

        "1. The question paper comprises **03 questions** covering the entire syllabus.\n"

        "2. **Question 1 (20 marks):** Solve any **04 out of 06** questions (05 marks each).\n"

        "3. **Question 2 (40 marks):** Solve any **04 out of 06** questions (10 marks each).\n"

        "4. **Question 3 (20 marks):** Solve any **04 out of 06** questions (05 marks each).\n"

        "5. All Course Outcomes (COs) are mapped as per their weightage in the syllabus.\n\n"

        "*(Note: For 2-credit theory courses, ESE duration is 02 hours of 60 marks scaled to 45).*"

    )

def extract_course_assessment_and_evaluation(query: str, retrieved_chunks) -> str | None:

    is_assessment_query = bool(re.search(

        r"\b(evaluat(?:ion|e)|assessment|term\s*work|ciap|esep|bifurcat(?:ion)?|marks?\s*(?:bifurcation|distribution|breakdown)|internal\s*assessment|ise\s*marks?|mse\s*marks?)\b",

        query,

        re.IGNORECASE,

    ))

    if not is_assessment_query:

        return None

    # Don't intercept if explicitly asking only for ESE question paper pattern without mentioning evaluation/term work/assessment/bifurcation

    if re.search(r"\b(ese|end\s*sem(?:ester)?|question\s*paper)\s*(?:paper\s*)?pattern\b", query, re.I) and not re.search(r"\b(term\s*work|ciap|esep|internal\s*assessment|ise|evaluation|assessment\s*scheme|course\s*assessment|bifurcation)\b", query, re.I):

        return None

    # Don't intercept if query specifically asks for modules, chapters, textbooks, or experiments

    if re.search(r"\b(modules?|chapters?|units?|textbooks?|experiments?|practicals?)\b", query, re.I):

        return None

    sections = get_sections_dict()

    def clean_name(raw: str) -> str:

        name = extract_course_name_from_header(raw)

        name = re.sub(r"(?i)\bCourse\s+Code\b|\bCourse\s+Name\b", "", name)

        name = re.sub(r"[\d\s\-\+\*\/()]+$", "", name)

        name = re.sub(r"[\d\s\-\+\*\/()]{3,}", " ", name)

        name = re.sub(r"\s+", " ", name).strip(" -:\n")

        return name

    def clean_bullets(txt: str) -> str:

        txt = re.sub(r"[\uf0b7\u2022\ufffd\x95\x96\x97\x98]", "-", txt)

        txt = re.sub(r"(?m)^\s*o\s+", "  - ", txt)

        txt = re.sub(r"\s{2,}(\d+\s*marks)", r": **\1**", txt)

        txt = re.sub(r"(?m)^\s*-\s*", "- ", txt)

        txt = re.sub(r"(?m)^\s*\d+\s*\n\s*SIES\s+Graduate\s+School\s+of\s+Technology\s*\n\s*Department\s+of\s+[^\n]+\s*\n\s*Bachelor\s+of\s+Engineering\s*$", "", txt)

        return txt.strip()

    def find_target_course(q: str):

        if retrieved_chunks:

            for item in retrieved_chunks:

                meta = item.get("metadata", {})

                if meta.get("course_code") and meta["course_code"] in sections:

                    return meta["course_code"]

        code_match = re.search(r"\b[A-Z]{2,6}\d{3,4}[A-Z]?\b", q.upper())

        if code_match and code_match.group() in sections:

            return code_match.group()

        q_low = q.lower()

        if "interpersonal" in q_low or "career skill" in q_low:

            for c in ["CEL503", "CEL403"]:

                if c in sections: return c

        if "devops" in q_low:

            for c in ["CEL501", "CEC501"]:

                if c in sections: return c

        if "data warehouse" in q_low or "dwm" in q_low:

            for c in ["CEPEC5014", "CEPEL5014"]:

                if c in sections: return c

        if "computer network" in q_low or "networking" in q_low:

            if "lab" in q_low and "CEL502" in sections:

                return "CEL502"

            if "CEC503" in sections:

                return "CEC503"

        if "mini project" in q_low:

            for c in ["CEM501", "CEM601", "CEM401"]:

                if c in sections: return c

        best = None

        best_len = 0

        for code, sec in sections.items():

            cname = clean_name(sec["header"]).lower()

            if len(cname) > 4 and cname in q_low:

                if len(cname) > best_len:

                    best = code

                    best_len = len(cname)

        return best

    target_code = resolve_course_code_from_query(query, retrieved_chunks)

    if not target_code or target_code not in sections:

        return (

            "### SIES GST Course Evaluation Scheme & Marks Bifurcation\n\n"

            "Under the autonomous curriculum regulations, courses are evaluated based on the following standard examination schemes:\n\n"

            "#### 1. Theory Courses (3-Credit / 4-Credit Courses - Total: 100 Marks)\n"

            "- **Continuous Internal Assessment (40 Marks):**\n"

            "  - **In-Semester Evaluation (ISE - 20 Marks):** 05 marks for Attendance + 15 marks for activities (Assignments, Quizzes, Class Tests, Presentations, or Case Studies).\n"

            "  - **Mid-Semester Examination (MSE - 20 Marks):** Written test conducted on 40% – 50% of the syllabus.\n"

            "- **End Semester Examination (ESE - 60 Marks):**\n"

            "  - 03 hours written examination of 80 marks scaled down to 60 marks.\n"

            "  - Comprises 03 questions covering all Course Outcomes (COs).\n\n"

            "#### 2. Laboratory / Practical Courses (1-Credit / 2-Credit Courses - Total: 50 Marks)\n"

            "- **Continuous Internal Assessment Practical (CIAP / Term Work - 25 or 50 Marks):**\n"

            "  - Laboratory experiments/performance (minimum 12 experiments covering all LOs).\n"

            "  - Continuous laboratory assessment + Attendance.\n"

            "- **End Semester Examination Practical (ESEP - 25 Marks):**\n"

            "  - 02 hours Practical and Oral exam conducted by internal and external examiners.\n\n"

            "#### 3. Mini Project / Major Project (Total: 50 Marks)\n"

            "- **Term Work (CIAP - 25 Marks):** Evaluated based on Guide Logbook (10 marks), Review Committee evaluations (10 marks), and Project Report (05 marks).\n"

            "- **Practical / Oral Examination (ESEP - 25 Marks):** Project demonstration and defense before an expert panel."

        )

    sec = sections[target_code]

    course_name = clean_name(sec["header"])

    p1_text = sec["all_pages"][0]["text"]

    text_clean = re.sub(rf"\b{re.escape(target_code)}\b", "", p1_text)

    teaching_scheme = None

    credits_assigned = None

    m_teach = re.search(r"(?is)(?:Teaching\s*Scheme|Theory\s+Practical\s+Tutorial|Credits\s*Assigned).*?(?=\n\s*(?:Examination\s*Scheme|Pre-?requisite|Program\s*Outcomes)|\Z)", text_clean)

    if m_teach:

        block = m_teach.group(0)

        header_match = re.search(r"(?i)(?:Tot\s*al|Total)", block)

        sub_block = block[header_match.end():] if header_match else block

        nums = re.findall(r"(?:(?<=\s)|(?<=^))(\d+(?:\.\d+)?(?:[*+#&]?\s*\+?\s*[*+#&]?\s*\d+(?:\.\d+)?)?[*+#&]?|\-{1,2})(?=\s|$)", sub_block)

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

    exam_scheme = None

    total_marks = None

    m_exam = re.search(r"(?is)(?:Examination\s*Scheme|Theory\s*Marks|Course\s*Assessment\s*ESE).*?(?=\n\s*(?:Pre-?requisite|Program\s*Outcomes)|\Z)", text_clean)

    if m_exam:

        e_block = m_exam.group(0)

        nums = re.findall(r"(\d+|\-{1,2})", e_block)

        if len(nums) >= 6:

            ise, mse, ese, ciap, esep, tot = nums[0], nums[1], nums[2], nums[3], nums[4], nums[5]

            parts = []

            if ise not in ["--", "-", "0"]: parts.append(f"ISE ({ise})")

            if mse not in ["--", "-", "0"]: parts.append(f"MSE ({mse})")

            if ese not in ["--", "-", "0"]: parts.append(f"ESE ({ese})")

            if ciap not in ["--", "-", "0"]: parts.append(f"CIAP / Term Work ({ciap})")

            if esep not in ["--", "-", "0"]: parts.append(f"ESEP ({esep})")

            exam_scheme = ", ".join(parts) if parts else "See details below"

            total_marks = tot

        elif len(nums) >= 1:

            total_marks = nums[-1]

    all_text = []

    for i, p in enumerate(sec["all_pages"]):

        t = p.get("text", "")

        if i == 0:

            t = re.sub(r"(?is)Course\s*Assessment\s*ESE.*?Pre-?requisite", "Pre-requisite", t)

        all_text.append(t)

    combined = "\n".join(all_text)

    m_assess = re.search(r"(?is)(?:\n\s*(?:Course\s*Assessment|Term\s*Work\s*(?:Marks|\(CIAP\)|Evaluation)?|2\s*Guidelines\s+for\s+Assessment|Evaluation\s+of\s+Term\s*Work)\s*:?).*", combined)

    result_lines = []

    course_name_clean = re.sub(r"(?i)\bCourse\s+Code\b|\bCourse\s+Name\b", "", course_name).strip(" -:\n")

    result_lines.append(f"### {target_code}: {course_name_clean} - Evaluation Scheme & Course Assessment\n")

    meta_info = []

    if credits_assigned: meta_info.append(f"**Credits Assigned:** {credits_assigned}")

    if teaching_scheme: meta_info.append(f"**Teaching Scheme:** {teaching_scheme}")

    if exam_scheme and total_marks: meta_info.append(f"**Examination Scheme:** {exam_scheme} | **Total Marks:** {total_marks}")

    elif exam_scheme: meta_info.append(f"**Examination Scheme:** {exam_scheme}")

    if meta_info:

        result_lines.append("\n".join(meta_info) + "\n")

    if m_assess:

        raw_assess = m_assess.group(0).strip()

        cleaned_assess = clean_bullets(raw_assess)

        cleaned_assess = re.sub(r"(?i)^Course Assessment:\s*", "#### Course Assessment Breakdown:\n", cleaned_assess)

        cleaned_assess = re.sub(r"(?i)^Term Work:\s*", "#### Term Work (CIAP) Guidelines:\n", cleaned_assess)

        cleaned_assess = re.sub(r"(?i)\nISE:\s*", "\n**1. In-Semester Evaluation (ISE - 20 Marks):**\n", cleaned_assess)

        cleaned_assess = re.sub(r"(?i)\nMSE:\s*", "\n**2. Mid-Semester Examination (MSE - 20 Marks):**\n", cleaned_assess)

        cleaned_assess = re.sub(r"(?i)\nEnd Semester Examination:\s*", "\n**3. End Semester Examination (ESE - 60 Marks):**\n", cleaned_assess)

        cleaned_assess = re.sub(r"(?i)\nPractical Exam:\s*", "\n**Practical Examination (ESEP):**\n", cleaned_assess)

        cleaned_assess = re.sub(r"(?i)\nTerm work Marks\s*(\(\s*CIAP\s*\))?:\s*", "\n**Term Work Marks Bifurcation (CIAP):**\n", cleaned_assess)

        cleaned_assess = re.sub(r"(?m)^-\s*(Report\s+Presentation|Group\s+Discussion|Mock\s+Interview|Project\s+Report|Assignments\s+based|Attendance)", r"  - \1", cleaned_assess)

        result_lines.append(cleaned_assess)

    else:

        result_lines.append(f"Detailed assessment follows the autonomous curriculum scheme for {target_code} with total {total_marks or '100'} marks.")

    return "\n\n".join(result_lines)

def extract_course_prerequisites(query: str, retrieved_chunks) -> str | None:

    from rag.query_rewriter import reframe_query

    norm_q = reframe_query(query)

    if not re.search(r"\b(prereq\w*|pre-req\w*|requirement\w*|prior\s+knowledge)\b", norm_q, re.I):

        return None

    if re.search(r"\b(full syllabus|complete syllabus|all modules|all details)\b", norm_q, re.I):

        return None

    sections = get_sections_dict()

    target_code = resolve_course_code_from_query(norm_q, retrieved_chunks)

    if not target_code or target_code not in sections:

        return None

    sec = sections[target_code]

    course_name = extract_course_name_from_header(sec.get("header", ""))

    course_name = re.sub(r"(?i)\bCourse\s+Code\b|\bCourse\s+Name\b", "", course_name)

    course_name = re.sub(r"[\d\s\-\+\*\/()]+$", "", course_name)

    course_name = re.sub(r"[\d\s\-\+\*\/()]{3,}", " ", course_name)

    course_name = re.sub(r"\s+", " ", course_name).strip(" -:\n") or target_code

    first_page = sec.get("all_pages", [{}])[0].get("text", "")

    m_prereq = re.search(

        r"(?is)Pre-?\s*requisite[s]?\s*:\s*(.*?)(?=\n\s*(?:Program\s*Outcomes?|Course\s*Objectives?|Lab\s*Objectives?|Course\s*Outcomes?)|\Z)",

        first_page,

    )

    prereq_items = []

    if m_prereq:

        raw_pr = m_prereq.group(1).strip()

        lines = [l.strip() for l in raw_pr.split("\n") if l.strip()]

        for l in lines:

            cleaned = re.sub(r"^\d+\.\s*", "", l).strip()

            cleaned = re.sub(r"^[:\s]+", "", cleaned).strip()

            cleaned = re.sub(r"\s{2,}", " ", cleaned)

            if cleaned and cleaned.lower() not in ["nil", "none", "-", "--", "na", "not applicable"]:

                prereq_items.append(cleaned)

    res = [f"### Pre-requisites for {target_code}: {course_name}\n"]

    res.append(f"- **Course Code:** {target_code}")

    res.append(f"- **Course Name:** {course_name}")

    if prereq_items:

        res.append("- **Pre-requisite(s):**")

        for idx, item in enumerate(prereq_items, 1):

            res.append(f"  {idx}. {item}")

    else:

        res.append("- **Pre-requisite:** None / Nil (No prior prerequisite required)")

    return "\n".join(res)

def extract_course_scheme_or_credits(query: str, retrieved_chunks) -> str | None:

    if not retrieved_chunks:

        return None

    if re.search(r"\b(credit\s+distribution|credits?\s+distribution|semester-?wise\s+credit|total\s+credits?\s+for\s+(?:the\s+)?(?:degree|b\.?tech|program|engineering))\b", query, re.I):

        return None

    if re.search(r"\b(modules?|chapters?|topics?|experiments?|practicals?|tasks?|syllabus|curriculum|prerequisites?|evaluat(?:ion|e)|assessment|term\s*work|ciap|esep|bifurcat(?:ion)?)\b", query, re.I):

        return None

    wants_credits = bool(re.search(r"\b(credits?|how\s+many\s+credits?|credit\s+assigned|assigned\s+credits?)\b", query, re.I))

    wants_teaching = bool(re.search(r"\b(teaching\s+scheme|contact\s+hours?|hours?\s+per\s+week|lecture\s+hours?)\b", query, re.I))

    wants_exam = bool(re.search(r"\b(examination\s+scheme|exam\s+scheme|marks\s+distribution|evaluation\s+scheme|assessment\s+scheme|ise|mse|ese)\b", query, re.I))

    if not (wants_credits or wants_teaching or wants_exam):
        return None

    # Do not match overall program credit questions (handled by extract_total_program_credits)
    if re.search(r"\b(computer\s+engineering|overall|in\s+total|total\s+credits?|all\s+together|altogether|8\s*sem|eight\s*sem|b\.?tech|degree|program|curriculum)\b", query, re.I):
        if not resolve_all_course_codes_from_query(query):
            return None

    # Do not match whole semester queries (handled by extract_semester_program_structure)
    if re.search(r"\b(?:sem(?:ester)?|term)\s*([1-8]|I{1,3}|IV|V|VI|VII|VIII)\b", query, re.I):
        if not resolve_all_course_codes_from_query(query):
            return None

    sections = get_sections_dict()

    target_code = resolve_course_code_from_query(query, retrieved_chunks)

    if not target_code or target_code not in sections:

        return None

    section = sections[target_code]

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

        nums = re.findall(r"(?:(?<=\s)|(?<=^))(\d+(?:\.\d+)?(?:[*+#&]?\s*\+?\s*[*+#&]?\s*\d+(?:\.\d+)?)?[*+#&]?|\-{1,2})(?=\s|$)", sub_block)

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

        nums = re.findall(r"(?:(?<=\s)|(?<=^))(\d{1,3}|\-{1,2})(?=\s|$)", sub_block)

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

    details = []

    if credits_assigned:

        clean_cr = re.sub(r"[^\d]+", "", credits_assigned) or credits_assigned

        details.append(f"- **Credits Assigned:** {clean_cr}")

    if teaching_scheme:

        details.append(f"- **Teaching Scheme:** {teaching_scheme}")

    if exam_scheme:

        details.append(f"- **Examination Scheme:** {exam_scheme}")

    if not details:

        return None

    details_str = "\n".join(details)

    return f"**Course Code:** {target_code}\n**Course Name:** {course_name}\n\n{details_str}"

def extract_semester_detailed_syllabus(query: str, retrieved_chunks) -> str | None:
    # Only trigger when query asks for detailed / module wise / each subject / all subjects syllabus of a semester
    wants_detailed = bool(re.search(r"\b(module\s*wise|detailed\s+syllabus|each\s+subject|all\s+subjects|all\s+courses|detailed\s+module|every\s+subject|syllabus\s+for\s+each)\b", query, re.I))
    wants_sem = bool(re.search(r"\b(?:sem(?:ester)?|term)\s*([1-8]|I|II|III|IV|V|VI|VII|VIII)\b", query, re.I))
    if not (wants_detailed and wants_sem):
        return None
        
    m = re.search(r"\b(?:sem(?:ester)?|term)\s*([1-8]|I|II|III|IV|V|VI|VII|VIII)\b", query, re.I)
    val = m.group(1).upper()
    roman = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
    sem_num = roman.get(val, int(val) if val.isdigit() else None)
    if not sem_num:
        return None
        
    structure_table = extract_semester_program_structure(query, retrieved_chunks)
    sections = get_sections_dict()
    
    SEM_CORE_COURSES = {
        1: [('FEC101', 'Theory'), ('FEC1021', 'Theory'), ('FEC1022', 'Theory'), ('FEC103', 'Theory'), ('FEC104', 'Theory'), ('FEC105', 'Theory'), ('FEL1011', 'Lab'), ('FEL1012', 'Lab'), ('FEL102', 'Lab'), ('FEL103', 'Lab'), ('FEL104', 'Lab')],
        2: [('FEC201', 'Theory'), ('FEC2021', 'Theory'), ('FEC2022', 'Theory'), ('FEC203', 'Theory'), ('FEC204', 'Theory'), ('FEC205', 'Theory'), ('FEL201', 'Lab'), ('FEL202', 'Lab'), ('FEL203', 'Lab'), ('FEL204', 'Lab')],
        3: [('CEC301', 'Theory'), ('CEC302', 'Theory'), ('CEC303', 'Theory'), ('CEC304', 'Theory'), ('CEC305', 'Theory'), ('CEL301', 'Lab'), ('CEL302', 'Lab'), ('CEL303', 'Lab'), ('CEL304', 'Lab')],
        4: [('CEC401', 'Theory'), ('CEC402', 'Theory'), ('CEC403', 'Theory'), ('CEC404', 'Theory'), ('CEC405', 'Theory'), ('CEL401', 'Lab'), ('CEL402', 'Lab'), ('CEL403', 'Lab'), ('CEL404', 'Lab')],
        5: [('CEC501', 'Theory'), ('CEC502', 'Theory'), ('CEC503', 'Theory'), ('CEL501', 'Lab'), ('CEL502', 'Lab'), ('CEL503', 'Lab')],
        6: [('CEC601', 'Theory'), ('CEC602', 'Theory'), ('CEC603', 'Theory'), ('CEL601', 'Lab'), ('CEL602', 'Lab')],
        7: [('CEC701', 'Theory'), ('CEC702', 'Theory'), ('CEL701', 'Lab'), ('CEL702', 'Lab')],
        8: [('CEC801', 'Theory'), ('CEL801', 'Lab')]
    }
    
    courses_to_show = SEM_CORE_COURSES.get(sem_num, [])
    if re.search(r"\b(only\s+theory|theory\s+subjects?|theory\s+courses?)\b", query, re.I) and not re.search(r"\blabs?\b", query, re.I):
        courses_to_show = [c for c in courses_to_show if c[1] == 'Theory']
    elif re.search(r"\b(only\s+labs?|lab\s+subjects?|practical\s+subjects?|practicals?)\b", query, re.I) and not re.search(r"\btheory\b", query, re.I):
        courses_to_show = [c for c in courses_to_show if c[1] == 'Lab']
        
    out = []
    if structure_table:
        out.append(structure_table)
        out.append('\n---\n')
    
    out.append(f"## Detailed Module-Wise Syllabus for Semester {val}\n")
    for code, ctype in courses_to_show:
        if code not in sections:
            continue
        sec = sections[code]
        cname = extract_course_name_from_header(sec.get('header', ''))
        outlines = sec.get('module_outlines', [])
        
        if ctype == 'Lab':
            exps = extract_lab_experiments('all experiments', sec['all_pages'])
            if exps:
                clean_exps = re.sub(r"^Here are (?:the|experiments).*?:\n\n", "", exps, flags=re.I).strip()
                out.append(f"### {code}: {cname} (Practical/Lab)\n")
                out.append(f"{clean_exps}\n")
            elif outlines:
                out.append(f"### {code}: {cname} (Practical/Lab)\n")
                for m in outlines:
                    out.append(format_self_learning_text(m.get('text', '')))
                    out.append('')
        else:
            if outlines:
                out.append(f"### {code}: {cname}\n")
                for m in outlines:
                    out.append(format_self_learning_text(m.get('text', '')))
                    out.append('')
    return '\n'.join(out)

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

    fast_special = extract_special_academic_queries(check_query, retrieved_chunks)
    if fast_special:
        return early_return(fast_special)

    fast_detailed_sem = extract_semester_detailed_syllabus(check_query, retrieved_chunks)
    if fast_detailed_sem:
        return early_return(fast_detailed_sem)

    fast_module_count = extract_course_module_count(check_query, retrieved_chunks)
    if fast_module_count:
        return early_return(fast_module_count)

    # Fast deterministic extractors (0.005s execution)

    wants_structure = bool(

        re.search(r"\b(program structure|curriculum structure|teaching scheme|course structure|subject structure|structure)\b", check_query, re.I)

        or re.search(r"\b(?:sem(?:ester)?|term)\s*([1-8](?:st|nd|rd|th)?|I|II|III|IV|V|VI|VII|VIII)\b.*\b(?:subjects?|courses?|curriculum|syllabus|credits?)\b", check_query, re.I)
        or re.search(r"\b(?:subjects?|courses?|curriculum|syllabus|credits?)\b.*\b(?:sem(?:ester)?|term)\s*([1-8](?:st|nd|rd|th)?|I|II|III|IV|V|VI|VII|VIII)\b", check_query, re.I)
        or re.search(r"\b(?:subjects?|courses?|curriculum|syllabus|credits?)\b.*\b([1-8](?:st|nd|rd|th)?|I|II|III|IV|V|VI|VII|VIII)\s*(?:sem(?:ester)?|term)\b", check_query, re.I)
        or re.search(r"\b([1-8](?:st|nd|rd|th)?|I|II|III|IV|V|VI|VII|VIII)\s*(?:sem(?:ester)?|term)\b.*\b(?:subjects?|courses?|curriculum|syllabus|credits?)\b", check_query, re.I)

    )

    # If a specific course is named and query is not asking for whole semester structure, prioritize course
    target_code_in_query = resolve_course_code_from_query(check_query)
    if target_code_in_query and not re.search(r"\b(program structure|curriculum structure|course structure|all subjects|all courses|teaching scheme)\b", check_query, re.I):
        wants_structure = False

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

    fast_academic_dispatch = extract_academic_query_dispatch(check_query, retrieved_chunks)

    if fast_academic_dispatch:

        return early_return(fast_academic_dispatch)

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

    fast_ese = extract_end_semester_examination_pattern(check_query, retrieved_chunks)

    if fast_ese:

        return early_return(fast_ese)

    fast_assess = extract_course_assessment_and_evaluation(check_query, retrieved_chunks)

    if fast_assess:

        return early_return(fast_assess)

    fast_prereq = extract_course_prerequisites(check_query, retrieved_chunks)

    if fast_prereq:

        return early_return(fast_prereq)

    fast_scheme = extract_course_scheme_or_credits(check_query, retrieved_chunks)

    if fast_scheme:

        return early_return(fast_scheme)

    fast_info = extract_course_full_information(check_query, retrieved_chunks)

    if fast_info:

        return early_return(fast_info)

    fast_outline = extract_course_module_outline(check_query, retrieved_chunks)

    if fast_outline:

        return early_return(fast_outline)

    res_tot_cred = extract_total_program_credits(check_query, retrieved_chunks)
    if res_tot_cred:
        return early_return(res_tot_cred)

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

        single_match = re.search(r'\b(?:experiments?|practicals?|tasks?|exps?|exp\.?|pracs?|prac\.?)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b', check_query, re.IGNORECASE)

        nth_match = re.search(r'\b(\d+)(?:st|nd|rd|th)?\s+(?:experiments?|practicals?|tasks?|exps?|exp\.?|pracs?|prac\.?)\b', check_query, re.IGNORECASE)

        

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

        has_exp_keyword = re.search(r"\b(experiments?|practicals?|tasks?|exps?|exp\.?|pracs?|prac\.?|list)\b", check_query, re.IGNORECASE)

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

