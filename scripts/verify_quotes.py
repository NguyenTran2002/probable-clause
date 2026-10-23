"""Fetch each cited page once and check that each quote appears in its text.

Used to re-open every cited source after drafting research notes (brief §9).
Pages are cached under data/cache/pages/ (gitignored). HTML is stripped and
entities, curly quotes and dashes normalised before matching. Pages rendered
by JavaScript come back nearly empty and cannot be checked this way; PDFs
need their text extracted first (for example with pdftotext).

Usage:
    uv run python scripts/verify_quotes.py quotes.json

Input: a JSON file of [{"id": ..., "url": ..., "quote": ...}, ...].
Quotes containing "…" or "..." are split and each part must appear, in order.
"""

import html
import json
import re
import sys
import urllib.request
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "pages"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


def norm(s: str) -> str:
    s = html.unescape(s)
    s = s.replace(" ", " ")
    for a, b in (("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'"),
                 ("—", "-"), ("–", "-"), ("*", "")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip().lower()


def page_text(url: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (re.sub(r"[^A-Za-z0-9]+", "_", url)[:150] + ".html")
    if not f.exists():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            # Placeholder until measured: 30 s, one attempt, no retry.
            with urllib.request.urlopen(req, timeout=30) as r:
                f.write_bytes(r.read())
        except Exception as e:  # noqa: BLE001 (report any fetch failure, keep going)
            return f"__FETCH_ERROR__ {e}"
    raw = f.read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    return norm(re.sub(r"(?s)<[^>]+>", " ", raw))


def found(text: str, quote: str) -> bool:
    parts = [norm(p) for p in re.split(r"…|\.\.\.", quote) if norm(p)]
    pos = 0
    for p in parts:
        i = text.find(p, pos)
        if i < 0:
            return False
        pos = i + len(p)
    return True


def main() -> None:
    items = json.loads(Path(sys.argv[1]).read_text())
    for it in items:
        text = page_text(it["url"])
        if text.startswith("__fetch_error__"):
            status = "FETCH-ERROR " + text[16:80]
        else:
            status = "FOUND" if found(text, it["quote"]) else "NOT FOUND"
        print(f"{it['id']:>6}  {status:<12} {it['url']}")


if __name__ == "__main__":
    main()
