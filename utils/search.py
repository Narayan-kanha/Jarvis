# utils/search.py
"""
Search helpers for Jarvis.

Primary flow:
  1) DuckDuckGo (duckduckgo_search ddg) -> returns title, snippet, href
  2) Wikipedia summary fallback (if installed)
  3) Final fallback: "Sorry, I couldn't find anything"

Exposes:
  - google_search_summary(query) -> (summary_text, filename_or_None)
  - search_top_result(query) -> dict(title, href, snippet) or None
  - download_via_search(query_or_url, gui_cb=None, gui_confirm=None)
"""

import os
import time
import webbrowser
from urllib.parse import urlparse, urljoin, quote_plus

SUMMARY_DIR = "./search_summaries"
os.makedirs(SUMMARY_DIR, exist_ok=True)

# Try duckduckgo-search (fast and no key required)
try:
    from duckduckgo_search import ddg
    DDG_AVAILABLE = True
except Exception:
    ddg = None
    DDG_AVAILABLE = False

# Optional wikipedia fallback
try:
    import wikipedia
    WIKI_AVAILABLE = True
except Exception:
    wikipedia = None
    WIKI_AVAILABLE = False

# standard requests for direct fetching if needed
try:
    import requests
    REQUESTS_AVAILABLE = True
except Exception:
    requests = None
    REQUESTS_AVAILABLE = False

def _save_summary_file(query: str, title: str, url: str, summary: str) -> str:
    """Save a short summary file and return its path."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe_title = (title or "result").replace("/", "_").replace("\\", "_")[:60]
    fname = os.path.join(SUMMARY_DIR, f"summary_{safe_title}_{ts}.txt")
    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(f"Query: {query}\nURL: {url}\n\n{summary}\n")
        return fname
    except Exception:
        return None

def search_top_result(query: str):
    """
    Return a top result dict from DuckDuckGo if available:
      {"title": ..., "href": ..., "snippet": ...}
    Returns None if no usable result.
    """
    if not query:
        return None

    # Prefer DuckDuckGo results
    if DDG_AVAILABLE:
        try:
            results = ddg(query, max_results=4)
            if results:
                first = results[0]
                return {
                    "title": first.get("title", "").strip(),
                    "href": first.get("href", first.get("url", "")).strip(),
                    "snippet": first.get("body", "").strip() or first.get("snippet", "").strip()
                }
            return None
        except Exception as exc:
            # graceful fallback
            print("[search] DuckDuckGo search failed:", exc)

    # If ddg not available, try wiki quick lookup (best-effort)
    if WIKI_AVAILABLE:
        try:
            page = wikipedia.search(query, results=1)
            if page:
                title = page[0]
                url = f"https://en.wikipedia.org/wiki/{quote_plus(title)}"
                snippet = wikipedia.summary(title, sentences=2)
                return {"title": title, "href": url, "snippet": snippet}
        except Exception:
            pass

    # As final fallback, try a basic Google-like fetch (very unreliable due to blocks)
    # We'll skip scraping here — return None to indicate no top result.
    return None

def google_search_summary(query: str):
    """
    Primary method used by older code. Returns (summary_text, filename_or_None).
    Order:
      1) DuckDuckGo -> take title + snippet
      2) Wikipedia -> summary
      3) Final fallback message
    """
    if not query:
        return ("Empty query", None)

    # 1) Try DuckDuckGo summary
    if DDG_AVAILABLE:
        try:
            results = ddg(query, max_results=3)
            if results:
                first = results[0]
                title = first.get("title", "").strip()
                body = first.get("body", "") or first.get("snippet", "") or ""
                href = first.get("href", first.get("url", "")).strip()
                summary = f"{title}\n\n{body}".strip()
                fname = _save_summary_file(query, title, href, summary)
                return (summary or f"{title} — {href}", fname)
        except Exception as exc:
            print("[search] DuckDuckGo error:", exc)

    # 2) Wikipedia fallback
    if WIKI_AVAILABLE:
        try:
            # wikipedia.summary can raise exceptions for ambiguous pages; catch them
            summ = wikipedia.summary(query, sentences=2)
            if summ:
                fname = _save_summary_file(query, query, f"https://en.wikipedia.org/wiki/{quote_plus(query)}", summ)
                return (summ, fname)
        except Exception as exc:
            print("[search] Wikipedia fallback failed:", exc)

    # 3) No results
    return ("Sorry — I couldn't find anything useful for that query.", None)


# The existing download helpers (kept for compatibility)
def download_file_with_progress(url: str, dest: str, gui_cb=None):
    """Simple streaming download with a gui callback signature (progress, progress_text)."""
    try:
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests not available")
        headers = {"User-Agent": "Mozilla/5.0"}
        with requests.get(url, stream=True, headers=headers, timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0) or 0)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            written = 0
            chunk = 8192
            with open(dest, "wb") as f:
                for piece in r.iter_content(chunk_size=chunk):
                    if piece:
                        f.write(piece)
                        written += len(piece)
                        if gui_cb:
                            if total:
                                gui_cb(progress=written / total, progress_text=f"{int((written/total)*100)}%")
                            else:
                                gui_cb(progress=None, progress_text=f"{written//1024} KB")
        if gui_cb:
            gui_cb(assistant_text=f"Downloaded to {dest}", status="Idle")
        return True
    except Exception as exc:
        print("[download] error:", exc)
        if gui_cb:
            gui_cb(assistant_text="Download failed", status="Idle")
        return False

def download_via_search(query_or_url: str, gui_cb=None, gui_confirm=None):
    """
    Find and download a file. If a direct URL passed, downloads directly.
    If a query, uses search_top_result to find a candidate page and tries to extract a direct download link.
    (This function keeps previous semantics, simplified.)
    """
    # If looks like URL, download directly
    if not query_or_url:
        if gui_cb:
            gui_cb(assistant_text="No URL or query provided", status="Idle")
        return

    if query_or_url.startswith("http"):
        url = query_or_url
    else:
        top = search_top_result(query_or_url)
        if not top:
            if gui_cb:
                gui_cb(assistant_text="No search result found (download failed).", status="Idle")
            return
        url = top["href"]

    filename = os.path.basename(urlparse(url).path) or f"download_{int(time.time())}"
    dest = os.path.join(os.path.expanduser("~"), "Downloads", filename)
    if gui_confirm:
        ok = gui_confirm(f"Download {url} to {dest}?")
    else:
        ok = True
    if not ok:
        if gui_cb:
            gui_cb(assistant_text="Download cancelled", status="Idle")
        return

    # Start download in background thread from calling code (GUI currently does that).
    download_file_with_progress(url, dest, gui_cb)
