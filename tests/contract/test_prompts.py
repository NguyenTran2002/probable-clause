"""The prompt files load, cover every tool, and name only real settings (contract §4.G, §7)."""

import json
import re
from pathlib import Path

from api import settings

PROMPTS = Path(__file__).resolve().parents[2] / "api" / "prompts"
TOOLS = ["search_meaning", "search_exact", "read_passages", "keep_passages", "search_web_updates", "submit_answer"]
CORPUS_FIELDS = {"case_count", "catalog", "latest_decision_full_pull", "latest_decision_in_corpus", "ingested"}


def _all_text() -> str:
    return "".join(p.read_text() for p in sorted(PROMPTS.iterdir()) if p.suffix in (".md", ".json"))


def test_json_files_load():
    for name in ("tools.json", "rejections.json", "loop_messages.json"):
        json.loads((PROMPTS / name).read_text())


def test_every_tool_described():
    tools = json.loads((PROMPTS / "tools.json").read_text())
    for name in TOOLS:
        assert tools[name]["description"]


def test_placeholders_are_settings_or_corpus_fields():
    for name in set(re.findall(r"\{\{(\w+)\}\}", _all_text())):
        if name.isupper():
            assert isinstance(getattr(settings, name, None), settings.Setting), name
        else:
            assert name in CORPUS_FIELDS, name
