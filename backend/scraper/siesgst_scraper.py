#!/usr/bin/env python3
"""
SIES GST PDF Scraper — RAG Pipeline Ready
==========================================
Crawls https://siesgst.edu.in/ and extracts all PDF links with rich metadata
for Retrieval-Augmented Generation (RAG) pipelines.

Features:
- Recursive crawling with configurable depth
- PDF link extraction with metadata (title, context, source page, file size, etc.)
- Duplicate detection & filtering
- Rate limiting & polite crawling
- Retry logic with exponential backoff
- Structured output: JSON + CSV (RAG-ready)
- Resume capability (saves progress)
"""

import os
import sys
import re
import json
import csv
import time
import hashlib
import argparse
import logging
from urllib.parse import urljoin, urlparse, urldefrag
from datetime import datetime
from pathlib import Path
from typing import Set, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field

# Third-party dependencies (install via: pip install requests beautifulsoup4)
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install required packages: pip install requests beautifulsoup4")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ScraperConfig:
    """Configuration for the scraper."""
    base_url: str = "https://siesgst.edu.in"
    max_depth: int = 5
    delay: float = 1.0  # seconds between requests
    timeout: int = 30
    max_retries: int = 3
    output_dir: str = "./siesgst_rag_data"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.0 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0"
    )
    respect_robots: bool = False
    allowed_extensions: Tuple[str, ...] = (".pdf",)
    exclude_patterns: Tuple[str, ...] = (
        "mailto:", "tel:", "javascript:", "#",
        ".jpg", ".jpeg", ".png", ".gif", ".svg",
        ".css", ".js", ".xml", ".zip", ".mp4", ".mp3",
    )
    seed_paths: Tuple[str, ...] = (
        "/", "/about-sies-gst", "/library", "/academics",
        "/admissions", "/departments", "/notices", "/examination",
        "/downloads", "/docs", "/images", "/pdf", "/circulars",
        "/timetable", "/syllabus", "/results", "/placement",
    )


@dataclass
class PDFMetadata:
    """Rich metadata for each PDF — optimized for RAG pipelines."""
    url: str
    filename: str
    source_page: str
    title: str = ""
    context_text: str = ""
    link_text: str = ""
    file_size_bytes: Optional[int] = None
    content_type: str = ""
    last_modified: str = ""
    discovered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    crawl_depth: int = 0
    page_title: str = ""
    department: str = ""
    doc_category: str = ""
    hash_id: str = ""

    def __post_init__(self):
        if not self.hash_id:
            self.hash_id = hashlib.sha256(self.url.encode()).hexdigest()[:16]


# =============================================================================
# LOGGER SETUP
# =============================================================================

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("siesgst_scraper")


# =============================================================================
# HTTP SESSION WITH RETRIES
# =============================================================================

