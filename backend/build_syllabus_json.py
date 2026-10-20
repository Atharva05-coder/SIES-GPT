import json
import os
import glob
from pathlib import Path
from pypdf import PdfReader
from dotenv import load_dotenv

# Use the shiny new agents library for guaranteed structured output with Gemini!
from agents import Agent, Runner, set_tracing_disabled
from pydantic import BaseModel, Field

set_tracing_disabled(True)
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

class Course(BaseModel):
    code: str = Field(description="Course Code (e.g., CEC501)")
    name: str = Field(description="Course Name")
    category: str = Field(description="Category (e.g., PCC, PEC, MDM, Lab)")
    credits: int = Field(description="Credits")

class Curriculum(BaseModel):
    courses: list[Course]

from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel

extractor_agent = Agent(
    "curriculum_extractor",
    instructions="""You are an expert Data Engineer. Extract the course curriculum list from the university syllabus text provided below.
Identify the main courses (PCC), Electives (PEC), Minors (MDM), and Labs.
Cross-reference the modules to ensure you get all course names and codes correctly.""",
    model=OpenAIChatCompletionsModel(
        "",
        openai_client=AsyncOpenAI(
            api_key=os.getenv("LLM_API_KEY", "V7mQ2xL9pR4kT8nC"), 
            base_url=os.getenv("LLM_BASE_URL", "https://llama.atharva-amrutkar.in/v1")
        ),
    ),
    output_type=Curriculum
)

import asyncio

async def extract_curriculum_via_llm(syllabus_text_sample: str) -> list:
    """Uses Gemini via Agents library to dynamically extract the course nomenclature."""
    try:
        # Pass the first ~7k chars to ensure we don't blow out the local model's token limit (n_ctx=4096)
        result = await Runner.run(extractor_agent, f"Syllabus Sample Text:\n\n{syllabus_text_sample[:7000]}")
        curriculum = result.final_output_as(Curriculum)
        return [course.model_dump() for course in curriculum.courses]
    except Exception as e:
        print(f"  [Warning] Gemini Extraction failed: {e}. Defaulting to empty list.")
        return []

async def process_pdf(pdf_path: Path):
    output_filename = pdf_path.stem.lower().replace(" ", "_").replace("(", "").replace(")", "") + "_structured.json"
    output_path = DATA_DIR / output_filename

    print(f"Processing {pdf_path.name}...")
    reader = PdfReader(str(pdf_path))
    pages = []
    
    # Extract text and check for images
    first_pages_text = ""
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        
        # Capture first 25 pages for LLM curriculum extraction
        if page_number <= 25:
            first_pages_text += text + "\n"
            
        resources = page.get("/Resources") or {}
        xobjects = resources.get("/XObject") or {}
        has_image = any(
            reference.get_object().get("/Subtype") == "/Image"
            for reference in xobjects.values()
            if hasattr(reference, "get_object")
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

    print("  Extracting curriculum metadata via Gemini...")
    courses_list = await extract_curriculum_via_llm(first_pages_text)

    data = {
        "schema_version": 1,
        "document": {
            "filename": pdf_path.name,
            "source_url": f"https://siesgst.edu.in/images/{pdf_path.name}",
            "program": "Bachelor of Engineering",
            "department": "Unknown Department",
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
                "year": "Unknown",
                "semester": 0,
                "academic_year": "2026-27",
                "department": "Unknown",
                "source_page": 1,
                "courses": courses_list,
            }
        ],
    }

    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"  Saved {len(pages)} pages and {len(courses_list)} courses to {output_filename}")

async def main() -> None:
    pdf_files = glob.glob(str(DATA_DIR / "*.pdf"))
    if not pdf_files:
        print("No PDF files found in data directory.")
        return
        
    for pdf_file in pdf_files:
        await process_pdf(Path(pdf_file))

if __name__ == "__main__":
    asyncio.run(main())
