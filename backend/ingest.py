import json
import glob
from rag.chunker import chunk_syllabus_pages
from rag.embeddings import create_embedding
from rag.vector_store import collection

def main() -> None:
    json_files = glob.glob("backend/data/*_structured.json")
    stored_chunks = 0
    skipped_documents = 0
    failed_documents = 0

    for index, filepath in enumerate(json_files, start=1):
        print(f"[{index}/{len(json_files)}] {filepath}")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            filename = data.get("document", {}).get("filename", filepath)
            
            # Use filename as hash_id for idempotency
            existing = collection.get(where={"filename": filename}, include=["metadatas"])
            if existing and existing["ids"]:
                skipped_documents += 1
                print("  Skipped (already indexed)")
                continue

            # Convert to chunker format
            pages = [{"page": p["page_number"], "text": p["text"]} for p in data["pages"]]
            chunks = chunk_syllabus_pages(pages, filename)
            
            if not chunks:
                skipped_documents += 1
                print("  Skipped (no chunks generated)")
                continue

            ids = []
            texts = []
            embeddings = []
            metadatas = []
            
            for c in chunks:
                ids.append(c["id"])
                texts.append(c["text"])
                
                # Context prefix for better embedding
                context = f"Course: {c['metadata'].get('course_code', '')} {c['metadata'].get('course_name', '')}"
                embeddings.append(create_embedding(f"{context}\n\n{c['text']}"))
                metadatas.append(c["metadata"])

            collection.upsert(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            stored_chunks += len(ids)
            print(f"  Indexed {len(ids)} chunks")
            
        except Exception as error:
            failed_documents += 1
            print(f"  Failed: {error}")

    print("\nRAG ingestion completed")
    print(f"New chunks: {stored_chunks}")
    print(f"Skipped PDFs: {skipped_documents}")
    print(f"Failed PDFs: {failed_documents}")

if __name__ == "__main__":
    main()
