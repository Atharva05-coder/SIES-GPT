import re


# ============================================================
# COURSE DEFINITIONS
# ============================================================

COURSES = {
    "CEC501": "Theoretical Computer Science",
    "CEC502": "Software Engineering",
    "CEC503": "Computer Network",

    "CEPEC5011": "Advanced Database Management System",
    "CEPEC5012": "Internet of Things",
    "CEPEC5013": "Ethical Hacking",
    "CEPEC5014": "Data Warehouse and Mining",

    "CEC601": "System Programming and Compiler Construction",
    "CEC602": "Cryptography and Network Security",
    "CEC603": "Artificial Intelligence and Soft Computing",

    "CEPEC6011": "Machine Vision",
    "CEPEC6012": "Robotics and Applications",
    "CEPEC6013": "Digital Forensics",
    "CEPEC6014": "Natural Language Processing",
}


# ============================================================
# REGEX PATTERNS
# ============================================================

# Known course codes
COURSE_CODE_RE = re.compile(
    r"\b("
    + "|".join(re.escape(code) for code in COURSES)
    + r")\b",
    re.IGNORECASE
)


# Example:
# 1.0 Introduction to Networking 6
# 2.0 Data Link Layer 8
MODULE_RE = re.compile(
    r"^\s*(\d+)\.0\s+(.+?)\s+(\d+)\s*$",
    re.IGNORECASE
)


# Example:
# 1.1 Definition...
# 1.2 Network Models...
# 3.3 Network Layer Protocols...
#
# Anchored to beginning of line so that:
# 802.11
# 802.15
# 802.16
#
# are NOT interpreted as units.
UNIT_MARKER_RE = re.compile(
    r"^\s*(\d+)\.(\d+)(?=\s|$)"
)


# PDF extraction can produce:
#
# CO1 1.2 Basic Text Processing...
#
CO_UNIT_RE = re.compile(
    r"^\s*CO\d+\s+(\d+)\.(\d+)\s*(.*)$",
    re.IGNORECASE
)


# Self-learning
SELF_LEARNING_RE = re.compile(
    r"^\s*Self[- ]Learning(?:\s+Topics?)?\s*:?\s*(.*)$",
    re.IGNORECASE
)


# Generic course-code pattern.
#
# Used for course codes which are not present in COURSES,
# such as MDM / lab / other course codes.
GENERIC_COURSE_CODE_RE = re.compile(
    r"^(?:CEC|CEPEC|CEL|CEPEL|MDMC|MDML|CEM)"
    r"[A-Z0-9]+$",
    re.IGNORECASE
)


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_line(line: str) -> str:
    """
    Normalize whitespace.
    """

    return re.sub(
        r"\s+",
        " ",
        line
    ).strip()


# ============================================================
# SPLIT LONG TEXT
# ============================================================

def split_long_text(
    text: str,
    max_chars: int = 1200
):
    """
    Split long text into smaller chunks.

    Metadata is applied to every resulting chunk.
    """

    text = text.strip()

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    chunks = []

    start = 0

    while start < len(text):

        end = start + max_chars

        piece = text[start:end].strip()

        if piece:
            chunks.append(piece)

        start = end

    return chunks


# ============================================================
# COURSE DETECTION
# ============================================================

def detect_course(text: str):
    lines = [clean_line(line) for line in text.splitlines() if clean_line(line)]
    for line in lines[:30]:
        m = re.search(r"([A-Z]{2,6}[C]?\s*\d{3,4})\s*[:\-]?\s*(.+)", line, re.IGNORECASE)
        if m:
            course_code = m.group(1).replace(" ", "").upper()
            course_name = m.group(2).strip()
            if len(course_name) < 5:
                name_match = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", line)
                if name_match:
                    course_name = name_match.group(1)
            if "course code" in course_code.lower() or "course name" in course_name.lower():
                continue
            return {"course_code": course_code, "course_name": course_name}
    return None


# ============================================================
# COURSE BOUNDARIES
# ============================================================

def assign_course_boundaries(pages):
    """
    Assign each page to the currently active course.

    The current course changes ONLY when detect_course()
    finds an actual course header.
    """

    current_course = None

    result = []

    for page in pages:

        detected = detect_course(
            page["text"]
        )

        if detected is not None:

            current_course = detected

        result.append({
            "page": page["page"],
            "text": page["text"],
            "course": current_course if current_course else {"course_code": "GLOBAL", "course_name": "General Information"}
        })

    return result


# ============================================================
# MAIN SYLLABUS CHUNKER
# ============================================================

