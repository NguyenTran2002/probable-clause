"""The API's entry point: `uvicorn api.main:app` (contract §4.H; builder I's image runs this target).

Importing this module loads nothing and never imports `api.loop`: the corpus, the indexes, the vectors, Atlas and
the clients are built by `build_deps`, which the app's lifespan runs before the port opens (T3.6). Each step is
timed and logged with the time since this module was imported (about the process start), so the app's own start
reads apart from the container's in Cloud Run's logs.

The environment (contract §4.H, §8):
- `PC_ENV` is `live` or `test` (default `test`) and chooses the Atlas database (T3.4, T3.5).
- `PC_CORPUS=before_chatrie` is the recording-only corpus; refused when `PC_ENV=live` (T5.6).
- `PC_COMMIT` is the short commit SHA baked into the image, reported by `/health`.
- `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `EXA_API_KEY`, `MONGODB_URI` are read in-process from the environment,
  never logged and never put in an error: a missing one is named, never shown.
"""

import logging
import os
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from api.server import AppDeps, create_app

_PROCESS_T0 = time.monotonic()
ROOT = Path(__file__).resolve().parents[1]
SECRETS = ("ANTHROPIC_API_KEY", "VOYAGE_API_KEY", "EXA_API_KEY", "MONGODB_URI")
_COMMIT = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

log = logging.getLogger("api.main")


class ConfigError(RuntimeError):
    """The environment cannot start the app. The message names variables, never their values."""


@dataclass(frozen=True)
class Config:
    env: str                 # "live" or "test"
    corpus_label: str        # "full" or "before_chatrie"
    commit: str


def read_config(environ: Mapping[str, str]) -> Config:
    env = (environ.get("PC_ENV") or "test").strip()
    if env not in ("live", "test"):
        raise ConfigError("PC_ENV must be 'live' or 'test'")
    corpus = (environ.get("PC_CORPUS") or "full").strip()
    if corpus not in ("full", "before_chatrie"):
        raise ConfigError("PC_CORPUS must be 'full' or 'before_chatrie'")
    if corpus == "before_chatrie" and env == "live":
        raise ConfigError("PC_CORPUS=before_chatrie is recording-only and refused when PC_ENV=live (T5.6)")
    missing = [k for k in SECRETS if not (environ.get(k) or "").strip()]
    if missing:
        raise ConfigError("not set: " + ", ".join(missing))
    commit = (environ.get("PC_COMMIT") or "").strip()
    return Config(env=env, corpus_label=corpus, commit=commit if _COMMIT.match(commit) else "unknown")


class _Steps:
    def __init__(self):
        self._t = time.monotonic()

    def done(self, step: str) -> None:
        now = time.monotonic()
        log.info("start-up: %s in %.3f s (%.3f s since the process started)", step, now - self._t, now - _PROCESS_T0)
        self._t = now


async def build_deps(environ: Mapping[str, str] | None = None) -> AppDeps:
    """Load everything the app needs, in order, before the port opens (T3.6)."""
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    environ = os.environ if environ is None else environ
    steps = _Steps()
    cfg = read_config(environ)
    steps.done(f"configuration (PC_ENV={cfg.env}, corpus {cfg.corpus_label}, commit {cfg.commit})")

    from api.corpus.keyword import KeywordIndex
    from api.corpus.store import Corpus
    from api.search.meaning import MeaningIndex
    from api.search.voyage import HttpVoyageClient
    from api.state.store import MongoStore, db_name_for
    from api.web_updates.exa import McpExaTransport, UpdateSearch

    corpus = Corpus.load(ROOT, exclude=("chatrie",) if cfg.corpus_label == "before_chatrie" else ())
    steps.done(f"corpus ({len(corpus.passages)} passages, {corpus.label})")
    keyword = KeywordIndex(corpus)
    steps.done("keyword index")
    meaning = MeaningIndex.load(ROOT / "data" / "vectors", corpus.passages.values())
    steps.done("vectors")

    store = MongoStore(environ["MONGODB_URI"].strip(), db_name_for(cfg.env))
    try:
        await store.ensure_indexes()
        steps.done("Atlas indexes")
    except Exception as e:
        # Not fatal: /health reports "unknown" and POST /runs refuses with atlas_unreachable (fail closed, T3.4).
        log.error("start-up: Atlas indexes not checked (%s)", type(e).__name__)
        steps.done("Atlas indexes (not reached)")

    from api.loop import LoopDeps, SdkAnthropicStreamer, execute_run   # G's part, imported only here

    loop_deps = LoopDeps(corpus=corpus, keyword=keyword, meaning=meaning,
                         voyage=HttpVoyageClient(api_key=environ["VOYAGE_API_KEY"].strip()),
                         updates=UpdateSearch(McpExaTransport(), store),      # Exa's key is read from EXA_API_KEY
                         anthropic=SdkAnthropicStreamer(environ["ANTHROPIC_API_KEY"].strip()))
    steps.done("clients and the loop")
    return AppDeps(store=store, execute_run=execute_run, loop_deps=loop_deps, corpus_label=corpus.label,
                   commit=cfg.commit, aclose=store.close)


app = create_app(build_deps)
