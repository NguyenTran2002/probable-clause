"""The prompt files of api/prompts/, loaded and filled (contract §4.G; T1.14).

`{{UPPER}}` comes from api/settings.py, lower-case `{{...}}` from the corpus (catalog, case count, coverage dates),
and `<field>` per call. The texts are the main session's (contract v2.0's drafts, for the user's review before the
first paid run, T1.14); this module only fills them and never writes text of its own.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from api import settings

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_SETTING = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
_CORPUS = re.compile(r"\{\{([a-z0-9_]+)\}\}")


def fill_settings(text: str) -> str:
    """`{{NAME}}` from api/settings.py. An unknown name is an error, never left in the text."""
    def one(m: re.Match) -> str:
        s = getattr(settings, m.group(1), None)
        if not isinstance(s, settings.Setting):
            raise KeyError(f"prompt placeholder {{{{{m.group(1)}}}}} is not a setting")
        return str(s.value)
    return _SETTING.sub(one, text)


def fill_fields(template: str, **fields) -> str:
    """`<name>` per call, in one pass, so an inserted value is never filled again. Settings are filled first."""
    text = fill_settings(template)
    if not fields:
        return text
    pattern = re.compile("<(" + "|".join(re.escape(k) for k in fields) + ")>")
    return pattern.sub(lambda m: str(fields[m.group(1)]), text)


def _json(name: str) -> dict:
    return json.loads((PROMPTS_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def tool_texts() -> dict:
    return _json("tools.json")


@lru_cache(maxsize=1)
def rejections() -> dict:
    return _json("rejections.json")


@lru_cache(maxsize=1)
def loop_messages() -> dict:
    return _json("loop_messages.json")


@lru_cache(maxsize=1)
def composition_system() -> str:
    text = fill_settings((PROMPTS_DIR / "composition_system.md").read_text(encoding="utf-8")).strip()
    if _CORPUS.search(text):
        raise KeyError("composition_system.md has a corpus placeholder this module does not fill")
    return text


def loop_system(corpus) -> str:
    """loop_system.md with the settings and the corpus's fields filled (T1.14)."""
    fields = {
        "case_count": str(len(corpus.manifest["cases"])),
        "catalog": corpus.catalog_text,
        **{k: str(corpus.coverage[k]) for k in ("latest_decision_full_pull", "latest_decision_in_corpus", "ingested")},
    }
    text = (PROMPTS_DIR / "loop_system.md").read_text(encoding="utf-8")
    text = fill_settings(text)

    def one(m: re.Match) -> str:
        if m.group(1) not in fields:
            raise KeyError(f"loop_system.md placeholder {{{{{m.group(1)}}}}} is not a corpus field")
        return fields[m.group(1)]
    # The catalog goes in last, so a "{{" inside corpus text could never be read as a placeholder.
    return _CORPUS.sub(one, text).strip()


def rejection(group: str, key: str, **fields) -> str:
    return fill_fields(rejections()[group][key], **fields)


def message(key: str, **fields) -> str:
    return fill_fields(loop_messages()[key], **fields)


def status_line(round_no: int, kept: int) -> str:
    """Research's per-turn status line (T1.14, contract v2.0 §4.G.3): "Round <round> of {{MAX_ROUNDS}} · <kept> kept"."""
    return fill_fields(loop_messages()["status_line"], round=round_no, kept=kept)


def update_status(*, searches_counted: int, unavailable: bool) -> str:
    """The last part of the update step's status line, from `status_update` (contract v2.0 §4.G.4)."""
    lm = loop_messages()["status_update"]
    if unavailable:
        return fill_fields(lm["unavailable"])
    if searches_counted:
        return fill_fields(lm["some_run"], n=searches_counted)
    return fill_fields(lm["not_run"])


def status_line_update(round_no: int, *, searches_counted: int, unavailable: bool) -> str:
    """The update step's per-turn status line (contract v2.0 §4.G.4): "Update step · round <round> of
    {{UPDATE_MAX_ROUNDS}} · <update_status>"."""
    return fill_fields(loop_messages()["status_line_update"], round=round_no,
                       update_status=update_status(searches_counted=searches_counted, unavailable=unavailable))


def kept_passages_text(n: int) -> str:
    """`<passages>` in the accepted texts: "1 kept passage" or "<n> kept passages" (loop_messages.json's _about)."""
    return "1 kept passage" if n == 1 else f"{n} kept passages"