def chunk_syllabus_pages(
    pages,
    filename
):
    """
    Convert PDF pages into structured chunks.

    Each chunk contains:

        filename
        course_code
        course_name
        module_no
        module_name
        unit_no
        unit_name
        section_type
        is_self_learning
        page

    All courses remain in ONE Chroma collection.
    """

    pages_with_courses = assign_course_boundaries(
        pages
    )

    chunks = []

    chunk_counter = 0

    # ========================================================
    # CURRENT COURSE
    # ========================================================

    current_course_code = None
    current_course_name = None

    # ========================================================
    # CURRENT MODULE
    # ========================================================

    current_module_no = None
    current_module_name = None

    # ========================================================
    # CURRENT UNIT
    # ========================================================

    current_unit_no = None
    current_unit_name = None

    # ========================================================
    # CURRENT SECTION
    # ========================================================

    current_section_type = "general"

    current_is_self_learning = False

    # ========================================================
    # CURRENT TEXT
    # ========================================================

    current_text = []

    current_page = None

    # ========================================================
    # FLUSH CURRENT TEXT
    # ========================================================

    def flush():

        nonlocal chunk_counter
        nonlocal current_text

        if not current_text:
            return

        text = "\n".join(
            current_text
        ).strip()

        if not text:

            current_text = []

            return

        pieces = split_long_text(
            text,
            max_chars=1200
        )

        for piece in pieces:

            chunk_id = (
                f"{current_course_code}_"
                f"p{current_page}_"
                f"m{current_module_no or 'x'}_"
                f"u{current_unit_no or 'x'}_"
                f"{chunk_counter}"
            )

            chunks.append({

                "id": chunk_id,

                "text": piece,

                "metadata": {

                    "filename": filename,

                    "course_code":
                        current_course_code,

                    "course_name":
                        current_course_name,

                    "module_no":
                        current_module_no,

                    "module_name":
                        current_module_name,

                    "unit_no":
                        current_unit_no,

                    "unit_name":
                        current_unit_name,

                    "section_type":
                        current_section_type,

                    "is_self_learning":
                        current_is_self_learning,

                    "page":
                        current_page,
                }
            })

            chunk_counter += 1

        current_text = []

    # ========================================================
    # PROCESS ALL PAGES
    # ========================================================

    for page_record in pages_with_courses:

        page_number = page_record["page"]

        text = page_record["text"]

        course = page_record["course"]

        # ----------------------------------------------------
        # Ignore pages before the first detected course.
        # ----------------------------------------------------



        new_course_code = course[
            "course_code"
        ]

        new_course_name = course[
            "course_name"
        ]

        # ====================================================
        # COURSE CHANGED
        # ====================================================

        if (
            current_course_code is not None
            and new_course_code != current_course_code
        ):

            # Save previous course's pending text.
            flush()

            # ------------------------------------------------
            # RESET ALL STRUCTURAL STATE
            # ------------------------------------------------

            current_module_no = None
            current_module_name = None

            current_unit_no = None
            current_unit_name = None

            current_section_type = "general"

            current_is_self_learning = False

            current_text = []

            current_page = None

        # ----------------------------------------------------
        # Set current course.
        # ----------------------------------------------------

        current_course_code = new_course_code

        current_course_name = new_course_name

        # ====================================================
        # PROCESS LINES
        # ====================================================

        for raw_line in text.splitlines():

            line = clean_line(
                raw_line
            )

            if not line:
                continue

            # =================================================
            # STANDALONE COURSE CODE
            # =================================================

            if COURSE_CODE_RE.fullmatch(
                line
            ):

                continue

            # =================================================
            # SELF-LEARNING
            # =================================================

            self_match = SELF_LEARNING_RE.match(
                line
            )

            if self_match:

                flush()

                current_unit_no = None

                current_unit_name = None

                current_section_type = (
                    "self_learning"
                )

                current_is_self_learning = True

                current_page = page_number

                content = (
                    self_match
                    .group(1)
                    .strip()
                )

                if content:

                    current_text = [
                        "Self-Learning: "
                        + content
                    ]

                else:

                    current_text = [
                        "Self-Learning:"
                    ]

                continue

            # =================================================
            # MODULE
            # =================================================

            module_match = MODULE_RE.match(
                line
            )

            if module_match:

                flush()

                current_module_no = (
                    module_match.group(1)
                )

                current_module_name = (
                    module_match
                    .group(2)
                    .strip()
                )

                current_unit_no = None

                current_unit_name = None

                current_section_type = (
                    "module"
                )

                current_is_self_learning = False

                current_page = page_number

                current_text = [
                    line
                ]

                continue

            # =================================================
            # UNIT WITH CO PREFIX
            #
            # Example:
            #
            # CO1 1.2 Basic Text Processing
            # =================================================

            co_unit_match = CO_UNIT_RE.match(
                line
            )

            if co_unit_match:

                unit_module = (
                    co_unit_match
                    .group(1)
                )

                unit_number = (
                    co_unit_match
                    .group(2)
                )

                unit_content = (
                    co_unit_match
                    .group(3)
                    .strip()
                )

                # Only accept the unit if it belongs
                # to the current module.

                if (
                    current_module_no is not None
                    and unit_module ==
                    current_module_no
                ):

                    flush()

                    current_unit_no = (
                        f"{unit_module}."
                        f"{unit_number}"
                    )

                    current_unit_name = (
                        unit_content
                    )

                    current_section_type = (
                        "unit"
                    )

                    current_is_self_learning = False

                    current_page = page_number

                    current_text = []

                    if unit_content:

                        current_text.append(
                            unit_content
                        )

                    continue

            # =================================================
            # NORMAL UNIT
            #
            # Example:
            #
            # 1.1 Definition...
            # 2.1 Introduction...
            # =================================================

            unit_match = UNIT_MARKER_RE.match(
                line
            )

            if unit_match:

                unit_module = (
                    unit_match
                    .group(1)
                )

                unit_number = (
                    unit_match
                    .group(2)
                )

                # Unit must belong to active module.

                if (
                    current_module_no is not None
                    and unit_module ==
                    current_module_no
                ):

                    unit_content = (
                        line[
                            unit_match.end():
                        ].strip()
                    )

                    flush()

                    current_unit_no = (
                        f"{unit_module}."
                        f"{unit_number}"
                    )

                    current_unit_name = (
                        unit_content
                    )

                    current_section_type = (
                        "unit"
                    )

                    current_is_self_learning = False

                    current_page = page_number

                    current_text = []

                    if unit_content:

                        current_text.append(
                            unit_content
                        )

                    continue

            # =================================================
            # NORMAL CONTENT
            # =================================================

            if not current_text:

                current_page = page_number

            current_text.append(
                line
            )

    # ========================================================
    # FLUSH FINAL CHUNK
    # ========================================================

    flush()

    return chunks
