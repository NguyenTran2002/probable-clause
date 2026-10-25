"""Report whether each required variable is set in .env, never its value.

The agent runs this instead of reading .env (brief §10.7). It prints one line
per variable: set, empty, missing, or commented out. No value, length or
prefix is ever printed.

Usage:
    uv run python scripts/check_env.py            # every variable
    uv run python scripts/check_env.py --phase 1  # only those Phase 1 needs

Exit code 0 when every checked variable is set, 1 otherwise.
"""

import argparse
import re
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# Variable -> first phase that needs it.
REQUIRED = {
    "COURTLISTENER_API_TOKEN": 1,
    "ANTHROPIC_API_KEY": 1,
    "EXA_API_KEY": 2,
    "MONGODB_URI": 4,
    "VOYAGE_API_KEY": 4,
}

LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
COMMENTED = re.compile(r"^\s*#+\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\S")


def parse(text: str) -> tuple[dict[str, bool], set[str], set[str]]:
    """Return (key -> has a non-empty value, commented-out keys, duplicate keys)."""
    present: dict[str, bool] = {}
    commented: set[str] = set()
    duplicates: set[str] = set()
    for raw in text.splitlines():
        if raw.lstrip().startswith("#"):
            m = COMMENTED.match(raw)
            if m:
                commented.add(m.group(1))
            continue
        m = LINE.match(raw)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value[:1] in ("'", '"'):
            value = value[1:-1] if len(value) > 1 and value[-1] == value[0] else value[1:]
        else:
            value = value.split(" #", 1)[0].strip()
        if key in present:
            duplicates.add(key)
        present[key] = bool(value)  # later lines win, as in python-dotenv
    return present, commented, duplicates


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--phase", type=int, help="check only variables needed by this phase")
    args = ap.parse_args()

    names = [k for k, p in REQUIRED.items() if args.phase is None or p <= args.phase]

    if not ENV_PATH.exists():
        print(".env: not found (copy .env.example to .env and fill it in)")
        for name in names:
            print(f"  {name}: missing")
        return 1

    present, commented, duplicates = parse(ENV_PATH.read_text(encoding="utf-8"))
    ok = True
    for name in names:
        if present.get(name):
            status = "set"
        elif name in present:
            status, ok = "empty", False
        elif name in commented:
            status, ok = "commented out", False
        else:
            status, ok = "missing", False
        note = " (defined more than once; the last one wins)" if name in duplicates else ""
        print(f"  {name}: {status}{note}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
