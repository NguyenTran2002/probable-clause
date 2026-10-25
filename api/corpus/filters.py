"""The filters both search tools share (T1.4; contract §4.B)."""

import re
import unicodedata
from datetime import date
from functools import lru_cache

from api.corpus.store import Corpus
from api.errors import ToolInputError
from api.settings import KEYWORD_ITEMS_PER_LIST, value
from api.types import Filters, Passage

GROUPS = ("majority", "plurality", "concurrence", "dissent")
FILTER_KEYS = ("cases", "decided_from", "decided_to", "opinion_types", "authors", "none_of", "include_footnotes")
PER_CURIAM = "per curiam"
_TOKEN = re.compile(r"[^\W_]+")


def tokens(text: str) -> list[str]:
    """Lowercase words as FTS5's unicode61 tokenizer splits them: letters and digits, diacritics folded."""
    folded = "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))
    return _TOKEN.findall(folded)


def _list(raw: dict, key: str) -> list:
    v = raw.get(key)
    if v is None:
        return []
    if not isinstance(v, list):
        raise ToolInputError(f"'{key}' must be a list; got {type(v).__name__}. Leave it out to leave it unset.")
    return v


def _strings(raw: dict, key: str) -> list[str]:
    items = _list(raw, key)
    for x in items:
        if not isinstance(x, str) or not x.strip():
            raise ToolInputError(f"'{key}' must hold non-empty strings; got {x!r}.")
    return [x.strip() for x in items]


def _date(raw: dict, key: str) -> str | None:
    v = raw.get(key)
    if v is None or v == "":
        return None
    if isinstance(v, int) and not isinstance(v, bool):
        v = str(v)
    bad = ToolInputError(f"'{key}' must be a year (YYYY) or a full date (YYYY-MM-DD); got {v!r}.")
    if not isinstance(v, str):
        raise bad
    v = v.strip()
    if re.fullmatch(r"\d{4}", v):
        return v
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        try:
            date.fromisoformat(v)
        except ValueError:
            raise bad from None
        return v
    raise bad


def parse_filters(raw: dict | None, corpus: Corpus) -> Filters:
    """Validate Claude's `filters` object. An empty list, or every value, means unset (T1.4)."""
    if raw is None:
        return Filters()
    if not isinstance(raw, dict):
        raise ToolInputError("'filters' must be an object. Filters are optional: leave it out to set none.")
    unknown = [k for k in raw if k not in FILTER_KEYS]
    if unknown:
        raise ToolInputError(f"Unknown filter(s) {', '.join(map(repr, unknown))}. The filters are: {', '.join(FILTER_KEYS)}. "
                             "All are optional.")

    cases = []
    for c in _strings(raw, "cases"):
        k = c.lower()
        if k not in corpus.case_keys:
            raise ToolInputError(f"Unknown case key '{c}'. Case keys: {', '.join(sorted(corpus.case_keys))}.")
        if k not in cases:
            cases.append(k)
    if set(cases) == set(corpus.case_keys):
        cases = []

    types = []
    for t in _strings(raw, "opinion_types"):
        if t.lower() not in GROUPS:
            raise ToolInputError(f"Unknown opinion type '{t}'. Opinion types are the four groups: {', '.join(GROUPS)}.")
        if t.lower() not in types:
            types.append(t.lower())
    if set(types) == set(GROUPS):
        types = []

    by_lower = {a.lower(): a for a in corpus.authors}
    authors = []
    for a in _strings(raw, "authors"):
        name = by_lower.get(a.lower())
        if name is None:
            raise ToolInputError(f"Unknown author '{a}'. Authors are surnames ({', '.join(sorted(corpus.authors - {PER_CURIAM}))}) "
                                 f"or '{PER_CURIAM}'.")
        if name not in authors:
            authors.append(name)
    if set(authors) == set(corpus.authors):
        authors = []

    none_of = _strings(raw, "none_of")
    cap = int(value(KEYWORD_ITEMS_PER_LIST))
    if len(none_of) > cap:
        raise ToolInputError(f"'none_of' holds {len(none_of)} items; the most allowed is {cap}.")
    for item in none_of:
        if not tokens(item):
            raise ToolInputError(f"'none_of' item {item!r} has no word in it.")

    inc = raw.get("include_footnotes", True)
    if inc is None:
        inc = True
    if not isinstance(inc, bool):
        raise ToolInputError(f"'include_footnotes' must be true or false; got {inc!r}.")

    d_from, d_to = _date(raw, "decided_from"), _date(raw, "decided_to")
    if d_from and d_to and _lower_bound(d_from) > _upper_bound(d_to):
        raise ToolInputError(f"'decided_from' ({d_from}) is after 'decided_to' ({d_to}).")
    return Filters(cases=tuple(cases), decided_from=d_from, decided_to=d_to, opinion_types=tuple(types),
                   authors=tuple(authors), none_of=tuple(none_of), include_footnotes=inc)


def _lower_bound(d: str) -> str:
    return d if len(d) == 10 else f"{d}-01-01"


def _upper_bound(d: str) -> str:
    return d if len(d) == 10 else f"{d}-12-31"


def matches(p: Passage, f: Filters) -> bool:
    """Every filter but none_of (which `excluded_by_none_of` and the keyword query apply)."""
    if f.cases and p.case_key not in f.cases:
        return False
    if f.decided_from and p.decided < _lower_bound(f.decided_from):
        return False
    if f.decided_to and p.decided > _upper_bound(f.decided_to):
        return False
    if f.opinion_types and not set(f.opinion_types) & set(p.opinion_groups):
        return False
    if f.authors:
        names = {a.lower() for a in f.authors}
        mine = {a.lower() for a in p.authors} or ({PER_CURIAM} if p.joined_by_source == "per curiam" else set())
        if not names & mine:
            return False
    if not f.include_footnotes and p.kind == "footnote":
        return False
    return True


def parse_item(item: str) -> tuple[str, list[str]]:
    """("phrase", words) for a double-quoted item; ("all", words) for an unquoted one, which means every one of
    its words, anywhere (a single word is the same thing). T1.4 and the main session's ruling on multi-word items."""
    s = item.strip()
    quoted = len(s) >= 2 and s[0] == '"' and s[-1] == '"'
    return ("phrase" if quoted else "all"), tokens(s)


@lru_cache(maxsize=8192)
def _spaced_tokens(text: str) -> str:
    return " " + " ".join(tokens(text)) + " "


@lru_cache(maxsize=8192)
def _word_set(text: str) -> frozenset[str]:
    return frozenset(tokens(text))


def item_in(item: str, text: str) -> bool:
    """Whether the text holds the item: a quoted item as an exact phrase, an unquoted one as all its words.
    Whole words, ignoring case, no stemming."""
    mode, words = parse_item(item)
    if not words:
        return False
    if mode == "phrase":
        return " " + " ".join(words) + " " in _spaced_tokens(text)
    return _word_set(text).issuperset(words)


def excluded_by_none_of(p: Passage, f: Filters) -> bool:
    """True when the passage holds any `none_of` item (semantic search drops these before ranking, T1.4)."""
    return any(item_in(item, p.text) for item in f.none_of)
