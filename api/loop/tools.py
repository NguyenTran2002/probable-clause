"""The six tools Claude sees in the research loop (contract §7; T1.2 to T1.10, T2.1, T2.3, T3.7).

Schemas are ours; every description is read from api/prompts/tools.json. Our code validates every field of every
call whatever the schema says (T3.7): a bad input raises ToolInputError, which becomes an error tool result.

Strict tool use (T3.7) is set only where the schema fits its limits. Its limits, from
https://platform.claude.com/docs/en/build-with-claude/structured-outputs ("Schema complexity limits", read Oct 24,
2026): at most 20 strict tools, 24 optional parameters across all strict schemas, 16 union-typed parameters; no
numeric or length constraints (`minimum`, `maxLength` ...). Strict here: keep_passages (0 optional), submit_answer
(4), read_passages (2) and search_web_updates (7), 13 optional parameters, no unions. The two search tools share
the filters object (8 optional parameters each with its fields), so making them strict too would leave no margin
under 24 if nested fields are counted; they stay non-strict and our validation covers them.
"""

import copy
import math

from api import settings
from api.errors import ToolInputError
from api.loop.prompts import fill_settings, tool_texts

TOOL_NAMES = ("search_meaning", "search_exact", "read_passages", "keep_passages", "search_web_updates", "submit_answer")
STRICT_TOOLS = ("read_passages", "keep_passages", "search_web_updates", "submit_answer")                # T3.7
GROUPS = ("majority", "plurality", "concurrence", "dissent")                                            # T1.4


def _d(key: str) -> str:
    """A description from tools.json, settings filled."""
    t = tool_texts()
    node = t
    for part in key.split("/"):
        node = node[part]
    return fill_settings(node)


def _field(tool: str, name: str) -> str:
    return fill_settings(tool_texts()[tool]["fields"][name])


def _filters_schema() -> dict:
    f = tool_texts()["_filters"]
    s = lambda k: fill_settings(f[k])   # noqa: E731
    return {
        "type": "object",
        "description": s("filters"),
        "properties": {
            "cases": {"type": "array", "items": {"type": "string"}, "description": s("filters.cases")},
            "decided_from": {"type": "string", "description": s("filters.decided_from")},
            "decided_to": {"type": "string", "description": s("filters.decided_to")},
            "opinion_types": {"type": "array", "items": {"type": "string", "enum": list(GROUPS)},
                              "description": s("filters.opinion_types")},
            "authors": {"type": "array", "items": {"type": "string"}, "description": s("filters.authors")},
            "none_of": {"type": "array", "items": {"type": "string"}, "description": s("filters.none_of")},
            "include_footnotes": {"type": "boolean", "description": s("filters.include_footnotes")},
        },
        "additionalProperties": False,
    }


def _max_results_schema() -> dict:
    return {"type": "integer", "description": fill_settings(tool_texts()["_max_results"])}


def _strings(desc: str) -> dict:
    return {"type": "array", "items": {"type": "string"}, "description": desc}


