# utils/search.py
import time
import requests, webbrowser, os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote_plus
try:
    from duckduckgo_search import ddg
    DDG_AVAILABLE = True
except Exception:
    DDG_AVAILABLE = False

SUMMARY_DIR = "./search_summaries"; os.makedirs(SUMMARY_DIR, exist_ok=True)

def google_search_top_url(query: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        r = requests.get(url, headers=headers, timeout=10)
        text = r.text
        if "unusual traffic" in text.lower():
            return None, "google-block"
        soup = BeautifulSoup(text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/url?q="):
                u = href.split("/url?q=")[1].split("&")[0]
                if u and "google" not in u:
                    return u, None
        return None, "no-link"
    except Exception as e:
        return None, str(e)

def google_fetch_summary_from_url(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(r.text, "html.parser")
        meta = soup.find("meta", attrs={"name":"description"}) or soup.find("meta", attrs={"property":"og:description"})
        if meta and meta.get("content"):
            return meta.get("content").strip()[:800]
        for p in soup.find_all("p"):
            t = p.get_text(strip=True)
            if len(t) > 50:
                return t[:800]
        return soup.get_text(separator=" ", strip=True)[:800]
    except Exception:
        return ""

def duckduckgo_search_summary(query: str):
    if not DDG_AVAILABLE:
        return ("DuckDuckGo not available", None)
    try:
        results = ddg(query, max_results=3)
        if not results:
            return ("No DDG results", None)
        first = results[0]
        title = first.get("title","")
        body = first.get("body","")
        href = first.get("href","")
        summary = f"{title} - {body}"
        fname = os.path.join(SUMMARY_DIR, f"ddg_{int(time.time())}.txt")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(f"Query:{query}\nURL:{href}\n\n{summary}")
        return (summary, fname)
    except Exception as e:
        return (f"DDG error: {e}", None)

def google_search_summary(query: str):
    top, err = google_search_top_url(query)
    if err:
        if DDG_AVAILABLE:
            return duckduckgo_search_summary(query)
        return (f"Google failed: {err}", None)
    if not top:
        if DDG_AVAILABLE:
            return duckduckgo_search_summary(query)
        return ("No result", None)
    summ = google_fetch_summary_from_url(top)
    if not summ:
        fname = os.path.join(SUMMARY_DIR, f"open_{int(time.time())}.txt")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(f"Query:{query}\nTop:{top}\n")
        try:
            webbrowser.open(top)
        except:
            pass
        return (f"I opened the top result: {top}", fname)
    fname = os.path.join(SUMMARY_DIR, f"summary_{int(time.time())}.txt")
    with open(fname, "w", encoding="utf-8") as f:
        f.write(f"Query:{query}\nURL:{top}\n\n{summ}")
    return (summ, fname)

# simple download helper using requests streaming (used earlier in GUI)
def download_file_with_progress(url: str, dest: str, gui_cb=None):
    try:
        headers = {"User-Agent":"Mozilla/5.0"}
        with requests.get(url, stream=True, headers=headers, timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            written = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        written += len(chunk)
                        if gui_cb and total:
                            gui_cb(progress=written/total, progress_text=f"{int((written/total)*100)}%")
        return True
    except Exception:
        return False

def download_via_search(query_or_url: str, gui_cb=None, gui_confirm=None):
    # If looks like url, download directly
    if query_or_url.startswith("http"):
        url = query_or_url
    else:
        top, err = google_search_top_url(query_or_url)
        if err or not top:
            if DDG_AVAILABLE:
                summ, fname = duckduckgo_search_summary(query_or_url)
                if gui_cb:
                    gui_cb(assistant_text=summ, status="Idle")
                return
            if gui_cb:
                gui_cb(assistant_text=f"Search failed: {err}", status="Idle")
            return
        url = top
    filename = os.path.basename(urlparse(url).path) or f"download_{int(time.time())}"
    dest = os.path.join(os.path.expanduser("~"), "Downloads", filename)
    if gui_confirm:
        ok = gui_confirm(f"Download {url} to {dest}?")
    else:
        ok = True
    if not ok:
        if gui_cb: gui_cb(assistant_text="Download cancelled", status="Idle")
        return
    download_file_with_progress(url, dest, gui_cb)
    if gui_cb: gui_cb(assistant_text=f"Downloaded to {dest}", status="Idle")
