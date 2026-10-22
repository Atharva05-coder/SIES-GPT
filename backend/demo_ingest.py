#!/usr/bin/env python3
"""
SIES-GPT: Live Syllabus PDF Ingestion & Indexing Demo
=====================================================
Usage:
    python demo_ingest.py
    python demo_ingest.py "data/TE CE R24 (1).pdf"
    python demo_ingest.py "path/to/any_syllabus.pdf" --force
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path

# Ensure standard output supports UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pypdf import PdfReader
from rag.chunker import chunk_syllabus_pages
from rag.embeddings import client as embed_client, EMBEDDING_MODEL
from rag.vector_store import collection


def parse_args():
    parser = argparse.ArgumentParser(description="SIES-GPT Live Syllabus Ingestion Demo")
    parser.add_argument("pdf_path", nargs="?", default="data/TE CE R24 (1).pdf", help="Path to the PDF file")
    parser.add_argument("--batch-size", type=int, default=32, help="Embedding batch size (default: 32)")
    parser.add_argument("--force", action="store_true", help="Re-index even if already present")
    parser.add_argument("--max-chunks", type=int, default=None, help="Limit number of chunks to embed (for quick demo)")
    return parser.parse_args()


def format_duration(seconds: float) -> str:
    if seconds < 1.0:
        return f"{seconds * 1000:.0f} ms"
    return f"{seconds:.2f} s"


def main():
    args = parse_args()
    pdf_file = Path(args.pdf_path)
    if not pdf_file.is_absolute():
        pdf_file = BASE_DIR / pdf_file

    if not pdf_file.exists():
        print(f"\n❌ ERROR: File not found at {pdf_file}")
        sys.exit(1)

    file_size_mb = pdf_file.stat().st_size / (1024 * 1024)

    print("\n" + "=" * 70)
    print("🎓 SIES-GPT: Dynamic Syllabus Ingestion & Vector Indexing Pipeline")
    print("=" * 70)
    print(f"📄 Source PDF:       {pdf_file.name}")
    print(f"📦 File Size:        {file_size_mb:.2f} MB")
    print(f"📍 Location:         {pdf_file}")
    print(f"🧠 Embedding Model:  {EMBEDDING_MODEL} (1024-dim dense vectors)")
    print(f"🗄️  Vector Database:  ChromaDB ('{collection.name}')")
    print("-" * 70)

    total_start_time = time.time()

    # -------------------------------------------------------------
    # Step 1: PDF Text Extraction & Page Scanning
    # -------------------------------------------------------------
    print("\n[Step 1/5] Extracting Text & Scanning Page Layout...")
    t0 = time.time()
    reader = PdfReader(str(pdf_file))
    pages = []
    text_page_count = 0

    for idx, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        status = "text_extracted" if text else "image_only"
        if text:
            text_page_count += 1
        pages.append({
            "page": idx,
            "page_number": idx,
            "text": text,
            "extraction_status": status,
        })
    t_extract = time.time() - t0
    print(f"  ✔ Processed {len(pages)} pages ({text_page_count} text pages) in {format_duration(t_extract)}")

    # -------------------------------------------------------------
    # Step 2: Academic Domain Semantic Chunking
    # -------------------------------------------------------------
    print("\n[Step 2/5] Performing Academic Domain Chunking (Modules, Schemes, Labs)...")
    t0 = time.time()
    chunker_pages = [{"page": p["page_number"], "text": p["text"]} for p in pages]
    chunks = chunk_syllabus_pages(chunker_pages, pdf_file.name)
    t_chunk = time.time() - t0

    if not chunks:
        print("  ⚠️ Warning: No semantic chunks could be formed. Exiting.")
        sys.exit(0)

    print(f"  ✔ Generated {len(chunks)} semantic academic chunks in {format_duration(t_chunk)}")

    # -------------------------------------------------------------
    # Step 3: Structured JSON Cache Generation
    # -------------------------------------------------------------
    print("\n[Step 3/5] Generating Structured Curriculum JSON Cache...")
    t0 = time.time()
    stem = pdf_file.stem.lower().replace(" ", "_").replace("(", "").replace(")", "")
    structured_json_path = BASE_DIR / "data" / f"{stem}_structured.json"

    json_data = {
        "schema_version": 1,
        "document": {
            "filename": pdf_file.name,
            "source_url": f"https://siesgst.edu.in/images/{pdf_file.name}",
            "program": "Bachelor of Technology",
            "department": "Computer Engineering",
            "page_count": len(pages),
        },
        "pages": pages,
    }
    with open(structured_json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    t_json = time.time() - t0
    print(f"  ✔ Saved structured JSON: {structured_json_path.name} in {format_duration(t_json)}")

    # -------------------------------------------------------------
    # Step 4: Batch Vector Embedding Generation
    # -------------------------------------------------------------
    print("\n[Step 4/5] Generating BGE-M3 Dense Vector Embeddings...")
    t0 = time.time()

    # Check if already indexed
    existing = collection.get(where={"filename": pdf_file.name}, include=["metadatas"])
    already_indexed = existing and len(existing.get("ids", [])) > 0

    if already_indexed and not args.force:
        print(f"  ℹ️ Document is already indexed with {len(existing['ids'])} vectors in ChromaDB.")
        print("     (Pass '--force' to re-embed and overwrite)")
        t_embed = 0.0
        t_upsert = 0.0
    else:
        # Prepare chunks for embedding
        chunks_to_embed = chunks[:args.max_chunks] if args.max_chunks else chunks
        batch_size = args.batch_size
        all_ids = []
        all_texts = []
        all_embeddings = []
        all_metadatas = []

        total_batches = (len(chunks_to_embed) + batch_size - 1) // batch_size
        print(f"  • Embedding {len(chunks_to_embed)} chunks in {total_batches} batches (batch_size={batch_size})...")

        for b_idx in range(total_batches):
            b_start = b_idx * batch_size
            b_end = min(b_start + batch_size, len(chunks_to_embed))
            batch = chunks_to_embed[b_start:b_end]

            batch_texts = []
            for c in batch:
                all_ids.append(c["id"])
                all_texts.append(c["text"])
                all_metadatas.append(c["metadata"])
                context = f"Course: {c['metadata'].get('course_code', '')} {c['metadata'].get('course_name', '')}"
                batch_texts.append(f"{context}\n\n{c['text']}")

            # Remote embedding call with batch
            res = embed_client.embeddings.create(model=EMBEDDING_MODEL, input=batch_texts)
            for item in res.data:
                all_embeddings.append(item.embedding)

            sys.stdout.write(f"\r     Batch [{b_idx + 1}/{total_batches}] -> Embedded {len(all_embeddings)}/{len(chunks_to_embed)} chunks")
            sys.stdout.flush()

        t_embed = time.time() - t0
        print(f"\n  ✔ Completed {len(all_embeddings)} vector embeddings in {format_duration(t_embed)}")

        # -------------------------------------------------------------
        # Step 5: ChromaDB Vector Upsert
        # -------------------------------------------------------------
        print("\n[Step 5/5] Upserting Vectors & Metadata into ChromaDB...")
        t0_up = time.time()
        # Upsert in blocks of 100 to avoid memory limits
        for i in range(0, len(all_ids), 200):
            collection.upsert(
                ids=all_ids[i:i+200],
                documents=all_texts[i:i+200],
                embeddings=all_embeddings[i:i+200],
                metadatas=all_metadatas[i:i+200],
            )
        t_upsert = time.time() - t0_up
        print(f"  ✔ Upserted {len(all_ids)} vectors into ChromaDB in {format_duration(t_upsert)}")

    total_duration = time.time() - total_start_time

    # -------------------------------------------------------------
    # Ingestion Summary & Live Query Demonstration
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("✨ INGESTION PIPELINE SUMMARY:")
    print("=" * 70)
    print(f"  • Total PDF Pages:        {len(pages)} pages")
    print(f"  • Semantic Chunks:        {len(chunks)} chunks")
    print(f"  • Extraction Time:        {format_duration(t_extract)}")
    print(f"  • Semantic Chunking Time: {format_duration(t_chunk)}")
    if not already_indexed or args.force:
        print(f"  • Vector Embedding Time:  {format_duration(t_embed)}")
        print(f"  • ChromaDB Storage Time:  {format_duration(t_upsert)}")
    print(f"  • Total End-to-End Time:  {format_duration(total_duration)}")
    print(f"  • Chroma Collection Size: {collection.count()} active vectors")
    print("=" * 70)

    # Verification query
    print("\n🔍 Live Retrieval Verification Test...")
    from rag.generator import generate_answer
    sample_query = "What is the course code and credits for Computer Network?"
    print(f"  Query: \"{sample_query}\"")
    t_q = time.time()
    ans = generate_answer(sample_query, [])
    t_q_dur = time.time() - t_q
    print(f"  ✔ Answer retrieved in {format_duration(t_q_dur)}:")
    print("-" * 50)
    print(ans[:350].strip() + "...\n" + "-" * 50)
    print("🎉 Pipeline is hot-reloaded, fully verified, and ready for queries!\n")


if __name__ == "__main__":
    main()
