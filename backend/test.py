from __future__ import annotations

import asyncio
import gc
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import chromadb
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI
from rank_bm25 import BM25Okapi
from agents import (
    Agent,
    Runner,
    function_tool,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
)

# ============================================================
# 1. CONFIGURATION
# ============================================================

load_dotenv()
set_tracing_disabled(True)

HOME_URL = os.getenv(
    "HOME_URL",
    "https://siesgst.edu.in/",
)

LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://llama.atharva-amrutkar.in/v1",
).rstrip("/")

EMBED_BASE_URL = os.getenv(
    "EMBED_BASE_URL",
    "https://embed.atharva-amrutkar.in/v1",
).rstrip("/")

# Uses the API key you supplied, with .env overrides supported.
API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "V7mQ2xL9pR4kT8nC"

LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
EMBED_MODEL = os.getenv("EMBED_MODEL", "").strip()
MINERU_TIER = os.getenv("MINERU_TIER", "basic")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
MARKDOWN_DIR = DATA_DIR / "markdown"
CHROMA_DIR = DATA_DIR / "chroma"
CHUNKS_FILE = DATA_DIR / "chunks.json"

COLLECTION_NAME = "sies_gst_documents"

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 250
BATCH_SIZE = 16
TOP_K = 5

REQUEST_TIMEOUT = 90
MINERU_TIMEOUT = 3600

for folder in (DATA_DIR, PDF_DIR, MARKDOWN_DIR, CHROMA_DIR):
    folder.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. WINDOWS UTF-8 FIX
# ============================================================

# Prevent UnicodeEncodeError when printing to a Windows terminal.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(
                encoding="utf-8",
                errors="replace",
            )
        except (ValueError, OSError):
            pass


def read_text(path: Path) -> str:
    """Read text without Windows charmap decoding failures."""
    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def write_text(path: Path, text: str) -> None:
    """Write text explicitly as UTF-8."""
    path.write_text(
        text,
        encoding="utf-8",
        errors="replace",
    )


# ============================================================
# 3. API CLIENTS AND MODEL DISCOVERY
# ============================================================

embedding_client = None
async_chat_client = None
chroma_client = None
collection = None

CHUNKS: list[dict] = []
BM25_INDEX = None


def discover_model(base_url: str) -> str:
    """Discover the first model ID exposed by an API endpoint."""

    response = requests.get(
        f"{base_url}/models",
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=30,
    )
    response.raise_for_status()

    models = response.json().get("data", [])

    if not models:
        raise RuntimeError(f"No models returned by {base_url}/models")

    return models[0]["id"]


def initialize_clients() -> None:
    global embedding_client
    global async_chat_client
    global chroma_client
    global collection
    global LLM_MODEL
    global EMBED_MODEL

    if not LLM_MODEL:
        LLM_MODEL = discover_model(LLM_BASE_URL)

    if not EMBED_MODEL:
        EMBED_MODEL = discover_model(EMBED_BASE_URL)

    print(f"Chat endpoint: {LLM_BASE_URL}")
    print(f"Embedding endpoint: {EMBED_BASE_URL}")
    print(f"Chat model: {LLM_MODEL}")
    print(f"Embedding model: {EMBED_MODEL}")

    embedding_client = OpenAI(
        api_key=API_KEY,
        base_url=EMBED_BASE_URL,
        timeout=120,
        max_retries=2,
    )

    async_chat_client = AsyncOpenAI(
        api_key=API_KEY,
        base_url=LLM_BASE_URL,
        timeout=180,
        max_retries=1,
    )

    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    load_chunks()


# ============================================================
# 4. PDF DISCOVERY AND DOWNLOAD
# ============================================================


