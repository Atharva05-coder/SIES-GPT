#!/usr/bin/env python3

"""
SIES GST website Q&A agent.

Usage:

    python site_agent.py --test
    python site_agent.py --inspect computer-engineering
    python site_agent.py "Who are the faculty in Computer Engineering?"
    python site_agent.py --refresh "..."
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime

from collections import Counter, deque
from pathlib import Path
from urllib import robotparser
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from rank_bm25 import BM25Okapi

from agents import (
    Agent,
    ModelSettings,
    OpenAIChatCompletionsModel,
    Runner,
    function_tool,
    set_tracing_disabled,
)

from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent

load_dotenv(Path(__file__).resolve().parent / ".env")
set_tracing_disabled(True)


# ----------------------------- configuration ------------------------------ #

DOMAIN = "siesgst.edu.in"
START_URL = f"https://{DOMAIN}/"

USER_AGENT = "Mozilla/5.0 (compatible; SIESGST-QA-Bot/1.0)"

MAX_PAGES = 250
MAX_DEPTH = 3
REQUEST_DELAY = 0.3

CACHE_FILE = Path(__file__).resolve().parent / "data" / "site_cache.json"
CACHE_MAX_AGE_DAYS = 7
PARSER_VERSION = 2

CHUNK_MAX_CHARS = 1500
BOILERPLATE_RATIO = 0.4

TOP_K = 6
META_BOOST = 1.0
READ_PAGE_CHARS = 6000

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://llama.atharva-amrutkar.in/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "V7mQ2xL9pR4kT8nC")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")

MAX_TURNS = 10


SKIP_EXTENSIONS = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".zip",
    ".rar",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".mp4",
    ".mp3",
)

SKIP_URL_PARTS = (
    "login",
    "logout",
)


STOPWORDS = frozenset(
    "a an the of in on at for to and or is are was were "
    "who what which list me tell about its it with from by "
    "be as do does name names show give all please".split()
)


log = logging.getLogger("site_agent")


# -------------------------------- crawling -------------------------------- #


def make_session() -> requests.Session:
    session = requests.Session()

    session.headers["User-Agent"] = USER_AGENT

    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )

    adapter = HTTPAdapter(max_retries=retry)

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)

    parsed = urlparse(url)

    path = parsed.path.rstrip("/") or "/"

    return parsed._replace(
        path=path,
        fragment="",
    ).geturl()


def in_scope(url: str) -> bool:
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return False

    host = parsed.netloc.lower()

    if not (host == DOMAIN or host.endswith("." + DOMAIN)):
        return False

    lowered = url.lower()

    if lowered.split("?")[0].endswith(SKIP_EXTENSIONS):
        return False

    return not any(part in lowered for part in SKIP_URL_PARTS)


def load_robots(
    session: requests.Session,
) -> robotparser.RobotFileParser:

    rp = robotparser.RobotFileParser()

    try:
        resp = session.get(
            f"https://{DOMAIN}/robots.txt",
            timeout=10,
        )

        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
        else:
            rp.parse([])

    except requests.RequestException:
        rp.parse([])

    return rp


def sitemap_urls(
    session: requests.Session,
) -> list[str]:

    try:
        resp = session.get(
            f"https://{DOMAIN}/sitemap.xml",
            timeout=10,
        )

        if resp.status_code == 200:
            return re.findall(
                r"<loc>\s*(.*?)\s*</loc>",
                resp.text,
            )

    except requests.RequestException:
        pass

    return []


def page_label(url: str) -> str:
    slug = urlparse(url).path.strip("/").rsplit("/", 1)[-1]

    slug = re.sub(
        r"\.(php|html?)$",
        "",
        slug,
    )

    return re.sub(r"[-_]+", " ", slug).strip() or "home"


def table_to_text(table) -> str:

    rows = [tr.find_all(["th", "td"]) for tr in table.find_all("tr")]

    rows = [row for row in rows if row]

    if not rows:
        return "\n"

    texts = [
        [
            cell.get_text(
                " ",
                strip=True,
            )
            for cell in row
        ]
        for row in rows
    ]

    is_data_table = (
        len(rows) >= 2
        and len(texts[0]) >= 2
        and len({len(row) for row in texts}) == 1
        and all(
            len(value) <= 300 and "## " not in value for row in texts for value in row
        )
    )

    if is_data_table:

        header = texts[0]

        lines = [
            "; ".join(f"{h}: {v}" for h, v in zip(header, row) if v)
            for row in texts[1:]
        ]

        return "\n" + "\n".join(line for line in lines if line) + "\n"

    parts = [
        cell.get_text(
            "\n",
            strip=True,
        )
        for row in rows
        for cell in row
    ]

    return "\n" + "\n".join(part for part in parts if part) + "\n"


def html_to_lines(
    soup: BeautifulSoup,
) -> list[str]:

    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "iframe",
            "select",
            "button",
        ]
    ):
        tag.decompose()

    # Preserve headings.
    for heading in soup.find_all(re.compile(r"^h[1-4]$")):

        text = heading.get_text(
            " ",
            strip=True,
        )

        heading.replace_with(NavigableString(f"\n## {text}\n" if text else "\n"))

    # Convert tables.
    while True:

        tables = [table for table in soup.find_all("table") if not table.find("table")]

        if not tables:
            break

        for table in tables:
            table.replace_with(NavigableString(table_to_text(table)))

    lines = []

    for raw in soup.get_text("\n").splitlines():

        line = re.sub(
            r"\s+",
            " ",
            raw,
        ).strip()

        if line:
            lines.append(line)

    return lines


def crawl() -> list[dict]:

    session = make_session()

    robots = load_robots(session)

    start = normalize_url(START_URL)

    queue: deque[tuple[str, int]] = deque([(start, 0)])

    seen = {start}

    # Sitemap seeds.
    for extra in sitemap_urls(session):

        extra = normalize_url(extra)

        if in_scope(extra) and extra not in seen:
            seen.add(extra)

            queue.append((extra, 1))

    pages: list[dict] = []

    while queue and len(pages) < MAX_PAGES:

        url, depth = queue.popleft()

        if not robots.can_fetch(
            USER_AGENT,
            url,
        ):
            log.info(
                "robots.txt disallows %s",
                url,
            )
            continue

        try:
            resp = session.get(
                url,
                timeout=20,
            )

        except requests.RequestException as exc:

            log.warning(
                "fetch failed %s: %s",
                url,
                exc,
            )

            continue

        time.sleep(REQUEST_DELAY)

        if resp.status_code != 200 or "text/html" not in resp.headers.get(
            "content-type",
            "",
        ):
            continue

        final_url = normalize_url(resp.url)

        seen.add(final_url)

        soup = BeautifulSoup(
            resp.content,
            "html.parser",
        )

        # Discover links before modifying soup.
        if depth < MAX_DEPTH:

            for anchor in soup.find_all(
                "a",
                href=True,
            ):

                link = normalize_url(
                    urljoin(
                        final_url,
                        anchor["href"],  # pyright: ignore[reportArgumentType]
                    )
                )

                if in_scope(link) and link not in seen:
                    seen.add(link)

                    queue.append(
                        (
                            link,
                            depth + 1,
                        )
                    )

        pages.append(
            {
                "url": final_url,
                "label": page_label(final_url),
                "lines": html_to_lines(soup),
            }
        )

        log.info(
            "crawled %d: %s",
            len(pages),
            final_url,
        )

    return remove_boilerplate(pages)


def remove_boilerplate(
    pages: list[dict],
) -> list[dict]:

    if len(pages) < 5:
        return pages

    counts = Counter(line for page in pages for line in set(page["lines"]))

    limit = BOILERPLATE_RATIO * len(pages)

    for page in pages:

        page["lines"] = [line for line in page["lines"] if counts[line] <= limit]

    return [page for page in pages if page["lines"]]


def load_or_build_pages(
    refresh: bool = False,
) -> list[dict]:

    if CACHE_FILE.exists() and not refresh:

        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))

        age_days = (
            time.time()
            - data.get(
                "built_at",
                0,
            )
        ) / 86400

        if data.get("version") == PARSER_VERSION and age_days < CACHE_MAX_AGE_DAYS:

            log.info(
                "using cache (%d pages, %.1f days old)",
                len(data["pages"]),
                age_days,
            )

            return data["pages"]

        log.info("cache is stale or from " "an older parser; re-crawling")

    log.info(
        "crawling %s ...",
        DOMAIN,
    )

    pages = crawl()

    CACHE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    CACHE_FILE.write_text(
        json.dumps(
            {
                "version": PARSER_VERSION,
                "built_at": time.time(),
                "pages": pages,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return pages


# -------------------------------- indexing -------------------------------- #


def tokenize(
    text: str,
) -> list[str]:

    tokens = re.findall(
        r"[a-z0-9]+",
        text.lower(),
    )

    tokens = [token for token in tokens if token not in STOPWORDS]

    # Simple plural stripping.
    return [
        token[:-1] if (len(token) > 3 and token.endswith("s")) else token
        for token in tokens
    ]


def chunk_page(
    page: dict,
) -> list[dict]:

    chunks: list[dict] = []

    def emit(
        section: str,
        lines: list[str],
    ) -> None:

        text = "\n".join(lines)

        if len(text) >= 40:

            chunks.append(
                {
                    "url": page["url"],
                    "label": page["label"],
                    "section": section,
                    "text": text,
                }
            )

    section = ""
    buffer: list[str] = []
    size = 0

    for line in page["lines"]:

        if line.startswith("## "):

            emit(
                section,
                buffer,
            )

            section = line[3:]

            buffer = []
            size = 0

            continue

        if buffer and size + len(line) > CHUNK_MAX_CHARS:

            emit(
                section,
                buffer,
            )

            buffer = []
            size = 0

        buffer.append(line)

        size += len(line) + 1

    emit(
        section,
        buffer,
    )

    return chunks


class SiteIndex:

    def __init__(
        self,
        pages: list[dict],
    ):

        self.pages = {page["url"]: page for page in pages}

        self.chunks = [chunk for page in pages for chunk in chunk_page(page)]

        if not self.chunks:
            raise RuntimeError(
                "No content indexed. " "Check network access / site structure."
            )

        self.bm25 = BM25Okapi(
            [
                tokenize(f'{chunk["label"]} ' f'{chunk["section"]} ' f'{chunk["text"]}')
                for chunk in self.chunks
            ]
        )

        self.meta = [
            set(tokenize(f'{chunk["label"]} ' f'{chunk["section"]}'))
            for chunk in self.chunks
        ]

    def search(
        self,
        query: str,
        k: int = TOP_K,
    ) -> list[dict]:
        clean_query = query
        expansions = {
            r"\bhod\b": "hod head of department",
            r"\bce\b": "ce computer engineering",
            r"\bit\b": "it information technology",
            r"\bextc\b": "extc electronics telecommunication",
            r"\becs\b": "ecs electronics computer science",
            r"\baids\b": "aids artificial intelligence data science",
            r"\baiml\b": "aiml artificial intelligence machine learning",
            r"\bmech\b": "mech mechanical engineering",
            r"\bppt\b": "ppt printing packaging technology",
            r"\bdept\b": "department",
            r"\bcompter\b": "computer",
            r"\biiic\b": "iiic innovation incubation industry interface cell",
            r"\biqac\b": "iqac internal quality assurance cell",
            r"\btpc\b": "tpc training placement cell",
            r"\b(?:programs?|courses?(?:\s+(?:offered|available|in\s+sies|in\s+siesgst))?|branches|degrees?)\b": "programs courses undergraduate postgraduate btech b.e mtech engineering intake",
        }
        for p, repl in expansions.items():
            clean_query = re.sub(p, repl, clean_query, flags=re.IGNORECASE)

        query_tokens = tokenize(clean_query)

        if not query_tokens:
            return []

        query_set = set(query_tokens)

        scores = self.bm25.get_scores(query_tokens)

        top_score = max(scores) or 1.0

        is_program_query = bool(
            re.search(
                r"\b(courses?\s+(?:offered|available|in|at)|programs?\s+(?:offered|available|in|at)|what\s+are\s+(?:the\s+)?(?:programs|courses)|branches|degrees|intake|ug\s+and\s+pg|undergraduate|postgraduate|courses?\s+in\s+sies|programs?\s+in\s+sies)\b",
                query,
                re.IGNORECASE,
            )
        )

        is_dept_faculty_query = any(w in query_set for w in ["faculty", "staff", "teacher", "professor", "hod", "head"]) and any(
            w in query_set for w in ["computer", "it", "information", "extc", "electronics", "ecs", "mech", "mechanical", "aids", "aiml", "ai"]
        )

        ignore_words = {"faculty", "mam", "sir", "prof", "professor", "dr", "tell", "about", "who", "details", "info", "experience", "qualification", "publications"}
        person_tokens = [t for t in query_tokens if len(t) >= 3 and t not in ignore_words]

        ranked = []
        for index, (score, metadata) in enumerate(zip(scores, self.meta)):
            chunk = self.chunks[index]
            url = chunk["url"].lower()
            slug = url.rstrip("/").split("/")[-1]

            dept_boost = 0.0
            if "committee" in url:
                dept_boost -= 0.25  # De-prioritize raw committee spreadsheets
            if any(w in slug for w in ["computer-engineering", "information-technology", "electronics-telecommunication", "mechanical", "artificial-intelligence"]):
                if any(w in query_set for w in ["computer", "engineering", "it", "information", "extc", "electronics", "aids"]):
                    dept_boost += 0.5
                    if is_dept_faculty_query:
                        dept_boost += 1.5
            if "/faculty/" in url:
                if any(pt in slug for pt in person_tokens):
                    dept_boost += 3.0
            elif url.rstrip("/") == "https://siesgst.edu.in/faculty":
                if person_tokens:
                    dept_boost -= 2.0
                elif any(w in query_set for w in ["hod", "head", "faculty", "professor", "dr"]):
                    if is_dept_faculty_query:
                        dept_boost -= 1.0
                    else:
                        dept_boost += 0.35

            if is_program_query:
                if any(u in url for u in ["about-sies-gst", "first-year-engineering", "admissions-ug-engineering", "admissions-pg-engineering", "workingprof"]):
                    dept_boost += 1.8
                if any(u in url for u in ["nisp", "preincubation", "faculty", "committee"]):
                    dept_boost -= 1.5

            final_score = (
                score / top_score
                + META_BOOST * len(query_set & metadata) / len(query_set)
                + dept_boost
            )
            ranked.append((final_score, score, index))

        ranked.sort(reverse=True)

        return [
            self.chunks[index]
            for final_score, score, index in ranked[:k]
            if (final_score > 0 and (score > 0 or final_score > 0.5))
        ]

    def read_page(
        self,
        url: str,
        offset: int = 0,
    ) -> str:

        page = self.pages.get(normalize_url(url))

        if page is None:
            return "Page not found in the index. " "Use search_site to find valid URLs."

        text = "\n".join(
            line[3:].upper() if line.startswith("## ") else line
            for line in page["lines"]
        )

        piece = text[offset : offset + READ_PAGE_CHARS]

        end = offset + len(piece)

        if end < len(text):

            piece += (
                "\n\n[Truncated. "
                f"Call read_page again "
                f"with offset={end} for more.]"
            )

        return piece if piece else "No more content."


# --------------------------------- agent ---------------------------------- #


def format_hits(
    hits: list[dict],
) -> str:

    if not hits:
        return "No relevant pages found on the website. Try a different search query."

    lines = [
        f"Found {len(hits)} relevant pages. MANDATORY NEXT STEP: You MUST call read_page(url) on the top matching URL below before formulating your answer:"
    ]
    seen_urls = set()
    for hit in hits:
        u = hit["url"]
        if u in seen_urls:
            continue
        seen_urls.add(u)
        snippet = hit["text"][:140].replace("\n", " ").strip()
        lines.append(
            f"Source: {u}\nPage: {hit['label']} | Section: {hit['section'] or 'General'}\nPreview: {snippet}...\nAction: Call read_page(\"{u}\") to inspect complete content"
        )
    return "\n\n---\n\n".join(lines)


def build_agent(
    index: SiteIndex,
) -> Agent:

    @function_tool
    def search_site(
        query: str,
    ) -> str:
        """
        Search the SIES GST website to discover candidate pages and URLs.

        Include the department, person name, or topic in the query.
        Example: 'computer engineering faculty', 'Saylee Narkhede'
        """

        return format_hits(index.search(query))

    @function_tool
    def read_page(
        url: str,
        offset: int = 0,
    ) -> str:
        """
        Read the complete text of a page.

        STRICTLY REQUIRED: You MUST call this tool on the most relevant URL
        returned by search_site() to read full page details before answering.
        """

        return index.read_page(
            url,
            offset,
        )

    model = OpenAIChatCompletionsModel(
        model=LLM_MODEL,
        openai_client=AsyncOpenAI(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            timeout=45.0,
        ),
    )
    today = datetime.now().strftime("%d/%m/%Y, %A, %H:%M:%S")
    return Agent(
        name="SIES GST Assistant",
        instructions=(f"""You are an intelligent assistant for SIES Graduate School of Technology (SIES GST) answering questions using official website content.
