# Interfaces contract

**Version 2.0** (Oct 25, 2026), for Wave 3 (P4.18 to P4.21, `docs/design/wave3-design.md`). It changes these:
- **Research** ends with `submit_answer(out_of_scope, note?)`, with no rule 4 and no copy guard on the note (§4.G.3).
- **The update step** continues the research conversation for its cache: one tool list of seven, one system prompt, each step's tools refused in the other, and `submit_update` with `same_turn`, `findings`, `copy_guard` and `no_check` (§4.G.2, §4.G.4).
- **Branches:** the update step runs beside the composition, which is on Sonnet 5.5 (§4.G.1, §4.G.5).
- **Admission:** no reservation; a run is admitted under the caps, its spend recorded per call, and at most `MAX_CONCURRENT_RUNS` run at once, so a further request gets `busy` (§4.E, §4.H, §5, §8).
- **Limits:** looser, each step with its own (§9).
- **Events:** envelope `v: 2`, a `step` field, `update_started` and `update_ended`, the band without `declined`, the new `submit.rule` values, and `cost_usd.update` (§6, §6.2, §7).
- **The documented worst case,** $11.161 a run, is no longer a gate (§4.E).
- **Contract review:** revised after the Opus 5.5 xhigh review, before any builder started (the plan's step 0). The review added the copy guard on refused calls in the update step, `update_start_note`, cancellation and the slot's `finally`, the band's order, the counts by step, and composition output in the worst case.

1.9, for P4.17: the quotation check compares without regard to letter case, throughout; the answer keeps the quotation as written (§4.F). 1.8, for P4.16: `submit_answer` must be the only call in its turn, and sent once; otherwise every submit in the turn is refused under rule `same_turn` and the turn's other tools run as usual, in Claude's order (§4.G). 1.7, for P4.11 and P4.13: the daily cap at $15, and the copy guard on `update_skip_reason` on every submit once a page was returned, withheld when flagged, with `submit.copy_guard_skip_reason` (§4.E, §4.F, §4.G, §6). 1.6, after the fixtures were regenerated from the real code: `paid_call.estimated_usage`, the tokens an estimated Claude attempt was priced at, so H's `interrupted` totals add up when an attempt broke after streaming (P4.5, P4.10; §4.H, §6). Then, after the final review of the night: more negation words for the ellipsis rule and no quotation starting right after a negating prefix's hyphen (§4.F); the copy guard folding compatibility forms and dropping invisible format characters (§4.F); and the spend-limit pause also when a spend stop is in `stop_kinds` (§4.H). 1.5, for P4.6 to P4.10: the composition's reserve at 66,000 and the run's input limit at 436,000, so the worst case is $2.106; the note capped at `NOTE_MAX_CHARS` (`note_too_long`); rule 4 waived for an out-of-scope submit; the copy guard on a no-sources reply's note once a page was returned; every copy-guard check ignoring words that are also the corpus's; a broken composition attempt counted as streamed (§4.E, §4.F, §4.G, §6, §7). 1.4, after the cross-part Opus review: `run_ended.stop_kinds`, `RunContext.call_not_billed` for Exa's 402 and 401, Voyage's per-run bound enforced, and an ellipsis never dropping a negation (§4.C, §4.D, §4.F, §4.H, §6). 1.3, after part G's review: the order of a turn's tools, the withholding on any refused submit, the `no_note` rule, the end pairings of a composition after a loop limit, the response path of a citation, and a citation whose text disagrees with ours (§4.G, §6). 1.2, after part H's review in Wave 2: the `internal` error kind, `interrupted`'s number when the page is ahead of Atlas, the extra HTTP error codes, `answer_chars` on H's endings, and the shutdown grace (§4.H, §5, §6). Version 1 was revised after the Opus xhigh review (P4.1) before any builder started; 1.1 adds `loop_messages.json` to §4.G's prompt files, has `scripts/embed_corpus.py` read passages through B's `Corpus` (§4.C), and settles the embedded header's section wording and the appendix labels (§3, §4.C, after the main session's review of the labels), all during Wave 1. Written by the main session for Phase 4. One writer, the main session; a change bumps the version and is announced to every builder and to the frontend session (P0.3). Where this contract and `docs/design/locked-decisions.md` differ, the decisions win and this file is fixed.

Machine-checkable and shared code, all the main session's: `contracts/events.schema.json` (every event), `api/types.py` (shared types), `api/settings.py` (every figure and its basis), `api/errors.py` (errors and the closed error vocabulary), `api/retry.py` (our retries, T3.3), `api/protocols.py` (the Atlas store's interface). Builders import these and never redefine what they hold.

---

## 1. Conventions for every builder

- **Python 3.13, async throughout** (`async def` for anything that waits on the network or Atlas). FastAPI and uvicorn for the server; `httpx2` for plain HTTP (Voyage); the `anthropic` SDK for Claude; the `mcp` package for Exa; `pymongo`'s `AsyncMongoClient` for Atlas; `numpy` for vectors. No other dependency without asking the main session (only it touches `pyproject.toml`).
- **Tests first**, with pytest under `tests/<area>/`; async tests use anyio's pytest plugin (`@pytest.mark.anyio`, backend asyncio). Tests import in `importlib` mode (set in `pyproject.toml`), so two folders may hold files with the same name. No test makes a network call: every outside service has a fake (§12). No builder holds a key or makes a paid call.
- **Figures** come from `api/settings.py` only, each with its basis (brief §10.7). A figure not there is asked for, not invented.
- **SDK clients** are created with their own retries off (`max_retries=0`). Retries are `api/retry.py`'s, only where T3.3 says.
- **Dates shown to a person are America/Chicago**, computed with `zoneinfo` (brief §10.7). Timestamps in events and records are ISO 8601 strings with their offset. **Fields a TTL index reads are BSON dates** (`events.created`, `heartbeats.at`), since MongoDB expires only dates. Exa's published dates are kept as written (T2.2).
- **Logs** hold run IDs, states, timings, costs and error kinds, never the question, Claude's queries, the answer or page text (T3.7).
- **Text is data.** Passage and web text are never instructions (T1.14); nothing from a visitor, Claude, the corpus or the web is ever inserted as HTML (T3.7).
- **No web page text is ever stored or streamed** (T2.2, P1.3, P1.7): not in events, Atlas, logs or replays. §6 says where it is replaced.
- **No absolute local paths** in committed files; paths are built from the repository root.
- **Ownership:** each builder writes only its own paths (§13). Builders never commit; the main session commits after review.

## 2. Shared types and errors

`api/types.py`: `Passage`, `Filters`, `Hit`, `Usage`, `WebPage`, `RunFlags`, `KeptPassage`, the `RunContext` protocol and `RunStopped`; from v2.0, `Purpose` gains `update`, and `Step` (`research`, `update`, `composition`) with `STEP_OF_PURPOSE`, the step each purpose belongs to (§6). `api/errors.py`: `ToolInputError` (bad input from Claude; its `message` is written to Claude and becomes an error tool result, T3.7) and `ServiceError(service, kind, status, message, retry_after_s)`, where `kind` is one of the closed `ErrorKind` values. **Every client classifies its failures into `ErrorKind`**; `api/retry.py` decides from it what is retried. Mapping for Anthropic: 429 → `rate_limited`, except the usage tier's spend-cap 429 → `spend_cap`; 400 → `bad_request`, except the Console spend limit → `spend_limit`; 500 → `server_error`; 504 → `gateway_timeout`; 529 → `overloaded`; our deadline → `deadline`; the `refusal` stop reason → `refusal`. How the two special cases are told apart is read from Anthropic's error docs by the builder of G and cited in a comment.

## 3. The corpus as passages (T1.6, T1.9)

Source: `data/corpus/cases/<key>.json` and `data/corpus/manifest.json`, committed and frozen (changed only through `scripts/corrections.json`).

- **Opinion IDs** are `<case_key>-<k>`, k counted **from 1** in the manifest's order (T1.6). The manifest's own `id` field counts from 0 (`katz-0` there is `katz-1` here) and is never used as an ID.
- **Paragraph passages:** every paragraph whose `kind` is not `section` (kinds `text`, `quote`, `appendix`), numbered from 1 within its opinion: `katz-1-p1`. Section paragraphs are never passages and never returned by search (T1.6).
- **Footnote passages:** each footnote is **one** passage, numbered from 1 in the opinion's `footnotes` order (by order, never by label: labels repeat, as in *Boyd*): `katz-1-n1`. Its text is its paragraphs joined with `"\n\n"`; that join is always a sentence boundary. *(The main session's call.)*
- **Counts, by script** (Oct 24, 2026, after T1.5): 1,964 paragraph passages and 498 footnote passages, **2,462 passages**. Phase 3's "2,748 units" (T3.6) also counted the 286 section headings; the vectors file is therefore about 10.1 MB (2,462 × 1,024 × 4 bytes), not 11.3 MB.
- **Text** is the corpus text exactly. The loop's view adds footnote markers `[n. <label>]` at each reference, inserted at `footnote_refs[].offset`, an insertion point (after `text[:offset]`; 155 of 498 references sit at the end of the text; v1.1), each reference resolved to a footnote ID: an opinion's references match its footnotes one to one in label order (checked by script). The composition call and the page get the text without markers (T1.6).
- **Section label** (T1.6). It is part of the text Voyage embeds (§4.C), so it is fixed before the embedding and never changed after without re-embedding. The rule:
  - **Numbered headings:** level and numeral are read as `scripts/check_structure.py`'s `level()` reads them. That is the existing reading of I/V/C/D, which can be numerals or letters.
  - **Joining:** the heading stack is joined with "-", with trailing periods dropped ("I." → "I", so Part III subpart A is "III-A").
  - **A letter heading with a title** ("A. TITLE I—THE RECORDKEEPING REQUIREMENTS") contributes its letter only.
  - **Unnumbered title rows** inside an appendix ("PROOF OF CRIMINAL VIOLATION") do not change the label.
  - **Appendix paragraphs** take the appendix's title row, verbatim, final period included ("APPENDIX TO OPINION OF MR. JUSTICE WHITE."), as their label, or "Appendix" where the corpus has no title row (the *Kyllo* and *Carpenter* dissents). Footnotes take the label of the paragraph that cites them (v1.1).
  - **Not labels:** omission rows and letterhead lines typed as sections.
  - Before the first heading the label is `None`.
  - **Check before embedding:** B's tests print every distinct label per opinion, and the main session reviews that list before the embedding runs.
