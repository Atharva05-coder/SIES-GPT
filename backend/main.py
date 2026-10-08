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

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("api")

SOURCES_NOTE = (
    "Interface note: the app shows source links automatically below your answer. "
    "Do not include URLs or a 'Sources' section in your answer, even if an earlier rule says to."
)
SOURCE_LINE = re.compile(r"^Source: (\S+)", re.MULTILINE)
MAX_SOURCES = 4
PER_SEARCH = 3


# ------------------------------- app state -------------------------------- #
class AppState:
    def __init__(self):
        self.index: sa.SiteIndex | None = None
        self.agent: Any = None
        self.building = False
        self.error: str | None = None
        self.lock = asyncio.Lock()
        self.tasks: set[asyncio.Task[None]] = set()


state = AppState()


def _build(refresh: bool) -> tuple[sa.SiteIndex, Any]:
    index = sa.SiteIndex(sa.load_or_build_pages(refresh=refresh))
    agent = sa.build_agent(index)
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


def spawn(coro: Coroutine[Any, Any, None]) -> None:
    task = asyncio.create_task(coro)
    state.tasks.add(task)  # keep a reference so the task isn't garbage-collected
    task.add_done_callback(state.tasks.discard)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    spawn(
        rebuild(refresh=False)
    )  # server starts immediately; index builds in background
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
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[Msg] = Field(min_length=1, max_length=20)


# -------------------------------- sources --------------------------------- #
def dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def pick_sources(answer: str, searches: list[list[str]], reads: list[str]) -> list[str]:
    """Prefer pages the answer mentions; otherwise pages the agent read in full,
    then the top results of each search."""
    retrieved = dedupe([u for hits in searches for u in hits])
    cited = [u for u in dedupe(reads + retrieved) if u in answer]
    fallback = dedupe(reads + [u for hits in searches for u in hits[:PER_SEARCH]])
    return (cited or fallback)[:MAX_SOURCES]


def source_title(index: sa.SiteIndex, url: str) -> str:
    page = index.pages.get(url)
    label = page["label"] if page else sa.page_label(url)
    return "SIES GST" if label == "home" else label.title()


# -------------------------------- streaming ------------------------------- #
def sse(event_type: str, **data: Any) -> str:
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


async def stream_answer(
    agent: Any, index: sa.SiteIndex, messages: list[Msg]
) -> AsyncIterator[str]:
    answer: list[str] = []
    searches: list[list[str]] = []
    reads: list[str] = []
    try:
        result = Runner.run_streamed(
            agent,
            [m.model_dump() for m in messages],  # type: ignore
            max_turns=sa.MAX_TURNS,
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
                    yield sse("tool_output")

        chosen = pick_sources("".join(answer), searches, reads)
        if chosen:
            yield sse(
                "sources",
                sources=[{"url": u, "title": source_title(index, u)} for u in chosen],
            )
        yield sse("done")
    except MaxTurnsExceeded:
        yield sse(
            "error",
            message="The assistant took too many steps. Try a more specific question.",
        )
    except Exception:
        log.exception("chat stream failed")
        yield sse(
            "error",
            message="Something went wrong. Check that the model server is running.",
        )


# -------------------------------- endpoints ------------------------------- #
@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ready": state.agent is not None,
        "building": state.building,
        "pages": len(state.index.pages) if state.index else 0,
        "chunks": len(state.index.chunks) if state.index else 0,
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

@app.post("/api/smart_chat")
async def smart_chat(req: ChatRequest) -> StreamingResponse:
    if req.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="The last message must be from the user.")
        
    last_message = req.messages[-1].content
    
    # Classify intent using the new agent in agent.py
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
                yield sse("tool_call", name="search_syllabus")
                from rag.rag_pipeline import ask_sies_gpt
                result = await asyncio.to_thread(ask_sies_gpt, last_message)
                yield sse("tool_output")
                yield sse("token", text=result["answer"])
                
                # Group sources by filename so pages are grouped together
                grouped_dict = {}
                for s in result.get("sources", []):
                    filename = s.get("filename")
                    page = s.get("page")
                    url = s.get("url") or f"https://siesgst.edu.in/images/{filename}"
                    
                    if filename not in grouped_dict:
                        grouped_dict[filename] = {"url": url, "pages": []}
                    
                    if page not in grouped_dict[filename]["pages"]:
                        grouped_dict[filename]["pages"].append(page)
                
                grouped_sources = []
                for filename, data in grouped_dict.items():
                    pages_str = ", ".join(str(p) for p in sorted(data["pages"]))
                    title = f"{filename} (Pages {pages_str})" if len(data["pages"]) > 1 else f"{filename} (Page {pages_str})"
                    grouped_sources.append({
                        "url": data["url"],
                        "title": title
                    })
                
                if grouped_sources:
                    yield sse("sources", sources=grouped_sources)
                    
                yield sse("done")
            except Exception as e:
                log.exception("Syllabus stream failed")
                yield sse("error", message="Syllabus search failed.")
                
        return StreamingResponse(
            stream_syllabus(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
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