def discover_pdf_links() -> list[str]:
    """Find direct PDF links on the homepage, without recursive crawling."""

    print(f"\nScanning homepage: {HOME_URL}")

    response = requests.get(
        HOME_URL,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "Mozilla/5.0 SIES-GST-RAG/1.0"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    homepage_host = urlparse(HOME_URL).netloc.lower()

    pdf_urls = set()

    for anchor in soup.find_all("a", href=True):
        url = urljoin(HOME_URL, anchor["href"].strip())
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            continue

        if parsed.netloc.lower() != homepage_host:
            continue

        if not parsed.path.lower().endswith(".pdf"):
            continue

        pdf_urls.add(requests.utils.requote_uri(url))

    result = sorted(pdf_urls)

    print(f"Found {len(result)} direct PDF links.")
    return result


def file_key(url: str) -> str:
    """Generate a stable filesystem-safe identifier for a PDF URL."""

    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

    name = Path(urlparse(url).path).stem
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    name = (name or "document")[:70]

    return f"{name}_{digest}"


def download_pdf(url: str, destination: Path) -> None:
    """Download a PDF and validate its signature."""

    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "Mozilla/5.0 SIES-GST-RAG/1.0"},
    )
    response.raise_for_status()

    if not response.content.startswith(b"%PDF"):
        raise ValueError(f"URL did not return a valid PDF: {url}")

    destination.write_bytes(response.content)


# ============================================================
# 5. MARKDOWN CLEANUP
# ============================================================


