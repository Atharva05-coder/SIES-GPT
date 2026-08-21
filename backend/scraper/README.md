# SIES GST PDF Scraper — RAG Pipeline Ready

A production-grade Python scraper that crawls `https://siesgst.edu.in/` and extracts all PDF links with rich metadata, optimized for **Retrieval-Augmented Generation (RAG)** pipelines.

## Features

| Feature | Description |
|---------|-------------|
| **Recursive Crawling** | Discovers PDFs across the entire site with configurable depth |
| **Rich Metadata** | Filename, title, context text, source page, department, category, file size, last-modified |
| **RAG-Optimized Output** | JSON manifest with pre-built `content_for_embedding` fields |
| **Duplicate Detection** | SHA-256 hashing prevents duplicate entries |
| **Resume Capability** | Saves progress — safe to interrupt and resume later |
| **Rate Limiting** | Polite crawling with configurable delays |
| **Retry Logic** | Exponential backoff for transient failures |
| **Category Inference** | Auto-tags PDFs as syllabus, notice, brochure, timetable, etc. |
| **Department Detection** | Infers department (CE, IT, EXTC, AI&DS, etc.) from context |

## Installation

```bash
pip install -r requirements.txt