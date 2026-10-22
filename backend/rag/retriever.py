import json

import math

import re

from collections import Counter

from functools import lru_cache

from pathlib import Path



from rag.embeddings import create_embedding

from rag.outline_formatter import (

    extract_module_outlines,

    select_requested_modules,

)

from rag.vector_store import collection



DATA_DIR = Path(__file__).resolve().parents[1] / "data"

COURSE_CODE = re.compile(r"\b[A-Z]{2,6}\d{3,4}[A-Z]?\b")

TOKEN = re.compile(r"[a-z0-9]+")

OUTLINE_REQUEST = re.compile(

    r"\b(syllabus|curriculum|modules?|topics?|units?|chapters?|sections?|self.?learning|course content|course outline|labs?|practicals?|experiments?|tasks?|assignments?|outcomes?|objectives?|goals?|aims?|purpose|books?|textbooks?|references?|bibliography|reading|materials?|prerequisites?|pre-requisites?|requirements?|background|marks?|grading|graded|grades?|evaluat\w*|assess\w*|exam\w*|scheme)\b",

    re.IGNORECASE,

)

LAB_REQUEST = re.compile(r"\b(labs?|practicals?|experiments?|exps?|exp\.?|pracs?|prac\.?)\b", re.IGNORECASE)

SEMESTER_TOKEN = r"(?:VIII|VII|VI|V|IV|III|II|I|[1-8](?:st|nd|rd|th)?)"

SEMESTER_MARKER = re.compile(

    rf"\b(?:semester|sem)\s*[-:#]?\s*({SEMESTER_TOKEN})\b|\b({SEMESTER_TOKEN})\s*(?:semester|sem)\b",

    re.IGNORECASE,

)

SEMESTER_RANGE = re.compile(

    rf"\b(?:semesters?|sems?)\s*({SEMESTER_TOKEN})\s*(?:-|to|through)\s*({SEMESTER_TOKEN})\b",

    re.IGNORECASE,

)

NUM_TO_ROMAN = {

    "1": "i", "2": "ii", "3": "iii", "4": "iv",

    "5": "v", "6": "vi", "7": "vii", "8": "viii",

    "i": "i", "ii": "ii", "iii": "iii", "iv": "iv",

    "v": "v", "vi": "vi", "vii": "vii", "viii": "viii",

}





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

STOP_WORDS = {

    "a",

    "about",

    "an",

    "and",

    "are",

    "as",

    "based",

    "complete",

    "could",

    "course",

    "courses",

    "from",

    "give",

    "in",

    "is",

    "me",

    "my",

    "you",

    "your",

    "we",

    "our",

    "he",

    "him",

    "his",

    "she",

    "her",

    "it",

    "its",

    "they",

    "them",

    "their",

    "can",

    "should",

    "would",

    "could",

    "refer",

    "read",

    "use",

    "suggest",

    "recommended",

    "of",

    "on",

    "please",

    "show",

    "tell",

    "the",

    "their",

    "to",

    "what",

    "which",

    "with",

    "wise",

    "syllabus",

    "module",

    "modules",

    "topic",

    "topics",

    "self",

    "learning",

    "content",

    "outline",

    "lab",

    "labs",

    "practical",

    "practicals",

    "experiment",

    "experiments",

    "complete",

    "list",

    "first",

    "initial",

    "top",

    "last",

    "final",

    "between",

}

SEMESTER_ROMANS = {

    "I": 1,

    "II": 2,

    "III": 3,

    "IV": 4,

    "V": 5,

    "VI": 6,

    "VII": 7,

    "VIII": 8,

}





def _normalize_token(token: str) -> str:

    if len(token) > 5 and token.endswith("ies"):

        return token[:-3] + "y"

    if len(token) > 7 and token.endswith("ing"):

        stem = token[:-3]

        if len(stem) > 2 and stem[-1] == stem[-2]:

            stem = stem[:-1]

        return stem

    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):

        return token[:-1]

    return token





