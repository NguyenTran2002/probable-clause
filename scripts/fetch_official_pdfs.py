"""Download the official PDFs the user approved (locked-decisions P1.11).

22 per-case PDFs of the U.S. Reports from GovInfo, and Chatrie's slip opinion
from supremecourt.gov, into data/raw/pdfs/ (gitignored). Already-downloaded
files are skipped. Serial, 2 s apart, no automatic retry. Each file's size and
SHA-256 go into data/raw/pdfs/manifest.json.

Usage:
    uv run python scripts/fetch_official_pdfs.py
"""

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "pdfs"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
TIMEOUT_S = 120  # placeholder until measured; the largest file is about 15 MB
GOVINFO = "https://www.govinfo.gov/content/pkg/USREPORTS-{v}/pdf/USREPORTS-{v}-{p}.pdf"

US_CITES = [
    ("olmstead", "277-438"), ("goldman", "316-129"), ("on_lee", "343-747"),
    ("silverman", "365-505"), ("lopez", "373-427"), ("berger", "388-41"),
    ("katz", "389-347"), ("white", "401-745"), ("miller", "425-435"),
    ("smith", "442-735"), ("knotts", "460-276"), ("karo", "468-705"),
    ("ciraolo", "476-207"), ("dow", "476-227"), ("florida_v_riley", "488-445"),
    ("kyllo", "533-27"), ("quon", "560-746"), ("jones", "565-400"),
    ("jardines", "569-1"), ("riley", "573-373"), ("grady", "575-306"),
    ("carpenter", "585-296"),
]
FILES = [(key, f"USREPORTS-{vp}.pdf", GOVINFO.format(v=vp.split("-")[0], p=vp.split("-")[1]))
         for key, vp in US_CITES]
FILES.append(("chatrie", "25-112_0am4.pdf", "https://www.supremecourt.gov/opinions/25pdf/25-112_0am4.pdf"))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for key, name, url in FILES:
        path = OUT / name
        if not path.exists():
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                    ctype, body = resp.headers.get("Content-Type", ""), resp.read()
            except urllib.error.URLError as e:
                print(f"STOP: {name}: {e}")
                return 1
            if "pdf" not in ctype or not body.startswith(b"%PDF"):
                print(f"STOP: {name}: not a PDF ({ctype}, {len(body)} bytes)")
                return 1
            path.write_bytes(body)
            time.sleep(2)
        data = path.read_bytes()
        manifest[key] = {"file": name, "url": url, "bytes": len(data),
                         "sha256": hashlib.sha256(data).hexdigest()}
        print(f"{key:16} {name:28} {len(data):>10}")
    manifest_path.write_text(json.dumps(manifest, indent=1))
    print(f"{len(manifest)} files, {sum(m['bytes'] for m in manifest.values())} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