- **Pages:** `page_start` from the paragraph (a footnote's `page`); `page_end` from the last page break inside it. *Chatrie* is a slip opinion (`slip_opinion: true`): its pages are slip pages and restart at 1 in each of its five opinions.
- **Opinion groups** (T1.4): majority → majority; plurality → plurality; a type containing "concurring" or "concurrence" → concurrence; a type containing "dissent" → dissent; a type with both maps to both.
- **Joiners** carry the manifest's `joined_by_source`; where it says "not printed", an empty `joined_by` means unknown, never "joined by nobody" (P1.18).
- **Sentences:** `api/corpus/sentences.split_sentences(text)` (§4.A) at load; offsets stored on the `Passage`.
- **The corpus catalog** for the system prompt (T1.6): each case's key, name, citation and decision date; each opinion's ID, exact type, author, joiners (or "not printed"), paragraph and footnote counts with their ID ranges, page range (marked as slip pages for *Chatrie*); one line saying the filter groups types and results show the exact type.
- **Coverage** (brief §2): the three dates from the manifest.
- **The recording-only switch** (T5.6): `Corpus.load(..., exclude=("chatrie",))`, label `before_chatrie`. The case leaves the passages, both indexes, the catalog, the manifest the checks use, and the coverage. The latest decision in the corpus and in the full pull become *Carpenter*'s, 2018-06-22; the ingestion date stays. H turns it on only with `PC_CORPUS=before_chatrie` and refuses to start with it when `PC_ENV=live`.

## 4. The parts, their paths and interfaces

Signatures are binding; internals are the builder's; a builder may add private helpers in its own paths.

### R. Retries (the main session's, written): `api/retry.py`

`with_retries(attempt, policy, before_attempt, on_retry, sleep=asyncio.sleep)` runs `attempt(n)` until it returns, calling `before_attempt(n)` first each time (the caller passes `ctx.before_paid_call`) and `on_retry(next_attempt, error, wait_s)` before each wait (the caller records the failed attempt with `ctx.record_usage(..., outcome="retrying")`). `ANTHROPIC_POLICY` and `VOYAGE_POLICY` hold T3.3's retryable kinds, counts and waits; a `retry_after_s` on the error wins over the wait. Exa has no policy: never retried by our code (T2.4).

### A. The sentence splitter (T1.9): `api/corpus/sentences.py`, `scripts/check_sentences.py`, `tests/corpus/test_sentences.py`

```python
def split_sentences(text: str) -> list[tuple[int, int]]:
    """[start, end) spans that tile `text` exactly (no gap, no overlap, in order).
    Whitespace after a sentence belongs to that sentence. "\n\n" always ends one."""
LEGAL_ABBREVIATIONS: frozenset[str]   # e.g. "U. S.", "How.", "Cal.", "Pen.", "Stat.", "supra", "e. g."
```

The rule (T1.9): split only where a sentence plainly ends: `.`, `?` or `!` (or one followed by a closing quotation mark or bracket), then whitespace, then a capital letter or an opening quotation mark or bracket, **and** the token before the stop is a lowercase word that is not an abbreviation, a number, a closing bracket or quotation mark, or a capitalised word of five or more letters not on the abbreviation list. In doubt, do not split. Ellipsis rows (`. . .`) never end a sentence on their own.

`scripts/check_sentences.py` runs the splitter over every passage (it builds passage texts from `data/corpus/` itself, by §3's rules, so it does not wait on B), asserts the tiling for all 2,462, and writes `data/verification/sentences/report.json` (local) listing suspicious splits: a split before a capital that follows a short capitalised word, an initial, a section sign, "v.", "No.", a reporter abbreviation or a number. The main session reviews a sample (T1.9; no subagent). Tests use `tests/fixtures/sentences/hardest.json` (the ten passages `scripts/probe_chunking.py` chose; committed).

### B. The corpus index: `api/corpus/store.py`, `api/corpus/filters.py`, `api/corpus/keyword.py`, `api/corpus/web_data.py`, `scripts/build_web_data.py`, `tests/corpus/`

```python
class Corpus:
    @classmethod
    def load(cls, root: Path, exclude: tuple[str, ...] = ()) -> "Corpus": ...
    label: CorpusLabel                    # "full", or "before_chatrie" when exclude == ("chatrie",)
    passages: dict[str, Passage]          # insertion order = reading order (case, opinion, paragraphs then footnotes)
    manifest: dict                        # the manifest with excluded cases removed (used by the checks)
    coverage: dict                        # {"latest_decision_full_pull", "latest_decision_in_corpus", "ingested"}
    catalog_text: str
    case_keys: frozenset[str]
    def loop_text(self, passage_id: str) -> str          # text with "[n. <label>]" markers (§3)
    def attached_footnotes(self, passage_id: str) -> list[Passage]   # the footnotes a paragraph cites (T1.6)
    def read(self, target: str, before: int, after: int) -> list[Passage]
        # target: a passage ID; or "<case_key>:<page>" (every passage on that U.S. Reports page, in reading
        # order, across the case's opinions); or, for a slip opinion, "<opinion_id>:<slip page>" (a case-level
        # page target is refused there with a message naming the opinion form). before/after 0..READ_AROUND_MAX
        # within the target passage's opinion and kind. Raises ToolInputError naming the valid range (T1.6).

def parse_filters(raw: dict | None, corpus: Corpus) -> Filters      # validates; raises ToolInputError (T1.4)
def matches(p: Passage, f: Filters) -> bool                          # every filter but none_of
def excluded_by_none_of(p: Passage, f: Filters) -> bool              # words or quoted phrases, case-insensitive

class KeywordIndex:                       # SQLite FTS5, porter + unicode61, built at start (T1.2, T3.6)
    def __init__(self, corpus: Corpus): ...
    def search(self, all_of: list[str], any_of: list[str], none_of: list[str],
               f: Filters, limit: int) -> list[Hit]                  # bm25 order, best first, at most `limit`
    @staticmethod
    def compile(all_of, any_of, none_of) -> str                     # the FTS5 query; Claude never writes syntax
```

`parse_filters` treats an empty list, or a filter set to every value, as unset (T1.4). `KeywordIndex.search` raises `ToolInputError` when both `all_of` and `any_of` are empty, a list exceeds `KEYWORD_ITEMS_PER_LIST`, or a list is not a list of strings. A double-quoted item is an exact phrase; an unquoted item of several words needs all its words, anywhere; word forms match (porter) in `all_of` and `any_of`. **`none_of` matches exact words and phrases, unstemmed, on both tools** (`excluded_by_none_of` and the keyword index agree; v1.1). The caller asks for `limit = max_results + len(already seen)` so it can top up (T1.6).

`scripts/build_web_data.py --out <dir>` writes, for the web image: the reader files (§11.1), `corpus.json` (§11.3) and `config.json` (§5.1). It always uses the full corpus.

### C. Meaning search: `api/search/voyage.py`, `api/search/meaning.py`, `scripts/embed_corpus.py`, `tests/search/`

C depends only on `api/types.py`, `api/errors.py`, `api/retry.py` and `api/settings.py`: its tests build `Passage` objects directly, so it never waits on B.

```python
class VoyageClient(Protocol):
    async def embed(self, texts: list[str], input_type: Literal["query", "document"]) -> tuple[list[list[float]], Usage]: ...
    async def rerank(self, query: str, documents: list[str]) -> tuple[list[tuple[int, float]], Usage]: ...  # every document, best first

class HttpVoyageClient(VoyageClient):     # VOYAGE_BASE_URL, bearer VOYAGE_API_KEY, VOYAGE_TIMEOUT_S, no retries;
    ...                                   # failures raised as ServiceError with an ErrorKind
class FakeVoyageClient(VoyageClient): ... # deterministic vectors from a hash; scripted failures

def embedded_text(p: Passage) -> str:
    """One header line, then the text (T3.6): '<case name> (<year>), <exact type>, <authors or per curiam>[, <section>]',
    where <section> is "Part <label>" for a numbered label ("Part III-A") and the label as it stands for an
    appendix label ("Appendix", "APPENDIX TO OPINION OF MR. JUSTICE WHITE."); several authors joined with " and "."""

class MeaningIndex:
    @classmethod
    def load(cls, vectors_dir: Path, passages: Iterable[Passage]) -> "MeaningIndex": ...
        # reads voyage-law-2.f32 and manifest.json; raises if the model, dimension or any passage's
        # embedded-text hash disagrees; rows of passages not given (an excluded case) are dropped (T3.6)
    async def search(self, query: str, keep: Callable[[Passage], bool], ctx: RunContext,
                     voyage: VoyageClient) -> "MeaningResult": ...
        # `keep` is the caller's filter (B's matches and excluded_by_none_of)

@dataclass
class MeaningResult:
    hits: list[Hit]                      # every reranked candidate (up to SEMANTIC_CANDIDATES), best first; the caller tops up
    status: Literal["ok", "not_reranked", "unavailable"]
    message_for_claude: str | None       # the "not reranked" note, or the error saying keyword search still works
```

Order (T1.4, T3.3): filter with `keep`; embed the query (`input_type="query"`); brute-force dot product over unit-normalised rows; take `SEMANTIC_CANDIDATES`; rerank them all with `rerank-3` over their embedded texts. Each Voyage request: `with_retries(..., VOYAGE_POLICY, before_attempt=lambda n: ctx.before_paid_call("voyage", purpose), ...)`, each attempt recorded with `ctx.record_usage` (purpose `embed` or `rerank`). Rerank still failing → embedding order, `not_reranked`, `ctx.flags.meaning_degraded = True`. Embed still failing → `unavailable`, no hits, `ctx.flags.meaning_unavailable_once = True`. A 401 → also `ctx.flags.voyage_unavailable = True`, and every later search in the run returns `unavailable` without calling Voyage (logged as configuration fault).

**The per-run bound (T3.4, v1.4):** each attempt's cost, as `record_usage` returns it, is added to `ctx.flags.voyage_spent_usd`. Before a search, C estimates its two calls (the query's embed and the rerank of the candidates, from characters at `VOYAGE_CHARS_PER_TOKEN_ESTIMATE`, priced at list price with no retries). Each call is checked with all its allowed attempts priced. If the embed would pass `VOYAGE_RUN_BOUND_USD`, the search makes no call, sets `meaning_unavailable_once` and returns `unavailable`; if only the rerank would, it returns the embedding order as `not_reranked` and sets `meaning_degraded`. So the worst case's Voyage part holds.

`scripts/embed_corpus.py` embeds every passage's `embedded_text` with `input_type="document"`, in batches paced under Voyage's Tier 1 limits (read from Voyage's docs; figures and source in the docstring), caching each batch under `data/cache/voyage/` (gitignored) so a rerun never pays twice. It prints the token count and the cost at list price and **spends only with `--confirm`**; the main session runs it. Output: `data/vectors/voyage-law-2.f32` (row-major float32, rows in passage reading order) and `data/vectors/manifest.json` (`model`, `dimension`, `count`, `created` as a Chicago date, `units`: `[{id, sha256}]` of each embedded text). It reads passages through B's `Corpus.load` and prices through E's `price`, both imported inside `main()`, so B's section labels are the only ones; its tests inject passages and a price function, so C never waits on B or E (v1.1).

### D. The update check: `api/web_updates/params.py`, `api/web_updates/exa.py`, `api/web_updates/format.py`, `tests/web_updates/`

```python
@dataclass(frozen=True)
class WebSearchParams:                    # our wrapper's fields (T2.1), validated
    query: str
    start_published_date: str | None      # YYYY-MM-DD
    end_published_date: str | None
    include_domains: tuple[str, ...]      # <= EXA_DOMAINS_MAX; hostname, path prefix or "*.example.com"
    exclude_domains: tuple[str, ...]
    category: Literal["news", "publication"] | None
    type: Literal["auto", "lite"]         # default "auto"
    num_results: int                      # 1..10, default 10, clamped

def parse_params(raw: dict) -> WebSearchParams    # raises ToolInputError (refused by our code, not counted, T2.4)
def to_exa_arguments(p: WebSearchParams) -> dict  # snake_case to Exa's tool argument names. Fixed settings are applied
                                                  # by omission (no highlights, no summaries are simply not requested),
                                                  # except the text cap EXA_TEXT_CHARS, sent explicitly

class ExaTransport(Protocol):
    async def call(self, arguments: dict, timeout_s: float) -> dict: ...     # Exa's parsed JSON; raises ServiceError
    async def list_tool_schema(self) -> dict: ...                           # free; for the schema check (T2.5)
class McpExaTransport(ExaTransport): ...  # one MCP session per call (T2.5), EXA_MCP_URL, key only in x-api-key
class FakeExaTransport(ExaTransport): ... # scripted results and every failure kind

@dataclass
class WebSearchOutcome:
    kind: Literal["ok", "refused_by_exa", "failed", "unavailable"]
    unavailable_reason: Literal["no_credit", "key_refused"] | None
    pages: list[WebPage]                  # new pages, in Exa's order
    repeats: list[str]                    # IDs of pages an earlier search in this run returned (T2.2)
    undated: int
    exa_message: str | None               # Exa's own message, for refused_by_exa
    cost_usd: float                       # informational: already recorded through ctx.record_usage

class UpdateSearch:
    def __init__(self, transport: ExaTransport, store: Store): ...
    async def search(self, p: WebSearchParams, search_no: int, seen_urls: dict[str, str],
                     ctx: RunContext) -> WebSearchOutcome: ...
    async def schema_check(self) -> list[str]: ...    # warnings; never blocks (T2.5)

def format_for_claude(p: WebSearchParams, o: WebSearchOutcome) -> str        # T2.2, with page text in data markers
def format_for_events(p: WebSearchParams, o: WebSearchOutcome) -> str        # the same text, each page's text replaced
                                                                             # by "[page text: <n> characters, not stored]"
```

`search` calls `ctx.before_paid_call("exa", "update_search")` and `ctx.record_usage(...)` itself (once: no retries). It checks the out-of-credit flag (`store.flag_until("exa_out_of_credit")`) and `ctx.flags.exa_unavailable` before opening a session; on the first 402 it sets the flag (until the 1st of the next Chicago month), records the stop `exa_no_credit`, and sets `ctx.flags.exa_unavailable = "no_credit"`; a 401 sets `ctx.flags.exa_unavailable = "key_refused"` for this run only (T2.4). After either, `search` calls `ctx.call_not_billed("exa", "update_search")`, since the gate was passed and nothing was billed (v1.4). Four failure kinds, the 30 s timeout covering the handshake, list price for a failed search: T2.4, T2.5. A published date that is not a parseable `YYYY-MM-DD` date part becomes `None` (counted as undated); a result whose URL is not `http` or `https` is dropped. Any copy of the closing data marker inside page text is escaped (T2.2). **Recording (T2.4, v1.1):** `record_usage` is called once for each search that reached Exa and counts: completed, `Usage(service="exa", model=type, exa_cost_usd=<costDollars>)`, or with `exa_cost_usd=None, estimated=True` when Exa reported no cost (priced at list price); refused by Exa, `exa_cost_usd=0.0`, outcome `failed`; failed, `Usage(..., estimated=True)` (list price). An unavailable search (402, 401) is not counted and calls no `record_usage`. `price` treats `exa_cost_usd=0.0` as a reported zero (test with `is not None`). G calls `schema_check()` on the instance's first update search (T2.5). v2.0: D is unchanged. The update step calls `search` (§4.G.4), and `UPDATE_SEARCHES_PER_RUN` is 5 (P4.18).

### E. Money and state: `api/state/store.py`, `api/state/budget.py`, `api/state/prices.py`, `api/state/clock.py`, `scripts/spend_report.py`, `tests/state/`

```python
class MongoStore(Store): ...              # api/protocols.Store; pymongo AsyncMongoClient; ATLAS_OP_TIMEOUT_S
class MemoryStore(Store): ...             # the fake every other part tests against; same semantics

def worst_case_components() -> dict[str, float]   # P4.21: a documented, tested figure only, never a gate
def worst_case_usd() -> float             # $11.161 (v2.0)
def price(u: Usage) -> float              # list price (T3.4); a failed attempt with no usage as T3.3
def list_price_exa(type: str) -> float
PRICE_TABLE: dict                         # §10, one source and date per provider

def chicago_now() -> datetime; def chicago_day(dt) -> str; def chicago_month(dt) -> str; def next_month_start(dt) -> datetime
```

**No reservation (P4.21, v2.0).** `reserve`, `settle`, `release`, reservation expiry and `open_reservations` are gone, and so is the worst case as an admission gate.

**`admit(run_id, now)`** reads the spend-limit flag (it lives in `flags`), then makes one conditional update of the month's document, with the day's entry upserted in it. A missing `days.<day>.spent` must count as 0 in that condition, and an upsert whose condition fails must not raise a duplicate-key error. It succeeds only if:
- the `anthropic_spend_limit` flag is clear;
- the month's `spent` is under `MONTHLY_CAP_USD`;
- the Chicago day's `spent` is under `DAILY_CAP_USD`.

"Under" is strict: at or over the cap refuses. A month or day with no document yet counts as $0 spent. On success it counts the day's `runs_started` in the same update and returns `Admission(run_id, month, day)`. Otherwise:
- While the flag is set, it returns `Refusal("spend_limit_paused")` (checked first).
- It returns `Refusal("monthly_cap")` or `Refusal("daily_cap")` and records that stop itself, with the spend at that moment.
- If Atlas can't be reached, it returns `Refusal("atlas_unreachable")` and records it, marked not a budget stop, where it can.

`ATLAS_ADMIT_TRIES` bounds any compare-and-swap rounds E needs; E removes the setting's use if one conditional update suffices, and says so in its report.

**`record_spend(admission, cost_usd)`** adds one paid call's cost, atomically (`$inc`), to the month's `spent` and the admitted day's `spent`. A cost below 0 or not a number is refused with `ValueError`. Spend counts toward the Chicago day and month the run was admitted in, as before. It raises when Atlas can't be reached; H decides what to do (§4.H).

**Runs in progress always finish** (P4.21): nothing in E stops or refuses a call of an admitted run. A cap reached during a run only refuses the next `admit`.

**Old documents.** `Probable_Clause_test` holds months written with `reserved` and `reservations` fields. E ignores them: they are never read as spend, never written, and never fail a read.

**`live_status(now, timeout_s)`** (for `/health`) reports:
- `paused_month` while the spend-limit flag is set, or when the month's spent is at or over the monthly cap;
- otherwise `paused_day` when the day's spent is at or over the daily cap;
- otherwise `open`;
- `unknown` past `timeout_s`.

It also reports whether the update check is available: not while the Exa flag is set.

**The documented worst case** (P4.21; Sonnet 5.5 prices for every Claude part, P4.20). Every input token is priced as a fresh 5-minute cache write except the composition's, which is uncached, and every limit is reached:
- **Research:** `LOOP_INPUT_BUDGET` at the 5-minute write price, $5.00; `LOOP_OUTPUT_BUDGET` at the output price, $0.16.
- **The update step:** `UPDATE_INPUT_BUDGET` at the 5-minute write price, $5.00; `UPDATE_OUTPUT_BUDGET` at the output price, $0.06.
- **Composition, three attempts:** 3 × `WORST_CASE_COMPOSITION_INPUT` uncached, $0.396; 3 × `COMPOSITION_MAX_TOKENS` at the output price, $0.48. An attempt that breaks before its first block is retried and its thinking is billed as output (P4.10), so all three can bill output.
- **Exa:** `UPDATE_SEARCHES_PER_RUN` × the `auto` price, $0.035.
- **Voyage:** `VOYAGE_RUN_BOUND_USD`, $0.03.

Total **$11.161**. So when a cap is reached, the `MAX_CONCURRENT_RUNS` runs then in progress can take spend past it by at most about **$55.81** before they finish. The caps only stop admission. The outer backstop is the Console's $60 monthly limit on the live workspace (T3.4), outside our code. It holds whatever our figures say: a month's cap of $60 plus that overrun is more than $60, so the Console limit, not the cap, is what finally stops spend.

Two things are not modelled:
- the system prompt's single 1-hour write (about 12,000 tokens, about $0.02 more than the 5-minute price);
- thinking that a broken research or update attempt never streamed. It is billed but not counted against the step's budgets (P4.5). A test asserts the components and the total. `tests/contract/test_composition_worst_case.py` (the main session's) recomputes the composition's largest input with G's request builder and estimator and asserts it fits in `WORST_CASE_COMPOSITION_INPUT`.

**Scripts:** `scripts/spend_report.py --day YYYY-MM-DD | --month YYYY-MM [--env live|test] [--json]` is read-only. It exits 0 when it read the store and 2 when Atlas can't be read. `--open-reservations` and its exit 1 are gone (v2.0). The deploy script reads the live month with it (§4.I).

### F. The answer checks: `api/checks/quotations.py`, `api/checks/citations.py`, `api/checks/update_findings.py`, `tests/checks/`

```python
@dataclass
class Flag:
    block: int; start: int; end_block: int; end: int    # from (block, start) to (end_block, end) in the answer blocks
    kind: Literal["quotation_not_found", "not_in_corpus"]
    text: str

@dataclass
class CheckResult:                        # the `checks` event's data, field for field (§6)
    quotations_checked: int; quotations_found: int
    citations_checked: int; citations_found: int
    not_in_corpus: list[str]              # the names or citations, as written
    flags: list[Flag]

def check_answer(blocks: list[str], kept_texts: list[str], manifest: dict) -> CheckResult
    # quotations of QUOTATION_MIN_WORDS or more words must appear in the kept passages, allowing the quoting
    # conventions of T1.12 (a quotation may span blocks); every full "X v. Y" name and every U.S. Reports citation
    # ("389 U. S. 347") must resolve to the given manifest, else "not in this corpus" (P1.10). Short names unchecked.

def check_update_findings(findings: list[dict], overview: str | None, returned_ids: set[str],
                          searches_run: int) -> list[str]
    # T2.3 item 2: unknown source ID, a statement with no source, findings with no search run; T2.3's caps
def copy_guard(texts: list[str], page_texts: list[str], n_words: int) -> list[str]
    # T2.3 item 3: n or more consecutive words of any returned page, ignoring case, punctuation and spacing
    # (v1.6: compatibility forms folded by NFKC; an invisible format character, Unicode Cf, read both as dropped
    # and as a space, a run in either reading counting)
def copy_guard_report(statements: list[str], overview: str | None, pages: Mapping[str, str],
                      n_words: int, *, note: str | None = None,
                      exempt: Container[tuple[str, ...]] = NO_EXEMPTION) -> CopyGuardReport
    # what G calls (v1.1): problems naming statements and page IDs, plus flagged_statements (0-based) and
    # overview_flagged, so G can withhold them in the stored tool_call (P4.3); v1.5: the note (P4.8), with
    # note_flagged and note_pages (page IDs), and `exempt` (P4.9); v1.7: `skip_reason=` (P4.13), with
    # skip_reason_flagged and skip_reason_pages
def corpus_words(texts: Iterable[str]) -> CorpusWords
    # v1.5 (P4.9): the corpus's words, normalised as the guard's; `gram in it` is true for a run of words found
    # inside one text. G builds it once per Corpus from the passages' texts and passes it as `exempt`
def pages_named(ids: list[str]) -> str     # "page web-1-2" or "pages web-1-2 and web-2-1"
```

**v2.0 (P4.19):** F is unchanged. Only the update step calls `check_update_findings` and `copy_guard_report`, over statements, the overview and `skip_reason=`. Research's note is no longer guarded, so `note=` is no longer passed.

**The corpus exemption (P4.9, v1.5):** a run of `n_words` words that a text shares with a page is not counted when it also appears, in F's normalisation, inside one passage of the corpus. So a statement, overview or note quoting the Court that a page also quotes passes, while a run that carries on into the page's own words is still caught (its runs past the quotation are not the corpus's). The exemption is one normalised string, about 2 MB for the corpus. The note's problem names "The note" and the page IDs and never quotes either.

**Quotation and name rules settled in review (v1.1):** a quotation is a double-quoted span (a multi-paragraph quotation by the legal convention included) or a Markdown blockquote; the comparison ignores letter case throughout, so a re-cased letter needs no brackets, and a flag still quotes the answer as written (P4.17, v1.9); a bracketed alteration stands for at most `QUOTATION_BRACKET_MAX_SOURCE_WORDS` source words and never adds or removes a negation; an ellipsis matches the smallest gap in the source, and a gap holding a negation word fails the match (v1.4; the words include "nowhere", "nobody", "hardly", "scarcely", "barely" and "absent", v1.6); no quotation or piece of one starts right after a negating prefix and its hyphen, so "intrusive" is never quoted out of "non-intrusive", and a bracket may not strip or add a hyphenated prefix either (v1.6); a full name's right party must equal the manifest's; a full name immediately followed by a U.S. Reports citation of a different corpus case flags the citation. A quotation that cannot be decided in bounded time is flagged, never passed. Offsets are Python code points; the page converts them for JavaScript strings. Each returned string is a problem written to Claude. It names the statement by its number and the page by its ID, and **never quotes the page's words** (the message is stored in events). The checks run on the text exactly as streamed.

### G. Research, the update step and composition: `api/loop/`, `tests/loop/`; prompt text in `api/prompts/` (the main session's)

```python
@dataclass
class LoopDeps:
    corpus: Corpus; keyword: KeywordIndex; meaning: MeaningIndex; voyage: VoyageClient
    updates: UpdateSearch; anthropic: "AnthropicStreamer"

class AnthropicStreamer(Protocol):        # the one place the SDK is called (streamed, max_retries=0, T3.3)
    async def stream(self, request: dict, deadline_s: float, on_block: Callable | None, *,
                     step: Step) -> "StreamResult": ...
        # raises ServiceError with an ErrorKind (§2). `step` (v2.0) is for logs and the fake's scripts; never sent
class FakeAnthropic(AnthropicStreamer): ...   # one script per step (§12)

async def execute_run(ctx: RunContext, deps: LoopDeps) -> None
    # emits run_started ... run_ended; returns normally for every expected end, RunStopped included
```

#### G.1 A run, in order (P4.19, v2.0)

1. **`run_started`.**
2. **Research** (§G.3) runs until an accepted `submit_answer`, a limit, an error or a stop.
3. **The branches are decided** when research ends:
   - **The update step** (§G.4) starts only when all of these hold:
     - research ended with an accepted `submit_answer`;
     - `out_of_scope` is false (design §3: `not_run` "now means out of scope", including an out-of-scope reply that searched);
     - at least one corpus search ran (the user's rule, P4.19, enforced by code: a reply that never searched the corpus is out of scope). Rule 2 already makes this true for an accepted in-scope submit; the check stays as the user's backstop;
     - the update check is available (`ctx.update_check_available`, and `ctx.flags.exa_unavailable` is None).

     Otherwise no update call is made and `update_band` is emitted at once: `unavailable` (reason `no_credit` or `key_refused`) when the update check's unavailability was the only reason, else `not_run`.
   - **The composition** (§G.5) runs exactly when v1.9 composed: an accepted, in-scope submit with something kept, or a research limit or error stop with something kept (T1.11, T3.3).
4. **The two branches run side by side** as asyncio tasks, the update task created first, so that with the fakes the stream is deterministic (the fixtures rely on it). `execute_run` waits for both, then emits `run_ended`. Neither branch's end cancels the other.
5. **The update branch never raises out of itself.** Every failure inside it ends the update step and is reported in `update_ended` and the band, including an unexpected exception (logged with its type, `failure_reason: internal`). It never changes the answer or the run's `state`, `stop_kind`, `answer_end`, `failure_reason` or `rounds`.
6. **An unexpected exception in research or the composition** goes like this:
   - G cancels the update task and awaits it;
   - G re-raises the original exception (never an `ExceptionGroup`), so H ends the run `failed`.

   A cancelled branch emits nothing more: no `update_ended` and no `update_band`. Nothing is emitted after H's `run_ended`.
7. **A Claude attempt in flight when its task is cancelled** is still recorded before the cancellation propagates, priced from what it streamed and reported (P4.5, P4.10). That covers cancellation by G (item 6) and by H's shutdown. At shutdown the recording happens within `SHUTDOWN_GRACE_S`, and one the grace doesn't cover is lost, as P4.21 accepts.

#### G.2 One conversation, one cache (P4.19)

Research and the update step are one conversation, so the update step reads research's cache. Every research and update request has identical `model` (`UPDATE_MODEL` equals `LOOP_MODEL`, asserted at import), `system` (the same text with the 1-hour breakpoint), `tools` (the same seven, in the same order, with the same schemas), `thinking`, `output_config` (`UPDATE_EFFORT` equals `LOOP_EFFORT`) and top-level `cache_control`. Only `max_tokens` and `messages` differ.

- **The update step's first request** is research's messages as they stand after research's last call (ending with the assistant turn holding the accepted `submit_answer`), plus one user turn: the submit's `tool_result` (content `loop_messages.json`'s `update_start`, not an error), then the update step's status line. Every later update call appends to the same list.
- **A test asserts the prefix byte for byte:**
  - both requests come from one builder;
  - the `json.dumps(..., ensure_ascii=False)` of every field but `max_tokens` and `messages` is identical, key order included, since tools are rendered into the prompt;
  - the update request's `messages` begin with research's last request's `messages` and that call's response, identical in the same way.
- **The breakpoints** stay as v1.9: 1 hour on the system block, the automatic 5-minute one on the growing conversation (T1.14).

**Tools by step.** All seven are in every research and update request; each step runs only its own:

| Tool | Research | Update step |
|---|---|---|
| `search_meaning`, `search_exact`, `read_passages`, `keep_passages`, `submit_answer` | runs | refused with `rejections.json`'s `wrong_step.research_tool` |
| `search_web_updates`, `submit_update` | refused with `wrong_step.update_tool` | runs |

A refused wrong-step call:
- has `is_error: true` and `wrong_step: true` in its `tool_result`, with these fields by tool:
  - `search_meaning` and `search_exact`: `found` and `matched_again` empty;
  - `read_passages`: `read` empty and `target` as given (or "");
  - `keep_passages`: `kept` empty and `kept_count` as it stands;
  - `search_web_updates`: `web` and `web_repeats` empty, `web_status: "refused_by_us"`, and no `search_no`;
  - `submit_answer` and `submit_update`: `submit: {"accepted": false, "rule": "wrong_step"}`;
- is never counted (a `search_web_updates` refused in research is not an update search);
- counts toward rule 1, which counts every `tool_use` in the turn.

**An unknown tool** gets `unknown_tool` (listing the seven), as v1.8.

**No page's words in a refused call (§1, T2.2, P4.3 carried to v2.0).** All seven tools are offered in the update step, so a call refused there could carry a page's words: a wrong-step `submit_answer` note, a keep reason, or a `submit_update` refused at the input check. In the update step, once any page has been returned in the run:
- every **refused** call's stored and streamed `tool_call` has each string in its input, at any depth, run through `copy_guard` with the corpus exemption;
- each flagged string is replaced by "[statement withheld: it repeated a page's words]".

This covers wrong-step calls, unknown tools and every rule's refusals. `submit_update`'s own rules withhold as §4.G.4 says, and both apply. Accepted calls are stored as Claude sent them, as in v1.9.

#### G.3 Research (T1.2 to T1.10, amended by P4.16 and P4.19)

- **What G owns, unchanged from v1.9:** the tools' validation (T1.2 to T1.10, T3.7; strict mode only where T3.7 allows it, the count of strict tools recorded), result formatting (T1.6), the "matched again" top-up (T1.6), the keep rules (T1.7), `api_fragment` events (T4.3), the Voyage warning (T3.3), and every Claude call through `with_retries(ANTHROPIC_POLICY, ...)` with each attempt recorded by `ctx.record_usage` (with `raw_usage` and `call_no`).
- **The first message** is `first_message` alone. The update-unavailable line goes, since research no longer has an update check.
- **The status line** is `status_line`: "Round <round> of {{MAX_ROUNDS}} · <kept> kept" (no update count).
- **The limits** are checked before each round, as v1.9: `MAX_ROUNDS` (`step_limit`), the deadline (`time_limit`), `LOOP_OUTPUT_BUDGET` (`token_ceiling_output`, also for a call stopped by `max_tokens`) and `LOOP_INPUT_BUDGET` by the estimate (`token_ceiling_input`). The first call's estimate is the system prompt, the tools and the messages at the corpus's ratio, with no fixed floor (`FIXED_PREFIX_TOKENS_ESTIMATE` is gone, P4.18). Every attempt counts toward the budgets (T3.4).
- **`submit_answer(out_of_scope, note?)`** must be the turn's only call, sent once (P4.16). The rules, in order:
  1. rule 1, `same_turn`;
  2. the input check, rule null (a field the tool no longer has, such as `update_findings`, is refused here);
  3. the note cap, `note_too_long` (P4.6);
  4. rule 2, `no_search`: in scope with no corpus search;
  5. rule 3, `nothing_kept`: in scope, nothing kept and no note;
  6. `no_note`: out of scope with no note.

  There is no rule 4, no reminder, no findings check and no copy guard: research never sees a web page (P4.19). Its `tool_call` is stored exactly as Claude sent it.
- **An accepted submit** stops research at once. Its `tool_result` content:
  - when the update step will start: `update_start` (`<passages>` as in `submit_accepted_answer`) when something was kept, or `update_start_note` when nothing was (a "nothing found" reply, which composes nothing);
  - otherwise: `submit_accepted_note` or `submit_accepted_answer`, never sent to Claude.

#### G.4 The update step (P4.19)

- **Its calls:** purpose `update`, model `UPDATE_MODEL`, effort `UPDATE_EFFORT`, the call deadline `LOOP_CALL_DEADLINE_S`, retries as research's (T3.3), each attempt recorded with `ctx.record_usage(purpose="update")`. Call numbers come from the run's one counter, shared with research and the composition.
- **`update_started`** (`{"kept": [...]}`, the kept IDs in keep order, as research ended) comes before its first round.
- **Rounds** count from 1 within the step. Each has a `round_started` with `step: "update"` and the status line `status_line_update`: "Update step · round <round> of {{UPDATE_MAX_ROUNDS}} · <update_status>", the last part from `status_update`.
- **Its limits** are checked before each round, each ending the step with its own stop kind:
  - `UPDATE_MAX_ROUNDS`: `update_step_limit`;
  - the run deadline (`ctx.seconds_left() <= 0`, or `RunStopped("deadline")` from the gate): `update_time_limit`;
  - `UPDATE_OUTPUT_BUDGET` used up, or a call stopped by `max_tokens`: `update_token_ceiling_output`;
  - `UPDATE_INPUT_BUDGET` by the estimate (research's estimator, carried on from research's last call): `update_token_ceiling_input`.

  Every update attempt counts toward the update budgets, and only toward them. `max_tokens` is the update output left.
- **Its other ends:**
  - `RunStopped("abandoned")` from the gate ends the step as abandoned, with no stop kind;
  - an error left after retries ends it `failed` with `failure_reason` that kind;
  - a `spend_limit` or `spend_cap` error instead ends it `stopped`, with `stop_kind` `console_spend_limit` or `tier_spend_cap` and `failure_reason` the error's kind. The stop also goes in `run_ended.stop_kinds`, so H pauses live research (§4.H);
  - the `refusal` stop reason ends it with `failure_reason: refusal`.
- **`search_web_updates`:** as v1.9 (T2.1 to T2.5), up to `UPDATE_SEARCHES_PER_RUN`. Claude gets `format_for_claude`, the event gets `format_for_events`, and `schema_check()` runs on the instance's first update search (T2.5).
- **`submit_update(update_findings?, update_overview?, update_skip_reason?)`** must be the turn's only call, sent once. The rules, in order:
  1. rule 1, `same_turn`;
  2. the input check, rule null;
  3. the findings checks, `findings` (T2.3 item 2, `check_update_findings`), when findings or an overview are given;
  4. the copy guard, `copy_guard` (T2.3 item 3, P4.3, P4.13, P4.9), once any page was returned in the run: `copy_guard_report(statements, overview, pages, COPY_GUARD_WORDS, skip_reason=..., exempt=corpus_words(...))` over the statements, the overview and the skip reason. The text is `submit_update.copy_guard_skip_reason` (`<pages>` from `pages_named`) when only the skip reason is flagged, else `submit_update.copy_guard` with all the problems;
  5. `no_check`: no counted search and no skip reason. Refused every time, with no reminder state; waived when the update check became unavailable during the step (`ctx.flags.exa_unavailable` set).

  P4.3's withholding: the stored and streamed `tool_call` has each flagged statement, a flagged overview and a flagged skip reason replaced by "[statement withheld: it repeated a page's words]", whichever rule refuses it.
- **An accepted `submit_update`** ends the step at once. Its `tool_result` content is `submit_update_accepted`, never sent to Claude.
- **At its end** it emits `update_ended`, then `update_band` (§6).

#### G.5 The composition (T1.8 amended by P4.20, T1.9, T1.11)

- **The call:** `COMPOSITION_MODEL` (Sonnet 5.5) at `COMPOSITION_EFFORT` (high), adaptive thinking, `max_tokens` `COMPOSITION_MAX_TOKENS` (16,000), uncached, the approved system prompt.
- **Its sources** are custom content documents of the passages kept when research ended (the update step can't change them), with our sentences, metadata and keep reason in `context`.
- **Its input** is estimated before the call, only to price an attempt that fails with no usage. There is no reserve to compare it with (P4.18).
- **Unchanged from v1.9:**
  - an attempt broken before its first block is priced and counted from what it streamed and reported, so a retry still runs (P4.10);
  - each citation's block range maps back to a passage ID and an inclusive sentence range;
  - a citation whose `cited_text` disagrees with our slice (spacing aside) is not attached, and is logged and counted as a mapping fault (v1.3);
  - F's checks run on the text exactly as streamed;
  - it proceeds past the run deadline (§4.H).

#### G.6 Ends

- **The run's `state`, `stop_kind`, `answer_end`, `failure_reason`, `no_sources_reason`, `note`, `scope_note` and `rounds`** come from research and the composition, as v1.9 (§6):
  - `RunStopped("deadline")` in research composes from what was kept and ends `time_limit`;
  - `RunStopped("abandoned")` in research or the composition ends the run `abandoned`, composing nothing more;
  - a `spend_limit` or `spend_cap` error in research or the composition ends it `spend_limit` with that `stop_kind`.
- **`rounds`** is research's.
- **The update step's end** never changes these. An update step abandoned after the composition finished leaves the run `answered`.
- **`stop_kinds`** lists every budget or limit stop of the run, each kind once at its first occurrence, in the order they happened, from either branch: research's and the composition's as v1.4, plus the update step's (`update_step_limit`, `update_token_ceiling_input`, `update_token_ceiling_output`, `update_time_limit`, and its spend stops).
- **After the answer:** running F's checks, working out the band's outcome (§6), and every event of §6 except `paused` and `resumed`, plus `run_ended` in H's two cases.

#### G.7 Prompts

Prompts and tool descriptions are read from `api/prompts/`:
- `loop_system.md`: one system prompt for research and the update step (P4.19);
- `composition_system.md`;
- `tools.json`: the seven tools' descriptions;
- `rejections.json`: under `submit` (research), `submit_update`, `findings_problem`, `wrong_step`, `keep` and `update_search`;
- `loop_messages.json`: the first message, the two status lines, `update_start`, the accepted texts, `unknown_tool` and the composition request's lines.

`{{NAME}}` in upper case is filled from `api/settings.py`, lower-case `{{...}}` from the corpus (catalog, case count, coverage dates), and `<...>` per call; `tests/contract/test_prompts.py` checks the names. The v2.0 texts are the main session's drafts. The builders work from them, and the user reviews them before the first paid run (T1.14).

### H. The API and the run lifecycle: `api/server/`, `api/main.py`, `tests/server/`

```python
def create_app(deps_factory: Callable[[], Awaitable["AppDeps"]]) -> FastAPI
class Run(RunContext): ...                # state, event buffer, Atlas copy queue, heartbeat, deadline, admission, totals
class RunRegistry: ...                    # runs on this instance; one stream per run; the count of runs in progress
```

**Start-up and endpoints:**
- The endpoints are §5.
- Everything loads before the port opens, each step timed and logged with the time since the process started (T3.6).
- `PC_ENV` (`live` or `test`, default `test`) chooses the database. `PC_CORPUS=before_chatrie` is refused when `PC_ENV=live` (T5.6). `PC_COMMIT` is the short commit SHA, set when the image is built.

**Admission at `POST /runs` (P4.21, v2.0),** in order:
1. The body and question checks (§5's 400 and 413).
2. **`busy`:** when the registry's count of runs in progress is at `MAX_CONCURRENT_RUNS`, the run is refused with `503 busy`, with no Atlas call.
   - A run is in progress from the moment its slot is taken until the slot is freed.
   - **The slot is freed in the run task's `finally`,** after `run_ended` whenever one is emitted. It is also freed on expiry of an unattached run, and on any failure after it was taken (a refusal, an exception while the run is created, a cancellation). So five broken runs can never lock the site.
   - The slot is taken before Atlas is awaited, so two requests at once can't both pass a count of 4.
3. **`store.admit(run_id, now)`.** A `Refusal` answers §5's 503 code, an Atlas failure answers `atlas_unreachable` (fail closed), and either frees the slot.

`busy` isn't recorded in Atlas: it is not a budget stop. It is logged with the count.

**Money:**
- **`record_usage`** is the one place spend is priced, recorded and totalled, and the one emitter of `paid_call`, with `step = STEP_OF_PURPOSE[purpose]` (§2). After pricing, it calls `store.record_spend(admission, cost)`.
- **A failed `record_spend`** is logged and its cost kept.
  - After a run's first failure, H stops calling Atlas for that run's spend and keeps every later cost too, so a run against a dead Atlas doesn't spend its deadline on 5 s timeouts.
  - The kept costs are recorded once, as one sum, when the run ends, and logged as lost if that fails too. P4.21 accepts losing those calls' figures.
  - `record_spend` isn't idempotent. A call whose `$inc` reached Atlas but whose reply was lost is counted again in that sum. The error errs high, so it is accepted (E's review, v2.0).
- **`before_paid_call` never checks the caps.** A run in progress always finishes (P4.21).
- **Totals** have `cost_usd.loop`, `cost_usd.update` and `cost_usd.composition` (§6.2), and the per-run record (§8) gains the update step's cost.
- **Concurrency:** `record_usage`, `emit` and `before_paid_call` may be called by the update step and the composition at once (§4.G). Event numbers follow the order of the `emit` calls, with no gap. One pause emits one `paused` and one `resumed`, however many calls wait on it.

**The run task:**
- It starts when the first stream attaches, and attaching counts as a heartbeat.
- A run no stream ever attaches to expires after `UNATTACHED_RUN_EXPIRY_S` with no spend, and frees its slot (T3.1).

**Counting by step (v2.0).** Wherever H counts from events (the per-run record, `failed` and `interrupted`):
- research's rounds are the `round_started` events with `step: research`;
- the update step's rounds and end come from `update_ended`;
- update searches are counted from `tool_result`s carrying `search_no`;
- wrong-step calls are never counted;
- a Claude attempt that reported no usage is priced at `LOOP_MODEL` for `loop`, `UPDATE_MODEL` for `update` and `COMPOSITION_MODEL` for `composition`.

**Events and streams:**
- H keeps the event buffer and the numbering, and copies events to Atlas in order without holding up the stream: the full envelope plus `created` (§8).
- A reconnect replays from memory, or from Atlas when it reaches another instance (T3.1). It honours `Last-Event-ID`.
- One stream per run. A keep-alive comment every `KEEPALIVE_S`, and the `X-Accel-Buffering: no` header.

**`before_paid_call`**, in order:
1. If the run is abandoned, raise `RunStopped("abandoned")`.
2. If the purpose is not `composition` and the run is past its deadline, raise `RunStopped("deadline")`. This covers `loop`, `update`, `embed`, `rerank` and `update_search`. Composition always proceeds, so T3.5's time limit still composes.
3. If the run is unattended (no heartbeat for `ATTENDED_WINDOW_S`), emit `paused` and wait. Heartbeats come from this instance or, polled every `HEARTBEAT_POLL_S`, from Atlas. On one, emit `resumed`. If none comes, the run is abandoned at `ABANDON_AFTER_S` after the last heartbeat (T3.2).

**At the end:**
- H writes the per-run record (T3.7).
- It records each budget or limit stop in `run_ended.stop_kinds`, once each, the update step's included (§8; T3.4, v1.4).
- On `spend_limit`, or any run whose `stop_kinds` holds `console_spend_limit` or `tier_spend_cap`, it sets the `anthropic_spend_limit` flag until the 1st of the next Chicago month, which pauses live research (T3.3, T5.4). This holds whichever step met the limit: an update step that meets it during an answered run sets the flag too.
- It frees the run's slot in the run task's `finally`, after `run_ended` (see Admission).

**The two `run_ended` events H emits:**
- **`failed`,** when `execute_run` raises an unexpected exception.
- **`interrupted`,** on an instance that doesn't hold the run. It is sent on the stream only, never stored.
  - Its `n` is one more than the larger of the last stored event and the page's `Last-Event-ID`, so the page always receives it (v1.2).
  - Stored events are replayed only while their numbers run on without a gap.
  - Its totals are summed from the stored `paid_call` events, purpose `update` included, an estimated attempt's tokens from its `estimated_usage` (v1.6).

**Shutdown (v1.2, v2.0):** uvicorn runs with `--timeout-graceful-shutdown` of `SHUTDOWN_GRACE_S`. After Cloud Run's SIGTERM, the open streams close, and the lifespan shutdown cancels the running runs and records their kept costs before the SIGKILL 10 s later.

**Protections:** the body-size caps and the question cap (T3.7).

### I. Images and the deploy script: `deploy/`, `tests/deploy/`

**Files:**
- **`deploy/api.Dockerfile`:** Python 3.13 with uv; the committed corpus and vectors; FTS5 checked at build; `PC_COMMIT` baked in.
- **`deploy/web.Dockerfile`:** nginx at an exact pinned version. It serves `web/` as is, plus `scripts/build_web_data.py`'s output, the replays from `replays/`, and the `.woff2` fonts with the OFL text that the frontend session places under `web/fonts/` (T4.2, T5.5). Every response carries `Cache-Control: no-cache`.
- **`deploy/nginx.conf`:** written from scratch, with no goodnight code (T3.5).
- **`deploy/deploy.sh`:**
  - deploys both services, every setting explicit from `api/settings.py`'s Cloud Run block, with `--scaling=auto`, Secret Manager references and one service account per service (T3.5);
  - first reads the live database with `scripts/spend_report.py --month <this Chicago month> --env live`, and stops if Atlas can't be read (exit 2). It reads again right before the API is replaced. v2.0: the open-reservation check is gone with the reservation (P4.21), so a run in progress when the revision changes is cut off, and nothing detects it;
  - deploys the API with `PC_ENV=live`, which `tests/deploy/` asserts, so production never writes development's database (P4.22);
  - **is written, never run**, except by the main session on the user's green light.
- **`deploy/local.sh`:** builds both images and runs them for the user's local review (P4.1):
  - the API on port 8000 with `PC_ENV=test`;
  - the web service on port 8080, whose local nginx profile proxies `/api/` to the API.

**How the page reaches the API:** the page always calls `api/...` relative to its own URL. In production that resolves to `/probable-clause/api/`, which goodnight routes. Locally it resolves to `http://localhost:8080/api/`, which the local profile proxies. Either way it is the same origin, with no CORS.

## 5. HTTP endpoints (API root; goodnight strips `/probable-clause/api`)

All JSON is UTF-8. Errors are `{"error": "<code>", "message": "<for logs, never shown verbatim>"}`. The page writes its own words from codes (T5.4).

**The refusal messages of `POST /runs`** (v2.0, the main session's, design §5). They go in the response's `message`, for logs. The page's words come from T5.4. For a code T5.4 has no line for (`busy`, and the caps reworded now that nothing is reserved), the page uses these texts as its own words:
- `busy`: "Five questions are being researched right now, the most this site handles at once. Please try again in a minute." The number is written out in words from `MAX_CONCURRENT_RUNS` ("Five" at 5).
- `paused_day`: "Today's spending has reached the daily cap, so no new question can start until midnight, Central Time."
- `paused_month` for the monthly cap: "This month's spending has reached the monthly cap, so no new question can start until the 1st."
- `paused_month` for the spend-limit pause, and `atlas_unreachable`: as v1.9.

| Method and path | Body | Answers |
|---|---|---|
| `GET /health` | — | `200 {"app": "probable-clause", "ready": true, "live_research": "open" \| "paused_day" \| "paused_month" \| "unknown", "update_check": "available" \| "unavailable" \| "unknown", "commit": "<short sha>"}`, only once loading is complete (T3.6) |
| `POST /runs` | `{"question": "<text>"}`, at most `REQUEST_BODY_MAX_BYTES` | `201 {"run_id": "<random, unguessable>"}`; `400 question_empty` / `question_too_long`; `413 body_too_large`; `503 busy` (v2.0: `MAX_CONCURRENT_RUNS` runs in progress) / `paused_day` (the daily cap) / `paused_month` (the monthly cap, or the spend-limit pause) / `atlas_unreachable` (authoritative over `/health`, T3.4) |
| `GET /runs/{id}/events` | `Last-Event-ID` header optional | `200 text/event-stream`: each event as `id: <n>`, `event: <kind>`, `data: <JSON envelope>`; a comment line every `KEEPALIVE_S`; the stream closes after `run_ended`. `404 run_unknown` (never existed or expired: T5.4's "no longer stored") |
| `POST /runs/{id}/alive` | `{"last_event": <n>}` | `204`; `404 run_unknown` |

**Other codes (v1.2):** `400 bad_request` (a body that isn't the JSON above), `404 not_found` (no such path), `405 method_not_allowed`, `500 internal`, and `503 atlas_unreachable` when Atlas fails on an events read or a heartbeat for a run held by another instance. The page shows any code it has no words for as T5.4's general failure.

Control characters are stripped from the question, and an empty or whitespace-only question is refused before any paid call (T3.7). No cookies are set and no client IP is read (T3.5, T3.7).

### 5.1 The wake protocol (brief §8.5, T3.6), on the page

The page reads its figures from `config.json` (§11.3), generated from `api/settings.py`: `WAKE_CHECK_TIMEOUT_S`, `WAKE_CHECK_GAP_S`, `LONG_WAIT_S`, `WAKE_GIVE_UP_S`, `HEARTBEAT_INTERVAL_S`, `PAGE_WATCHDOG_S`, `QUESTION_MAX_CHARS`.

1. **One `/health` check in flight at a time.** Each waits up to `WAKE_CHECK_TIMEOUT_S`, with `WAKE_CHECK_GAP_S` between checks. Never a second check while one is open, and never parallel retries.
2. **Any answer that isn't our JSON means still starting** and leads to the next serial check: Cloud Run's plain-text 429, 500 or 503, goodnight's HTML error pages, or a network error.
3. **One check on landing,** fire and forget (brief §2). The live-research wake joins it if it is still open.
4. **A fresh `/health` right before `POST /runs`,** and `POST /runs` only after `/health` has answered our JSON. `POST /runs` is **never retried automatically** (brief §8.5 rule 2).
5. **The long wait** (T4.4, T5.4):
   - the elapsed time shows from the start;
   - at `LONG_WAIT_S` the "taking longer" step appears, with the recorded runs offered;
   - at `WAKE_GIVE_UP_S` checking stops and **Try again** appears, which starts a fresh check, never a run.
6. **A stream that can't reconnect** runs this protocol before reattaching (T3.1, T3.6).
7. **Heartbeats** every `HEARTBEAT_INTERVAL_S` while the stream is open (T3.2). The page reconnects after `PAGE_WATCHDOG_S` of silence, and keeps the run ID in sessionStorage to reattach after a reload.

## 6. Events (T3.1, T4.3, T4.5)

Every event, live or replayed, is one envelope; `contracts/events.schema.json` is the binding definition, and both the backend tests and the frontend's fixtures validate against it (P0.3).

```json
{"v": 2, "run": "<id>", "n": 7, "t_ms": 12840, "at": "2026-10-24T20:31:05.123-05:00", "kind": "tool_result", "data": { } }
```

- **`n`** counts from 1 with no gaps, `t_ms` is the time since the run started (replays play at this pace), and `at` carries its offset.
- **`v` is 2** from contract v2.0, the first version whose events carry `step`. The schema accepts only `v: 2`, and the page plays only v2. Earlier local recordings are `v: 1` and are kept for the record, never served.

**Steps (v2.0).** A run has up to three steps: `research`, then `update` and `composition` side by side (§4.G):
- Their events interleave in the one stream, in the order they happen, so **the page places events by their step, not by position**.
- `round_started`, `tool_call`, `tool_result`, `paid_call` and `api_fragment` carry `step`.
- `update_started` and `update_ended` bound the update step; `composition_started` opens the composition.
- `paid_call.step` follows its purpose (§2's `STEP_OF_PURPOSE`): `loop`, `embed` and `rerank` are research; `update` and `update_search` are the update step.
- The update step emits no `api_fragment`: its new blocks are web pages, never fragments.

**Order:**
- A passage's `passage` event comes before the first event that names it, except `tool_call`, whose input is Claude's exactly and may name an ID first (v1.3). Every passage whose text is sent to Claude gets one, **attached footnotes included**.
- A tool's `tool_call` comes before its `tool_result`.
- Each Claude call's `paid_call` comes after the response is complete. `api_fragment` events for a request come before the call's `paid_call`, and those for a response after it.
- `run_started` is first. Research's events come next, until research ends.
- **`update_band`** comes at once when the update step isn't started (before any `composition_started`); otherwise right after `update_ended`.
- `checks` comes after the composition's last `answer_block` and its response fragments.
- **`run_ended`** is last, after both branches have ended.
- **A stream may end with no `update_ended` or `update_band`** after `update_started`: H's `failed` follows a cancelled branch, and `interrupted` cuts a stream short. The page closes the update lane on `run_ended`.

| Kind | Emitted by | `data` (summary; the schema has every field) |
|---|---|---|
| `run_started` | G | question; `limits` (`rounds`, `loop_input_tokens`, `loop_output_tokens`, `update_rounds`, `update_input_tokens`, `update_output_tokens`, `update_searches`, `composition_max_tokens`, `deadline_s`); coverage dates; `update_check_available`; `models` (`loop`, `update`, `composition`); `corpus_label` |
| `round_started` | G | `step` (`research` or `update`), round number within the step, the status line sent to Claude (T1.14) |
| `tool_call` | G | `step`, `round`, `tool_use_id`, tool name, the exact input Claude sent. Only a `submit_update` with text the copy guard flags, whichever rule refuses it, has each flagged statement, a flagged overview and a flagged `update_skip_reason` replaced by "[statement withheld: it repeated a page's words]" (P4.3, P4.13) |
| `passage` | G | the passage (§6.1) |
| `tool_result` | G | `step`, `tool_use_id`, name, `is_error`, `content` (the text sent to Claude; for `search_web_updates`, `format_for_events`'s text, with page text replaced; for an accepted `submit_answer` that opens the update step, the `update_start` text Claude is sent; for any other accepted submit, its accepted text, never sent). By tool: `found` (the matched passages only, not attached footnotes) and `matched_again` (searches), `not_reranked`, `target` and `read` (reads), `kept` (each with `replaced`) and `refused` and `kept_count` (keep), `web` and `web_repeats` and `web_status` and `search_no` (update search: page details, never text), `submit` (`accepted`, and `rule` when refused). `wrong_step: true` on a call its step refuses (§4.G) |
| `paid_call` | H, from `record_usage` (called by C, D and G) | `step`, `call_no` (Claude calls only), service, purpose (`loop`, `update`, `composition`, `embed`, `rerank`, `update_search`), attempt, `max_attempts`, outcome (`ok`, `retrying`, `failed`), `error_kind`, `duration_ms`, Claude's exact `usage` object, `estimated_usage` (v1.6), cost in dollars, `estimated` |
| `api_fragment` | G | `step` (`research` or `composition`); for one passage: `call_no`, `role` (`request` or `response`), `path` (`messages[4].content[2]`), the exact JSON at that path (T4.3); never for web results |
| `paused`, `resumed` | H | `since_ms` |
| `warning` | G | `meaning_search_degraded` or `meaning_search_unavailable` (T3.3), once each, from `ctx.flags` |
| `update_started` | G | `kept`: the passage IDs kept when research ended, in keep order (v2.0) |
| `update_ended` | G | `end` (`submitted`, `stopped`, `failed` or `abandoned`), `stop_kind` (when `end` is `stopped`: an update stop kind, `console_spend_limit` or `tier_spend_cap`; else null), `failure_reason` (an `ErrorKind` when `end` is `failed`, and the error's kind for a spend stop; else null), `rounds`, `searches` (the counted update searches) (v2.0) |
| `composition_started` | G | `call_no`, the kept passage IDs in document order (T1.11) |
| `answer_block` | G | `index`, the block's text, its citations: `passage_id`, `first_sentence` and `last_sentence` (both **inclusive** indexes into the passage's `sentences`; the API's end index is exclusive, so `last_sentence = end_block_index − 1`), `cited_text`, the response's `call_no` and `path` |
| `checks` | G (F's `CheckResult`) | exactly `CheckResult`'s fields |
| `update_band` | G | `outcome`, `reason`, the searches (every wrapper field Claude could set, unset ones null; our fixed settings; `status`; counts), findings, overview, every page returned (details, never text) |
| `run_ended` | G; H for `failed` and `interrupted` | `state`, `stop_kind`, `stop_kinds`, `no_sources_reason`, `note`, `scope_note`, `answer_end`, `failure_reason`, `rounds` (research's), `answer_chars`, `totals` (§6.2) |

**`update_ended.end` with an update spend stop (v2.0):** a `spend_limit` or `spend_cap` error has `end: "stopped"`, `stop_kind` `console_spend_limit` or `tier_spend_cap`, and `failure_reason` the error's kind.

**`submit.rule`** (v2.0):
- on `submit_answer`: `same_turn`, `no_search`, `nothing_kept`, `no_note`, `note_too_long`, `wrong_step`, or null for bad input;
- on `submit_update`: `same_turn`, `findings`, `copy_guard`, `no_check`, `wrong_step`, or null for bad input.

`no_update_check` and `declined` are gone with rule 4 (P4.19).

**The band's outcome** (T2.3 item 4 amended by P4.19, worked out by code from the update step). Checked in this order, the first that applies wins:
1. **A counted search ran:**
   - **`found`:** the accepted `submit_update` has at least one finding;
   - **`nothing_relevant`:** it was accepted with its findings empty or left out;
   - **`not_summarised`:** no `submit_update` was accepted (a limit, a failure, the deadline or abandonment).
2. **`not_run`:** the update step was never started for research's reasons (out of scope, no corpus search, or research ended without an accepted submit).
3. **`unavailable`,** with no counted search:
   - first, when the update check was unavailable at the start (the step never started) or became unavailable during it: `reason` is `no_credit` or `key_refused` (P2.11). This holds even if a skip reason was given, as v1.9 checked;
   - then, when the step ended `stopped` or `failed`: `reason` is `update_ended`'s `stop_kind` when it has one, else its `failure_reason`.
4. **`skipped`:** accepted with an `update_skip_reason`; `reason` is that text.
5. **`not_run`:** otherwise, for example abandoned before any counted search.

**`run_ended` fields:**
- **`note`** is only for no-sources replies (T1.10).
- **`scope_note`** is only for a normal answer's scope note.
- **`stop_kinds`** (v1.4) lists every budget or limit stop of the run, from any step, in the order it happened, `stop_kind` among them. So a loop limit is recorded even when the composition then fails or is cut off, and the update step's stops are recorded without changing the run's state (v2.0). G emits it; H records each.
- **`stop_kind`** is the run's own stop, from research or the composition: one of `api/protocols.StopKind` for a budget or limit stop, else null:
  - `step_limit` and `token_ceiling_input` / `token_ceiling_output` with those states;
  - `composition_max_tokens` with `answer_end: cut_off`;
  - `console_spend_limit` / `tier_spend_cap` with `spend_limit`;
  - `time_limit` with `time_limit`.
  
  The update step's stop kinds are never `stop_kind`.
- **A loop limit then a composition (v1.3):** `step_limit`, `token_ceiling` and `time_limit` keep their own `stop_kind` when the composition is then cut off (`answer_end: cut_off`), and these three and `error_stopped` take `answer_end: incomplete` when the composition broke after its first block, with `failure_reason` that error's kind.
- **`answer_end: incomplete`** goes with state `answered` (research finished; the composition broke after its first block, T3.3), with `failure_reason` the error kind. `error_stopped` is only for research stopped by an error after retries, composed from what was kept (v1.1).
- **`failure_reason`** is an `api/errors.ErrorKind` or null; H's `failed` after an unexpected exception carries `internal` (v1.2).
- **`answer_chars`** is always the length of the `answer_block` text streamed, so H's `failed` and `interrupted` keep `answer_end: none` with the characters that did arrive (v1.2).
- **`paused.since_ms`** is the time since the last heartbeat, and `resumed.since_ms` the time paused (v1.1).
- **A failed attempt with no usage reported** has `usage: null` and `estimated: true` in its `paid_call`, priced from the caller's input estimate (T3.3, v1.1). Any attempt priced from an estimate, including one priced from what it streamed (P4.5, P4.10), has `usage: null` and its priced tokens in `estimated_usage` (v1.6).

### 6.1 A passage in events

`{"id", "kind", "case_key", "case_name", "citation", "decided", "slip_opinion", "opinion_id", "opinion_type", "authors", "joined_by", "joined_by_source", "section", "page_start", "page_end", "paragraph_kind", "footnote_label", "footnotes", "cited_by", "text", "sentences"}`: the `Passage` of §3, with `sentences` as `[[start, end], ...]`. The text is the citable text, with no markers.

### 6.2 Totals (T4.5)

`{"claude": {"calls", "input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens", "cost_usd": {"loop", "update", "composition"}}, "exa": {"searches", "cost_usd"}, "voyage": {"requests", "cost_usd"}, "prices": {"anthropic": {"source", "date"}, "exa": {...}, "voyage": {...}}}`.
- `calls` and `requests` count attempts, since each is billed.
- `input_tokens` is all input: uncached + cache writes + cache reads (T4.5's "186,000 input tokens, 142,000 from cache").
- `cost_usd.update` is the update step's Claude calls (v2.0); its Exa searches stay under `exa`.
- The page shows Claude and Exa only (T4.5). Voyage is carried for the record and the caps.

## 7. The tools Claude sees (names and fields; descriptions in `api/prompts/`)

All seven are sent in every research and update request (§4.G.2); each step runs only its own.

| Tool | Step | Input | Rules |
|---|---|---|---|
| `search_meaning` | research | `query`, `filters?`, `max_results?` | T1.4; §4.C |
| `search_exact` | research | `all_of?`, `any_of?`, `none_of?`, `filters?`, `max_results?` | T1.2, T1.4; at least one item in `all_of` or `any_of` |
| `read_passages` | research | `target`, `before?`, `after?` | T1.3, T1.6; one target a call; target forms in §4.B |
| `keep_passages` | research | `keep: [{id, reason}]` | T1.7; only IDs already shown; reason ≤ `KEEP_REASON_MAX_CHARS`; cap `KEEP_CAP` |
| `submit_answer` | research | `out_of_scope`, `note?` | T1.10 amended by P4.19; rule 1 (alone in its turn, once, P4.16), the input check, the note cap (`NOTE_MAX_CHARS`, P4.6), then rules 2 and 3 and `no_note` |
| `search_web_updates` | update | the fields of §4.D | T2.1; `UPDATE_SEARCHES_PER_RUN` (5) a run; counting as T2.1 |
| `submit_update` | update | `update_findings?`, `update_overview?`, `update_skip_reason?` | T2.3, P4.19; rule 1, the input check, the findings checks, the copy guard, then `no_check` |

`filters`: `{cases?, decided_from?, decided_to?, opinion_types?, authors?, none_of?, include_footnotes?}` (T1.4). `max_results`: 1 to 10, default 8, clamped. `update_findings`: `[{statement, sources}]` (T2.3).

## 8. Atlas (T3.4, T3.5, T3.7)

Database `Probable_Clause` (`PC_ENV=live`) or `Probable_Clause_test` (`PC_ENV=test`, the default, for local and test runs).

| Collection | Document | Index |
|---|---|---|
| `events` | the full envelope (`v`, `run`, `n`, `t_ms`, `at`, `kind`, `data`) plus `created` (BSON date) | unique (`run`, `n`); TTL on `created`, `EVENTS_TTL_S` |
| `runs` | the per-run record of T3.7, with no question or answer text: run ID, Chicago start date and time, end state and `stop_kind`, `stop_kinds`, research's rounds, the update step's rounds and end, searches, keeps, tokens and cost by service and by step, retries, answer length, check flags, the Voyage warning, `corpus_label` | unique `run` |
| `spend` | one per Chicago month, `_id` `"2026-10"`: `spent`, `days: {"2026-10-24": {spent, runs_started, stops: {<kind>: n}}}` (v2.0: no `reserved`, no `reservations`; older documents that have them are read without them, §4.E) | `_id` |
| `budget_stops` | one per refusal or stop: Chicago date and time, run ID or null, `kind`, the day's and month's spent at that moment, `budget: true \| false` | `at` |
| `heartbeats` | `run`, `last_event`, `at` (BSON date) | TTL on `at`, `HEARTBEATS_TTL_S` |
| `flags` | `_id: "exa_out_of_credit"` or `"anthropic_spend_limit"`, `until` (the 1st of the next Chicago month) | `_id` |

**Stop kinds** (`api/protocols.StopKind`; T3.4):
- **Budget stops:** `daily_cap`, `monthly_cap`, `step_limit`, `token_ceiling_input`, `token_ceiling_output`, `composition_max_tokens`, `console_spend_limit`, `tier_spend_cap`, `exa_no_credit`, and (v2.0) `update_step_limit`, `update_token_ceiling_input`, `update_token_ceiling_output`.
- **Limit stops:** `time_limit` (T3.5) and `update_time_limit` (v2.0).
- **Not a budget stop:** `atlas_unreachable`.
- `busy` is not a stop kind: it is a refusal of the moment, logged only (§4.H).

**Who records them:**
- `admit` records the cap refusals.
- D records `exa_no_credit`.
- H records the rest from `run_ended.stop_kinds`.

## 9. Settings

`api/settings.py` is the table: every figure, its value and its basis. "PLACEHOLDER" means until Phase 5 measures it, and "main session's" marks a figure the decisions left open, chosen here. Those gap-fills:
- `UNATTACHED_RUN_EXPIRY_S`, 120 s;
- `HEARTBEAT_POLL_S`, 2 s;
- `REQUEST_BODY_MAX_BYTES`, 16 KB;
- `ATLAS_HEALTH_TIMEOUT_S`, 2 s;
- `ATLAS_OP_TIMEOUT_S`, 5 s;
- `WORST_CASE_COMPOSITION_INPUT`, 66,000, for the documented worst case only (v2.0, §4.E).

v2.0 (P4.18, P4.21) removes `RUN_INPUT_TOKENS`, `RUN_OUTPUT_TOKENS`, `COMPOSITION_RESERVE_INPUT`, `COMPOSITION_RESERVE_OUTPUT` and `FIXED_PREFIX_TOKENS_ESTIMATE`, renames `ATLAS_RESERVE_TRIES` to `ATLAS_ADMIT_TRIES`, and adds `UPDATE_MODEL`, `UPDATE_EFFORT`, `UPDATE_MAX_ROUNDS`, `UPDATE_INPUT_BUDGET`, `UPDATE_OUTPUT_BUDGET` and `MAX_CONCURRENT_RUNS`.

The Cloud Run figures of T3.5 are there too, and are used only by `deploy/deploy.sh`.

## 10. Prices (T3.4)

In `api/state/prices.py`, one source and date per provider:
- **Claude** (Anthropic's pricing page, Oct 24, 2026, as T3.4 records them; per million tokens):

  | Model | Input | Output | 5-minute cache write | 1-hour cache write | Cache read |
  |---|---|---|---|---|---|
  | Sonnet 5.5 | $2 | $10 | $2.50 | $4 | $0.10 |
  | Opus 5.5 | $4 | $20 | $5 | $8 | $0.20 |

  From v2.0 every Claude call is Sonnet 5.5 (P4.20); Opus stays in the table for older runs' records.

  The main session re-read the pricing page before the paid build tests (Oct 25, 2026; `api/state/prices.py`) and re-reads it before Wave 3's.
- **Exa** (Phase 2 findings §4, observed): `auto` $0.007 and `lite` $0.004 a search with text. `costDollars` wins when it is reported.
- **Voyage** (Voyage AI's pricing page, https://docs.voyageai.com/docs/pricing, read Oct 24, 2026; the key is a Voyage platform key, checked by `scripts/probe_voyage.py`, so MongoDB's page does not apply): `voyage-law-2` $0.12 and `rerank-3` $0.05 per million tokens. Free tokens are not modelled; list price is the conservative figure for the caps (v1.1).

## 11. Static files

### 11.1 Reader files (T4.3)

One per opinion, `opinions/<opinion_id>.json`, generated from `data/corpus/` into the web image:

`{"opinion_id", "case": {"key", "name", "citation", "decided", "slip_opinion", "credit": "courtlistener" | "us_reports" | "slip_opinion"}, "type", "authors", "joined_by", "joined_by_source", "joined_by_note", "heading", "paragraphs": [{"id" | null for sections, "kind", "text", "page_start", "page_breaks": [{"offset", "page"}], "footnote_refs": [{"offset", "label", "footnote_id"}]}], "footnotes": [{"id", "label", "page", "page_starts", "paragraphs", "page_breaks"}]}`; a footnote's `page_starts` and `page_breaks` are per paragraph, in the order of `paragraphs` (v1.1)

The `credit` code selects T5.1's reader credit line.

### 11.2 Replay files (brief §7.4, T5.6)

`replays/<slug>.json` in the repository, written by the main session's export script in Phase 5 and copied into the web image. `replays/index.json` lists the chips in order (`slug`, `question`, `recorded_at`, `corpus_label`).

Each replay file: `{"format": 1, "slug", "question", "recorded_at" (Chicago ISO), "commit", "models": {"loop", "update", "composition"}, "prices": {...as §6.2}, "corpus_label": "full" | "before_chatrie", "events": [<envelopes as §6>]}`. Each replay is a real run's events, never edited (T5.6). It holds no web page text (§1).

### 11.3 `corpus.json` and `config.json`

Both are written by `scripts/build_web_data.py`.
- **`corpus.json`:** what the landing page and credits need before any run (T5.1, T5.2): `cases`, `earliest_decided`, the three coverage dates, and the case counts by text source.
- **`config.json`:** the page's figures from `api/settings.py` (§5.1).

## 12. Fakes, fixtures and test seams

**Fakes:** every outside service has a protocol and a fake, owned by the part that owns the real client:
- `FakeVoyageClient` (C);
- `FakeExaTransport` (D);
- `MemoryStore` (E);
- `FakeAnthropic` (G). From v2.0 it keeps **one script per step**: `push(*items, step="research" | "update" | "composition")`, and `stream(..., step=...)` takes the next item from that step's script. So a test, and the fixtures, script research, the update step and the composition apart, and the two branches' order never decides which turn a call gets. Its `requests` record each request with its step. It yields to the event loop (`await asyncio.sleep(0)`) before each block it delivers, so the two branches really interleave in tests and fixtures.

**Fixtures for the frontend session's mock** (P0.3), the main session's, in the replay format of §11.2:
- **`tests/fixtures/events/`** holds one stream for each of:
  - an answered run with an update step that searched and found something (the two branches interleaved);
  - an answered run whose update step skipped the check;
  - each no-sources reply (the update step not run);
  - a step-limit stop;
  - a pause and resume;
  - an abandoned run;
  - an interrupted run;
  - a refused `submit_answer` and a refused `submit_update` (the copy guard's withholding included), and a wrong-step refusal;
  - check flags;
  - each band outcome, the update step's limit stops and failure included;
  - nothing found with the update step running and no composition;
  - the Voyage warning;
  - a reconnect partway (the events after a `Last-Event-ID`);
  - a replay.
- **`tests/fixtures/http/`** holds:
  - `/health` answers: ready, `paused_day`, `paused_month`, `unknown`;
  - Cloud Run's plain-text 429, 500 and 503, and goodnight's HTML 502;
  - the `POST /runs` refusals: `busy`, the daily cap, the monthly cap and `atlas_unreachable`;
  - a 404 for an expired run.

**Contract test:** `tests/contract/test_events_schema.py` validates every fixture and every event the backend tests emit.

## 13. Ownership

| Part | Builder (Wave 3) | Writes only |
|---|---|---|
| A | — (unchanged) | `api/corpus/sentences.py`, `scripts/check_sentences.py`, `tests/corpus/test_sentences.py` |
| B | — (unchanged) | `api/corpus/` except `sentences.py`, `scripts/build_web_data.py`, `tests/corpus/` except `test_sentences.py` |
| C | — (unchanged) | `api/search/`, `scripts/embed_corpus.py`, `tests/search/` |
| D | — (unchanged; 5 searches come from settings) | `api/web_updates/`, `tests/web_updates/` |
| E | Sonnet 5.5, high | `api/state/`, `scripts/spend_report.py`, `tests/state/` |
| F | — (unchanged; the update step calls it) | `api/checks/`, `tests/checks/` |
| G | Opus 5.5, xhigh | `api/loop/`, `tests/loop/` |
| H | Sonnet 5.5, high | `api/server/`, `api/main.py`, `tests/server/` |
| I | the main session (one line) | `deploy/`, `tests/deploy/` |
| Main session | — | this file, `api/__init__.py`, `api/types.py`, `api/settings.py`, `api/errors.py`, `api/retry.py`, `api/protocols.py`, `api/prompts/`, `contracts/`, `tests/contract/`, `tests/fixtures/`, `replays/`, `scripts/run_client.py`, `scripts/render_run.py`, `data/vectors/` (by running C's script), `pyproject.toml`, `uv.lock`, every shared document |
| Frontend session | its own model | `web/` (fonts under `web/fonts/`), `webdev/`, `docs/sessions/frontend-log.md` |

**Wave 3** (`docs/sessions/wave3-plan.md`):
- **3a:** E and G run in parallel, each depending only on this contract and the main session's shared files. G's tests use their own `RunContext` fake, and `MemoryStore` only for the flags D reads, which v2.0 doesn't change.
- **3b:** H starts after E is merged, since its tests run on E's new `MemoryStore`.
- The main session merges each part after its review and runs the whole suite at the end. **Between step 0 and the end of the wave the whole suite is expected to fail** where the parts still use what v2.0 removed (the reservation, the removed settings, rule 4); each part's own tests pass when it is merged.

## 14. Open items (none open)

1. ~~A refused submit's `tool_call` and page text~~: ruled as P4.3 (flagged statements withheld in the stored and streamed event), Oct 24, 2026, 20:52 CDT.
2. ~~T3.6's unit count~~: recorded as P4.2 (2,462 passages), Oct 24, 2026, 20:50 CDT.