Today is {today}.

Rules:
1. Provide comprehensive, detailed, and well-structured answers using official website content. Stay directly focused on what the user asked without omitting key factual information.
   - For an individual faculty member query (e.g. 'Tell me about [Name]', 'Who is [Name]?'):
     * Start with an introductory sentence: '[Name] is an [Designation] in the Department of [Department] at SIES Graduate School of Technology (SIES GST). Here are key details about [him/her]:'
     * Structure with clean Markdown headings, bullet points, and tables:
       ### Academic Background
       - **Qualifications:** [degrees/qualifications]
       - **Employee ID:** [Employee ID from Department Roster Data] (if available)
       - **Date of Joining:** [Date of Joining] (if available)
       - **Designation:** [Designation]
       - **Department:** [Department]
       - **Contact Email:** [email] (if available)
       - **Status of Appointment:** [Status] (if available)
       ### Teaching Responsibilities
       - **Courses Taught:**
         * [Course 1]
         * [Course 2]
       ### Professional Work Experience
       Format as a clean Markdown table with columns:
       | Designation | Organization | Location | From Date | To Date |
       ### Research and Publications
       Format Conference Contributions and Journal Publications as clean Markdown table(s) with columns:
       | Date / Academic Year | Title | Type / Level |
       ### Professional Development
       Format workshops, training programs, FDPs & STTPs as a clean Markdown table with columns:
       | Date | Program Title | Type / Level | Role | Venue |
       ### Achievements and Certifications
       Format as a clean Markdown table with columns:
       | Academic Year | Certification / Award | Details |
     * CRITICAL: ALWAYS include Employee ID and Date of Joining in Academic Background if available in the data.
     * CRITICAL: NEVER output boilerplate placeholder phrases like 'Not explicitly specified in the provided data', 'Not specified', or 'N/A'. If data for a section is missing, completely omit that section heading.
     * Conclude with: 'For more details, visit her faculty profile page.' (or his profile page).
   - For a general department faculty roster query (e.g. 'Who are the faculty in Computer Engineering?', 'List IT faculty'): Present a clean, query-specific markdown table or structured list showing Name, Designation, and Qualification. Do NOT repeat boilerplate placeholders (e.g. never repeat 'Date of Joining: Not specified', 'Research Areas: Not specified'). If detailed info is explicitly requested, include available details.
   - For specific attribute queries (e.g. 'Who is the HOD of Computer Engineering?', 'What are the awards of Dr. X?'): Answer directly and concisely with only the requested information.
   - For committees or teams, clearly present the Coordinator/Head followed by all members with their designations.