def build_tools() -> list[dict]:
    """The tool list, in a fixed order (the cached prefix must never change, T1.14)."""
    tools = [
        {
            "name": "search_meaning",
            "description": _d("search_meaning/description"),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": _field("search_meaning", "query")},
                    "filters": _filters_schema(),
                    "max_results": _max_results_schema(),
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "search_exact",
            "description": _d("search_exact/description"),
            "input_schema": {
                "type": "object",
                "properties": {
                    "all_of": _strings(_field("search_exact", "all_of")),
                    "any_of": _strings(_field("search_exact", "any_of")),
                    "none_of": _strings(_field("search_exact", "none_of")),
                    "filters": _filters_schema(),
                    "max_results": _max_results_schema(),
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "read_passages",
            "description": _d("read_passages/description"),
            "input_schema": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": _field("read_passages", "target")},
                    "before": {"type": "integer", "description": _field("read_passages", "before")},
                    "after": {"type": "integer", "description": _field("read_passages", "after")},
                },
                "required": ["target"],
                "additionalProperties": False,
            },
        },
        {
            "name": "keep_passages",
            "description": _d("keep_passages/description"),
            "input_schema": {
                "type": "object",
                "properties": {
                    "keep": {
                        "type": "array",
                        "description": _field("keep_passages", "keep"),
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "description": _field("keep_passages", "keep.id")},
                                "reason": {"type": "string", "description": _field("keep_passages", "keep.reason")},
                            },
                            "required": ["id", "reason"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["keep"],
                "additionalProperties": False,
            },
        },
        {
            "name": "search_web_updates",
            "description": _d("search_web_updates/description"),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": _field("search_web_updates", "query")},
                    "start_published_date": {"type": "string",
                                             "description": _field("search_web_updates", "start_published_date")},
                    "end_published_date": {"type": "string",
                                           "description": _field("search_web_updates", "end_published_date")},
                    "include_domains": _strings(_field("search_web_updates", "include_domains")),
                    "exclude_domains": _strings(_field("search_web_updates", "exclude_domains")),
                    "category": {"type": "string", "enum": ["news", "publication"],
                                 "description": _field("search_web_updates", "category")},
                    "type": {"type": "string", "enum": ["auto", "lite"],
                             "description": _field("search_web_updates", "type")},
                    "num_results": {"type": "integer", "description": _field("search_web_updates", "num_results")},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "submit_answer",
            "description": _d("submit_answer/description"),
            "input_schema": {
                "type": "object",
                "properties": {
                    "out_of_scope": {"type": "boolean", "description": _field("submit_answer", "out_of_scope")},
                    "note": {"type": "string", "description": _field("submit_answer", "note")},
                    "update_skip_reason": {"type": "string",
                                           "description": _field("submit_answer", "update_skip_reason")},
                    "update_findings": {
                        "type": "array",
                        "description": _field("submit_answer", "update_findings"),
                        "items": {
                            "type": "object",
                            "properties": {
                                "statement": {"type": "string",
                                              "description": _field("submit_answer", "update_findings.statement")},
                                "sources": _strings(_field("submit_answer", "update_findings.sources")),
                            },
                            "required": ["statement", "sources"],
                            "additionalProperties": False,
                        },
                    },
                    "update_overview": {"type": "string", "description": _field("submit_answer", "update_overview")},
                },
                "required": ["out_of_scope"],
                "additionalProperties": False,
            },
        },
    ]
    for t in tools:
        if t["name"] in STRICT_TOOLS:
            t["strict"] = True
    assert [t["name"] for t in tools] == list(TOOL_NAMES)
    return tools


_TOOLS: list[dict] | None = None


def tools() -> list[dict]:
    """A fresh copy of the tool list each time (callers may not mutate the cached prefix)."""
    global _TOOLS
    if _TOOLS is None:
        _TOOLS = build_tools()
    return copy.deepcopy(_TOOLS)


def strict_optional_count(tool_list: list[dict]) -> int:
    """Optional parameters across strict schemas, nested ones included (the 24 limit, T3.7)."""
    def count(schema: dict) -> int:
        n = 0
        if schema.get("type") == "object":
            req = set(schema.get("required", []))
            for name, sub in schema.get("properties", {}).items():
                n += (name not in req) + count(sub)
        elif schema.get("type") == "array":
            n += count(schema.get("items", {}))
        return n
    return sum(count(t["input_schema"]) for t in tool_list if t.get("strict"))


# ---------- validation shared by the tools (T3.7) ----------

def check_fields(tool: str, inp, allowed: tuple[str, ...], required: tuple[str, ...] = ()) -> dict:
    """The input is an object with only the tool's fields, and its required ones."""
    if not isinstance(inp, dict):
        raise ToolInputError(f"The {tool} input must be an object with the fields: {', '.join(allowed)}.")
    unknown = [k for k in inp if k not in allowed]
    if unknown:
        raise ToolInputError(f"Unknown field(s) {', '.join(repr(k) for k in unknown)}. The fields of {tool} are: "
                             f"{', '.join(allowed)}.")
    missing = [k for k in required if inp.get(k) is None]
    if missing:
        raise ToolInputError(f"{tool} needs {', '.join(repr(k) for k in missing)}.")
    return inp


def text_field(inp: dict, name: str, *, required: bool = False) -> str | None:
    """A string field; empty or whitespace-only counts as not given (an error if required)."""
    v = inp.get(name)
    if v is None:
        if required:
            raise ToolInputError(f"'{name}' is required and must be text.")
        return None
    if not isinstance(v, str):
        raise ToolInputError(f"'{name}' must be text; got {type(v).__name__}.")
    if not v.strip():
        if required:
            raise ToolInputError(f"'{name}' must not be empty.")
        return None
    return v


def string_list(inp: dict, name: str) -> list[str]:
    v = inp.get(name)
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ToolInputError(f"'{name}' must be a list of strings (words or quoted phrases).")
    return v


def max_results(v) -> int:
    """1 to MAX_RESULTS_CAP, default MAX_RESULTS_DEFAULT, clamped by our code (T1.4)."""
    default, cap = int(settings.MAX_RESULTS_DEFAULT.value), int(settings.MAX_RESULTS_CAP.value)
    if v is None:
        return default
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v != int(v):
        raise ToolInputError(f"'max_results' must be a whole number from 1 to {cap}; got {v!r}.")
    return max(1, min(cap, int(v)))


def whole_number(inp: dict, name: str) -> int:
    """before/after of read_passages: a whole number, default 0; the corpus checks the range (T1.6)."""
    v = inp.get(name)
    if v is None:
        return 0
    if isinstance(v, float) and math.isfinite(v) and v == int(v):
        return int(v)
    return v      # Corpus.read refuses anything else with the valid range