def clean_markdown(text: str) -> str:
    """
    Remove Base64 image payloads and image markup.

    Base64 image data is removed before chunking or indexing.
    The substitution is performed in one pass to avoid repeated
    copying of enormous strings.
    """

    # Remove Markdown images containing embedded Base64 data.
    # Standard Base64 does not contain a closing parenthesis.
    text = re.sub(
        r"!\[[^\]]*\]\(\s*data:image/[^)]*\)",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Remove remaining Markdown images.
    text = re.sub(
        r"!\[[^\]]*\]\([^)]*\)",
        "",
        text,
    )

    # Remove reference-style Markdown images.
    text = re.sub(
        r"!\[[^\]]*\]\s*\[[^\]]*\]",
        "",
        text,
    )

    # Remove HTML image tags.
    text = re.sub(
        r"<img\b[^>]*>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Remove HTML comments.
    text = re.sub(
        r"<!--.*?-->",
        "",
        text,
        flags=re.DOTALL,
    )

    # Remove standalone Base64 data URLs.
    text = re.sub(
        r"data:image/[A-Za-z0-9.+-]+;base64,[A-Za-z0-9+/=\r\n]+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Clean excessive blank lines.
    text = re.sub(
        r"\n[ \t]*\n(?:[ \t]*\n)+",
        "\n\n",
        text,
    )

    return text.strip()


def clean_markdown_file(path: Path) -> str:
    """Clean a Markdown file and save it using UTF-8."""

    raw = read_text(path)
    cleaned = clean_markdown(raw)

    write_text(path, cleaned + "\n")

    return cleaned


# ============================================================
# 6. MINERU EXTRACTION
# ============================================================


def extract_pdf_to_markdown(
    pdf_path: Path,
    markdown_path: Path,
) -> str:
    """Run MinerU and clean the generated Markdown immediately."""

    command = [
        "mineru-kit",
        "parse",
        str(pdf_path),
        "-o",
        str(markdown_path),
        "--tier",
        MINERU_TIER,
    ]

    print(f"Running MinerU: {pdf_path.name}")

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=MINERU_TIMEOUT,
        check=False,
    )

    if result.returncode != 0:
        message = (
            result.stderr.strip() or result.stdout.strip() or "Unknown MinerU error"
        )

        raise RuntimeError(f"MinerU failed for {pdf_path.name}:\n" f"{message[-2500:]}")

    if not markdown_path.exists():
        raise FileNotFoundError(f"MinerU did not create {markdown_path}")

    # Clean the output BEFORE creating any chunks.
    cleaned = clean_markdown_file(markdown_path)

    if not cleaned:
        raise ValueError(f"No usable text extracted from {pdf_path.name}")

    print(f"Clean Markdown saved: {markdown_path.name}")

    return cleaned


# ============================================================
# 7. TEXT CHUNKING
# ============================================================


def split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Split a single document into overlapping text chunks."""

    text = text.strip()

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            boundary = max(
                text.rfind("\n\n", start, end),
                text.rfind(". ", start, end),
                text.rfind(" ", start, end),
            )

            if boundary > start + chunk_size // 2:
                end = boundary

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(start + 1, end - overlap)

    return chunks


# ============================================================
# 8. EMBEDDINGS
# ============================================================


def create_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings in small batches."""

    vectors = []

    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]

        response = embedding_client.embeddings.create(
            model=EMBED_MODEL,
            input=batch,
        )

        ordered = sorted(
            response.data,
            key=lambda item: item.index,
        )

        vectors.extend(item.embedding for item in ordered)

        print(
            f"Embedded {min(start + len(batch), len(texts))}"
            f"/{len(texts)} chunks in current batch"
        )

    return vectors


# ============================================================
# 9. BM25
# ============================================================


def tokenize(text: str) -> list[str]:
    return re.findall(
        r"\w+",
        text.lower(),
        flags=re.UNICODE,
    )


def refresh_bm25() -> None:
    """Rebuild the keyword index from the currently indexed chunks."""

    global BM25_INDEX

    tokenized = [tokenize(item["text"]) for item in CHUNKS]

    if CHUNKS and any(tokenized):
        BM25_INDEX = BM25Okapi(tokenized)
    else:
        BM25_INDEX = None


def load_chunks() -> None:
    """Load the persisted clean chunk cache on startup."""

    global CHUNKS

    if not CHUNKS_FILE.exists():
        CHUNKS = []
        refresh_bm25()
        return

    try:
        loaded = json.loads(read_text(CHUNKS_FILE))

        # Only retain valid chunk records.
        CHUNKS = [
            item
            for item in loaded
            if isinstance(item, dict)
            and item.get("id")
            and item.get("text")
            and item.get("source")
        ]

    except (json.JSONDecodeError, OSError) as exc:
        print(f"Could not load chunk cache: {exc}")
        CHUNKS = []

    refresh_bm25()


# ============================================================
# 10. INCREMENTAL CHROMADB INDEXING
# ============================================================


def reset_index() -> None:
    """
    Start a fresh index for a full refresh.

    Each subsequent batch is persisted immediately.
    """

    global collection, CHUNKS, BM25_INDEX

    try:
        chroma_client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = chroma_client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    CHUNKS = []
    BM25_INDEX = None

    write_text(CHUNKS_FILE, "[]")

    print("Created a fresh ChromaDB collection.")


def index_pdf_chunks(chunks: list[dict]) -> None:
    """
    Index a PDF in batches instead of waiting for all PDFs.

    Each batch is embedded, inserted into ChromaDB, and saved
    to the local chunk cache before the next batch proceeds.
    """

    global CHUNKS

    if not chunks:
        print("No chunks to index for this PDF.")
        return

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        texts = [item["text"] for item in batch]

        vectors = create_embeddings(texts)

        collection.add(
            ids=[item["id"] for item in batch],
            documents=texts,
            embeddings=vectors,
            metadatas=[
                {
                    "source": item["source"],
                    "title": item["title"],
                    "chunk_index": item["chunk_index"],
                }
                for item in batch
            ],
        )

        # Update the local cache after a successful ChromaDB insert.
        CHUNKS.extend(batch)

        write_text(
            CHUNKS_FILE,
            json.dumps(CHUNKS, ensure_ascii=False),
        )

        print(f"Indexed {collection.count()} chunks total.")

        # Drop temporary references before the next batch.
        del vectors, texts, batch

    # Make newly indexed documents available to BM25.
    refresh_bm25()

    print(f"Finished indexing {chunks[0]['title']}: " f"{len(chunks)} chunks.")


# ============================================================
# 11. HYBRID RETRIEVAL
# ============================================================


def hybrid_search(
    query: str,
    top_k: int = TOP_K,
) -> list[dict]:
    """Combine semantic retrieval and BM25 with reciprocal rank fusion."""

    if not CHUNKS or collection is None or collection.count() == 0:
        return []

    query_response = embedding_client.embeddings.create(
        model=EMBED_MODEL,
        input=[query],
    )

    query_vector = query_response.data[0].embedding

    semantic = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k * 3, collection.count()),
        include=["documents", "metadatas"],
    )

    semantic_ids = semantic.get("ids", [[]])[0]

    bm25_ids = []

    if BM25_INDEX is not None:
        scores = BM25_INDEX.get_scores(tokenize(query))

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )

        bm25_ids = [CHUNKS[index]["id"] for index in ranked_indices[: top_k * 3]]

    # Reciprocal Rank Fusion.
    fused_scores = {}
    rank_constant = 60

    for rank, chunk_id in enumerate(semantic_ids, start=1):
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (
            rank_constant + rank
        )

    for rank, chunk_id in enumerate(bm25_ids, start=1):
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (
            rank_constant + rank
        )

    chunk_lookup = {item["id"]: item for item in CHUNKS}

    ranked_ids = sorted(
        fused_scores,
        key=fused_scores.get,
        reverse=True,
    )

    return [
        chunk_lookup[chunk_id]
        for chunk_id in ranked_ids[:top_k]
        if chunk_id in chunk_lookup
    ]


