# Interfaces contract

**Version 1.8** (Oct 25, 2026). 1.8, for P4.16: `submit_answer` must be the only call in its turn, and sent once; otherwise every submit in the turn is refused under rule `same_turn` and the turn's other tools run as usual, in Claude's order (§4.G). 1.7, for P4.11 and P4.13: the daily cap at $15, and the copy guard on `update_skip_reason` on every submit once a page was returned, withheld when flagged, with `submit.copy_guard_skip_reason` (§4.E, §4.F, §4.G, §6). 1.6, after the fixtures were regenerated from the real code: `paid_call.estimated_usage`, the tokens an estimated Claude attempt was priced at, so H's `interrupted` totals add up when an attempt broke after streaming (P4.5, P4.10; §4.H, §6). Then, after the final review of the night: more negation words for the ellipsis rule and no quotation starting right after a negating prefix's hyphen (§4.F); the copy guard folding compatibility forms and dropping invisible format characters (§4.F); and the spend-limit pause also when a spend stop is in `stop_kinds` (§4.H). 1.5, for P4.6 to P4.10: the composition's reserve at 66,000 and the run's input limit at 436,000, so the worst case is $2.106; the note capped at `NOTE_MAX_CHARS` (`note_too_long`); rule 4 waived for an out-of-scope submit; the copy guard on a no-sources reply's note once a page was returned; every copy-guard check ignoring words that are also the corpus's; a broken composition attempt counted as streamed (§4.E, §4.F, §4.G, §6, §7). 1.4, after the cross-part Opus review: `run_ended.stop_kinds`, `RunContext.call_not_billed` for Exa's 402 and 401, Voyage's per-run bound enforced, and an ellipsis never dropping a negation (§4.C, §4.D, §4.F, §4.H, §6). 1.3, after part G's review: the order of a turn's tools, the withholding on any refused submit, the `no_note` rule, the end pairings of a composition after a loop limit, the response path of a citation, and a citation whose text disagrees with ours (§4.G, §6). 1.2, after part H's review in Wave 2: the `internal` error kind, `interrupted`'s number when the page is ahead of Atlas, the extra HTTP error codes, `answer_chars` on H's endings, and the shutdown grace (§4.H, §5, §6). Version 1 was revised after the Opus xhigh review (P4.1) before any builder started; 1.1 adds `loop_messages.json` to §4.G's prompt files, has `scripts/embed_corpus.py` read passages through B's `Corpus` (§4.C), and settles the embedded header's section wording and the appendix labels (§3, §4.C, after the main session's review of the labels), all during Wave 1. Written by the main session for Phase 4. One writer, the main session; a change bumps the version and is announced to every builder and to the frontend session (P0.3). Where this contract and `docs/design/locked-decisions.md` differ, the decisions win and this file is fixed.

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

`api/types.py`: `Passage`, `Filters`, `Hit`, `Usage`, `WebPage`, `RunFlags`, `KeptPassage`, the `RunContext` protocol and `RunStopped`. `api/errors.py`: `ToolInputError` (bad input from Claude; its `message` is written to Claude and becomes an error tool result, T3.7) and `ServiceError(service, kind, status, message, retry_after_s)`, where `kind` is one of the closed `ErrorKind` values. **Every client classifies its failures into `ErrorKind`**; `api/retry.py` decides from it what is retried. Mapping for Anthropic: 429 → `rate_limited`, except the usage tier's spend-cap 429 → `spend_cap`; 400 → `bad_request`, except the Console spend limit → `spend_limit`; 500 → `server_error`; 504 → `gateway_timeout`; 529 → `overloaded`; our deadline → `deadline`; the `refusal` stop reason → `refusal`. How the two special cases are told apart is read from Anthropic's error docs by the builder of G and cited in a comment.

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

`search` calls `ctx.before_paid_call("exa", "update_search")` and `ctx.record_usage(...)` itself (once: no retries). It checks the out-of-credit flag (`store.flag_until("exa_out_of_credit")`) and `ctx.flags.exa_unavailable` before opening a session; on the first 402 it sets the flag (until the 1st of the next Chicago month), records the stop `exa_no_credit`, and sets `ctx.flags.exa_unavailable = "no_credit"`; a 401 sets `ctx.flags.exa_unavailable = "key_refused"` for this run only (T2.4). After either, `search` calls `ctx.call_not_billed("exa", "update_search")`, since the gate was passed and nothing was billed (v1.4). Four failure kinds, the 30 s timeout covering the handshake, list price for a failed search: T2.4, T2.5. A published date that is not a parseable `YYYY-MM-DD` date part becomes `None` (counted as undated); a result whose URL is not `http` or `https` is dropped. Any copy of the closing data marker inside page text is escaped (T2.2). **Recording (T2.4, v1.1):** `record_usage` is called once for each search that reached Exa and counts: completed, `Usage(service="exa", model=type, exa_cost_usd=<costDollars>)`, or with `exa_cost_usd=None, estimated=True` when Exa reported no cost (priced at list price); refused by Exa, `exa_cost_usd=0.0`, outcome `failed`; failed, `Usage(..., estimated=True)` (list price). An unavailable search (402, 401) is not counted and calls no `record_usage`. `price` treats `exa_cost_usd=0.0` as a reported zero (test with `is not None`). G calls `schema_check()` on the instance's first update search (T2.5).

### E. Money and state: `api/state/store.py`, `api/state/budget.py`, `api/state/prices.py`, `api/state/clock.py`, `scripts/spend_report.py`, `tests/state/`

```python
class MongoStore(Store): ...              # api/protocols.Store; pymongo AsyncMongoClient; ATLAS_OP_TIMEOUT_S
class MemoryStore(Store): ...             # the fake every other part tests against; same semantics

def worst_case_usd() -> float             # the formula below; about $2.11 (T3.4, P4.6)
def price(u: Usage) -> float              # list price (T3.4); a failed attempt with no usage as T3.3
def list_price_exa(type: str) -> float
PRICE_TABLE: dict                         # §10, one source and date per provider

def chicago_now() -> datetime; def chicago_day(dt) -> str; def chicago_month(dt) -> str; def next_month_start(dt) -> datetime
```

**The worst case** (T3.4), with Sonnet prices for the loop and Opus prices for composition:
- **Loop input:** `FIXED_PREFIX_TOKENS_ESTIMATE` at the 1-hour cache-write price, plus the rest of `LOOP_INPUT_BUDGET` at the 5-minute write price.
- **Loop output:** `LOOP_OUTPUT_BUDGET` at the output price.
- **Composition:** `COMPOSITION_RESERVE_INPUT` uncached input plus `COMPOSITION_MAX_TOKENS` output.
- **Two failed composition attempts:** another 2 × `COMPOSITION_RESERVE_INPUT` of input.
- **Exa:** `UPDATE_SEARCHES_PER_RUN` × the `auto` price.
- **Voyage:** `VOYAGE_RUN_BOUND_USD`.

Total: 0.943 + 0.08 + 0.504 + 0.528 + 0.021 + 0.03 = **$2.106** (P4.6, v1.5; it was $1.674 with a 30,000 reserve). A test asserts it, and `tests/contract/test_composition_worst_case.py` recomputes the composition's worst-case input with G's own request builder and estimator (the `KEEP_CAP` largest documents with full keep reasons, a question of `QUESTION_MAX_CHARS` and a note of `NOTE_MAX_CHARS`) and asserts it fits in `COMPOSITION_RESERVE_INPUT`. At this figure seven reservations fit in the $15 day at once (P4.11; four would at $10).

**`reserve`** is one conditional update of the month's document (T3.4, B1). It succeeds only if, for the Chicago day and for the month, spent + reserved + worst case stays within `DAILY_CAP_USD` and `MONTHLY_CAP_USD`. Otherwise:
- It returns `Refusal("daily_cap")` or `Refusal("monthly_cap")` and records that stop itself.
- While the `anthropic_spend_limit` flag is set, it returns `Refusal("spend_limit_paused")`.
- If Atlas can't be reached, it returns `Refusal("atlas_unreachable")` and records it, marked not a budget stop, where it can.

**`settle`, `release` and attribution:**
- `settle` moves a call's cost from reserved to spent.
- `release` frees the rest when the run ends.
- A reservation that is never settled stays counted.
- Spend counts toward the Chicago day and month the run started in.

**`live_status`** (for `/health`) reports:
- `paused_month` while the spend-limit flag is set, or when the month's spent + reserved + worst case would exceed the monthly cap;
- otherwise `paused_day` when the day's would exceed the daily cap;
- otherwise `open`;
- `unknown` past `ATLAS_HEALTH_TIMEOUT_S`.

It also reports whether the update check is available: not while the Exa flag is set.

**Scripts:** `scripts/spend_report.py --day YYYY-MM-DD | --month YYYY-MM | --open-reservations` is read-only. The last option is for the deploy check (T3.5).

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

**The corpus exemption (P4.9, v1.5):** a run of `n_words` words that a text shares with a page is not counted when it also appears, in F's normalisation, inside one passage of the corpus. So a statement, overview or note quoting the Court that a page also quotes passes, while a run that carries on into the page's own words is still caught (its runs past the quotation are not the corpus's). The exemption is one normalised string, about 2 MB for the corpus. The note's problem names "The note" and the page IDs and never quotes either.

**Quotation and name rules settled in review (v1.1):** a quotation is a double-quoted span (a multi-paragraph quotation by the legal convention included) or a Markdown blockquote; a bracketed alteration stands for at most `QUOTATION_BRACKET_MAX_SOURCE_WORDS` source words and never adds or removes a negation; an ellipsis matches the smallest gap in the source, and a gap holding a negation word fails the match (v1.4; the words include "nowhere", "nobody", "hardly", "scarcely", "barely" and "absent", v1.6); no quotation or piece of one starts right after a negating prefix and its hyphen, so "intrusive" is never quoted out of "non-intrusive", and a bracket may not strip or add a hyphenated prefix either (v1.6); a full name's right party must equal the manifest's; a full name immediately followed by a U.S. Reports citation of a different corpus case flags the citation. A quotation that cannot be decided in bounded time is flagged, never passed. Offsets are Python code points; the page converts them for JavaScript strings. Each returned string is a problem written to Claude. It names the statement by its number and the page by its ID, and **never quotes the page's words** (the message is stored in events). The checks run on the text exactly as streamed.

### G. The research loop and composition: `api/loop/`, `tests/loop/`; prompt text in `api/prompts/` (the main session's)

```python
@dataclass
class LoopDeps:
    corpus: Corpus; keyword: KeywordIndex; meaning: MeaningIndex; voyage: VoyageClient
    updates: UpdateSearch; anthropic: "AnthropicStreamer"

class AnthropicStreamer(Protocol):        # the one place the SDK is called (streamed, max_retries=0, T3.3)
    async def stream(self, request: dict, deadline_s: float, on_block: Callable | None) -> "StreamResult": ...
        # raises ServiceError with an ErrorKind (§2)
class FakeAnthropic(AnthropicStreamer): ...   # scripted turns: tool calls, text blocks with citations, errors

async def execute_run(ctx: RunContext, deps: LoopDeps) -> None
    # emits run_started ... run_ended; returns normally for every expected end, RunStopped included
```

**What G owns:**
- **Tools:** the six tool definitions and their validation (T1.2 to T1.10, T2.1, T2.3, T3.7). Strict mode only where T3.7 allows it, with the count of strict tools recorded.
- **What Claude sees:** result formatting (T1.6, T2.2), the per-turn status line (T1.14), and the "matched again" top-up (T1.6).
- **Keeping and submitting:** the keep rules (T1.7), and the rejection rules in order: rule 1, then the findings checks, then the note cap, then the copy guard, then rules 2 to 4 (T1.10, T2.3). v1.5:
  - **The note cap (P4.6):** a `note` longer than `NOTE_MAX_CHARS` is refused with `rejections.json`'s `submit.note_too_long`, rule `note_too_long`.
  - **Rule 4 (P4.7):** waived when `out_of_scope` is true; such a submit is accepted with no reminder, and with no search run the band's outcome is `not_run`.
  - **The note's copy guard (P4.8):** on a no-sources submit (`out_of_scope` true, or nothing kept) when any update search in the run has returned a page, the note goes to `copy_guard_report(..., note=...)`. A hit refuses with rule `copy_guard`: with `submit.copy_guard_note` (`<pages>` filled by `pages_named`) when only the note is flagged, else with `submit.copy_guard` and all the problems. The stored and streamed `tool_call` has the note replaced by P4.3's text. The scope note of an answered run and keep reasons are not guarded.
  - **The skip reason's copy guard (P4.13, v1.7):** once any update search in the run has returned a page, `update_skip_reason` goes to `copy_guard_report(..., skip_reason=...)` on every submit. A hit refuses with rule `copy_guard`: with `submit.copy_guard_skip_reason` (`<pages>` from `pages_named`) when only the skip reason is flagged, `submit.copy_guard_note` when only the note is, else `submit.copy_guard` with all the problems. The stored and streamed `tool_call` has it replaced by P4.3's text.
  - **The corpus exemption (P4.9):** every copy-guard call passes `exempt=corpus_words(...)`, built once per `Corpus` (a weak-keyed cache, like `chars_per_token`).
- **Budget and caching:** the token budget and its estimate before each loop call (T3.3), and caching (T1.14: a one-hour breakpoint on tools, system prompt and catalog).
- **Claude calls:** every one runs through `with_retries(ANTHROPIC_POLICY, ...)`, with each attempt recorded by `ctx.record_usage` (with `raw_usage` and `call_no`).
- **A turn's tools** run in Claude's order. `submit_answer` must be the turn's only call, and sent once: a turn holding two or more submits, or a submit with any other call (`keep_passages` included), has every submit refused under rule 1 (`same_turn`), and its other calls run as usual (P4.16, v1.8; replaces v1.3's "a keep in the same turn counts").
- **Composition** (T1.8, T1.9, T1.11): its input is estimated before the call; past `COMPOSITION_RESERVE_INPUT` is logged as an error, since P4.6's settings make it unreachable for plain text. An attempt broken before its first block is priced and counted from what it streamed and reported, never at `max_tokens`, so a retry still runs (P4.10, as P4.5 does for the loop). Custom content documents of our sentences, metadata and keep reason in `context`. Each citation's block range maps back to a passage ID and an inclusive sentence range. A citation whose `cited_text` disagrees with our slice of those sentences (spacing aside) is not attached, and is logged and counted as a mapping fault, so the page never lights sentences Claude did not cite (v1.3).
- **Ends:** the fallbacks and stop states (T1.11, T3.3, T3.5). On `RunStopped("deadline")` G composes from what was kept and ends `time_limit`. On `RunStopped("abandoned")` it composes nothing and ends `abandoned`. On a `spend_limit` or `spend_cap` error it ends `spend_limit` with that `stop_kind`.
- **After the answer:** running F's checks, working out the band's outcome (§6, T2.3 item 4), and every event of §6 except `paused` and `resumed`, plus `run_ended` in H's two cases.

Prompts and tool descriptions are read from `api/prompts/`: `loop_system.md`, `composition_system.md`, `tools.json` (the descriptions), `rejections.json` and `loop_messages.json` (the first user message, the update-unavailable line and the status line). `{{NAME}}` in upper case is filled from `api/settings.py`, lower-case `{{...}}` from the corpus (catalog, case count, coverage dates), and `<...>` per call; `tests/contract/test_prompts.py` checks the names. They are placeholders until the main session's drafts land, and the user reviews them before the first paid run (T1.14).

### H. The API and the run lifecycle: `api/server/`, `api/main.py`, `tests/server/`

```python
def create_app(deps_factory: Callable[[], Awaitable["AppDeps"]]) -> FastAPI
class Run(RunContext): ...                # state, event buffer, Atlas copy queue, heartbeat, deadline, reservation, totals
class RunRegistry: ...                    # runs on this instance; one stream per run
```

**Start-up and endpoints:**
- The endpoints are §5.
- Everything loads before the port opens, each step timed and logged with the time since the process started (T3.6).
- `PC_ENV` (`live` or `test`, default `test`) chooses the database. `PC_CORPUS=before_chatrie` is refused when `PC_ENV=live` (T5.6). `PC_COMMIT` is the short commit SHA, set when the image is built.

**Money:**
- The reservation is made at `POST /runs` and released at the end (T3.4).
- `record_usage` is the one place spend is priced, settled and totalled, and the one emitter of `paid_call`.

**The run task:**
- It starts when the first stream attaches, and attaching counts as a heartbeat.
- A run no stream ever attaches to expires after `UNATTACHED_RUN_EXPIRY_S` with no spend, and its reservation is released (T3.1).

**Events and streams:**
- H keeps the event buffer and the numbering, and copies events to Atlas in order without holding up the stream: the full envelope plus `created` (§8).
- A reconnect replays from memory, or from Atlas when it reaches another instance (T3.1). It honours `Last-Event-ID`.
- One stream per run. A keep-alive comment every `KEEPALIVE_S`, and the `X-Accel-Buffering: no` header.

**`before_paid_call`**, in order:
1. If the run is abandoned, raise `RunStopped("abandoned")`.
2. If the purpose is not `composition` and the run is past its deadline, raise `RunStopped("deadline")`. Composition always proceeds, so T3.5's time limit still composes.
3. If the run is unattended (no heartbeat for `ATTENDED_WINDOW_S`), emit `paused` and wait. Heartbeats come from this instance or, polled every `HEARTBEAT_POLL_S`, from Atlas. On one, emit `resumed`. If none comes, the run is abandoned at `ABANDON_AFTER_S` after the last heartbeat (T3.2).

The caps need no check here, because the run's reservation already bounds what it can spend (T3.4).

**At the end:**
- H writes the per-run record (T3.7).
- It records each budget or limit stop in `run_ended.stop_kinds`, once each (§8; T3.4, v1.4).
- On `spend_limit`, or any run whose `stop_kinds` holds `console_spend_limit` or `tier_spend_cap` (a composition that met the limit after its first block ends `answered`, v1.6), it sets the `anthropic_spend_limit` flag until the 1st of the next Chicago month, which pauses live research (T3.3, T5.4).

**The two `run_ended` events H emits:**
- **`failed`,** when `execute_run` raises an unexpected exception.
- **`interrupted`,** on an instance that doesn't hold the run. It is sent on the stream only, never stored. Its `n` is one more than the larger of the last stored event and the page's `Last-Event-ID`, so the page always receives it (v1.2). Stored events are replayed only while their numbers run on without a gap. Its totals are summed from the stored `paid_call` events, an estimated attempt's tokens from its `estimated_usage` (v1.6).

**Shutdown (v1.2):** uvicorn runs with `--timeout-graceful-shutdown` of `SHUTDOWN_GRACE_S`, so after Cloud Run's SIGTERM the open streams close and the lifespan shutdown cancels the running runs and releases their reservations (a reservation with a paid call in flight stays counted) before the SIGKILL 10 s later.

**Protections:** the body-size caps and the question cap (T3.7).

### I. Images and the deploy script: `deploy/`, `tests/deploy/`

**Files:**
- **`deploy/api.Dockerfile`:** Python 3.13 with uv; the committed corpus and vectors; FTS5 checked at build; `PC_COMMIT` baked in.
- **`deploy/web.Dockerfile`:** nginx at an exact pinned version. It serves `web/` as is, plus `scripts/build_web_data.py`'s output, the replays from `replays/`, and the `.woff2` fonts with the OFL text that the frontend session places under `web/fonts/` (T4.2, T5.5). Every response carries `Cache-Control: no-cache`.
- **`deploy/nginx.conf`:** written from scratch, with no goodnight code (T3.5).
- **`deploy/deploy.sh`:**
  - deploys both services, every setting explicit from `api/settings.py`'s Cloud Run block, with `--scaling=auto`, Secret Manager references and one service account per service (T3.5);
  - first runs `scripts/spend_report.py --open-reservations` and stops if any reservation is open (T3.5);
  - **is written, never run**, except by the main session on the user's green light.
- **`deploy/local.sh`:** builds both images and runs them for the user's local review (P4.1):
  - the API on port 8000 with `PC_ENV=test`;
  - the web service on port 8080, whose local nginx profile proxies `/api/` to the API.

**How the page reaches the API:** the page always calls `api/...` relative to its own URL. In production that resolves to `/probable-clause/api/`, which goodnight routes. Locally it resolves to `http://localhost:8080/api/`, which the local profile proxies. Either way it is the same origin, with no CORS.

## 5. HTTP endpoints (API root; goodnight strips `/probable-clause/api`)

All JSON is UTF-8. Errors are `{"error": "<code>", "message": "<for logs, never shown verbatim>"}`. The page writes its own words from codes (T5.4).

| Method and path | Body | Answers |
|---|---|---|
| `GET /health` | — | `200 {"app": "probable-clause", "ready": true, "live_research": "open" \| "paused_day" \| "paused_month" \| "unknown", "update_check": "available" \| "unavailable" \| "unknown", "commit": "<short sha>"}`, only once loading is complete (T3.6) |
| `POST /runs` | `{"question": "<text>"}`, at most `REQUEST_BODY_MAX_BYTES` | `201 {"run_id": "<random, unguessable>"}`; `400 question_empty` / `question_too_long`; `413 body_too_large`; `503 paused_day` / `paused_month` / `atlas_unreachable` (authoritative over `/health`, T3.4; the spend-limit pause answers `paused_month`) |
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
{"v": 1, "run": "<id>", "n": 7, "t_ms": 12840, "at": "2026-10-24T20:31:05.123-05:00", "kind": "tool_result", "data": { } }
```

`n` counts from 1 with no gaps; `t_ms` is since the run started (replays play at this pace); `at` carries its offset.

**Order:** a passage's `passage` event comes before the first event that names it, except `tool_call`, whose input is Claude's exactly and may name an ID first (v1.3). Every passage whose text is sent to Claude gets one, **attached footnotes included**. A tool's `tool_call` comes before its `tool_result`. Each Claude call's `paid_call` comes after the response is complete. `api_fragment` events for a request come before the call's `paid_call`, and those for a response after it.

| Kind | Emitted by | `data` (summary; the schema has every field) |
|---|---|---|
| `run_started` | G | question, limits, coverage dates, `update_check_available`, models, `corpus_label` |
| `round_started` | G | round number, the status line sent to Claude (T1.14) |
| `tool_call` | G | `round`, `tool_use_id`, tool name, the exact input Claude sent, except that a submit with statements the copy guard flags, whichever rule refuses it (v1.3), has each flagged statement replaced by "[statement withheld: it repeated a page's words]" (P4.3); a flagged overview, a flagged note (P4.8, v1.5) and a flagged `update_skip_reason` (P4.13, v1.7) are replaced by the same text |
| `passage` | G | the passage (§6.1) |
| `tool_result` | G | `tool_use_id`, name, `is_error`, `content` (the text sent to Claude; for `search_web_updates`, `format_for_events`'s text, with page text replaced); by tool: `found` (the matched passages only, not attached footnotes) and `matched_again` (searches), `not_reranked`, `target` and `read` (reads), `kept` (each with `replaced`) and `refused` and `kept_count` (keep), `web` and `web_repeats` and `web_status` and `search_no` (update search: page details, never text), `submit` (`accepted`, and `rule` when refused: `same_turn`, `findings`, `copy_guard`, `no_search`, `nothing_kept`, `no_update_check`, `no_note` for `out_of_scope` without a note, or null for bad input, v1.3; `note_too_long`, v1.5) |
| `paid_call` | H, from `record_usage` (called by C, D and G) | `call_no` (Claude calls only), service, purpose, attempt, `max_attempts`, outcome (`ok`, `retrying`, `failed`), `error_kind`, `duration_ms`, Claude's exact `usage` object, `estimated_usage` (v1.6: for a Claude attempt priced from an estimate, the tokens it was priced at, `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`; ours, never Claude's, so `usage` stays null; null otherwise), cost in dollars, `estimated` |
| `api_fragment` | G | for one passage: `call_no`, `role` (`request` or `response`), `path` (`messages[4].content[2]`), the exact JSON at that path (T4.3); never for web results |
| `paused`, `resumed` | H | `since_ms` |
| `warning` | G | `meaning_search_degraded` or `meaning_search_unavailable` (T3.3), once each, from `ctx.flags` |
| `composition_started` | G | `call_no`, the kept passage IDs in document order (T1.11) |
| `answer_block` | G | `index`, the block's text, its citations: `passage_id`, `first_sentence` and `last_sentence` (both **inclusive** indexes into the passage's `sentences`; the API's end index is exclusive, so `last_sentence = end_block_index − 1`), `cited_text`, the response's `call_no` and `path` |
| `checks` | G (F's `CheckResult`) | exactly `CheckResult`'s fields |
| `update_band` | G | `outcome`, `reason`, the searches (every wrapper field Claude could set, unset ones null; our fixed settings; `status`; counts), findings, overview, every page returned (details, never text) |
| `run_ended` | G; H for `failed` and `interrupted` | `state`, `stop_kind`, `no_sources_reason`, `note`, `scope_note`, `answer_end`, `failure_reason`, `rounds`, `answer_chars`, `totals` (§6.2) |

**The band's outcome** (T2.3 item 4, worked out by code):
- **`found`:** at least one finding.
- **`nothing_relevant`:** an update search ran and the findings are empty, or were left out.
- **`skipped`:** `update_skip_reason` was given; `reason` is that text.
- **`declined`:** accepted after rule 4's reminder with no reason. `reason` is null, and the page shows no reason line.
- **`unavailable`:** no search could run; `reason` is `no_credit` or `key_refused`.
- **`not_summarised`:** searches ran, but the run stopped before a submit.
- **`not_run`:** no search and no submit, for example abandoned early; or an out-of-scope reply with no search, since rule 4 is waived there (P4.7, v1.5).

**`run_ended` fields:**
- **`note`** is only for no-sources replies (T1.10).
- **`scope_note`** is only for a normal answer's scope note.
- **`stop_kinds`** (v1.4) lists every budget or limit stop of the run in order, `stop_kind` among them, so a loop limit is recorded even when the composition then fails or is cut off (G emits it; H records each).
- **`stop_kind`** is one of `api/protocols.StopKind` for a budget or limit stop, else null:
  - `step_limit` and `token_ceiling_input` / `token_ceiling_output` with those states;
  - `composition_max_tokens` with `answer_end: cut_off`;
  - `console_spend_limit` / `tier_spend_cap` with `spend_limit`;
  - `time_limit` with `time_limit`.
- **A loop limit then a composition (v1.3):** `step_limit`, `token_ceiling` and `time_limit` keep their own `stop_kind` when the composition is then cut off (`answer_end: cut_off`), and these three and `error_stopped` take `answer_end: incomplete` when the composition broke after its first block, with `failure_reason` that error's kind.
- **`answer_end: incomplete`** goes with state `answered` (the loop finished; the composition broke after its first block, T3.3), with `failure_reason` the error kind; `error_stopped` is only for a loop stopped by an error after retries, composed from what was kept (v1.1).
- **`failure_reason`** is an `api/errors.ErrorKind` or null; H's `failed` after an unexpected exception carries `internal` (v1.2). **`answer_chars`** is always the length of the `answer_block` text streamed, so H's `failed` and `interrupted` keep `answer_end: none` with the characters that did arrive (v1.2); `paused.since_ms` is the time since the last heartbeat and `resumed.since_ms` the time paused (v1.1).
- **A failed attempt with no usage reported** has `usage: null` and `estimated: true` in its `paid_call`, priced from the caller's input estimate (T3.3, v1.1). Any attempt priced from an estimate, including one priced from what it streamed (P4.5, P4.10), has `usage: null` and its priced tokens in `estimated_usage` (v1.6).

### 6.1 A passage in events

`{"id", "kind", "case_key", "case_name", "citation", "decided", "slip_opinion", "opinion_id", "opinion_type", "authors", "joined_by", "joined_by_source", "section", "page_start", "page_end", "paragraph_kind", "footnote_label", "footnotes", "cited_by", "text", "sentences"}`: the `Passage` of §3, with `sentences` as `[[start, end], ...]`. The text is the citable text, with no markers.

### 6.2 Totals (T4.5)

`{"claude": {"calls", "input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens", "cost_usd": {"loop", "composition"}}, "exa": {"searches", "cost_usd"}, "voyage": {"requests", "cost_usd"}, "prices": {"anthropic": {"source", "date"}, "exa": {...}, "voyage": {...}}}`.
- `calls` and `requests` count attempts, since each is billed.
- `input_tokens` is all input: uncached + cache writes + cache reads (T4.5's "186,000 input tokens, 142,000 from cache").
- The page shows Claude and Exa only (T4.5). Voyage is carried for the record and the caps.

## 7. The tools Claude sees (names and fields; descriptions in `api/prompts/`)

| Tool | Input | Rules |
|---|---|---|
| `search_meaning` | `query`, `filters?`, `max_results?` | T1.4; §4.C |
| `search_exact` | `all_of?`, `any_of?`, `none_of?`, `filters?`, `max_results?` | T1.2, T1.4; at least one item in `all_of` or `any_of` |
| `read_passages` | `target`, `before?`, `after?` | T1.3, T1.6; one target a call; target forms in §4.B |
| `keep_passages` | `keep: [{id, reason}]` | T1.7; only IDs already shown; reason ≤ `KEEP_REASON_MAX_CHARS`; cap `KEEP_CAP` |
| `search_web_updates` | the fields of §4.D | T2.1; 3 a run; counting as T2.1 |
| `submit_answer` | `out_of_scope`, `note?`, `update_skip_reason?`, `update_findings?`, `update_overview?` | T1.10, T2.3; rule 1 (alone in its turn, once, P4.16), then the findings checks, the note cap (`NOTE_MAX_CHARS`, P4.6) and the copy guard, then rules 2 to 4 (rule 4 waived when out of scope, P4.7) |

`filters`: `{cases?, decided_from?, decided_to?, opinion_types?, authors?, none_of?, include_footnotes?}` (T1.4). `max_results`: 1 to 10, default 8, clamped.

## 8. Atlas (T3.4, T3.5, T3.7)

Database `Probable_Clause` (`PC_ENV=live`) or `Probable_Clause_test` (`PC_ENV=test`, the default, for local and test runs).

| Collection | Document | Index |
|---|---|---|
| `events` | the full envelope (`v`, `run`, `n`, `t_ms`, `at`, `kind`, `data`) plus `created` (BSON date) | unique (`run`, `n`); TTL on `created`, `EVENTS_TTL_S` |
| `runs` | the per-run record of T3.7, with no question or answer text: run ID, Chicago start date and time, end state and `stop_kind`, rounds, searches, keeps, tokens and cost by service, retries, answer length, check flags, the Voyage warning, `corpus_label` | unique `run` |
| `spend` | one per Chicago month, `_id` `"2026-10"`: `spent`, `reserved`, `days: {"2026-10-24": {spent, reserved, runs_started, stops: {<kind>: n}}}`, `reservations: {<run>: {day, amount}}` | `_id` |
| `budget_stops` | one per refusal or stop: Chicago date and time, run ID or null, `kind`, spent and reserved at that moment, `budget: true \| false` | `at` |
| `heartbeats` | `run`, `last_event`, `at` (BSON date) | TTL on `at`, `HEARTBEATS_TTL_S` |
| `flags` | `_id: "exa_out_of_credit"` or `"anthropic_spend_limit"`, `until` (the 1st of the next Chicago month) | `_id` |

**Stop kinds** (`api/protocols.StopKind`; T3.4):
- **Budget stops:** `daily_cap`, `monthly_cap`, `step_limit`, `token_ceiling_input`, `token_ceiling_output`, `composition_max_tokens`, `console_spend_limit`, `tier_spend_cap`, `exa_no_credit`.
- **Limit stop:** `time_limit` (T3.5).
- **Not a budget stop:** `atlas_unreachable`.

**Who records them:**
- `reserve` records the cap refusals.
- D records `exa_no_credit`.
- H records the rest from `run_ended.stop_kind`.

## 9. Settings

`api/settings.py` is the table: every figure, its value and its basis. "PLACEHOLDER" means until Phase 5 measures it, and "main session's" marks a figure the decisions left open, chosen here. Those gap-fills:
- `UNATTACHED_RUN_EXPIRY_S`, 120 s;
- `HEARTBEAT_POLL_S`, 2 s;
- `REQUEST_BODY_MAX_BYTES`, 16 KB;
- `ATLAS_HEALTH_TIMEOUT_S`, 2 s;
- `ATLAS_OP_TIMEOUT_S`, 5 s.

The Cloud Run figures of T3.5 are there too, and are used only by `deploy/deploy.sh`.

## 10. Prices (T3.4)

In `api/state/prices.py`, one source and date per provider:
- **Claude** (Anthropic's pricing page, Oct 24, 2026, as T3.4 records them; per million tokens):

  | Model | Input | Output | 5-minute cache write | 1-hour cache write | Cache read |
  |---|---|---|---|---|---|
  | Sonnet 5.5 | $2 | $10 | $2.50 | $4 | $0.10 |
  | Opus 5.5 | $4 | $20 | $5 | $8 | $0.20 |

  The main session re-reads the pricing page before the first paid build test and records the date.
- **Exa** (Phase 2 findings §4, observed): `auto` $0.007 and `lite` $0.004 a search with text. `costDollars` wins when it is reported.
- **Voyage** (Voyage AI's pricing page, https://docs.voyageai.com/docs/pricing, read Oct 24, 2026; the key is a Voyage platform key, checked by `scripts/probe_voyage.py`, so MongoDB's page does not apply): `voyage-law-2` $0.12 and `rerank-3` $0.05 per million tokens. Free tokens are not modelled; list price is the conservative figure for the caps (v1.1).

## 11. Static files

### 11.1 Reader files (T4.3)

One per opinion, `opinions/<opinion_id>.json`, generated from `data/corpus/` into the web image:

`{"opinion_id", "case": {"key", "name", "citation", "decided", "slip_opinion", "credit": "courtlistener" | "us_reports" | "slip_opinion"}, "type", "authors", "joined_by", "joined_by_source", "joined_by_note", "heading", "paragraphs": [{"id" | null for sections, "kind", "text", "page_start", "page_breaks": [{"offset", "page"}], "footnote_refs": [{"offset", "label", "footnote_id"}]}], "footnotes": [{"id", "label", "page", "page_starts", "paragraphs", "page_breaks"}]}`; a footnote's `page_starts` and `page_breaks` are per paragraph, in the order of `paragraphs` (v1.1)

The `credit` code selects T5.1's reader credit line.

### 11.2 Replay files (brief §7.4, T5.6)

`replays/<slug>.json` in the repository, written by the main session's export script in Phase 5 and copied into the web image. `replays/index.json` lists the chips in order (`slug`, `question`, `recorded_at`, `corpus_label`).

Each replay file: `{"format": 1, "slug", "question", "recorded_at" (Chicago ISO), "commit", "models": {"loop", "composition"}, "prices": {...as §6.2}, "corpus_label": "full" | "before_chatrie", "events": [<envelopes as §6>]}`. Each replay is a real run's events, never edited (T5.6). It holds no web page text (§1).

### 11.3 `corpus.json` and `config.json`

Both are written by `scripts/build_web_data.py`.
- **`corpus.json`:** what the landing page and credits need before any run (T5.1, T5.2): `cases`, `earliest_decided`, the three coverage dates, and the case counts by text source.
- **`config.json`:** the page's figures from `api/settings.py` (§5.1).

## 12. Fakes, fixtures and test seams

**Fakes:** every outside service has a protocol and a fake, owned by the part that owns the real client:
- `FakeVoyageClient` (C);
- `FakeExaTransport` (D);
- `MemoryStore` (E);
- `FakeAnthropic` (G).

**Fixtures for the frontend session's mock** (P0.3), the main session's, in the replay format of §11.2:
- **`tests/fixtures/events/`** holds one stream for each of:
  - an answered run;
  - each no-sources reply;
  - a step-limit stop;
  - a pause and resume;
  - an abandoned run;
  - an interrupted run;
  - a refused submit;
  - check flags;
  - each band outcome;
  - the Voyage warning;
  - a reconnect partway (the events after a `Last-Event-ID`);
  - a replay.
- **`tests/fixtures/http/`** holds:
  - `/health` answers: ready, `paused_day`, `paused_month`, `unknown`;
  - Cloud Run's plain-text 429, 500 and 503, and goodnight's HTML 502;
  - the `POST /runs` refusals, the daily cap included;
  - a 404 for an expired run.

**Contract test:** `tests/contract/test_events_schema.py` validates every fixture and every event the backend tests emit.

## 13. Ownership

| Part | Builder | Writes only |
|---|---|---|
| A | Opus 5.5, xhigh | `api/corpus/sentences.py`, `scripts/check_sentences.py`, `tests/corpus/test_sentences.py` |
| B | Sonnet 5.5, high | `api/corpus/` except `sentences.py`, `scripts/build_web_data.py`, `tests/corpus/` except `test_sentences.py` |
| C | Sonnet 5.5, high | `api/search/`, `scripts/embed_corpus.py`, `tests/search/` |
| D | Sonnet 5.5, xhigh | `api/web_updates/`, `tests/web_updates/` |
| E | Sonnet 5.5, xhigh | `api/state/`, `scripts/spend_report.py`, `tests/state/` |
| F | Sonnet 5.5, xhigh | `api/checks/`, `tests/checks/` |
| G | Opus 5.5, xhigh | `api/loop/`, `tests/loop/` |
| H | Opus 5.5, high | `api/server/`, `api/main.py`, `tests/server/` |
| I | Sonnet 5.5, high | `deploy/`, `tests/deploy/` |
| Main session | — | this file, `api/__init__.py`, `api/types.py`, `api/settings.py`, `api/errors.py`, `api/retry.py`, `api/protocols.py`, `api/prompts/`, `contracts/`, `tests/contract/`, `tests/fixtures/`, `replays/`, `data/vectors/` (by running C's script), `pyproject.toml`, `uv.lock`, every shared document |
| Frontend session | its own model | `web/` (fonts under `web/fonts/`), `docs/sessions/frontend-log.md` |

**Wave 1 (A to F)** runs in parallel. Each part depends only on the main session's shared files, plus:
- **B** calls `split_sentences`. Until A lands, B's tests use a trivial splitter behind the same signature.
- **D** codes against `api/protocols.Store`, with a minimal fake of its own until `MemoryStore` lands.

The main session merges Wave 1 and runs the whole suite. **Wave 2 (G, H, I)** starts after that.

## 14. Open items (none open)

1. ~~A refused submit's `tool_call` and page text~~: ruled as P4.3 (flagged statements withheld in the stored and streamed event), Oct 24, 2026, 20:52 CDT.
2. ~~T3.6's unit count~~: recorded as P4.2 (2,462 passages), Oct 24, 2026, 20:50 CDT.
