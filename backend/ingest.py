import json

from rag.loader import (
    download_pdf,
    extract_pdf_pages
)

from rag.chunker import chunk_text

from rag.embeddings import (
    create_embedding
)

from rag.vector_store import collection


METADATA_FILE = (
    "scraper/siesgst_rag_data/"
    "pdfs_metadata.json"
)


# -----------------------------------------
# Load scraper metadata
# -----------------------------------------

with open(
    METADATA_FILE,
    "r",
    encoding="utf-8"
) as file:

    data = json.load(file)


documents = data["pdfs"]


# -----------------------------------------
# Find Third Year CE R24 syllabus
# -----------------------------------------

target = None

for document in documents:

    if (
        document.get("filename")
        == "TE CE R24 (1).pdf"
    ):

        target = document

        break


if target is None:

    raise Exception(
        "Third Year CE syllabus not found"
    )


print(
    "\nFound document:"
)

print(
    target["filename"]
)

print(
    target["url"]
)


# -----------------------------------------
# Download PDF
# -----------------------------------------

print("\nDownloading PDF...")

pdf_bytes = download_pdf(
    target["url"]
)

print("PDF downloaded.")


# -----------------------------------------
# Extract pages
# -----------------------------------------

print("\nExtracting text...")

pages = extract_pdf_pages(
    pdf_bytes
)

print(
    f"Pages extracted: {len(pages)}"
)


# -----------------------------------------
# Create chunks
# -----------------------------------------

chunks = []

for page in pages:

    page_chunks = chunk_text(
        page["text"]
    )

    for index, chunk in enumerate(
        page_chunks
    ):

        chunks.append({

            "id": (
                f"{target['hash_id']}_"
                f"p{page['page']}_"
                f"c{index}"
            ),

            "text": chunk,

            "page": page["page"]

        })


print(
    f"Chunks created: {len(chunks)}"
)


# -----------------------------------------
# Create embeddings
# -----------------------------------------

print("\nCreating embeddings...")

ids = []

texts = []

embeddings = []

metadatas = []


for index, chunk in enumerate(
    chunks
):

    print(
        f"Embedding "
        f"{index + 1}/{len(chunks)}"
    )


    embedding = create_embedding(
        chunk["text"]
    )


    ids.append(
        chunk["id"]
    )

    texts.append(
        chunk["text"]
    )

    embeddings.append(
        embedding
    )


    metadatas.append({

        "filename": target["filename"],

        "url": target["url"],

        "department": target["department"],

        "category": target["doc_category"],

        "source_page": target["source_page"],

        "page": chunk["page"],

        "hash_id": target["hash_id"]

    })


# -----------------------------------------
# Store in ChromaDB
# -----------------------------------------

print("\nStoring in ChromaDB...")


collection.upsert(

    ids=ids,

    documents=texts,

    embeddings=embeddings,

    metadatas=metadatas

)


print("\n================================")
print("RAG INGESTION COMPLETED")
print("================================")

print(
    f"Stored chunks: {len(chunks)}"
)