2. Format your response cleanly using standard Markdown:
   - Use clear section headings (e.g., ### Overview, ### Programs Offered, ### Objectives, ### Faculty Roster, ### Committee Members, ### Key Details, ### Roles & Responsibilities, ### Collaborations & MoUs).
   - Use structured bullet points (`- **Field:** Value`) or markdown tables for lists, attributes, intakes, and programs.
   - For questions about courses, branches, or programs offered at SIES GST, provide the complete, detailed breakdown:
     * **Undergraduate (B.Tech - 4 Years):** List all engineering branches along with their intake (e.g., Computer Engineering - 180, IT - 120, AI & DS - 120, AI & ML - 60, ECS - 60, EXTC - 60, CSE IoT & Cyber Security including Blockchain - 60, Mechanical - 60).
     * **Postgraduate (M.Tech - 2 Years):** AI & Data Science (18), Information Security (18).
     * **Working Professionals (B.Tech - 3 Years):** AI & DS (30), Computer Engineering (30), IT (30).
     * **Doctoral (Ph.D.):** Ph.D. in Computer Engineering.
   - For committees or teams, clearly present the Coordinator/Head followed by all members with their designations.
3. When prefetched website data is provided in the prompt, answer directly and factually using that content. Do NOT call search_site or read_page if the prefetched data answers the question.
4. If no data is provided or the prefetched data is missing the topic, use search_site to find candidate URLs and read_page to inspect them.
5. CRITICAL: Do NOT use internal thinking or reasoning steps. Output your formatted answer directly.
6. Do not include URLs or a 'Sources' section in your answer text (the interface renders source links separately)."""),
        model=model,
        model_settings=ModelSettings(temperature=0.0),
        tools=[
            search_site,
            read_page,
        ],
    )


# ----------------------------- streaming ---------------------------------- #


async def ask(
    agent: Agent,
    question: str,
) -> str:

    print("\n" + "=" * 70)
    print(f"[USER] {question}")
    print("=" * 70)

    result = Runner.run_streamed(
        agent,
        question,
        max_turns=MAX_TURNS,
    )

    print("\n[ASSISTANT] ", end="", flush=True)

    async for event in result.stream_events():

        # -------------------------------------------------
        # Tool calls / tool outputs
        # -------------------------------------------------

        if event.type == "run_item_stream_event":

            if event.name == "tool_called":

                item = event.item
                raw_item = getattr(
                    item,
                    "raw_item",
                    None,
                )

                if raw_item is not None:

                    name = getattr(
                        raw_item,
                        "name",
                        "unknown",
                    )

                    arguments = getattr(
                        raw_item,
                        "arguments",
                        "",
                    )

                    print(f"\n\n[TOOL CALL] {name}")

                    print(f"[ARGS] {arguments}")

            elif event.name == "tool_output":

                # Don't dump the entire tool result.
                print("\n[TOOL OUTPUT RECEIVED]")

                print(
                    "[ASSISTANT] ",
                    end="",
                    flush=True,
                )

        # -------------------------------------------------
        # Streaming assistant text
        # -------------------------------------------------

        elif event.type == "raw_response_event":

            if isinstance(
                event.data,
                ResponseTextDeltaEvent,
            ):

                print(
                    event.data.delta,
                    end="",
                    flush=True,
                )

    print("\n")

    if result.run_loop_exception:
        raise result.run_loop_exception

    return result.final_output


# ------------------------------ tests / debug ------------------------------ #


def inspect_pages(
    index: SiteIndex,
    url_part: str,
) -> None:

    found = False

    for chunk in index.chunks:

        if url_part in chunk["url"]:

            found = True

            preview = chunk["text"][:90].replace("\n", " / ")

            print(
                f'{chunk["url"]} | '
                f"section="
                f'{chunk["section"] or "-"!r} | '
                f'{len(chunk["text"])} chars | '
                f"{preview}"
            )

    if not found:
        print(f"No indexed page URL contains " f"{url_part!r}.")


def run_retrieval_test(
    index: SiteIndex,
) -> None:

    query = "computer engineering faculty"

    hits = index.search(query)

    print(f"Top hits for {query!r}:")

    for hit in hits:

        print(f'  - {hit["url"]} ' f'[{hit["section"] or "-"}]')

    ok = any(
        hit["url"].endswith("/computer-engineering") and "Aparna Bannore" in hit["text"]
        for hit in hits
    )

    if not ok:

        raise AssertionError(
            "Computer Engineering faculty "
            "table not in top results. "
            "Run: python site_agent.py "
            "--inspect computer-engineering"
        )

    print(
        "\nPASS: /computer-engineering " "faculty table was crawled " "and retrieved."
    )


# ---------------------------------- main ---------------------------------- #


def main() -> None:

    parser = argparse.ArgumentParser(description="SIES GST website Q&A agent")

    parser.add_argument(
        "question",
        nargs="?",
        default=(
            "Who are the faculty members "
            "in the Computer Engineering "
            "department? List name, "
            "designation and qualification."
        ),
    )

    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-crawl the website",
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="run offline retrieval test and exit",
    )

    parser.add_argument(
        "--inspect",
        metavar="URL_PART",
        help=("print chunks of pages whose " "URL contains this text"),
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    set_tracing_disabled(True)

    index = SiteIndex(load_or_build_pages(refresh=args.refresh))

    log.info(
        "indexed %d pages into %d chunks",
        len(index.pages),
        len(index.chunks),
    )

    if args.inspect:

        inspect_pages(
            index,
            args.inspect,
        )

        return

    if args.test:

        run_retrieval_test(index)

        return

    asyncio.run(
        ask(
            build_agent(index),
            args.question,
        )
    )


if __name__ == "__main__":
    main()
