"""Write the web image's static data files from the committed corpus (contract §11.1, §11.3, §5.1).

Usage:
    uv run python scripts/build_web_data.py --out <dir>

Writes <dir>/opinions/<opinion_id>.json (the reader files, T4.3), <dir>/corpus.json and <dir>/config.json.
Always the full corpus.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.corpus.web_data import build_web_data  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, type=Path, help="directory to write into")
    ap.add_argument("--corpus", type=Path, default=ROOT / "data" / "corpus", help="the corpus folder (default: data/corpus)")
    args = ap.parse_args()
    build_web_data(args.corpus, args.out)
    n = len(list((args.out / "opinions").glob("*.json")))
    print(f"wrote {n} reader files, corpus.json and config.json to {args.out}")


if __name__ == "__main__":
    main()
