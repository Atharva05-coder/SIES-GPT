import json
from pathlib import Path

from pypdf import PdfReader

BASE_DIR = Path(__file__).resolve().parent
PDF_PATH = BASE_DIR / "data" / "TE CE R24 (1).pdf"
OUTPUT_PATH = BASE_DIR / "data" / "te_ce_r24_structured.json"
SOURCE_URL = "https://siesgst.edu.in/images/TE%20CE%20R24%20(1).pdf"

SEMESTER_V_COURSES = [
    {
        "code": "CEC501",
        "name": "Theoretical Computer Science",
        "category": "PCC",
        "credits": 3,
    },
    {"code": "CEC502", "name": "Software Engineering", "category": "PCC", "credits": 3},
    {"code": "CEC503", "name": "Computer Network", "category": "PCC", "credits": 3},
    {
        "code": "MDMC50X2",
        "name": "Multidisciplinary Minor (MDM-II)",
        "category": "MDM",
        "credits": 3,
    },
    {
        "code": "CEPEC501X",
        "name": "Program Elective-I",
        "category": "PEC",
        "credits": 3,
    },
    {"code": "CEL501", "name": "DevOps Lab", "category": "PCC", "credits": 1},
    {"code": "CEL502", "name": "Computer Network Lab", "category": "PCC", "credits": 1},
    {
        "code": "CEL503",
        "name": "Interpersonal and Career Skills",
        "category": "HSSM (AEC)",
        "credits": 2,
    },
    {
        "code": "MDML50X1",
        "name": "Multidisciplinary Minor (MDM-II) Lab/Tutorial",
        "category": "MDM",
        "credits": 1,
    },
    {
        "code": "CEPEL501X",
        "name": "Program Elective-I Lab",
        "category": "PEC",
        "credits": 1,
    },
    {"code": "CEM501", "name": "Mini Project 2", "category": "Project", "credits": 1},
]


def main() -> None:
    reader = PdfReader(str(PDF_PATH))
    pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        resources = page.get("/Resources") or {}
        xobjects = resources.get("/XObject") or {}
        has_image = any(
            reference.get_object().get("/Subtype") == "/Image"
            for reference in xobjects.values()
        )
        extraction_status = (
            "text_extracted"
            if text
            else "image_only_requires_ocr" if has_image else "no_text"
        )
        pages.append(
            {
                "page_number": page_number,
                "text": text,
                "extraction_status": extraction_status,
            }
        )

    data = {
        "schema_version": 1,
        "document": {
            "filename": PDF_PATH.name,
            "source_url": SOURCE_URL,
            "program": "Bachelor of Engineering",
            "department": "Computer Engineering",
            "page_count": len(pages),
            "pages_needing_ocr": [
                page["page_number"]
                for page in pages
                if page["extraction_status"] == "image_only_requires_ocr"
            ],
        },
        "pages": pages,
        "curricula": [
            {
                "year": "Third Year",
                "semester": 5,
                "academic_year": "2026-27",
                "department": "Computer Engineering",
                "source_page": 11,
                "courses": SEMESTER_V_COURSES,
            }
        ],
    }

    OUTPUT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(pages)} pages and {len(SEMESTER_V_COURSES)} Semester V courses to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
