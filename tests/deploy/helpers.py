"""Shared paths for the deploy tests. Nothing here builds an image or touches the cloud."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"


def read(name: str) -> str:
    return (DEPLOY / name).read_text()


def instructions(dockerfile: str) -> list[tuple[str, str]]:
    """(INSTRUCTION, rest) for each Dockerfile instruction, with continuation lines joined."""
    out = []
    buf = ""
    for line in dockerfile.splitlines():
        if not buf and (not line.strip() or line.lstrip().startswith("#")):
            continue
        if line.lstrip().startswith("#") and buf:
            continue
        buf += line.rstrip()
        if buf.endswith("\\"):
            buf = buf[:-1] + " "
            continue
        m = re.match(r"\s*([A-Za-z]+)\s*(.*)", buf)
        out.append((m.group(1).upper(), m.group(2)))
        buf = ""
    return out
