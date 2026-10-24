"""Shared helpers for the Phase 2 paid checks (scripts/probe_*.py, P2.5).

Every Claude call goes through `call()`, which prices the response from its
usage figures and appends it to a spend ledger under data/verification/phase2/
(gitignored). A call is refused before it is sent if the ledger has already
reached the ceiling, and a probe stops on the first call that passes it. Paid
requests are never retried (brief §10.7): the client is created with
max_retries=0.

The key is read from .env in-process and never printed.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
OUT = ROOT / "data" / "verification" / "phase2"
LEDGER = OUT / "spend.jsonl"
CHICAGO = ZoneInfo("America/Chicago")

MODEL = "claude-sonnet-5-5"  # P2.1
EFFORT = "high"  # P2.1
CEILING_USD = 2.00  # P2.5

# USD per million tokens for claude-sonnet-5-5, from Anthropic's pricing page
# (retrieval recorded in docs/research/phase2-findings.md).
PRICE = {
    "input": 2.00,
    "output": 10.00,
    "cache_write_5m": 2.50,
    "cache_write_1h": 4.00,
    "cache_read": 0.10,
}


def env_value(name: str) -> str:
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip().removeprefix("export ")
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit(f"{name} not found in .env")


def client():
    import anthropic

    # timeout: placeholder until measured; generous because thinking at high effort is slow
    return anthropic.Anthropic(api_key=env_value("ANTHROPIC_API_KEY"), max_retries=0, timeout=300)


def spent() -> float:
    if not LEDGER.exists():
        return 0.0
    return sum(json.loads(line)["usd"] for line in LEDGER.read_text().splitlines() if line.strip())


def cost(usage) -> float:
    u = usage.model_dump() if hasattr(usage, "model_dump") else dict(usage)
    cc = u.get("cache_creation") or {}
    w1h = cc.get("ephemeral_1h_input_tokens", 0) or 0
    w5m = (u.get("cache_creation_input_tokens", 0) or 0) - w1h
    return (
        (u.get("input_tokens", 0) or 0) * PRICE["input"]
        + (u.get("output_tokens", 0) or 0) * PRICE["output"]
        + w5m * PRICE["cache_write_5m"]
        + w1h * PRICE["cache_write_1h"]
        + (u.get("cache_read_input_tokens", 0) or 0) * PRICE["cache_read"]
    ) / 1_000_000


def call(c, probe: str, label: str, **kwargs):
    """Send one Messages request, log its usage and cost, enforce the ceiling."""
    if spent() >= CEILING_USD:
        sys.exit(f"ceiling ${CEILING_USD:.2f} reached; {probe}/{label} not sent")
    kwargs.setdefault("model", MODEL)
    resp = c.messages.create(**kwargs)
    usd = cost(resp.usage)
    OUT.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps({
            "time": datetime.now(CHICAGO).isoformat(timespec="seconds"),
            "probe": probe,
            "label": label,
            "model": kwargs["model"],
            "usage": resp.usage.model_dump(),
            "usd": round(usd, 6),
        }) + "\n")
    total = spent()
    print(f"  [{probe}/{label}] ${usd:.4f} (total ${total:.4f} of ${CEILING_USD:.2f})")
    if total > CEILING_USD:
        sys.exit("ceiling passed; stopping")
    return resp


def save(name: str, obj) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(obj, indent=2, default=str, ensure_ascii=False))
    return path