# ============================================================
# 12. AGENT TOOL
# ============================================================


@function_tool
def search_sies_pdfs(query: str) -> str:
    """Search indexed SIES GST PDFs for relevant information."""

    results = hybrid_search(query)

    if not results:
        return (
            "No relevant content was found in the indexed PDFs. "
            "The index may be empty or the documents may not "
            "contain the requested information."
        )

    sections = []

    for index, item in enumerate(results, start=1):
        sections.append(
            f"[Source {index}]\n"
            f"Document: {item['title']}\n"
            f"URL: {item['source']}\n"
            f"Content:\n{item['text']}"
        )

    return "\n\n---\n\n".join(sections)


def create_agent() -> Agent:
    from agents import ModelSettings

    model = OpenAIChatCompletionsModel(
        model=LLM_MODEL,
        openai_client=async_chat_client,
    )

    return Agent(
        name="SIES GST Assistant",
        instructions=(
            "You are an assistant for SIES Graduate School of "
            "Technology. Use search_sies_pdfs for questions about "
            "the institution and its official documents. Base answers strictly on "
            "retrieved content. Do not invent dates, fees, admission "
            "requirements, contact details, or policies. If the "
            "documents do not contain an answer, say so clearly. "
            "Include relevant document names in your explanation."
        ),
        model=model,
        model_settings=ModelSettings(temperature=0.2),
        tools=[search_sies_pdfs],
    )


def get_status() -> dict:
    """Return status dictionary of the indexed PDF documents and cache."""
    return {
        "cached_chunks": len(CHUNKS),
        "indexed_chunks": collection.count() if collection else 0,
        "documents": sorted(list(set(c.get("title") for c in CHUNKS if c.get("title")))),
    }


# ============================================================
# 13. INGESTION PIPELINE
# ============================================================


