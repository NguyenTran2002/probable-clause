"""The checks' result types (contract §4.F). `CheckResult` is the `checks` event's data, field for field (§6)."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Flag:
    """A spot in the answer, from (block, start) to (end_block, end).

    `start` and `end` are Python string offsets into the blocks exactly as given; `end` is exclusive,
    so `text` is the slice from (block, start) to (end_block, end) of the blocks joined as streamed.
    """
    block: int
    start: int
    end_block: int
    end: int
    kind: Literal["quotation_not_found", "not_in_corpus"]
    text: str


@dataclass
class CheckResult:
    quotations_checked: int
    quotations_found: int
    citations_checked: int
    citations_found: int
    not_in_corpus: list[str] = field(default_factory=list)   # the names or citations, as written; each distinct string once
    flags: list[Flag] = field(default_factory=list)
