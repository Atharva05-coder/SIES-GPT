"""
FastAPI backend for the SIES GST assistant.

Run from the folder that contains site_agent.py:
    uv run uvicorn main:app --reload --port 8000

Environment variables (all optional):
    CORS_ORIGINS   comma-separated allowed origins (default: Vite dev server)
    ADMIN_TOKEN    enables POST /api/refresh when set (send as X-Admin-Token)
"""

from __future__ import annotations
import queue
import threading
import asyncio
import hmac
import json
import logging
import os
import time
from rag.rag_pipeline import ask_sies_gpt
from dotenv import load_dotenv

load_dotenv()
import re
import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any, Literal

from agents import Runner
from agents.exceptions import MaxTurnsExceeded
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai.types.responses import ResponseTextDeltaEvent
from pydantic import BaseModel, Field

ACTIVE_REQUESTS: dict[str, Callable[[], None]] = {}
SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
CANCELLED_REQUESTS: set[str] = set()

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
            global _faculty_names_re
            _faculty_names_re = None
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
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,*"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------- schemas --------------------------------- #
class Msg(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=100000)


class ChatRequest(BaseModel):
    messages: list[Msg] = Field(min_length=1, max_length=20)
    request_id: str | None = None


class CancelRequest(BaseModel):
    request_id: str | None = None


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
    if any(len(w) >= 3 and w in ans for w in words):
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


def extract_page_repr(
    url: str,
    p_obj: dict | None,
    fallback_text: str,
    hit_chunks: list[str],
    max_chars: int = 4000,
    query: str = "",
) -> str:
    """
    Extract high-value structured text from a page object or fallback string.
    Ensures that for faculty profiles, basic bio, qualifications, and full employment
    work experience are never dropped due to chunk truncation.
    """
    if not p_obj:
        return fallback_text[:max_chars].strip()

    lines = p_obj.get("lines", [])
    if not lines:
        return fallback_text[:max_chars].strip()

    # Specialized structuring for faculty profiles to ensure bio, degrees, courses, work experience, awards, and publications are preserved
    if "/faculty/" in url.lower():
        nav_words = {
            "courses", "publications", "papers", "participations",
            "awards", "assignments", "achievements", "material url: view material",
            "date", "title", "presented/published", "level", "academic year", "organizer / venue"
        }
        bio_lines: list[str] = []
        course_lines: list[str] = []
        exp_lines: list[str] = []
        award_lines: list[str] = []
        pub_lines: list[str] = []
        dev_lines: list[str] = []

        for l in lines:
            s = l.strip()
            if not s or s.lower() in nav_words:
                continue
            if s.startswith("From Date:"):
                parts_dict = dict(p.strip().split(": ", 1) for p in s.split(";") if ": " in p)
                desig = parts_dict.get("Designation", "").strip()
                org = parts_dict.get("Organization", "").strip()
                addr = parts_dict.get("Organization Address", "").strip()
                from_d = parts_dict.get("From Date", "").strip()
                to_d = parts_dict.get("To Date", "").strip()
                loc_str = f" ({addr})" if addr else ""
                date_str = f" (From: {from_d} to {to_d})" if from_d and to_d else (f" (From: {from_d})" if from_d else "")
                exp_lines.append(f"- {desig} at {org}{loc_str}{date_str}")
            elif s.startswith("Year:") or "Award Title:" in s or "Secured Best" in s or "Award" in s:
                if "Award Title:" in s:
                    parts_dict = dict(p.strip().split(": ", 1) for p in s.split(";") if ": " in p)
                    title = parts_dict.get("Award Title", "").strip()
                    by = parts_dict.get("Awarded By", "").strip()
                    yr = parts_dict.get("Year", "").strip()
                    by_str = f" (Awarded by: {by})" if by else ""
                    yr_str = f" - {yr}" if yr else ""
                    award_lines.append(f"- **{title}**{by_str}{yr_str}")
                elif "Details:" in s:
                    parts_dict = dict(p.strip().split(": ", 1) for p in s.split(";") if ": " in p)
                    det = parts_dict.get("Details", "").strip()
                    if det:
                        award_lines.append(f"- {det}")
                    else:
                        award_lines.append(f"- {s}")
                else:
                    award_lines.append(f"- {s}")
            elif s.startswith("Course Title:"):
                course_lines.append("- " + s.replace("; Material URL: View Material", "").replace("Course Title:", "").strip())
            elif s.startswith("Date:"):
                if any(w in s for w in ["Type: Journal", "Type: Proceedings", "Type: Book", "Type: Conference", "Level: National", "Level: International"]):
                    pub_lines.append("- " + s)
                else:
                    dev_lines.append("- " + s)
            elif "Type: " in s and any(k in s for k in ["Badge", "Certificate", "Award", "Academic Year:", "Co-curricular"]):
                if "Details:" in s:
                    parts_dict = dict(p.strip().split(": ", 1) for p in s.split(";") if ": " in p)
                    det = parts_dict.get("Details", "").strip()
                    if det:
                        award_lines.append(f"- {det}")
                    else:
                        award_lines.append(f"- {s}")
                else:
                    award_lines.append(f"- {s}")
            else:
                if not exp_lines and not pub_lines and not dev_lines and not course_lines and not award_lines:
                    bio_lines.append(s)

        parts: list[str] = []
        if bio_lines:
            parts.append("### Overview & Academic Background\n" + "\n".join(bio_lines))
        if course_lines:
            parts.append("### Teaching Responsibilities (Courses Taught)\n" + "\n".join(course_lines))
        if exp_lines:
            parts.append("### Work Experience\n" + "\n".join(exp_lines))
        if award_lines:
            parts.append("### Awards, Honors & Achievements\n" + "\n".join(award_lines))
        if pub_lines:
            parts.append("### Research and Publications\n" + "\n".join(pub_lines))
        if dev_lines:
            parts.append("### Professional Development (Workshops, Training Programs, FDPs & STTPs)\n" + "\n".join(dev_lines))

        base = "\n\n".join(parts)
        remaining = max_chars - len(base)
        if remaining > 300 and hit_chunks:
            extra = []
            for ch in hit_chunks:
                sample = ch.split("\n")[0].strip()
                if sample and sample not in base:
                    extra.append(ch)
            if extra:
                base += "\n\n### Additional Relevant Records\n" + "\n\n".join(extra)[:remaining].strip()
        return base[:max_chars].strip()

    # Department pages: if faculty lines exist, extract clean faculty roster without losing staff entries
    fac_lines = [l.strip() for l in lines if l.strip().startswith("Name of the Staff:")]
    if fac_lines:
        ignore_words = {"faculty", "mam", "sir", "prof", "professor", "dr", "tell", "about", "who", "details", "info", "experience", "qualification", "publications"}
        person_tokens = [t.lower() for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) >= 3 and t not in ignore_words]
        matching_lines = [l for l in fac_lines if any(tok in l.lower() for tok in person_tokens)]
        if matching_lines:
            other_lines = [l for l in fac_lines if l not in matching_lines]
            fac_lines = matching_lines + other_lines
        intro = "\n".join(lines[:10])[:400].strip()
        fac_block = "\n".join(fac_lines)
        return f"{intro}\n\n### Faculty Roster\n{fac_block}"[:max_chars].strip()

    # Generic pages: if hit_chunks matched and page is long, prioritize hit_chunks; otherwise raw text
    page_content = "\n".join(lines)
    if hit_chunks and len(page_content) > max_chars:
        intro = "\n".join(lines[:10])[:600].strip()
        chunk_text = "\n\n".join(hit_chunks)
        if intro and intro.split("\n")[0] not in chunk_text:
            return (intro + "\n\n" + chunk_text)[:max_chars].strip()
        return chunk_text[:max_chars].strip()
    return page_content[:max_chars].strip()