def ingest_documents() -> None:
    """
    Process one PDF at a time.

    A PDF is downloaded, extracted, cleaned, chunked, and indexed
    before the next PDF is processed.
    """

    urls = discover_pdf_links()

    if not urls:
        print("No PDF links found.")
        return

    reset_index()

    successful = 0
    failed = 0

    for number, url in enumerate(urls, start=1):
        key = file_key(url)

        pdf_path = PDF_DIR / f"{key}.pdf"
        markdown_path = MARKDOWN_DIR / f"{key}.md"

        print(f"\n[{number}/{len(urls)}] {url}")

        try:
            download_pdf(url, pdf_path)

            # Extract and remove images before chunking.
            markdown = extract_pdf_to_markdown(
                pdf_path,
                markdown_path,
            )

            text_chunks = split_text(markdown)
            title = Path(urlparse(url).path).stem or key

            document_chunks = []

            for chunk_index, chunk_text in enumerate(text_chunks):
                chunk_id = hashlib.sha256(
                    (url + "|" + str(chunk_index) + "|" + chunk_text).encode("utf-8")
                ).hexdigest()

                document_chunks.append(
                    {
                        "id": chunk_id,
                        "text": chunk_text,
                        "source": url,
                        "title": title,
                        "chunk_index": chunk_index,
                    }
                )

            # Index this PDF immediately.
            index_pdf_chunks(document_chunks)

            successful += 1

            print(f"Completed PDF {number}/{len(urls)}.")

            # Release document-level temporary objects.
            del markdown, text_chunks, document_chunks
            gc.collect()

        except subprocess.TimeoutExpired:
            failed += 1
            print(f"MinerU timed out for {pdf_path.name}. " "Skipping this PDF.")

        except Exception as exc:
            failed += 1
            print(f"Failed to process {url}: {exc}")

            # Do not silently add a stale document to the new index.
            # Continue processing the remaining PDFs.

    print("\n========== INGESTION SUMMARY ==========")
    print(f"PDF links discovered: {len(urls)}")
    print(f"Successfully indexed: {successful}")
    print(f"Failed PDFs: {failed}")
    print(f"Total indexed chunks: {collection.count()}")
    print("=======================================")


# ============================================================
# 14. CHAT LOOP
# ============================================================


async def ask_question(
    agent: Agent,
    question: str,
) -> str:
    result = await Runner.run(agent, question)
    return str(result.final_output)


def chat_loop(agent: Agent) -> None:
    print("\nSIES GST Assistant")
    print("Type 'back' to return to the main menu.")

    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if question.lower() in {"back", "exit", "quit"}:
            return

        if not question:
            continue

        try:
            answer = asyncio.run(ask_question(agent, question))
            print(f"\nAssistant:\n{answer}")

        except Exception as exc:
            print(f"\nQuestion failed: {exc}")


# ============================================================
# 15. STATUS AND MAIN MENU
# ============================================================


def show_status() -> None:
    print("\n========== INDEX STATUS ==========")
    print(f"Homepage: {HOME_URL}")
    print(f"Chat model: {LLM_MODEL}")
    print(f"Embedding model: {EMBED_MODEL}")
    print(f"Markdown directory: {MARKDOWN_DIR}")
    print(f"ChromaDB directory: {CHROMA_DIR}")
    print(f"Cached chunks: {len(CHUNKS)}")

    try:
        print(f"Indexed chunks: {collection.count()}")
    except Exception:
        print("Indexed chunks: unavailable")

    print("==================================")


def main() -> None:
    print("=" * 55)
    print("             SIES GST RAG")
    print("=" * 55)

    try:
        initialize_clients()
    except Exception as exc:
        print(f"\nInitialization failed: {exc}")
        print("Check the API endpoints, API key, and model IDs.")
        return

    agent = create_agent()

    while True:
        print("\n1. Ingest / refresh PDFs")
        print("2. Ask a question")
        print("3. Show index status")
        print("4. Exit")

        try:
            choice = input("Choose an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if choice == "1":
            try:
                ingest_documents()
            except Exception as exc:
                print(f"\nIngestion error: {exc}")

        elif choice == "2":
            if not CHUNKS:
                print("Index is empty. Run option 1 first.")
            else:
                chat_loop(agent)

        elif choice == "3":
            show_status()

        elif choice == "4":
            print("Goodbye!")
            break

        else:
            print("Invalid option. Choose 1, 2, 3, or 4.")


if __name__ == "__main__":
    main()