def create_session(config: ScraperConfig) -> requests.Session:
    """Create a requests session with retry logic."""
    session = requests.Session()
    session.headers.update({"User-Agent": config.user_agent})

    retry_strategy = Retry(
        total=config.max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# =============================================================================
# CORE SCRAPER
# =============================================================================

class SIESGSTScraper:
    """Main scraper class for crawling SIES GST website and extracting PDF metadata."""

    def __init__(self, config: ScraperConfig):
        self.config = config
        self.session = create_session(config)
        self.logger = setup_logging()

        # State tracking
        self.visited_urls: Set[str] = set()
        self.pdf_records: Dict[str, PDFMetadata] = {}
        self.url_queue: List[Tuple[str, int]] = []

        # Output paths
        self.output_path = Path(config.output_dir)
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.state_file = self.output_path / "scraper_state.json"
        self.json_output = self.output_path / "pdfs_metadata.json"
        self.csv_output = self.output_path / "pdfs_metadata.csv"
        self.rag_manifest = self.output_path / "rag_manifest.json"

        # Load previous state if exists
        self._load_state()

    def _load_state(self):
        """Resume from previous run if state file exists."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                self.visited_urls = set(state.get("visited", []))
                self.pdf_records = {
                    k: PDFMetadata(**v) for k, v in state.get("pdfs", {}).items()
                }
                self.logger.info(f"Resumed from state: {len(self.visited_urls)} pages visited, {len(self.pdf_records)} PDFs found")
            except Exception as e:
                self.logger.warning(f"Could not load state file: {e}")

    def _save_state(self):
        """Save current progress to disk."""
        state = {
            "visited": list(self.visited_urls),
            "pdfs": {k: asdict(v) for k, v in self.pdf_records.items()},
            "last_updated": datetime.utcnow().isoformat(),
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def _is_internal_url(self, url: str) -> bool:
        """Check if URL belongs to the target domain."""
        parsed = urlparse(url)
        base_parsed = urlparse(self.config.base_url)
        return parsed.netloc == base_parsed.netloc or parsed.netloc == ""

    def _normalize_url(self, url: str, base: str) -> Optional[str]:
        """Normalize and filter URLs."""
        full_url = urljoin(base, url)
        full_url, _ = urldefrag(full_url)

        parsed = urlparse(full_url)

        if parsed.scheme not in ("http", "https", ""):
            return None

        if not parsed.scheme:
            full_url = "https:" + full_url if full_url.startswith("//") else f"https://{full_url}"

        lower_url = full_url.lower()
        for pattern in self.config.exclude_patterns:
            if pattern in lower_url:
                return None

        if not self._is_internal_url(full_url):
            return None

        return full_url

    def _is_pdf_url(self, url: str) -> bool:
        """Check if URL points to a PDF."""
        lower = url.lower()
        return any(lower.endswith(ext) for ext in self.config.allowed_extensions)

    def _infer_category(self, url: str, link_text: str, page_title: str) -> str:
        """Infer document category based on URL and context."""
        text = f"{url} {link_text} {page_title}".lower()

        categories = {
            "syllabus": ["syllabus", "curriculum", "scheme", "program structure"],
            "timetable": ["timetable", "time table", "schedule", "routine"],
            "notice": ["notice", "circular", "announcement", "notification"],
            "brochure": ["brochure", "prospectus", "information booklet"],
            "result": ["result", "marksheet", "grade", "score", "merit"],
            "exam": ["exam", "examination", "question paper", "qp", "ut", "ia"],
            "placement": ["placement", "recruitment", "company", "job", "career"],
            "admission": ["admission", "fees", "fee structure", "payment"],
            "event": ["event", "workshop", "seminar", "conference", "sdp", "guest lecture"],
            "academic_calendar": ["calendar", "academic calendar", "holiday"],
            "form": ["form", "application", "registration"],
            "report": ["report", "annual report", "audit", "minutes"],
            "department": ["department", "dept", "extc", "ce", "it", "me", "aids", "aiml"],
            "library": ["library", "koha", "opac", "book", "journal"],
        }

        for category, keywords in categories.items():
            if any(kw in text for kw in keywords):
                return category
        return "general"

    def _infer_department(self, url: str, link_text: str, page_title: str) -> str:
        """Infer department from context."""
        text = f"{url} {link_text} {page_title}".lower()

        depts = {
            "Computer Engineering": ["computer", "ce", "comp"],
            "Information Technology": ["information technology", "it ", "it_dept"],
            "Electronics & Telecommunication": ["electronics", "telecommunication", "extc", "e&tc"],
            "Electronics & Computer Science": ["electronics & computer", "ecs"],
            "AI & Data Science": ["artificial intelligence", "data science", "aids", "ai&ds"],
            "AI & Machine Learning": ["machine learning", "aiml", "ai & ml"],
            "Mechanical": ["mechanical", "me ", "me_dept"],
            "CSE (IoT & Cyber Security)": ["iot", "cyber security", "blockchain", "cse(iot)"],
            "Library": ["library"],
            "Administration": ["admin", "principal", "office"],
        }

        for dept, keywords in depts.items():
            if any(kw in text for kw in keywords):
                return dept
        return ""

    def _fetch_head(self, url: str) -> Dict:
        """Fetch HEAD request to get PDF metadata without downloading body."""
        try:
            resp = self.session.head(url, timeout=self.config.timeout, allow_redirects=True)
            return {
                "content_type": resp.headers.get("Content-Type", ""),
                "content_length": resp.headers.get("Content-Length"),
                "last_modified": resp.headers.get("Last-Modified", ""),
            }
        except Exception as e:
            self.logger.debug(f"HEAD failed for {url}: {e}")
            return {}

    def _extract_context(self, link_element, soup: BeautifulSoup, max_chars: int = 300) -> str:
        """Extract surrounding text context for a link element."""
        context_parts = []

        parent = link_element.find_parent(["p", "div", "li", "td", "span"])
        if parent:
            text = parent.get_text(separator=" ", strip=True)
            if text:
                context_parts.append(text[:max_chars])

        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            heading_text = heading.get_text(strip=True)
            if heading_text and len(heading_text) < 200:
                context_parts.append(heading_text)

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            context_parts.append(meta_desc["content"])

        return " | ".join(context_parts)[:max_chars] if context_parts else ""

    def _process_pdf(self, pdf_url: str, source_page: str, link_text: str,
                     page_title: str, soup: BeautifulSoup, depth: int):
        """Process a discovered PDF URL."""
        hash_id = hashlib.sha256(pdf_url.encode()).hexdigest()[:16]

        if hash_id in self.pdf_records:
            self.logger.debug(f"Skipping duplicate PDF: {pdf_url}")
            return

        self.logger.info(f"[PDF] {pdf_url}")

        head_info = self._fetch_head(pdf_url)

        context = ""
        if soup:
            for link in soup.find_all("a", href=True):
                normalized = self._normalize_url(link["href"], source_page)
                if normalized == pdf_url:
                    context = self._extract_context(link, soup)
                    break

        filename = os.path.basename(urlparse(pdf_url).path) or "unknown.pdf"

        metadata = PDFMetadata(
            url=pdf_url,
            filename=filename,
            source_page=source_page,
            title=page_title or filename.replace("_", " ").replace(".pdf", ""),
            context_text=context,
            link_text=link_text.strip(),
            file_size_bytes=int(head_info.get("content_length")) if head_info.get("content_length") else None,
            content_type=head_info.get("content_type", ""),
            last_modified=head_info.get("last_modified", ""),
            crawl_depth=depth,
            page_title=page_title,
            department=self._infer_department(pdf_url, link_text, page_title),
            doc_category=self._infer_category(pdf_url, link_text, page_title),
            hash_id=hash_id,
        )

        self.pdf_records[hash_id] = metadata

    def _crawl_page(self, url: str, depth: int):
        """Crawl a single page and extract links."""
        if url in self.visited_urls:
            return
        if depth > self.config.max_depth:
            return

        self.visited_urls.add(url)
        self.logger.info(f"[CRAWL d={depth}] {url}")

        try:
            resp = self.session.get(url, timeout=self.config.timeout)
            resp.raise_for_status()
        except Exception as e:
            self.logger.warning(f"Failed to fetch {url}: {e}")
            return

        content_type = resp.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        page_title = ""
        title_tag = soup.find("title")
        if title_tag:
            page_title = title_tag.get_text(strip=True)

        # Find all links
        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            link_text = link.get_text(strip=True)

            normalized = self._normalize_url(href, url)
            if not normalized:
                continue

            if self._is_pdf_url(normalized):
                self._process_pdf(normalized, url, link_text, page_title, soup, depth)
            elif normalized not in self.visited_urls:
                self.url_queue.append((normalized, depth + 1))

        # Check for PDFs in onclick handlers using chr() to avoid quote issues
        q = chr(34)  # double quote
        sq = chr(39)  # single quote
        pattern = f"{sq}([^\\s{sq}{q}]+\\.pdf){sq}|{q}([^\\s{sq}{q}]+\\.pdf){q}"
        for elem in soup.find_all(attrs={"onclick": True}):
            onclick = elem["onclick"]
            matches = re.findall(pattern, onclick, re.IGNORECASE)
            for match in matches:
                pdf_path = match[0] or match[1]
                normalized = self._normalize_url(pdf_path, url)
                if normalized and self._is_pdf_url(normalized):
                    text = elem.get_text(strip=True)
                    self._process_pdf(normalized, url, text, page_title, soup, depth)

    def run(self):
        """Execute the full crawl."""
        self.logger.info("=" * 60)
        self.logger.info("SIES GST PDF Scraper — RAG Pipeline Edition")
        self.logger.info("=" * 60)

        for path in self.config.seed_paths:
            seed_url = urljoin(self.config.base_url, path)
            if seed_url not in self.visited_urls:
                self.url_queue.append((seed_url, 0))

        if self.config.base_url not in self.visited_urls:
            self.url_queue.append((self.config.base_url, 0))

        seen_in_queue = set()
        unique_queue = []
        for url, depth in self.url_queue:
            if url not in seen_in_queue:
                seen_in_queue.add(url)
                unique_queue.append((url, depth))
        self.url_queue = unique_queue

        while self.url_queue:
            url, depth = self.url_queue.pop(0)
            self._crawl_page(url, depth)

            if len(self.visited_urls) % 10 == 0:
                self._save_state()

            time.sleep(self.config.delay)

        self._save_state()
        self._export_results()

        self.logger.info("=" * 60)
        self.logger.info(f"Crawl complete! Found {len(self.pdf_records)} unique PDFs")
        self.logger.info(f"Results saved to: {self.output_path}")
        self.logger.info("=" * 60)

    def _export_results(self):
        """Export all PDF metadata to JSON, CSV, and RAG manifest."""
        records = [asdict(r) for r in self.pdf_records.values()]

        # 1. Full JSON
        with open(self.json_output, "w", encoding="utf-8") as f:
            json.dump({
                "source": self.config.base_url,
                "crawled_at": datetime.utcnow().isoformat(),
                "total_pdfs": len(records),
                "pdfs": records,
            }, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Saved JSON: {self.json_output}")

        # 2. CSV
        if records:
            with open(self.csv_output, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=records[0].keys())
                writer.writeheader()
                writer.writerows(records)
            self.logger.info(f"Saved CSV: {self.csv_output}")

        # 3. RAG Manifest
        rag_docs = []
        for r in records:
            content_for_embedding = f"""Document: {r['filename']}
Title: {r['title']}
Category: {r['doc_category']}
Department: {r['department']}
Source Page: {r['source_page']}
Context: {r['context_text']}
Link Text: {r['link_text']}
URL: {r['url']}"""

            rag_docs.append({
                "id": r["hash_id"],
                "source_url": r["url"],
                "metadata": {
                    "filename": r["filename"],
                    "title": r["title"],
                    "category": r["doc_category"],
                    "department": r["department"],
                    "source_page": r["source_page"],
                    "file_size": r["file_size_bytes"],
                    "last_modified": r["last_modified"],
                    "discovered_at": r["discovered_at"],
                },
                "content_for_embedding": content_for_embedding,
                "raw_text_preview": r["context_text"][:500],
            })

        with open(self.rag_manifest, "w", encoding="utf-8") as f:
            json.dump({
                "manifest_version": "1.0",
                "source_domain": self.config.base_url,
                "generated_at": datetime.utcnow().isoformat(),
                "document_count": len(rag_docs),
                "documents": rag_docs,
            }, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Saved RAG Manifest: {self.rag_manifest}")


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Scrape PDFs from siesgst.edu.in for RAG pipelines",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python siesgst_scraper.py                    # Run with defaults
  python siesgst_scraper.py --depth 3 --delay 2  # Shallow crawl, slower
  python siesgst_scraper.py --output ./data    # Custom output directory
  python siesgst_scraper.py --resume           # Resume from saved state
        """
    )
    parser.add_argument("--depth", type=int, default=5, help="Max crawl depth (default: 5)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests in seconds (default: 1.0)")
    parser.add_argument("--output", type=str, default="./siesgst_rag_data", help="Output directory")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--resume", action="store_true", help="Resume from previous state")

    args = parser.parse_args()

    if args.verbose:
        setup_logging(verbose=True)

    config = ScraperConfig(
        max_depth=args.depth,
        delay=args.delay,
        output_dir=args.output,
        timeout=args.timeout,
    )

    scraper = SIESGSTScraper(config)

    if not args.resume and scraper.state_file.exists():
        scraper.logger.info("Previous state found. Use --resume to continue, or delete state file to restart.")
        response = input("Delete previous state and restart? [y/N]: ").strip().lower()
        if response == "y":
            scraper.state_file.unlink()
            scraper.visited_urls.clear()
            scraper.pdf_records.clear()

    try:
        scraper.run()
    except KeyboardInterrupt:
        scraper.logger.info("Interrupted by user. Saving progress...")
        scraper._save_state()
        scraper._export_results()
        scraper.logger.info("Progress saved. Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()