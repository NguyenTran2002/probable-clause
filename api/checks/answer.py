"""check_answer (contract §4.F): the quotation check and the full-citation check over the answer's blocks."""

from __future__ import annotations

from bisect import bisect_right

from api.checks.citations import Resolver, find_mentions
from api.checks.quotations import check_quotation, find_quotations, prepare_source
from api.checks.result import CheckResult, Flag


class _Blocks:
    """Maps offsets in the joined answer back to (block, offset) in the blocks as given."""

    def __init__(self, blocks: list[str]):
        self.starts = []
        self.ends = []
        total = 0
        for b in blocks:
            self.starts.append(total)
            total += len(b)
            self.ends.append(total)

    def spot(self, start: int, end: int) -> tuple[int, int, int, int]:
        """(block, start, end_block, end) for [start, end) of the joined text; empty blocks are skipped."""
        first = bisect_right(self.ends, start)
        last = bisect_right(self.ends, end - 1)
        return first, start - self.starts[first], last, end - self.starts[last]


def check_answer(blocks: list[str], kept_texts: list[str], manifest: dict) -> CheckResult:
    text = "".join(blocks)
    where = _Blocks(blocks)
    flags: list[tuple[int, int, Flag]] = []

    quotations_checked = quotations_found = 0
    sources = None
    cache: dict = {}    # matches of a piece in a passage, found once for the whole answer
    for q in find_quotations(text):
        if sources is None:
            sources = [prepare_source(t) for t in kept_texts]
        counted, found = check_quotation(q, sources, cache)
        if not counted:
            continue
        quotations_checked += 1
        if found:
            quotations_found += 1
        else:
            flags.append((q.start, q.end, Flag(*where.spot(q.start, q.end), "quotation_not_found", q.text)))

    citations_checked = citations_found = 0
    not_in_corpus: list[str] = []
    for m in find_mentions(text, Resolver(manifest)):
        citations_checked += 1
        if m.resolved:
            citations_found += 1
            continue
        flags.append((m.start, m.end, Flag(*where.spot(m.start, m.end), "not_in_corpus", m.text)))
        if m.text not in not_in_corpus:
            not_in_corpus.append(m.text)

    flags.sort(key=lambda f: (f[0], f[1]))
    return CheckResult(quotations_checked, quotations_found, citations_checked, citations_found,
                       not_in_corpus, [f for _, _, f in flags])
