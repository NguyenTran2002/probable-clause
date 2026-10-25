"""Keyword search over the passages: SQLite FTS5 (T1.2, T3.6).

Claude sends three lists; this code builds the FTS5 queries from their words, so Claude never writes syntax.
all_of and any_of match with the porter tokenizer (word forms). none_of matches exact whole words and phrases,
as the semantic tool's none_of does: a second table over the same rowids uses unicode61 without porter.
An unquoted item means all of its words anywhere; a double-quoted item is an exact phrase (T1.4).
"""

import sqlite3

from api.corpus.filters import matches, parse_item
from api.corpus.store import Corpus
from api.errors import ToolInputError
from api.settings import KEYWORD_ITEMS_PER_LIST, value
from api.types import Filters, Hit


def require_fts5(conn: sqlite3.Connection) -> None:
    """Fail at start-up, with a clear message, when this Python's sqlite3 has no FTS5 (T3.6)."""
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.fts5_probe USING fts5(x, tokenize='porter unicode61')")
        conn.execute("DROP TABLE temp.fts5_probe")
    except sqlite3.OperationalError as e:
        raise RuntimeError(
            f"This Python's sqlite3 ({sqlite3.sqlite_version}) lacks FTS5 with the porter tokenizer, which keyword "
            f"search needs: {e}") from e


def _strings(name: str, items) -> list[str]:
    if not isinstance(items, (list, tuple)) or not all(isinstance(x, str) for x in items):
        raise ToolInputError(f"'{name}' must be a list of strings (words or quoted phrases); got {items!r}.")
    return list(items)


def _item_expr(name: str, item: str) -> str:
    mode, words = parse_item(item)
    if not words:
        raise ToolInputError(f"'{name}' item {item!r} has no word in it. Give words, or a quoted phrase.")
    if mode == "phrase" or len(words) == 1:
        return '"' + " ".join(words) + '"'
    return "(" + " AND ".join(f'"{w}"' for w in words) + ")"


def _exprs(name: str, items) -> list[str]:
    items = _strings(name, items)
    cap = int(value(KEYWORD_ITEMS_PER_LIST))
    if len(items) > cap:
        raise ToolInputError(f"'{name}' holds {len(items)} items; the most allowed is {cap}.")
    return [_item_expr(name, i) for i in items]


class KeywordIndex:
    def __init__(self, corpus: Corpus):
        self.corpus = corpus
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        require_fts5(self._conn)
        self._conn.execute("CREATE VIRTUAL TABLE docs USING fts5(text, tokenize='porter unicode61')")
        self._conn.execute("CREATE VIRTUAL TABLE exact USING fts5(text, tokenize='unicode61')")   # for none_of only
        self._ids = list(corpus.passages)
        rows = [(i, corpus.passages[pid].text) for i, pid in enumerate(self._ids)]
        self._conn.executemany("INSERT INTO docs(rowid, text) VALUES (?, ?)", rows)
        self._conn.executemany("INSERT INTO exact(rowid, text) VALUES (?, ?)", rows)
        self._conn.commit()

    @staticmethod
    def compile(all_of: list[str], any_of: list[str], none_of: list[str]) -> str:
        """The FTS5 query: every all_of item AND (any_of items OR-ed), NOT any none_of item.

        `search` runs the positive part on the porter table and the none_of part on the exact table
        (`compile_none`), so it calls this with an empty none_of."""
        must = _exprs("all_of", all_of)
        either = _exprs("any_of", any_of)
        cut = _exprs("none_of", none_of)
        parts = list(must)
        if either:
            parts.append("(" + " OR ".join(either) + ")")
        if not parts:
            raise ToolInputError("Give at least one item in 'all_of' or 'any_of'.")
        query = "(" + " AND ".join(parts) + ")"
        if cut:
            query += " NOT (" + " OR ".join(cut) + ")"
        return query

    @staticmethod
    def compile_none(none_of: list[str]) -> str | None:
        cut = _exprs("none_of", none_of)
        return " OR ".join(cut) if cut else None

    def search(self, all_of: list[str], any_of: list[str], none_of: list[str], f: Filters, limit: int) -> list[Hit]:
        """Best first by bm25 (the score is -bm25, so larger is better), at most `limit` passages passing the filters."""
        all_of, any_of, own = _strings("all_of", all_of), _strings("any_of", any_of), _strings("none_of", none_of)
        filt = _strings("filters.none_of", f.none_of)
        if not all_of and not any_of:
            raise ToolInputError("Give at least one item in 'all_of' or 'any_of'.")
        excluded = list(dict.fromkeys(own + filt))
        cap = int(value(KEYWORD_ITEMS_PER_LIST))
        if len(excluded) > cap:
            raise ToolInputError(
                f"'none_of' holds {len(excluded)} items together ({len(own)} in the search's own none_of and "
                f"{len(filt)} in filters.none_of); the most allowed is {cap}.")
        query = self.compile(all_of, any_of, [])
        cut = self.compile_none(excluded)
        if limit <= 0:
            return []
        sql = "SELECT rowid, bm25(docs) FROM docs WHERE docs MATCH ?"
        args: list[str] = [query]
        if cut:
            sql += " AND rowid NOT IN (SELECT rowid FROM exact WHERE exact MATCH ?)"
            args.append(cut)
        try:
            rows = self._conn.execute(sql + " ORDER BY bm25(docs), rowid", args).fetchall()
        except sqlite3.OperationalError as e:
            raise ToolInputError(f"That keyword query could not be run ({e}). Use plain words and quoted phrases.") from e
        hits: list[Hit] = []
        for rowid, score in rows:
            pid = self._ids[rowid]
            if matches(self.corpus.passages[pid], f):
                hits.append(Hit(passage_id=pid, score=-float(score)))
                if len(hits) >= limit:
                    break
        return hits