def prefetch_site_context(index: sa.SiteIndex, query: str) -> tuple[str, list[str], list[str]]:
    """
    Guarantee read_page is called by doing it in Python before the LLM runs.

    Returns:
        context_block  - formatted text to inject into the user message
        searched_urls  - list of URLs returned by search
        read_urls      - list of URLs whose full content was read
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
    fallback_text = index.read_page(top_url) if not p_obj else ""
    is_fac_page = "/faculty/" in top_url.lower()
    top_max = 5000 if is_fac_page else 4000
    second_max = 1200 if is_fac_page else 1200
    top_hit_chunks = [h["text"].strip() for h in hits if h.get("url") == top_url and h.get("text")]
    full_content = extract_page_repr(top_url, p_obj, fallback_text, top_hit_chunks, max_chars=top_max, query=query)

    read_urls = [top_url]
    if not is_fac_page and len(searched_urls) > 1:
        second_url = searched_urls[1]
        if second_url.rstrip("/") != top_url.rstrip("/"):
            p2_obj = index.pages.get(sa.normalize_url(second_url))
            fallback2 = index.read_page(second_url) if not p2_obj else ""
            second_hit_chunks = [h["text"].strip() for h in hits if h.get("url") == second_url and h.get("text")]
            second_content = extract_page_repr(second_url, p2_obj, fallback2, second_hit_chunks, max_chars=second_max, query=query)
            if second_content:
                full_content += f"\n\n--- Additional details ({second_url}) ---\n{second_content}"
                read_urls.append(second_url)

    if not is_fac_page and len(searched_urls) > 2:
        third_url = searched_urls[2]
        if third_url.rstrip("/") not in [top_url.rstrip("/"), second_url.rstrip("/")]:
            p3_obj = index.pages.get(sa.normalize_url(third_url))
            fallback3 = index.read_page(third_url) if not p3_obj else ""
            third_content = extract_page_repr(third_url, p3_obj, fallback3, [], max_chars=800, query=query)
            if third_content:
                full_content += f"\n\n--- Additional details ({third_url}) ---\n{third_content}"
                read_urls.append(third_url)

    context_block = (
        f"[PREFETCHED WEBSITE DATA — answer using this content]\n"
        f"Primary source: {top_url}\n"
        f"---\n{full_content}\n---\n"
        f"Other pages found: {', '.join(searched_urls[1:4]) if len(searched_urls) > 1 else 'none'}"
    )
    return context_block, searched_urls, read_urls


def log_terminal_benchmark(
    query: str, route: str, total_time: float, ttft: float, tokens: int, tok_per_sec: float
) -> None:
    sep = "=" * 62
    summary = (
        f"\n{sep}\n"
        f"📊 [BENCHMARK] Response Generated\n"
        f" Query      : {query}\n"
        f" Route      : {route}\n"
        f" Latency    : {total_time:.2f}s\n"
        f" TTFT       : {ttft:.2f}s\n"
        f" Tokens     : {tokens}\n"
        f" Speed      : {tok_per_sec:.1f} tok/s\n"
        f"{sep}\n"
    )
    print(summary, flush=True)
    log.info(
        "Benchmark: Query='%s' | Route='%s' | Total=%.2fs | TTFT=%.2fs | Tokens=%d | Speed=%.1f tok/s",
        query,
        route,
        total_time,
        ttft,
        tokens,
        tok_per_sec,
    )


async def stream_answer(
    agent: Any,
    index: sa.SiteIndex,
    messages: list[Msg],
    request: Request | None = None,
    req_id: str | None = None,
) -> AsyncIterator[str]:
    yield ": connected\n\n"
    start_time = time.perf_counter()
    first_token_time: float | None = None
    token_count = 0
    answer: list[str] = []
    searches: list[list[str]] = []
    reads: list[str] = []
    pdf_sources: list[dict[str, str]] = []

    # Use an async queue with background keep-alive pinger so browser/proxy connection never times out during LLM generation
    event_queue: asyncio.Queue = asyncio.Queue()
    stop_ping = asyncio.Event()
    ping_task: asyncio.Task[None] | None = None
    stream_task: asyncio.Task[None] | None = None
    active_runner_result = None

    def cancel_this_stream():
        log.info("Cancelling stream_answer for req_id: %s", req_id)
        stop_ping.set()
        if ping_task and not ping_task.done():
            ping_task.cancel()
        if active_runner_result:
            try:
                active_runner_result.cancel(mode="immediate")
            except Exception as e:
                log.debug("Error cancelling runner: %s", e)
        if stream_task and not stream_task.done():
            stream_task.cancel()

    if req_id:
        ACTIVE_REQUESTS[req_id] = cancel_this_stream

    if req_id and req_id in CANCELLED_REQUESTS:
        log.info("stream_answer aborted immediately for cancelled req_id: %s", req_id)
        yield sse("done")
        return

    try:
        # ── Pre-fetch: guaranteed search + read_page before LLM runs ──────────
        user_query = messages[-1].content
        context_block, searched_urls, read_urls = await asyncio.to_thread(
            prefetch_site_context, index, user_query
        )

        # Prune conversation history to fit safely inside the model's 8,192 token limit.
        # Keep at most the last 3 messages (1 previous user/assistant exchange + current message).
        # Truncate any previous assistant message so old multi-thousand token syllabus dumps don't blow the context window.
        recent_messages = messages[-3:] if len(messages) > 3 else messages
        augmented_messages: list[dict[str, str]] = []
        for m in recent_messages[:-1]:
            content = m.content
            if m.role == "assistant" and len(content) > 500:
                content = content[:500] + "... [earlier response truncated]"
            augmented_messages.append({"role": m.role, "content": content})

        if context_block:
            searches.append(searched_urls)
            reads.extend(read_urls)
            # Inject prefetched context into the last user message with clear formatting requirements
            augmented_messages.append({
                "role": "user",
                "content": (
                    f"{user_query}\n\n"
                    f"{context_block}\n\n"
                    "INSTRUCTIONS:\n"
                    "1. Provide a comprehensive, detailed, and well-structured answer using the prefetched website data above, staying directly focused on what the user asked (e.g., if asked about a person/faculty/HOD, highlight their designation, roles, academic qualifications, experience, contact email, and institutional/committee appointments; if asked about a cell/committee, provide its objectives, complete committee roster with coordinators and members, roles & responsibilities, and MoUs).\n"
                    "2. Avoid dumping unrelated sections or general college blurbs that do not directly answer the specific question.\n"
                    "3. Use clean Markdown formatting: organize your response with clear section headings (e.g., ### Overview, ### Academic Background, ### Teaching Responsibilities, ### Work Experience, ### Awards, Honors & Achievements, ### Research and Publications, ### Professional Development, ### Objectives, ### Committee Members, ### Roles & Responsibilities), bold labels (`- **Field:** Value`), and bullet points.\n"
                    "   - In Overview, list each detail on its own separate line or bullet (e.g., - **Name:** ..., - **Designation:** ..., - **Department:** ..., - **Contact Email:** ..., - **Qualifications:** ...). Never combine multiple fields into a single line.\n"
                    "   - When presenting work experience for a faculty member, list each previous employment entry one by one in proper format: `- [Designation] at [Organization] ([Location]) (From: [From Date] to [To Date])`.\n"
                    "   - When presenting awards, honors, or achievements, list each one as a distinct bullet point.\n"
                    "   - For an individual faculty or person query, focus strictly on that individual; do NOT append a faculty roster, table of other department faculty, or other staff members at the end.\n"
                    "   - Do NOT output boilerplate placeholder phrases like 'Not explicitly specified in the provided data', 'Employee ID: Not explicitly specified', or 'Not specified'; if data for a field or section is not in the text, simply omit that line or heading entirely.\n"
                    "4. For committees or teams, clearly list the Coordinator/Head followed by the members with their respective designations or departments.\n"
                    "5. Do NOT use internal reasoning or thinking steps. Do NOT call search_site or read_page.\n"
                    "6. Do NOT include URLs or a 'Sources' section in your answer text (the interface renders source links separately).\n"
                    "7. Output your complete formatted response immediately."
                ),
            })
        else:
            augmented_messages.append({"role": "user", "content": user_query})

        if context_block:
            yield sse("tool_call", name="search_site") + f": {' ' * 1024}\n\n"
            yield sse("tool_output")
            yield sse("tool_call", name="read_page") + f": {' ' * 1024}\n\n"
            yield sse("tool_output")
        # ──────────────────────────────────────────────────────────────────────

        async def run_llm_stream():
            nonlocal active_runner_result
            try:
                result = Runner.run_streamed(
                    agent,
                    augmented_messages,  # type: ignore
                    max_turns=3,
                )
                active_runner_result = result
                async for event in result.stream_events():
                    stop_ping.set()
                    await event_queue.put(event)
            except asyncio.CancelledError:
                log.info("run_llm_stream task cancelled for req_id: %s", req_id)
                if active_runner_result:
                    try:
                        active_runner_result.cancel(mode="immediate")
                    except Exception:
                        pass
                raise
            except Exception as exc:
                stop_ping.set()
                await event_queue.put(exc)
            finally:
                stop_ping.set()
                await event_queue.put(None)

        async def pinger():
            try:
                while not stop_ping.is_set():
                    await asyncio.sleep(2.0)
                    if not stop_ping.is_set():
                        await event_queue.put(": keep-alive\n\n")
            except asyncio.CancelledError:
                pass

        ping_task = asyncio.create_task(pinger())
        stream_task = asyncio.create_task(run_llm_stream())

        while True:
            if request is not None and await request.is_disconnected():
                log.info("Client disconnected detected in stream_answer: %s", req_id)
                cancel_this_stream()
                break

            try:
                item = await asyncio.wait_for(event_queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                if request is not None and await request.is_disconnected():
                    log.info("Client disconnected during timeout in stream_answer: %s", req_id)
                    cancel_this_stream()
                    break
                continue

            if item is None:
                break
            if isinstance(item, str):
                yield item
                continue
            if isinstance(item, Exception):
                raise item

            event = item
            if event.type == "raw_response_event":
                if isinstance(event.data, ResponseTextDeltaEvent):
                    if first_token_time is None:
                        first_token_time = time.perf_counter()
                    token_count += 1
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

        ping_task.cancel()
        await stream_task

        chosen = pick_sources("".join(answer), searches, reads)
        sources = [{"url": u, "title": source_title(index, u)} for u in chosen]
        for s in pdf_sources:
            if len(sources) < MAX_SOURCES and not any(x["url"] == s["url"] for x in sources):
                sources.append(s)
        if sources:
            yield sse("sources", sources=sources)
        total_time = round(time.perf_counter() - start_time, 2)
        ttft = round(first_token_time - start_time, 2) if first_token_time else total_time
        gen_time = max(0.01, (time.perf_counter() - (first_token_time or start_time)))
        tok_per_sec = round(token_count / gen_time, 1) if token_count else 0.0
        log_terminal_benchmark(
            query=user_query,
            route="Website Agent",
            total_time=total_time,
            ttft=ttft,
            tokens=token_count,
            tok_per_sec=tok_per_sec,
        )
        yield sse("done")
    except (asyncio.CancelledError, GeneratorExit):
        log.info("stream_answer received cancellation / GeneratorExit for req_id: %s", req_id)
        cancel_this_stream()
        raise
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
    finally:
        cancel_this_stream()
        if req_id:
            ACTIVE_REQUESTS.pop(req_id, None)


def prefetch_pdf_context(query: str, top_k: int = 5) -> tuple[str, list[dict[str, str]]]:
    """
    Prefetch relevant PDF document chunks before running the LLM.
    Guarantees that official documents (e.g. NBA accreditation, IPR team,
    Internship, Emergency Exits, Epsilon brochure) are searched and grounded.
    """
    import urllib.parse

    all_chunks = []
    seen_ids = set()

    # 1. Primary search with full query
    try:
        primary = pdf_rag.hybrid_search(query, top_k=top_k)
        for c in primary:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                all_chunks.append(c)
    except Exception as e:
        log.warning("Primary hybrid_search failed: %s", e)

    # 2. Sub-clause search for multi-topic queries (e.g. "NBA accreditation and IPR team")
    clauses = re.split(r"\b(?:and|as well as|along with|\&)\b", query, flags=re.I)
    if len(clauses) > 1:
        for clause in clauses:
            clean_clause = clause.strip()
            clean_clause = re.sub(
                r"^(?:tell me about|what is|what are|explain|details? of|give|show)\s+",
                "",
                clean_clause,
                flags=re.I,
            ).strip()
            if len(clean_clause) >= 3:
                try:
                    sub_results = pdf_rag.hybrid_search(clean_clause, top_k=3)
                    for c in sub_results:
                        if c["id"] not in seen_ids:
                            seen_ids.add(c["id"])
                            all_chunks.append(c)
                except Exception as e:
                    log.warning("Sub-clause hybrid_search failed for '%s': %s", clean_clause, e)

    if not all_chunks:
        return "", []

    sections = []
    sources = []
    for index, item in enumerate(all_chunks[:8], start=1):
        clean_title = urllib.parse.unquote(item["title"]).replace("_", " ")
        url = item.get("source", "")
        if url and not any(s["url"] == url for s in sources):
            sources.append({"url": url, "title": clean_title})

        sections.append(
            f"[Source {index}: {clean_title}]\n"
            f"Document: {clean_title}\n"
            f"Content:\n{item['text']}"
        )

    context_block = (
        "OFFICIAL SIES GST PDF DOCUMENT CONTEXT:\n"
        "======================================\n"
        + "\n\n---\n\n".join(sections)
        + "\n======================================"
    )
    return context_block, sources


async def stream_pdf_answer(
    agent: Any,
    messages: list[Msg],
    request: Request | None = None,
    req_id: str | None = None,
) -> AsyncIterator[str]:
    yield ": connected\n\n"
    start_time = time.perf_counter()
    first_token_time: float | None = None
    token_count = 0
    answer: list[str] = []
    pdf_sources: list[dict[str, str]] = []
    runner_result = None

    def cancel_pdf_stream():
        log.info("Cancelling stream_pdf_answer for req_id: %s", req_id)
        if runner_result:
            try:
                runner_result.cancel(mode="immediate")
            except Exception as e:
                log.debug("Error cancelling PDF runner: %s", e)

    if req_id:
        ACTIVE_REQUESTS[req_id] = cancel_pdf_stream

    if req_id and req_id in CANCELLED_REQUESTS:
        log.info("stream_pdf_answer aborted immediately for cancelled req_id: %s", req_id)
        yield sse("done")
        return

    try:
        user_query = messages[-1].content
        context_block, prefetched_sources = await asyncio.to_thread(
            prefetch_pdf_context, user_query
        )

        recent_messages = messages[-3:] if len(messages) > 3 else messages
        augmented_messages: list[dict[str, str]] = []
        for m in recent_messages[:-1]:
            content = m.content
            if m.role == "assistant" and len(content) > 500:
                content = content[:500] + "... [earlier response truncated]"
            augmented_messages.append({"role": m.role, "content": content})

        if context_block:
            pdf_sources.extend(prefetched_sources)
            yield sse("tool_call", name="search_sies_pdfs") + f": {' ' * 1024}\n\n"
            yield sse("tool_output")

            prompt = (
                f"{user_query}\n\n"
                f"{context_block}\n\n"
                "INSTRUCTIONS:\n"
                "1. Answer the user's question directly, comprehensively, and factually using ONLY the provided official document context above.\n"
                "2. When multiple topics or documents are asked (e.g. NBA accreditation and IPR team), address each topic under distinct Markdown headings (### NBA Accreditation, ### IPR Team / KAPILA Committee).\n"
                "3. FORMATTING (CRITICAL):\n"
                "   - When presenting structured tabular information from official documents (such as committee members or lists with columns like Designation, Name, Organization, Contact, Email), format it as a clean Markdown table as given in the source document.\n"
                "   - Every metadata field MUST be on its own separate line as a distinct bullet point:\n"
                "     - **Validity Period:** Academic Years 2024-2025 to 2026-2027 (up to 30 June 2027)\n"
                "     - **Basis of Evaluation:** Tier-II June 2015 Document\n"
                "     - **Accreditation Scope:** Program accreditation (not institutional)\n"
                "   - Never run multiple fields, labels, or headers together on the same line.\n"
                "4. Do NOT invent dates, committee members, or document titles. Do NOT cite documents that are not in the context.\n"
                "5. Do NOT call search_sies_pdfs. Do NOT output tool call tags like <tool_call> or JSON in your answer.\n"
                "6. Do NOT include URLs or a 'Sources' section in your answer text (the interface renders source links separately).\n"
                "7. Output your complete formatted response immediately."
            )
            augmented_messages.append({"role": "user", "content": prompt})
        else:
            augmented_messages.append({"role": "user", "content": user_query})

        result = Runner.run_streamed(
            agent,
            augmented_messages,  # type: ignore
            max_turns=3 if context_block else 6,
        )
        runner_result = result
        tool_call_buffer = ""
        suppress_tool_call = False

        async for event in result.stream_events():
            if request is not None and await request.is_disconnected():
                log.info("Client disconnected detected in stream_pdf_answer: %s", req_id)
                cancel_pdf_stream()
                break

            if event.type == "raw_response_event":
                if isinstance(event.data, ResponseTextDeltaEvent):
                    delta = event.data.delta
                    tool_call_buffer += delta
                    if "<tool_call>" in tool_call_buffer:
                        suppress_tool_call = True
                    if "</tool_call>" in tool_call_buffer:
                        tool_call_buffer = re.sub(r"<tool_call>.*?</tool_call>", "", tool_call_buffer, flags=re.DOTALL)
                        suppress_tool_call = False
                        continue
                    if suppress_tool_call:
                        continue

                    if first_token_time is None:
                        first_token_time = time.perf_counter()
                    token_count += 1
                    answer.append(delta)
                    yield sse("token", text=delta)

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
            full_ans_lower = "".join(answer).lower()
            q_lower = user_query.lower()
            filtered_sources = []
            for s in pdf_sources:
                t_lower = s["title"].lower()
                title_words = [
                    w for w in re.findall(r"\w+", t_lower)
                    if len(w) > 3 and w not in ["letter", "document", "report", "with", "from"]
                ]
                if any(w in q_lower or w in full_ans_lower for w in title_words):
                    filtered_sources.append(s)

            final_sources = filtered_sources if filtered_sources else pdf_sources
            yield sse("sources", sources=final_sources[:MAX_SOURCES])
        total_time = round(time.perf_counter() - start_time, 2)
        ttft = round(first_token_time - start_time, 2) if first_token_time else total_time
        gen_time = max(0.01, (time.perf_counter() - (first_token_time or start_time)))
        tok_per_sec = round(token_count / gen_time, 1) if token_count else 0.0
        user_query = messages[-1].content
        log_terminal_benchmark(
            query=user_query,
            route="PDF Documents",
            total_time=total_time,
            ttft=ttft,
            tokens=token_count,
            tok_per_sec=tok_per_sec,
        )
        yield sse("done")
    except (asyncio.CancelledError, GeneratorExit):
        log.info("stream_pdf_answer received cancellation / GeneratorExit for req_id: %s", req_id)
        cancel_pdf_stream()
        raise
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
    finally:
        cancel_pdf_stream()
        if req_id:
            ACTIVE_REQUESTS.pop(req_id, None)


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


@app.post("/api/chat/cancel")
async def cancel_chat(
    req: CancelRequest | None = None,
    request_id: str | None = None,
) -> dict[str, str]:
    target_id = (req.request_id if req and req.request_id else request_id) or ""
    if target_id:
        CANCELLED_REQUESTS.add(target_id)
        if len(CANCELLED_REQUESTS) > 1000:
            CANCELLED_REQUESTS.pop()
    cb = ACTIVE_REQUESTS.pop(target_id, None)
    if cb:
        try:
            cb()
            log.info("Explicitly cancelled generation for request %s", target_id)
            return {"status": "cancelled", "request_id": target_id}
        except Exception as e:
            log.warning("Error cancelling request %s: %s", target_id, e)
    return {"status": "marked_cancelled", "request_id": target_id}


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request) -> StreamingResponse:
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
    req_id = req.request_id or request.headers.get("x-request-id") or str(uuid.uuid4())
    return StreamingResponse(
        stream_answer(agent, index, req.messages, request=request, req_id=req_id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


from agent import agent as intent_agent
from agents import Runner


_syllabus_courses_re: re.Pattern | None = None


def get_syllabus_courses_regex() -> re.Pattern | None:
    global _syllabus_courses_re
    if _syllabus_courses_re is None:
        try:
            from rag.retriever import _course_sections
            from rag.generator import extract_course_name_from_header

            sections = _course_sections()
            phrases: set[str] = set()
            for s in sections:
                code = s.get("code", "")
                if code:
                    phrases.add(re.escape(code.lower()))
                header = s.get("header", "")
                name = extract_course_name_from_header(header)
                clean = re.sub(r"[\s\-]+(lab|laboratory)$", "", name, flags=re.I).strip()
                clean = re.sub(r"^[^a-zA-Z]+", "", clean).strip()
                clean = re.sub(r"\s+Program Outcomes.*", "", clean, flags=re.I).strip()
                if len(clean) >= 4 and not clean.lower().startswith(("rtc", "esp", "hx7")):
                    phrases.add(re.escape(clean.lower()))
            if phrases:
                pattern = r"\b(?:" + "|".join(sorted(phrases, key=len, reverse=True)) + r")\b"
                _syllabus_courses_re = re.compile(pattern, re.IGNORECASE)
        except Exception as e:
            log.warning("Could not build dynamic syllabus courses regex: %s", e)
    return _syllabus_courses_re


_faculty_names_re: re.Pattern | None = None


def get_faculty_names_regex() -> re.Pattern | None:
    global _faculty_names_re
    if _faculty_names_re is None:
        try:
            pages = sa.load_or_build_pages(refresh=False)
            stopwords = {
                "and", "for", "the", "with", "from", "sies", "gst", "college", "school",
                "technology", "department", "engineering", "science", "humanities",
                "view", "material", "date", "course", "courses", "staff", "name",
                "principal", "leadership", "assistant", "professor", "associate",
                "lecturer", "faculty", "member", "head", "degree", "status", "about",
                "computer", "information", "mechanical", "electronics", "telecommunication",
                "electrical", "civil", "applied", "general", "first", "second", "third",
                "year", "semester", "academic", "institute", "institution", "university",
                "mumbai", "navi", "thane", "pune", "india", "maharashtra",
                "syllabus", "curriculum", "workshop", "module", "modules", "subject", "subjects",
                "scheme", "credit", "credits", "examination", "exam", "practical", "practicals",
                "lab", "labs", "laboratory", "laboratories", "project", "projects", "paper", "papers",
                "journal", "journals", "conference", "conferences", "national", "international",
            }
            tokens: set[str] = set()
            for p in pages:
                url = p.get("url", "")
                lines = p.get("lines", [])
                if "/faculty/" in url:
                    slug = url.split("/faculty/")[-1].strip("/")
                    for pt in slug.split("-"):
                        if len(pt) >= 3 and pt.lower() not in stopwords:
                            tokens.add(pt.lower())
                    # If slug ends with a single letter initial like deepikak -> deepika
                    m_initial = re.match(r"^([a-z]{4,})[a-z]$", slug.lower())
                    if m_initial and m_initial.group(1) not in stopwords:
                        tokens.add(m_initial.group(1))
                    clean_slug = slug.replace("-", " ").strip().lower()
                    if len(clean_slug) >= 3 and clean_slug not in stopwords:
                        tokens.add(clean_slug)
                    # Check first 4 lines of faculty page for short name lines (max 4 words)
                    for l in lines[:4]:
                        l_strip = l.strip()
                        if l_strip.startswith("##") or "@" in l_strip or "Home" in l_strip or "Serving" in l_strip:
                            continue
                        clean_l = re.sub(r"^(?:dr|mr|ms|mrs|prof)\.?\s*", "", l_strip, flags=re.I)
                        clean_l = re.sub(r"[^\w\s]", " ", clean_l).strip()
                        words = [w.lower() for w in clean_l.split() if len(w) >= 3 and w.lower() not in stopwords]
                        if 1 <= len(clean_l.split()) <= 4:
                            if len(words) >= 2:
                                tokens.add(" ".join(words))
                            for w in words:
                                tokens.add(w)
                for l in lines:
                    if l.startswith("Name of the Staff:"):
                        m = re.search(r"Name of the Staff:\s*(?:dr\.?|mr\.?|ms\.?|mrs\.?|prof\.?)?\s*([^;]+)", l, re.I)
                        if m:
                            raw_name = m.group(1).strip()
                            clean_name = re.sub(r"[\.\-]+", " ", raw_name).strip()
                            words = [w.lower() for w in clean_name.split() if len(w) >= 3 and w.lower() not in stopwords]
                            if len(words) >= 2:
                                tokens.add(" ".join(words))
                            for w in words:
                                tokens.add(w)
            if tokens:
                pattern = r"\b(?:" + "|".join(sorted([re.escape(t) for t in tokens], key=len, reverse=True)) + r")\b"
                _faculty_names_re = re.compile(pattern, re.IGNORECASE)
        except Exception as e:
            log.warning("Could not build dynamic faculty names regex: %s", e)
    return _faculty_names_re


FAST_SYLLABUS_RE = re.compile(
    r"\b(sem|semester|syllabus|curriculum|module|modules|course|courses|subject|subjects|credits?|"
    r"mini\s*projects?|major\s*projects?|capstone\s*projects?|CEM301|CEM401|CEM501|CEP601|CEP701|CEP801|"
    r"nomenclature|course\s+nomenclature|"
    r"exam|examination|scheme|internal assessment|assessment|evaluation|term\s*work|bifurcation|distribution|"
    r"ese|ise|ciap|esep|mse|practicals?|experiments?|"
    r"labs?|textbooks?|references?|minors?|mdm|electives?|pep|oec|hours?|teaching scheme|"
    r"unit\s*\d+|topics?|outcomes?|course\s*outcome|program\s*outcome|los|cos)\b"
    # Course codes must have a recognised 3-letter+ prefix followed by digits
    r"|\b(?:FEC|FEL|CEC|CEL|CEPEC|CEPEL|MDMC|MDML|OEC|CSC|CSL|ITC|ITL|AIDS|AIML)\d{2,4}[A-Z0-9/]*\b"
    # Common academic course abbreviations and shorthands
    r"|\b(?:m-?[1-4]|am-?[1-4]|maths?-?[1-4]|maths?-?[iIvVxX]+|dsa|ada|cns|coa|bda|hpc|dwm|eh|mv|df|adbms|dl|arvr|qc|rl|bc|se|cn|ics|tcs|spcc|aisc|dav|esr|scm|dmbi|st|obhrm|ra|dsgt|ctd|ee|spp|wt|oopm|beee?|cp|amrd|eg|dsd|pct|ew[12]|uhv|vec|mp[12][ab]?|mpi)\b"
    # Lab specific shorthands
    r"|\b(?:cn|se|dbms|ds|dsa|os|aoa|ada|coa|spcc|cns|ai|aisc|ci|cc|dwm|iot|eh|adbms|nlp|df|mv|ra|dav|esr|st|dmbi|ics|devops|wt|spp|python|oopm|dsd|eg|bee|beee|cp|amrd|ap|ac|pct)\s*labs?\b"
    # Common academic subjects & syllabus courses
    r"|\b(?:computer\s*networks?|theoretical\s*computer\s*science|tcs|data\s*structures?|"
    r"discrete\s*structures?|graph\s*theory|database\s*management|dbms|"
    r"computer\s*organization|operating\s*systems?|analysis\s*of\s*algorithms?|aoa|"
    r"software\s*engineering|cryptography|network\s*security|artificial\s*intelligence|"
    r"machine\s*learning|soft\s*computing|system\s*programming|compiler\s*construction|"
    r"spcc|digital\s*forensics?|machine\s*vision|internet\s*of\s*things|iot|"
    r"natural\s*language\s*processing|nlp|cloud\s*computing|devops|"
    r"interpersonal(\s*(?:and|&)?\s*career\s*skills?)?|career\s*skills?|"
    r"robotics(\s*and\s*applications)?|sensor\s*technology|ethical\s*hacking|"
    r"data\s*warehouse(\s*and\s*mining)?|applied\s*mathematics|engineering\s*economics|"
    r"critical\s*thinking|applied\s*physics|applied\s*chemistry|engineering\s*graphics|"
    r"digital\s*system\s*design|dsd|basic\s*electrical|robot\s*dynamics|"
    r"c\s*programming|python\s*programming|web\s*technology)\b",
    re.IGNORECASE,
)

FAST_DOCUMENT_RE = re.compile(
    r"\b(pdf|documents?|brochures?|polic(y|ies)|guidelines?|rules?|regulations?|handbook|"
    r"code of conduct|accreditation|nba|naac|nirf|ipr|patents?|emergency exits?|floor plans?|"
    r"internships?|mous?|epsilon)\b",
    re.IGNORECASE,
)

FAST_WEBSITE_RE = re.compile(
    r"\b(who\s+is|who\s+was|who\s+are|tell\s+me\s+about|details\s+of|profile\s+of|bio\s+of|"
    r"dr\.?|ms\.?|mr\.?|mrs\.?|prof\.?|professor|faculty|teachers?|staff|lecturer|instructor|ma\'?am|mam|sir|madam|hod|principal|dean|admissions?|fees?|placements?|"
    r"packages?|highest package|average package|companies|recruiters|campus|canteen|cafeteria|mess|library|"
    r"hostel|events?|fest|cultural fest|tech fest|rotaract|student council|contact|address|location|reach|bus|train|"
    r"railway|concession|documents? required|eligibility criteria|"
    r"facilities|infrastructure|auditorium|gymkhana|sports|ground|wifi|"
    r"timings?|working\s+hours?|holiday|vacation|academic\s+calendar|exam\s+cell|"
    r"cut\s*offs?|cap\s*round|dse|direct\s*second\s*year|seat\s*matrix|"
    r"scholarships?|financial\s*aid|fee\s*structure|"
    r"lakshya|cognition|tatva|saison|tedx|ecell|e-cell|gdsc|dsc|"
    r"about\s+(?:sies|gst|college|campus|institute)|vision|mission|"
    # College-wide degree programs, branches, courses offered
    r"courses?\s+offered|programs?\s+offered|degrees?\s+offered|branches?\s+offered|"
    r"courses?\s+available|programs?\s+available|degrees?\s+available|branches?\s+available|"
    r"what\s+(?:are\s+the\s+)?(?:courses|programs|degrees|branches)\b|"
    r"(?:courses|programs|branches|degrees)\s+(?:in|at|of)\b|"
    r"undergraduate\s+programs?|postgraduate\s+programs?|ug\s+programs?|pg\s+programs?|"
    r"ug\s+courses?|pg\s+courses?|b\.?tech\s+courses?|b\.?e\.?\s+courses?|"
    r"branches\b|departments\b|intake\b|seats?\s+available\b|"
    # SIES GST institutional cells, committees, and bodies
    r"IIIC|iiic|innovation.*incubation|incubation.*cell|"
    r"iste|nss|cultural committee|sports committee|"
    r"tpc|training.*placement|placement.*cell|"
    r"grievance|anti.?ragging|ragging|posh|"
    r"iqac|internal quality|cdc|career development|"
    r"alumni|entrepreneurship|e.?cell|"
    r"ieee|csi|acm|technical committee|"
    r"research committee|r&d|wep|women|gender|"
    r"mentoring|mentor|welfare|scholarship|"
    r"committee|cell|council|club|association|society|chapter)\b",
    re.IGNORECASE,
)


def fast_classify_intent(query: str) -> str | None:
    # 0. Nomenclature, course abbreviations, or mini/major projects route directly to syllabus
    if re.search(
        r"\b(nomenclature|course\s+nomenclature|abbreviations?\s+in\s+(?:the\s+)?curriculum|"
        r"mini\s*projects?|major\s*projects?|capstone\s*projects?|"
        r"CEM301|CEM401|CEM501|CEP601|CEP701|CEP801)\b",
        query,
        re.I,
    ):
        return "syllabus"
    # 1. Faculty names, staff names, institutional cells, committees, faculty, HOD, campus route to website
    fac_rgx = get_faculty_names_regex()
    if (fac_rgx and fac_rgx.search(query)) or FAST_WEBSITE_RE.search(query):
        return "website"
    # 2. PDF documents, policies, brochures route to document
    if FAST_DOCUMENT_RE.search(query):
        return "document"
    # 3. Dynamic course catalog check or syllabus keywords route to syllabus
    crgx = get_syllabus_courses_regex()
    if (crgx and crgx.search(query)) or FAST_SYLLABUS_RE.search(query):
        return "syllabus"
    # 4. Check with reframed/expanded abbreviations (e.g. M3 -> Applied Mathematics- III)
    try:
        from rag.query_rewriter import reframe_query
        expanded = reframe_query(query)
        if expanded != query:
            if (fac_rgx and fac_rgx.search(expanded)) or FAST_WEBSITE_RE.search(expanded):
                return "website"
            if (crgx and crgx.search(expanded)) or FAST_SYLLABUS_RE.search(expanded):
                return "syllabus"
    except Exception:
        pass
    return None


@app.post("/api/smart_chat")
async def smart_chat(req: ChatRequest, request: Request) -> StreamingResponse:
    if req.messages[-1].role != "user":
        raise HTTPException(
            status_code=422, detail="The last message must be from the user."
        )

    last_message = req.messages[-1].content
    req_id = req.request_id or request.headers.get("x-request-id") or str(uuid.uuid4())

    if req_id and req_id in CANCELLED_REQUESTS:
        log.info("smart_chat aborted early for cancelled req_id: %s", req_id)
        return StreamingResponse(
            iter([sse("done")]),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    # Fast-path hybrid intent routing (instant: 0.0001s)
    intent = fast_classify_intent(last_message)
    if intent is None:
        intent_task: asyncio.Task[Any] | None = None

        def cancel_intent():
            if intent_task and not intent_task.done():
                intent_task.cancel()

        if req_id:
            ACTIVE_REQUESTS[req_id] = cancel_intent

        try:
            from agent import Message

            intent_task = asyncio.create_task(Runner.run(intent_agent, last_message))
            result = await asyncio.wait_for(intent_task, timeout=3.5)
            parsed = result.final_output_as(Message)
            intent = parsed.intent
        except (asyncio.CancelledError, GeneratorExit):
            log.info("Intent classification cancelled for req_id: %s", req_id)
            return StreamingResponse(
                iter([sse("done")]),
                media_type="text/event-stream",
                headers=SSE_HEADERS,
            )
        except asyncio.TimeoutError:
            log.warning("Intent classification timed out after 3.5s, using fast heuristic fallback")
            if re.search(
                r"\b(nomenclature|course\s+nomenclature|abbreviations?\s+in\s+(?:the\s+)?curriculum|"
                r"mini\s*projects?|major\s*projects?|capstone\s*projects?|"
                r"CEM301|CEM401|CEM501|CEP601|CEP701|CEP801)\b",
                last_message,
                re.I,
            ):
                intent = "syllabus"
            else:
                fac_rgx = get_faculty_names_regex()
                if (fac_rgx and fac_rgx.search(last_message)) or FAST_WEBSITE_RE.search(last_message):
                    intent = "website"
                elif FAST_DOCUMENT_RE.search(last_message):
                    intent = "document"
                else:
                    crgx = get_syllabus_courses_regex()
                    if (crgx and crgx.search(last_message)) or FAST_SYLLABUS_RE.search(last_message):
                        intent = "syllabus"
                    else:
                        intent = "website"
        except Exception as e:
            if (req_id and req_id in CANCELLED_REQUESTS) or (request is not None and await request.is_disconnected()):
                log.info("Cancelled during intent classification for req_id: %s", req_id)
                return StreamingResponse(
                    iter([sse("done")]),
                    media_type="text/event-stream",
                    headers=SSE_HEADERS,
                )
            log.error(f"Intent classifier failed: {e}")
            if re.search(
                r"\b(nomenclature|course\s+nomenclature|abbreviations?\s+in\s+(?:the\s+)?curriculum|"
                r"mini\s*projects?|major\s*projects?|capstone\s*projects?|"
                r"CEM301|CEM401|CEM501|CEP601|CEP701|CEP801)\b",
                last_message,
                re.I,
            ):
                intent = "syllabus"
            else:
                fac_rgx = get_faculty_names_regex()
                if (fac_rgx and fac_rgx.search(last_message)) or FAST_WEBSITE_RE.search(last_message):
                    intent = "website"
                elif FAST_DOCUMENT_RE.search(last_message):
                    intent = "document"
                else:
                    crgx = get_syllabus_courses_regex()
                    if (crgx and crgx.search(last_message)) or FAST_SYLLABUS_RE.search(last_message):
                        intent = "syllabus"
                    else:
                        intent = "website"
        finally:
            if req_id:
                ACTIVE_REQUESTS.pop(req_id, None)

    if req_id and req_id in CANCELLED_REQUESTS:
        log.info("smart_chat aborted before dispatching for req_id: %s", req_id)
        return StreamingResponse(
            iter([sse("done")]),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    log.info(f"Routed query to: {intent} (req_id: {req_id})")

    if intent == "syllabus":

        async def stream_syllabus():
            yield ": connected\n\n"
            start_time = time.perf_counter()
            first_token_time: float | None = None
            token_count = 0
            cancel_event = threading.Event()

            def cancel_syllabus_stream():
                log.info("Cancelling stream_syllabus for req_id: %s", req_id)
                cancel_event.set()

            if req_id:
                ACTIVE_REQUESTS[req_id] = cancel_syllabus_stream

            if req_id and req_id in CANCELLED_REQUESTS:
                log.info("stream_syllabus aborted immediately for cancelled req_id: %s", req_id)
                yield sse("done")
                return

            try:
                yield sse("tool_call", name="search_syllabus") + f": {' ' * 2048}\n\n"

                from rag.rag_pipeline import ask_sies_gpt
              

                q = queue.Queue()

                def run():
                    try:
                        res = ask_sies_gpt(last_message, yield_callback=q.put, cancel_event=cancel_event)
                        ans = res.get("answer", "") if isinstance(res, dict) else ""
                        q.put({"type": "_fallback_answer", "answer": ans})
                    except Exception as e:
                        q.put(e)
                    finally:
                        q.put(None)

                t = threading.Thread(target=run, daemon=True)
                t.start()

                while True:
                    if request is not None and token_count > 0 and await request.is_disconnected():
                        log.info("Client disconnected detected in stream_syllabus: %s", req_id)
                        cancel_syllabus_stream()
                        break

                    try:
                        item = await asyncio.to_thread(q.get, timeout=0.25)
                    except queue.Empty:
                        if not t.is_alive():
                            break
                        continue

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
                            if first_token_time is None:
                                first_token_time = time.perf_counter()
                            token_count += 1
                            yield sse("token", text=item["text"])
                        elif item["type"] == "_fallback_answer":
                            if token_count == 0 and not cancel_event.is_set() and item.get("answer"):
                                ans_tokens = re.findall(r"\S+|\n|\s+", item["answer"])
                                for tok in ans_tokens:
                                    if first_token_time is None:
                                        first_token_time = time.perf_counter()
                                    token_count += 1
                                    yield sse("token", text=tok)

                total_time = round(time.perf_counter() - start_time, 2)
                ttft = round(first_token_time - start_time, 2) if first_token_time else total_time
                gen_time = max(0.01, (time.perf_counter() - (first_token_time or start_time)))
                tok_per_sec = round(token_count / gen_time, 1) if token_count else 0.0
                log_terminal_benchmark(
                    query=last_message,
                    route="Syllabus RAG",
                    total_time=total_time,
                    ttft=ttft,
                    tokens=token_count,
                    tok_per_sec=tok_per_sec,
                )
                yield sse("done")
            except (asyncio.CancelledError, GeneratorExit):
                log.info("stream_syllabus received cancellation / GeneratorExit for req_id: %s", req_id)
                cancel_syllabus_stream()
                raise
            except Exception as e:
                log.exception("Syllabus stream failed")
                yield sse("error", text=str(e))
            finally:
                cancel_syllabus_stream()
                if req_id:
                    ACTIVE_REQUESTS.pop(req_id, None)

        return StreamingResponse(
            stream_syllabus(),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    elif intent == "document":
        pdf_agent = state.pdf_agent
        if pdf_agent is None:
            app_agent, index = state.agent, state.index
            if app_agent is None or index is None:
                raise HTTPException(status_code=503, detail="Index not ready.")
            return StreamingResponse(
                stream_answer(app_agent, index, req.messages, request=request, req_id=req_id),
                media_type="text/event-stream",
                headers=SSE_HEADERS,
            )
        return StreamingResponse(
            stream_pdf_answer(pdf_agent, req.messages, request=request, req_id=req_id),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    else:
        app_agent, index = state.agent, state.index
        if app_agent is None or index is None:
            raise HTTPException(status_code=503, detail="Index not ready.")
        return StreamingResponse(
            stream_answer(app_agent, index, req.messages, request=request, req_id=req_id),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )


@app.post("/api/pdf_chat")
async def pdf_chat(req: ChatRequest, request: Request) -> StreamingResponse:
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
    req_id = req.request_id or request.headers.get("x-request-id") or str(uuid.uuid4())
    return StreamingResponse(
        stream_pdf_answer(agent, req.messages, request=request, req_id=req_id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
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
