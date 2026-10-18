"""
FastAPI backend for the SIES GST assistant.

Run from the folder that contains site_agent.py:
    uv run uvicorn main:app --reload --port 8000

Environment variables (all optional):
    CORS_ORIGINS   comma-separated allowed origins (default: Vite dev server)
    ADMIN_TOKEN    enables POST /api/refresh when set (send as X-Admin-Token)
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
from rag.rag_pipeline import ask_sies_gpt
from dotenv import load_dotenv

load_dotenv()
import re
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from typing import Any, Literal

from agents import Runner
from agents.exceptions import MaxTurnsExceeded
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai.types.responses import ResponseTextDeltaEvent
from pydantic import BaseModel, Field

import site_agent as sa
import test as pdf_rag

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("api")

SOURCES_NOTE = (
    "Interface note: the app shows source links automatically below your answer. "
    "Do not include URLs or a 'Sources' section in your answer, even if an earlier rule says to."
)
SOURCE_LINE = re.compile(r"^Source: (\S+)", re.MULTILINE)
PDF_SOURCE_PATTERN = re.compile(r"Document:\s*(.+?)\nURL:\s*(\S+)", re.MULTILINE)
MAX_SOURCES = 4
PER_SEARCH = 3


# ------------------------------- app state -------------------------------- #
class AppState:
    def __init__(self):
        self.index: sa.SiteIndex | None = None
        self.agent: Any = None
        self.pdf_agent: Any = None
        self.pdf_ready: bool = False
        self.pdf_chunks: int = 0
        self.building = False
        self.error: str | None = None
        self.lock = asyncio.Lock()
        self.tasks: set[asyncio.Task[None]] = set()


state = AppState()


def _build(refresh: bool) -> tuple[sa.SiteIndex, Any]:
    index = sa.SiteIndex(sa.load_or_build_pages(refresh=refresh))
    agent = sa.build_agent(index)
    try:
        agent = agent.clone(tools=list(agent.tools) + [pdf_rag.search_sies_pdfs])
    except Exception as e:
        log.warning("Could not add search_sies_pdfs to website agent: %s", e)
    if isinstance(agent.instructions, str):
        agent = agent.clone(instructions=f"{agent.instructions}\n\n{SOURCES_NOTE}")
    return index, agent


async def rebuild(refresh: bool) -> None:
    """Crawl/load + index in a worker thread so the event loop stays responsive."""
    async with state.lock:
        state.building = True
        state.error = None
        try:
            state.index, state.agent = await asyncio.to_thread(_build, refresh)
            log.info(
                "index ready: %d pages, %d chunks",
                len(state.index.pages),
                len(state.index.chunks),
            )
        except Exception:
            log.exception("index build failed")
            state.error = "Index build failed. See server logs."
        finally:
            state.building = False


async def init_pdf() -> None:
    """Initialize ChromaDB collection, BM25 index, and PDF agent in background."""
    try:
        await asyncio.to_thread(pdf_rag.initialize_clients)
        agent = pdf_rag.create_agent()
        if isinstance(agent.instructions, str):
            agent = agent.clone(instructions=f"{agent.instructions}\n\n{SOURCES_NOTE}")
        state.pdf_agent = agent
        state.pdf_chunks = len(pdf_rag.CHUNKS)
        state.pdf_ready = True
        log.info("PDF index and agent ready: %d chunks", state.pdf_chunks)
    except Exception:
        log.exception("PDF agent initialization failed")


def spawn(coro: Coroutine[Any, Any, None]) -> None:
    task = asyncio.create_task(coro)
    state.tasks.add(task)  # keep a reference so the task isn't garbage-collected
    task.add_done_callback(state.tasks.discard)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    spawn(init_pdf())
    spawn(rebuild(refresh=False))
    yield


app = FastAPI(title="SIES GST Assistant API", lifespan=lifespan)

origins = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)


# -------------------------------- schemas --------------------------------- #
class Msg(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=100000)


class ChatRequest(BaseModel):
    messages: list[Msg] = Field(min_length=1, max_length=20)


# -------------------------------- sources --------------------------------- #
def dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def is_url_cited(url: str, answer: str) -> bool:
    ans = answer.lower()
    if url.lower() in ans:
        return True
    slug = url.rstrip("/").split("/")[-1].replace("-", " ").lower()
    words = [w for w in slug.split() if w not in {"faculty", "content", "about", "images", "committee", "gstcontent"}]
    if not words:
        return False
    if len(words) >= 2 and all(w in ans for w in words):
        return True
    if any(len(w) > 4 and w in ans for w in words):
        return True
    return False


def pick_sources(answer: str, searches: list[list[str]], reads: list[str]) -> list[str]:
    """Prefer pages the answer mentions; otherwise pages the agent read in full,
    then the top results of each search."""
    retrieved = dedupe([u for hits in searches for u in hits])
    cited = [u for u in dedupe(reads + retrieved) if is_url_cited(u, answer)]
    fallback = dedupe(reads + [u for hits in searches for u in hits[:PER_SEARCH]])
    return (cited or fallback)[:MAX_SOURCES]


def source_title(index: sa.SiteIndex, url: str) -> str:
    page = index.pages.get(url)
    label = page["label"] if page else sa.page_label(url)
    return "SIES GST" if label == "home" else label.title()


# -------------------------------- streaming ------------------------------- #
def sse(event_type: str, **data: Any) -> str:
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


def prefetch_site_context(index: sa.SiteIndex, query: str) -> tuple[str, list[str], list[str]]:
    """
    Guarantee read_page is called by doing it in Python before the LLM runs.

    Returns:
        context_block  – formatted text to inject into the user message
        searched_urls  – list of URLs returned by search
        read_urls      – list of URLs whose full content was read
    """
    hits = index.search(query)
    if not hits:
        return "", [], []

    searched_urls: list[str] = []
    seen: set[str] = set()
    for h in hits:
        u = h["url"]
        if u not in seen:
            seen.add(u)
            searched_urls.append(u)

    # Extract clean text directly from index without "[Truncated]" strings
    top_url = searched_urls[0]
    p_obj = index.pages.get(sa.normalize_url(top_url))
    if p_obj:
        page_lines = p_obj.get("lines", [])
        page_content = "\n".join(page_lines)
    else:
        page_content = index.read_page(top_url)

    # Keep primary context concise (up to 3000 chars) for instant, fast LLM generation
    full_content = page_content[:3000].strip()

    read_urls = [top_url]
    if len(searched_urls) > 1:
        second_url = searched_urls[1]
        if second_url.rstrip("/") != top_url.rstrip("/"):
            p2_obj = index.pages.get(sa.normalize_url(second_url))
            if p2_obj:
                second_content = "\n".join(p2_obj.get("lines", []))[:1500].strip()
                if second_content:
                    full_content += f"\n\n--- Additional details ({second_url}) ---\n{second_content}"
                    read_urls.append(second_url)

    context_block = (
        f"[PREFETCHED WEBSITE DATA — answer using this content]\n"
        f"Primary source: {top_url}\n"
        f"---\n{full_content}\n---\n"
        f"Other pages found: {', '.join(searched_urls[1:3]) if len(searched_urls) > 1 else 'none'}"
    )
    return context_block, searched_urls, read_urls



async def stream_answer(
    agent: Any, index: sa.SiteIndex, messages: list[Msg]
) -> AsyncIterator[str]:
    answer: list[str] = []
    searches: list[list[str]] = []
    reads: list[str] = []
    pdf_sources: list[dict[str, str]] = []
    try:
        # ── Pre-fetch: guaranteed search + read_page before LLM runs ──────────
        user_query = messages[-1].content
        context_block, searched_urls, read_urls = await asyncio.to_thread(
            prefetch_site_context, index, user_query
        )

        # Build augmented message list with prefetched context injected
        augmented_messages = [m.model_dump() for m in messages]
        if context_block:
            searches.append(searched_urls)
            reads.extend(read_urls)
            # Inject prefetched context into the last user message
            augmented_messages[-1] = {
                "role": "user",
                "content": (
                    f"{user_query}\n\n"
                    f"{context_block}\n\n"
                    "INSTRUCTIONS: Answer the user's question directly, factually, and concisely using only the prefetched data above. "
                    "Do NOT use internal reasoning or thinking steps. Do NOT call search_site or read_page. "
                    "Output your final answer immediately."
                ),
            }
            yield sse("tool_call", name="search_site") + f": {' ' * 1024}\n\n"
            yield sse("tool_output")
            yield sse("tool_call", name="read_page")
            yield sse("tool_output")
        # ──────────────────────────────────────────────────────────────────────

        result = Runner.run_streamed(
            agent,
            augmented_messages,  # type: ignore
            max_turns=3,  # Only 1 LLM turn needed — data already prefetched
        )
        async for event in result.stream_events():
            if event.type == "raw_response_event":
                if isinstance(event.data, ResponseTextDeltaEvent):
                    answer.append(event.data.delta)
                    yield sse("token", text=event.data.delta)

            elif event.type == "run_item_stream_event":
                if event.name == "tool_called":
                    raw = getattr(event.item, "raw_item", None)
                    name = getattr(raw, "name", "tool")
                    arguments = getattr(raw, "arguments", "") or ""
                    if name == "read_page":
                        try:
                            parsed = json.loads(arguments)
                            url = sa.normalize_url(str(parsed.get("url", "")))
                            if url in index.pages:
                                reads.append(url)
                        except (ValueError, AttributeError):
                            pass
                    yield sse("tool_call", name=name)

                elif event.name == "tool_output":
                    output = str(getattr(event.item, "output", ""))
                    urls = [
                        u
                        for u in dedupe(SOURCE_LINE.findall(output))
                        if u in index.pages
                    ]
                    if urls:
                        searches.append(urls)
                    for title, url in PDF_SOURCE_PATTERN.findall(output):
                        import urllib.parse
                        clean_title = urllib.parse.unquote(title).replace("_", " ")
                        if not any(s["url"] == url for s in pdf_sources):
                            pdf_sources.append({"url": url, "title": clean_title})
                    yield sse("tool_output")

        chosen = pick_sources("".join(answer), searches, reads)
        sources = [{"url": u, "title": source_title(index, u)} for u in chosen]
        for s in pdf_sources:
            if len(sources) < MAX_SOURCES and not any(x["url"] == s["url"] for x in sources):
                sources.append(s)
        if sources:
            yield sse("sources", sources=sources)
        yield sse("done")
    except MaxTurnsExceeded:
        yield sse(
            "error",
            message="The assistant took too many steps. Try a more specific question.",
        )
    except Exception as e:
        log.exception(f"chat stream failed: {e}")
        yield sse(
            "error",
            message=f"Something went wrong while generating answer: {e}",
        )


async def stream_pdf_answer(
    agent: Any, messages: list[Msg]
) -> AsyncIterator[str]:
    answer: list[str] = []
    pdf_sources: list[dict[str, str]] = []
    try:
        result = Runner.run_streamed(
            agent,
            [m.model_dump() for m in messages],  # type: ignore
            max_turns=6,
        )
        async for event in result.stream_events():
            if event.type == "raw_response_event":
                if isinstance(event.data, ResponseTextDeltaEvent):
                    answer.append(event.data.delta)
                    yield sse("token", text=event.data.delta)

            elif event.type == "run_item_stream_event":
                if event.name == "tool_called":
                    raw = getattr(event.item, "raw_item", None)
                    name = getattr(raw, "name", "tool")
                    yield sse("tool_call", name=name)

                elif event.name == "tool_output":
                    output = str(getattr(event.item, "output", ""))
                    for title, url in PDF_SOURCE_PATTERN.findall(output):
                        import urllib.parse
                        clean_title = urllib.parse.unquote(title).replace("_", " ")
                        if not any(s["url"] == url for s in pdf_sources):
                            pdf_sources.append({"url": url, "title": clean_title})
                    yield sse("tool_output")

        if pdf_sources:
            yield sse("sources", sources=pdf_sources[:MAX_SOURCES])
        yield sse("done")
    except MaxTurnsExceeded:
        yield sse(
            "error",
            message="The assistant took too many steps. Try a more specific question.",
        )
    except Exception:
        log.exception("PDF chat stream failed")
        yield sse(
            "error",
            message="Something went wrong while searching PDF documents.",
        )


# -------------------------------- endpoints ------------------------------- #
@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ready": (state.agent is not None) or state.pdf_ready,
        "building": state.building,
        "pages": len(state.index.pages) if state.index else 0,
        "chunks": len(state.index.chunks) if state.index else 0,
        "pdf_ready": state.pdf_ready,
        "pdf_chunks": state.pdf_chunks,
        "error": state.error,
    }


@app.post("/api/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    agent, index = state.agent, state.index
    if agent is None or index is None:
        raise HTTPException(
            status_code=503,
            detail="The site index is still being built. Try again shortly.",
        )
    if req.messages[-1].role != "user":
        raise HTTPException(
            status_code=422, detail="The last message must be from the user."
        )
    return StreamingResponse(
        stream_answer(agent, index, req.messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


from agent import agent as intent_agent
from agents import Runner


FAST_SYLLABUS_RE = re.compile(
    r"\b(sem|semester|syllabus|curriculum|module|modules|course|courses|subject|subjects|credits?|"
    r"exam|examination|scheme|internal assessment|ese|ise|ciap|esep|mse|practicals?|experiments?|"
    r"labs?|textbooks?|references?|minors?|mdm|electives?|pep|oec|hours?|teaching scheme|"
    r"unit\s*\d+|topics?|outcomes?|course\s*outcome|program\s*outcome|los|cos)\b"
    # Course codes must have a recognised 3-letter+ prefix followed by digits
    r"|\b(?:FEC|FEL|CEC|CEL|CEPEC|CEPEL|MDMC|MDML|OEC|CSC|CSL|ITC|ITL|AIDS|AIML)\d{2,4}[A-Z0-9/]*\b"
    # Common academic subjects & syllabus courses
    r"|\b(?:computer\s*networks?|theoretical\s*computer\s*science|tcs|data\s*structures?|"
    r"discrete\s*structures?|graph\s*theory|database\s*management|dbms|"
    r"computer\s*organization|operating\s*systems?|analysis\s*of\s*algorithms?|aoa|"
    r"software\s*engineering|cryptography|network\s*security|artificial\s*intelligence|"
    r"machine\s*learning|soft\s*computing|system\s*programming|compiler\s*construction|"
    r"spcc|digital\s*forensics?|machine\s*vision|internet\s*of\s*things|iot|"
    r"natural\s*language\s*processing|nlp|cloud\s*computing|devops|"
    r"applied\s*mathematics|engineering\s*economics|critical\s*thinking|"
    r"applied\s*physics|applied\s*chemistry|engineering\s*graphics|"
    r"digital\s*system\s*design|dsd|basic\s*electrical|robot\s*dynamics|"
    r"c\s*programming|python\s*programming|web\s*technology)\b",
    re.IGNORECASE,
)

FAST_DOCUMENT_RE = re.compile(
    r"\b(pdf|documents?|brochures?|polic(y|ies)|guidelines?|rules?|regulations?|handbook|"
    r"code of conduct|accreditation|nba|naac|nirf|ipr|patents?|emergency exits?|floor plans?|"
    r"internships?|anti[- ]ragging|mous?|epsilon)\b",
    re.IGNORECASE,
)

FAST_WEBSITE_RE = re.compile(
    r"\b(who\s+is|who\s+was|who\s+are|dr\.?|ms\.?|mr\.?|prof\.?|faculty|teacher|prof|professor|hod|principal|dean|admissions?|fees?|placements?|"
    r"packages?|highest package|average package|companies|recruiters|campus|canteen|library|"
    r"hostel|events?|fest|rotaract|student council|contact|address|location|reach|bus|train|"
    r"railway|concession|documents? required|eligibility criteria|"
    # SIES GST institutional cells, committees, and bodies
    r"IIIC|iiic|innovation.*incubation|incubation.*cell|"
    r"iste|nss|cultural committee|sports committee|"
    r"tpc|training.*placement|placement.*cell|"
    r"grievance|anti.?ragging committee|posh|"
    r"iqac|internal quality|cdc|career development|"
    r"alumni|entrepreneurship|e.?cell|"
    r"ieee|csi|acm|technical committee|"
    r"research committee|r&d|wep|women|gender|"
    r"mentoring|mentor|welfare|scholarship|"
    r"committee|cell|council|club|association|society|chapter)\b",
    re.IGNORECASE,
)


def fast_classify_intent(query: str) -> str | None:
    # 1. Institutional cells, committees, faculty, HOD, campus always route to website
    if FAST_WEBSITE_RE.search(query):
        return "website"
    # 2. PDF documents, policies, brochures route to document
    if FAST_DOCUMENT_RE.search(query):
        return "document"
    # 3. Courses, curriculum, syllabus, subjects route to syllabus
    if FAST_SYLLABUS_RE.search(query):
        return "syllabus"
    return None


@app.post("/api/smart_chat")
async def smart_chat(req: ChatRequest) -> StreamingResponse:
    if req.messages[-1].role != "user":
        raise HTTPException(
            status_code=422, detail="The last message must be from the user."
        )

    last_message = req.messages[-1].content

    # Fast-path hybrid intent routing (instant: 0.0001s)
    intent = fast_classify_intent(last_message)
    if intent is None:
        try:
            from agent import Message

            result = await Runner.run(intent_agent, last_message)
            parsed = result.final_output_as(Message)
            intent = parsed.intent
        except Exception as e:
            log.error(f"Intent classifier failed: {e}")
            intent = "website"

    log.info(f"Routed query to: {intent}")

    if intent == "syllabus":

        async def stream_syllabus():
            try:
                yield sse("tool_call", name="search_syllabus") + f": {' ' * 2048}\n\n"

                from rag.rag_pipeline import ask_sies_gpt
                import queue
                import threading

                q = queue.Queue()

                def run():
                    try:
                        ask_sies_gpt(last_message, yield_callback=q.put)
                    except Exception as e:
                        q.put(e)
                    finally:
                        q.put(None)

                t = threading.Thread(target=run)
                t.start()

                while True:
                    item = await asyncio.to_thread(q.get)
                    if item is None:
                        break
                    if isinstance(item, Exception):
                        raise item
                    if isinstance(item, dict):
                        if item["type"] == "sources":
                            yield sse("tool_output")

                            grouped_dict = {}
                            for s in item.get("sources", []):
                                filename = s.get("filename")
                                page = s.get("page")
                                url = (
                                    s.get("url")
                                    or f"https://siesgst.edu.in/images/{filename}"
                                )

                                if filename not in grouped_dict:
                                    grouped_dict[filename] = {"url": url, "pages": []}

                                if page not in grouped_dict[filename]["pages"]:
                                    grouped_dict[filename]["pages"].append(page)

                            grouped_sources = []
                            for filename, data in grouped_dict.items():
                                pages_str = ", ".join(
                                    str(p) for p in sorted(data["pages"])
                                )
                                title = (
                                    f"{filename} (Pages {pages_str})"
                                    if len(data["pages"]) > 1
                                    else f"{filename} (Page {pages_str})"
                                )
                                grouped_sources.append(
                                    {"url": data["url"], "title": title}
                                )

                            if grouped_sources:
                                yield sse("sources", sources=grouped_sources)
                        elif item["type"] == "token":
                            yield sse("token", text=item["text"])

                yield sse("done")
            except Exception as e:
                log.exception("Syllabus stream failed")
                yield sse("error", text=str(e))

        return StreamingResponse(stream_syllabus(), media_type="text/event-stream")

    elif intent == "document":
        pdf_agent = state.pdf_agent
        if pdf_agent is None:
            app_agent, index = state.agent, state.index
            if app_agent is None or index is None:
                raise HTTPException(status_code=503, detail="Index not ready.")
            return StreamingResponse(
                stream_answer(app_agent, index, req.messages),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        return StreamingResponse(
            stream_pdf_answer(pdf_agent, req.messages),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    else:
        app_agent, index = state.agent, state.index
        if app_agent is None or index is None:
            raise HTTPException(status_code=503, detail="Index not ready.")
        return StreamingResponse(
            stream_answer(app_agent, index, req.messages),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )


@app.post("/api/pdf_chat")
async def pdf_chat(req: ChatRequest) -> StreamingResponse:
    agent = state.pdf_agent
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="PDF agent is still initializing. Try again shortly.",
        )
    if req.messages[-1].role != "user":
        raise HTTPException(
            status_code=422, detail="The last message must be from the user."
        )
    return StreamingResponse(
        stream_pdf_answer(agent, req.messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/pdf/status")
async def pdf_status() -> dict[str, Any]:
    return {
        "ready": state.pdf_ready,
        "cached_chunks": state.pdf_chunks,
        **pdf_rag.get_status(),
    }


@app.post("/api/pdf/ingest", status_code=202)
async def ingest_pdfs(x_admin_token: str | None = Header(default=None)) -> dict[str, str]:
    expected = os.getenv("ADMIN_TOKEN")
    if expected and (not x_admin_token or not hmac.compare_digest(x_admin_token, expected)):
        raise HTTPException(status_code=401, detail="Invalid admin token.")
    if state.building:
        raise HTTPException(status_code=409, detail="An ingestion or build task is already running.")
    def _run_ingest():
        pdf_rag.ingest_documents()
        state.pdf_chunks = len(pdf_rag.CHUNKS)
    spawn(asyncio.to_thread(_run_ingest))
    return {"status": "started"}


@app.post("/api/refresh", status_code=202)
async def refresh(x_admin_token: str | None = Header(default=None)) -> dict[str, str]:
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=403, detail="Refresh is disabled (ADMIN_TOKEN not set)."
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Invalid admin token.")
    if state.building:
        raise HTTPException(status_code=409, detail="A rebuild is already running.")
    spawn(rebuild(refresh=True))
    return {"status": "started"}


class SIESChatRequest(BaseModel):
    message: str


@app.post("/chat")
def sies_chat(request: SIESChatRequest):
    return ask_sies_gpt(request.message)