def _tokenize(text: str) -> list[str]:

    tokens = TOKEN.findall(text.casefold())

    compounds = re.findall(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b", text.casefold())

    tokens.extend(compound.replace("-", "") for compound in compounds)

    return [

        _normalize_token(token)

        for token in tokens

        if _normalize_token(token) not in STOP_WORDS

    ]





def _semester_number(token: str | None) -> int:

    if not token:

        return 0

    clean = re.sub(r"(?:st|nd|rd|th)$", "", token, flags=re.I).strip().upper()

    if clean in SEMESTER_ROMANS:

        return SEMESTER_ROMANS[clean]

    try:

        return int(clean)

    except ValueError:

        return 0





def _requested_semesters(question: str) -> list[int]:

    range_match = SEMESTER_RANGE.search(question)

    if range_match:

        first = _semester_number(range_match.group(1))

        last = _semester_number(range_match.group(2))

        low, high = sorted((first, last))

        return list(range(low, high + 1))



    sems = []

    for match in SEMESTER_MARKER.finditer(question):

        tok = match.group(1) or match.group(2)

        if tok:

            n = _semester_number(tok)

            if n > 0:

                sems.append(n)

    return sems





@lru_cache(maxsize=1)

def _semester_structure_pages() -> tuple[dict, ...]:

    pages = []

    for json_file in DATA_DIR.glob("*_structured.json"):

        try:

            with json_file.open("r", encoding="utf-8") as file:

                syllabus = json.load(file)

        except (OSError, json.JSONDecodeError):

            continue



        document = syllabus.get("document", {})

        filename = document.get("filename", "Unknown PDF")

        url = document.get("source_url", "")



        for page in syllabus.get("pages", []):

            text = page.get("text", "")

            page_num = page.get("page_number")

            

            semesters = [

                _semester_number(m.group(1) or m.group(2))

                for m in SEMESTER_MARKER.finditer(text)

                if _semester_number(m.group(1) or m.group(2)) > 0

            ]

            

            if "Program Structure for" in text or page_num in [10, 12, 14, 16]:

                if page_num == 10: semesters.append(4)

                if page_num == 12: semesters.append(5)

                if page_num == 14: semesters.append(6)

                if page_num == 16: semesters.append(7)

                

            semesters = list(dict.fromkeys(semesters))

                

            if semesters:

                pages.append({

                    "page_number": page.get("page_number"),

                    "text": text,

                    "semesters": semesters,

                    "filename": filename,

                    "url": url,

                })



    return tuple(pages)





@lru_cache(maxsize=1)

def _credit_distribution_pages() -> tuple[dict, ...]:

    pages = []

    for json_file in DATA_DIR.glob("*_structured.json"):

        try:

            with json_file.open("r", encoding="utf-8") as file:

                syllabus = json.load(file)

        except (OSError, json.JSONDecodeError):

            continue



        document = syllabus.get("document", {})

        filename = document.get("filename", "Unknown PDF")

        url = document.get("source_url", "")



        for page in syllabus.get("pages", []):

            if page.get("page_number") == 3:

                pages.append({

                    "text": page.get("text", ""),

                    "metadata": {

                        "filename": filename,

                        "url": url,

                        "page": 3,

                    },

                })

    return tuple(pages)





def _retrieve_semester_structures(question: str) -> list[dict] | None:

    if re.search(

        r"\b(credit distribution|credits? distribution|total credits?|degree credits?|credits? for (?:the )?(?:b\.?tech|degree|program|engineering))\b",

        question,

        re.IGNORECASE,

    ):

        dist_pages = _credit_distribution_pages()

        if dist_pages:

            return list(dist_pages)



    if not re.search(

        r"\b(syllabus|subjects?|courses?|curriculum|program structure|electives?|options?|mdms?|minors?|examination scheme|exam scheme|credits?|structure|list|semester|sem)\b",

        question,

        re.IGNORECASE,

    ):

        return None


    if not requested:

        return None



    matched_pages = [

        page

        for page in _semester_structure_pages()

        if set(page["semesters"]) & set(requested)

    ]

    if not matched_pages:

        return None



    return [

        {

            "text": page["text"],

            "metadata": {

                "filename": page["filename"],

                "url": page["url"],

                "page": page["page_number"],

            },

        }

        for page in matched_pages

    ]





@lru_cache(maxsize=1)

def _course_sections() -> tuple[dict, ...]:

    all_sections = []

    for json_file in DATA_DIR.glob("*_structured.json"):

        try:

            with json_file.open("r", encoding="utf-8") as file:

                syllabus = json.load(file)

                pages = syllabus.get("pages", [])

        except (OSError, json.JSONDecodeError, KeyError):

            continue

        document = syllabus.get("document", {})

        

        starts = []

        for index, page in enumerate(pages):

            ptext = page.get("text", "")

            code = COURSE_CODE.search(ptext)

            has_course_objectives = "Course Objective" in ptext or "Course Outcome" in ptext

            has_lab_objectives = "Lab Objective" in ptext or "Lab Outcome" in ptext or "Suggested List of Experiments" in ptext

            has_project = "Program Outcomes addressed" in ptext or ("Guidelines for" in ptext and "Project" in ptext)

            if code and (has_course_objectives or has_lab_objectives or has_project):

                starts.append((index, code.group()))

                

        for section_index, (start, code) in enumerate(starts):

            end = starts[section_index + 1][0] if section_index + 1 < len(starts) else len(pages)

            section_pages = pages[start:end]

            if not section_pages:

                continue

            header_text = section_pages[0].get("text", "")

            code_match = COURSE_CODE.search(header_text)

            header = header_text[code_match.end() : code_match.end() + 120] if code_match else ""

            

            module_pages = [

                p for p in section_pages

                if re.search(r"(?m)^\s*[1-6]\.0", p.get("text", "")) and re.search(r"(?i)self.?learning", p.get("text", ""))

            ]

            module_outlines = extract_module_outlines(section_pages)

            lab_pages = []

            in_lab_content = False

            for p in section_pages:

                t = p.get("text", "")

                stop = re.search(r"(?im)^\s*(Course Assessment:|End Semester Examination:)", t)

                if stop:

                    t = t[: stop.start()]

                if t.strip():

                    lab_pages.append({**p, "text": t.strip()})

                if stop:

                    break

                if "Lab Objective" in t or "Suggested List of Experiments" in t:

                    in_lab_content = True

                elif in_lab_content and "Lab Outcomes" not in t and not re.search(r"(?i)(?:LO\d|Sr\.?\s*No\.?|Title of Experiments)", t) and not re.search(r"(?im)^\s*(Textbooks:|Reference books:|Online References:)", t):

                    pass

            content_pages = module_pages if module_pages else section_pages

            has_lab_content = any(LAB_REQUEST.search(p.get("text", "")) for p in section_pages)

            

            all_sections.append({

                "code": code,

                "header": header,

                "text": "\n\n".join(p.get("text", "") for p in section_pages),

                "pages": content_pages,

                "all_pages": section_pages,

                "overview_page": section_pages[0],

                "module_pages": module_pages,

                "module_outlines": module_outlines,

                "lab_pages": lab_pages if has_lab_content else [],

                "filename": document.get("filename", "Unknown PDF"),

                "url": document.get("source_url", ""),

            })

    return tuple(all_sections)





def _bm25_scores(query: str, documents: list[str]) -> list[float]:

    query_terms = set(_tokenize(query))

    if not query_terms or not documents:

        return [0.0] * len(documents)



    tokenized_documents = [_tokenize(document) for document in documents]

    frequencies = [Counter(tokens) for tokens in tokenized_documents]

    document_frequency = {

        term: sum(term in counts for counts in frequencies) for term in query_terms

    }

    average_length = max(

        sum(map(len, tokenized_documents)) / len(tokenized_documents),

        1.0,

    )



    scores = []

    for tokens, counts in zip(tokenized_documents, frequencies):

        score = 0.0

        for term in query_terms:

            term_frequency = counts[term]

            if not term_frequency:

                continue

            inverse_frequency = math.log(

                1

                + (len(documents) - document_frequency[term] + 0.5)

                / (document_frequency[term] + 0.5)

            )

            length_factor = 1.2 * (0.3 + 0.7 * len(tokens) / average_length)

            score += (

                inverse_frequency

                * term_frequency

                * 2.2

                / (term_frequency + length_factor)

            )

        scores.append(score)

    return scores





def _retrieve_course_section(question: str) -> list[dict] | None:

    sections = _course_sections()

    if not sections:

        return None
    try:
        from rag.generator import resolve_all_course_codes_from_query
        detected_codes = resolve_all_course_codes_from_query(question)
        if len(detected_codes) > 1:
            sections_by_code = {s.get('code'): s for s in sections}
            matched_sections = [sections_by_code[c] for c in detected_codes if c in sections_by_code]
            if len(matched_sections) == len(detected_codes):
                multi_chunks = []
                for sec in matched_sections:
                    for p_item in sec.get('pages', []):
                        if p_item.get('text'):
                            multi_chunks.append({
                                'text': p_item['text'],
                                'metadata': {
                                    'filename': sec.get('filename'),
                                    'page': p_item.get('page_number'),
                                    'url': sec.get('url'),
                                    'course_code': sec.get('code'),
                                },
                            })
                if multi_chunks:
                    return multi_chunks
    except Exception:
        pass

    requested = _requested_semesters(question)



    scores = _bm25_scores(question, [section["text"] for section in sections])

    query_tokens = set(_tokenize(question))

    code_match = COURSE_CODE.search(question.upper())

    is_outline_request = bool(OUTLINE_REQUEST.search(question))

    is_lab_request = bool(LAB_REQUEST.search(question))

    is_books_request = bool(re.search(r"\b(references?|textbooks?|books?|online references?|online resources?|software tools?|hardware tools?|tools?|assignments?|useful links?|web resources?|bibliography)\b", question, re.IGNORECASE))

    is_assessment_request = bool(re.search(r"\b(evaluat\w*|assess\w*|exam\w*|scheme|marks?|grading|graded|grades?|weightage|ciap|esep?|ise|mse|term\s*work|passing criteria|criteria)\b", question, re.IGNORECASE))

    generic_title_terms = {

        "engineer",

        "engineering",

        "lab",

        "labs",

        "practical",

        "practicals",

        "experiment",

        "experiments",

        "i",

        "ii",

        "iii",

        "iv",

        "v",

        "vi",

        "vii",

        "viii",

    }

    is_roman_one = bool(re.search(r"(?:math(?:ematics)?|applied|project|physics|chemistry|mechanics|bee|graphics|part|sem(?:ester)?)\s*[-:]?\s*(?:1|i)\b", question, re.IGNORECASE))

    ranked_sections = []

    for section, score in zip(sections, scores):

        if code_match and section["code"] != code_match.group():

            continue

        # if is_outline_request and not is_lab_request and section["lab_pages"]:

        #     continue



        title_tokens = set(_tokenize(section["header"]))

        title_overlap = query_tokens & title_tokens

        subject_overlap = {

            token for token in title_overlap if not token.isdigit()

        } - generic_title_terms

        query_subject_tokens = {

            token for token in query_tokens if not token.isdigit()

        } - generic_title_terms

        if "computer" in query_tokens and ("engineer" in query_tokens or "engineering" in query_tokens):

            subject_overlap.discard("computer")

            query_subject_tokens.discard("computer")

        content_overlap = query_tokens & set(_tokenize(section["text"]))

        content_overlap = {token for token in content_overlap if not token.isdigit()}



        module_headers = re.findall(r"(?im)^\s*\d+\.0\s+(.+?)\s+\d+\s*$", section["text"])

        module_tokens = set()

        for h in module_headers:

            module_tokens.update(_tokenize(h))

        module_overlap = {token for token in (query_tokens & module_tokens) if not token.isdigit()}



        if is_outline_request and not subject_overlap and not code_match and not module_overlap:

            continue

        # Ratio check removed

        if is_lab_request and not subject_overlap and not code_match and not module_overlap:

            continue

        if not code_match and not subject_overlap and not module_overlap:

            continue



        cname = extract_course_name_from_header(section["header"])

        raw_cname_tokens = {t for t in _tokenize(cname) if not t.isdigit()}

        cname_levels = {NUM_TO_ROMAN[t] for t in raw_cname_tokens if t in NUM_TO_ROMAN}

        cname_tokens = raw_cname_tokens - generic_title_terms



        if cname_tokens and cname_tokens.issubset(query_tokens):

            score += 60.0

        elif cname_tokens and len(cname_tokens & query_tokens) >= 2 and len(cname_tokens & query_tokens) / len(cname_tokens) >= 0.66:

            score += 40.0



        score += len(subject_overlap) * 2.0

        score += len(module_overlap) * 1.5

        if code_match:

            score += 100.0



        # Check course level / roman numerals (e.g. Mathematics-III vs Mathematics-IV)

        query_levels = set()

        for t in query_tokens:

            if t in NUM_TO_ROMAN:

                if t == "i" and not is_roman_one:

                    continue

                query_levels.add(NUM_TO_ROMAN[t])



        if query_levels and cname_levels:

            if query_levels == cname_levels:

                score += 35.0

            else:

                score -= 50.0

        elif query_levels and not cname_levels:

            score -= 10.0



        distinguishing_words = {"advanced", "advance", "intro", "introduction", "basics", "basic", "applied", "application", "fundamentals", "principles", "design"}

        extra_distinguishing = (title_tokens & distinguishing_words) - query_tokens

        if extra_distinguishing:

            score -= 5.0

            

        if not is_lab_request and not re.search(r"\blab\b", section["header"], re.IGNORECASE):

            score += 5.0

        elif is_lab_request and re.search(r"\blab\b", section["header"], re.IGNORECASE):

            score += 10.0

            

        ranked_sections.append((score, section, bool(subject_overlap)))



    if not ranked_sections:

        return None



    best_score, best_section, title_match = max(

        ranked_sections,

        key=lambda item: item[0],

    )

    if best_score <= 0:

        return None

    if not code_match and not title_match and best_score < 1.5:

        return None



    is_strict_module_request = bool(re.search(r"\b(syllabus|curriculum|modules?|topics?|self.?learning|course content|course outline)\b", question, re.IGNORECASE))

    

    if is_books_request and "all_pages" in best_section:

        selected_pages = best_section["all_pages"]

    elif is_assessment_request and "all_pages" in best_section:

        selected_pages = best_section["all_pages"]

    elif is_outline_request and is_lab_request and best_section["lab_pages"]:

        selected_pages = best_section["lab_pages"]

    elif is_outline_request and is_strict_module_request and best_section["module_outlines"]:

        selected_modules = select_requested_modules(

            question,

            best_section["module_outlines"],

        )

        return [

            {

                "text": module["text"],

                "metadata": {

                    "filename": best_section["filename"],

                    "page": module["pages"][0],

                    "pages": module["pages"],

                    "url": best_section["url"],

                    "course_code": best_section["code"],

                    "course_outline": True,

                },

            }

            for module in selected_modules

        ]

    elif is_outline_request and is_strict_module_request and best_section["module_pages"]:

        selected_pages = best_section["module_pages"]

    else:

        selected_pages = best_section["pages"]



    return [

        {

            "text": page["text"],

            "metadata": {

                "filename": best_section["filename"],

                "page": page["page_number"],

                "url": best_section["url"],

                "course_code": best_section["code"],

                "course_outline": is_outline_request,

            },

        }

        for page in selected_pages

        if page.get("text")

    ]





def retrieve_relevant_chunks(question: str, top_k: int = 10):

    forced_results = []

    

    is_semester_catalog = (

        SEMESTER_MARKER.search(question) is not None

        and COURSE_CODE.search(question.upper()) is None

        and re.search(r"\bmodules?\b", question, re.IGNORECASE) is None

        and not LAB_REQUEST.search(question)

    )

    is_broad_semester_range = (

        SEMESTER_RANGE.search(question) is not None

        and COURSE_CODE.search(question.upper()) is None

        and re.search(r"\bmodules?\b", question, re.IGNORECASE) is None

        and not LAB_REQUEST.search(question)

    )

    

    is_credit_query = bool(

        re.search(r"\b(credit distribution|credits? distribution|total credits?|degree credits?|credits? for (?:the )?(?:b\.?tech|degree|program|engineering))\b", question, re.IGNORECASE)

    )



    if is_semester_catalog or is_broad_semester_range or is_credit_query:

        semester_results = _retrieve_semester_structures(question)

        if semester_results:

            return semester_results



    section_results = _retrieve_course_section(question)

    if section_results:

        return section_results

        

    semester_results = _retrieve_semester_structures(question)

    if semester_results:

        return semester_results





    collection_size = collection.count()

    if not collection_size:

        return []



    candidate_count = min(collection_size, 3000)

    query_embedding = create_embedding(question)

    results = collection.query(

        query_embeddings=[query_embedding],

        n_results=candidate_count,

        include=["documents", "metadatas", "distances"],

    )



    documents = results.get("documents", [[]])[0] or []

    metadatas = results.get("metadatas", [[]])[0] or []

    distances = results.get("distances", [[]])[0] or []

    lexical_scores = _bm25_scores(question, documents)

    if not any(score > 0 for score in lexical_scores) and (

        not distances or min(distances) > 0.85

    ):

        return []



    dense_order = sorted(

        range(len(documents)),

        key=lambda index: distances[index] if index < len(distances) else float("inf"),

    )

    lexical_order = sorted(

        (index for index, score in enumerate(lexical_scores) if score > 0),

        key=lambda index: lexical_scores[index],

        reverse=True,

    )

    dense_ranks = {index: rank for rank, index in enumerate(dense_order, start=1)}

    lexical_ranks = {index: rank for rank, index in enumerate(lexical_order, start=1)}



    ranked_indices = sorted(

        (

            index

            for index in range(len(documents))

            if lexical_scores[index] > 0

            or (index < len(distances) and distances[index] <= 0.85)

        ),

        key=lambda index: (

            max(

                1 / (60 + dense_ranks[index]),

                1 / (60 + lexical_ranks[index]) if index in lexical_ranks else 0

            ),

            lexical_scores[index],

        ),

        reverse=True,

    )

    file_scores = Counter()

    for rank, index in enumerate(ranked_indices[: max(top_k, 3)]):

        metadata = metadatas[index] or {}

        filename = metadata.get("filename")

        if filename:

            file_scores[filename] += 1.0 / (2 ** rank)

    if file_scores:

        best_filename = file_scores.most_common(1)[0][0]

        ranked_indices = [

            index

            for index in ranked_indices

            if (metadatas[index] or {}).get("filename") == best_filename

        ]



    dense_results = [

        {"text": documents[index], "metadata": metadatas[index]}

        for index in ranked_indices[:top_k]

    ]

    

    final_results = list(forced_results)

    seen = { (r["metadata"].get("page"), r["metadata"].get("filename"), r["text"]) for r in final_results }

    for r in dense_results:

        key = (r["metadata"].get("page"), r["metadata"].get("filename"), r["text"])

        if key not in seen:

            seen.add(key)

            final_results.append(r)

    

    return final_results[:top_k]











