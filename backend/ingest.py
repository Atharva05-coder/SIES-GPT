import json

from rag.chunker import chunk_text
from rag.embeddings import create_embedding
from rag.loader import download_pdf, extract_pdf_pages
from rag.vector_store import collection

METADATA_FILE = "scraper/siesgst_rag_data/pdfs_metadata.json"


def ingest_document(document: dict) -> int:
    url = document.get("url")
    hash_id = document.get("hash_id")

    if not url or not hash_id:
        return 0

    existing = collection.get(
        where={"hash_id": hash_id},
        include=["metadatas"],
    )
    if existing["ids"]:
        return 0

    pages = extract_pdf_pages(download_pdf(url))
    ids = []
    texts = []
    embeddings = []
    metadatas = []

    for page in pages:
        for index, text in enumerate(chunk_text(page["text"])):
            embedding_context = "\n".join(
                value
                for value in (
                    document.get("filename"),
                    document.get("title"),
                    document.get("doc_category"),
                    document.get("department"),
                    document.get("context_text"),
                    document.get("link_text"),
                )
                if value
            )
            ids.append(f"{hash_id}_p{page['page']}_c{index}")
            texts.append(text)
            embeddings.append(create_embedding(f"{embedding_context}\n\n{text}"))
            metadatas.append(
                {
                    "filename": document.get("filename", ""),
                    "url": url,
                    "department": document.get("department", ""),
                    "category": document.get("doc_category", ""),
                    "context": document.get("context_text", ""),
                    "source_page": document.get("source_page", ""),
                    "page": page["page"],
                    "hash_id": hash_id,
                }
            )

    if ids:
        collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    return len(ids)


def main() -> None:
    with open(METADATA_FILE, "r", encoding="utf-8") as file:
        documents = json.load(file)["pdfs"]

    stored_chunks = 0
    skipped_documents = 0
    failed_documents = 0

    for index, document in enumerate(documents, start=1):
        filename = document.get("filename", document.get("url", "Unknown PDF"))
        print(f"[{index}/{len(documents)}] {filename}")

        try:
            chunks = ingest_document(document)
            if chunks:
                stored_chunks += chunks
                print(f"  Indexed {chunks} chunks")
            else:
                skipped_documents += 1
                print("  Skipped (already indexed or no extractable text)")
        except Exception as error:
            failed_documents += 1
            print(f"  Failed: {error}")

    print("\nRAG ingestion completed")
    print(f"New chunks: {stored_chunks}")
    print(f"Skipped PDFs: {skipped_documents}")
    print(f"Failed PDFs: {failed_documents}")


if __name__ == "__main__":
    main()
