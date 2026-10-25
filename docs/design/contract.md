# Interfaces contract

**Version 1** (Oct 24, 2026). Written by the main session for Phase 4 (P4.1). One writer, the main session; a change bumps the version and is announced to every builder and to the frontend session (P0.3). Where this contract and `docs/design/locked-decisions.md` differ, the decisions win and this file is fixed.

Machine-checkable parts: `contracts/events.schema.json` (every event), `api/types.py` (shared types), `api/settings.py` (every figure and its basis). Builders import those three and never redefine what they hold.

---

## 1. Conventions for every builder

- **Python 3.13, async throughout** (`async def` for anything that waits on the network or Atlas). FastAPI and uvicorn for the server; `httpx2` for plain HTTP (Voyage); the `anthropic` SDK for Claude; the `mcp` package for Exa; `pymongo`'s `AsyncMongoClient` for Atlas; `numpy` for vectors. No other dependency without asking the main session (only it touches `pyproject.toml`).
- **Tests first**, with pytest, under `tests/<area>/`. No test makes a network call: every outside service has a fake (§12). No builder holds a key or makes a paid call.
- **Figures** come from `api/settings.py` only. A timeout, retry count or wait names its basis there (brief §10.7). A figure not in `settings.py` is asked for, not invented.
- **SDK clients** are created with their own retries off (`max_retries=0`); retries are ours (§4.E, T3.3). A paid call is retried only where T3.3 says.
- **Dates shown to a person are America/Chicago**, computed with `zoneinfo` (brief §10.7). Stored timestamps are ISO 8601 with their offset. The only exception is Exa's published dates, kept as written (T2.2).
- **Logs** hold run IDs, states, timings, costs and error kinds, never the question, Claude's queries, the answer or page text (T3.7).
- **Text is data.** Passage and web text are never instructions (T1.14); nothing from a visitor, Claude, the corpus or the web is ever inserted as HTML (T3.7).
- **No absolute local paths** in committed files; paths are built from the repository root.
- **Ownership:** each builder writes only its own paths (§13). Builders never commit; the main session commits after review.

## 2. Shared types

`api/types.py` holds: `Passage`, `Filters`, `Hit`, `Usage`, `WebPage`, `KeptPassage`, `RunTotals`, the `RunContext` protocol and `RunStopped`. Their fields and meanings are as documented there; §3 says how a `Passage` is derived.

Two errors every tool part uses, defined in `api/errors.py` (main session):

```python
class ToolInputError(Exception):   # bad input from Claude: becomes an error tool_result, shown as a step (T3.7)
    message: str                    # written to Claude: says what was wrong and how to fix it
class ServiceError(Exception):     # an outside service failed after our handling
    service: Service; kind: str; status: int | None; message: str
```

## 3. The corpus as passages (T1.6, T1.9)

Source: `data/corpus/cases/<key>.json` and `data/corpus/manifest.json`, committed and frozen (changed only through `scripts/corrections.json`).

- **Opinion IDs** are the manifest's (`katz-3`), counted from 1 within a case in the manifest's order.
- **Paragraph passages:** every paragraph whose `kind` is not `section` (kinds `text`, `quote`, `appendix`), numbered from 1 within its opinion: `katz-3-p1`. Section paragraphs are never passages and are never returned by search (T1.6).
- **Footnote passages:** each footnote of an opinion is **one** passage, numbered from 1 in the opinion's `footnotes` order (by order, never by label: labels repeat, as in *Boyd*): `katz-3-n1`. Its text is its paragraphs joined with `"\n\n"`; a paragraph join is always a sentence boundary. *(Claude's call: one passage per footnote, not per footnote paragraph.)*
- **Counts, by script** (Oct 24, 2026, after T1.5): 1,964 paragraph passages and 498 footnote passages, **2,462 passages**. Phase 3's "2,748 units" counted the 286 section headings as well; T3.6's 11.3 MB vectors figure becomes about 10.1 MB (2,462 × 1,024 × 4 bytes).
- **Text** is the corpus text exactly. Nothing is added to it. The loop's view adds footnote markers (`[n. 3]`) at each reference, after the referencing character (`footnote_refs[].offset`), resolved to footnote IDs in reading order; the composition call and the page get the text without markers (T1.6).
- **Section label:** the stack of numbered headings in force at the passage (Roman numerals, capital letters, arabic numerals, as printed: "II", "III-A"), or an appendix title; omission rows and letterhead lines that the corpus types as sections are not labels (T1.6). `None` before the first heading.
- **Pages:** `page_start` from the paragraph (or footnote's `page`); `page_end` from the last page break inside it.
- **Opinion groups** (T1.4): majority → majority; plurality → plurality; any type containing "concurring" or "concurrence" → concurrence; any containing "dissent" → dissent; a type with both maps to both.
- **Sentences:** `api/corpus/sentences.split_sentences(text)` (§4.A) at load; offsets stored on the `Passage`.
- **The corpus catalog** for the system prompt (T1.6): each case's key, name, citation and decision date; each opinion's ID, exact type, author, joiners, paragraph and footnote counts with their ID ranges, page range; one line saying the filter groups types and results show the exact type.
- **Coverage** (brief §2): the three dates from the manifest. With the recording-only switch (T5.6, `exclude=("chatrie",)`), the case leaves the passages, both indexes, the catalog and the coverage: the latest decision in the corpus and in the full pull become *Carpenter*'s, 2018-06-22; the ingestion date stays.

## 4. The parts, their paths and interfaces

Each part lists its paths, its public interface and its tests. A builder may add private helpers in its own paths. Signatures are binding; internals are the builder's.

### A. The sentence splitter (T1.9): `api/corpus/sentences.py`, `scripts/check_sentences.py`, `tests/corpus/test_sentences.py`

```python
def split_sentences(text: str) -> list[tuple[int, int]]:
    """[start, end) spans that tile `text` exactly (no gap, no overlap, in order).
    Whitespace after a sentence belongs to that sentence. "\n\n" always ends one."""
LEGAL_ABBREVIATIONS: frozenset[str]   # e.g. "U. S.", "How.", "Cal.", "Pen.", "Stat.", "supra", "e. g."
```

The rule (T1.9): split only where a sentence plainly ends: `.`, `?` or `!` (or one followed by a closing quotation mark or bracket) then whitespace then a capital letter or an opening quotation mark or bracket, **and** the token before the stop is a lowercase word that is not an abbreviation, a number, a closing bracket or quotation mark, or a capitalised word of five or more letters not on the abbreviation list. In doubt, do not split. Ellipsis rows (`. . .`) never end a sentence on their own.

`scripts/check_sentences.py` runs the splitter over every passage, asserts the tiling for all 2,462, and writes `data/verification/sentences/report.json` (local) listing suspicious splits (a split before a capital that follows a short capitalised word, an initial, a section sign, "v.", "No.", a reporter abbreviation or a number) for the main session's sampled review (T1.9; no subagent). Tests use the ten hardest passages chosen by `scripts/probe_chunking.py` and the citation forms it found broken.

### B. The corpus index: `api/corpus/store.py`, `api/corpus/filters.py`, `api/corpus/keyword.py`, `api/corpus/reader_files.py`, `scripts/build_reader_files.py`, `tests/corpus/`

```python
class Corpus:
    @classmethod
    def load(cls, root: Path, exclude: tuple[str, ...] = ()) -> "Corpus": ...
    passages: dict[str, Passage]          # insertion order = reading order (case, opinion, paragraphs then footnotes)
    coverage: dict                        # {"latest_decision_full_pull", "latest_decision_in_corpus", "ingested"}
    catalog_text: str
    case_keys: frozenset[str]
    def loop_text(self, passage_id: str) -> str          # text with "[n. <label>]" markers (§3)
    def read(self, target: str, before: int, after: int) -> list[Passage]
        # target: a passage ID, or "<case_key>:<U.S. Reports page>" (every passage on that page, in reading order,
        # across opinions). before/after 0..READ_AROUND_MAX within the target's opinion and kind.
        # Raises ToolInputError naming the valid range for an unknown ID or page (T1.6).

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

`parse_filters` treats an empty list, or a filter set to every value, as unset (T1.4); a year is the whole year. `KeywordIndex.search` raises `ToolInputError` when both `all_of` and `any_of` are empty or a list exceeds `KEYWORD_ITEMS_PER_LIST`. A quoted item is a phrase; word forms match (porter).

`scripts/build_reader_files.py --out <dir>` writes the reader files (§11.1) for every opinion, used when the web image is built (T4.3). `--exclude chatrie` is not offered: the reader serves the full corpus.

### C. Meaning search: `api/search/voyage.py`, `api/search/meaning.py`, `scripts/embed_corpus.py`, `data/vectors/` (written only by the main session running the script), `tests/search/`

```python
class VoyageClient(Protocol):
    async def embed(self, texts: list[str], input_type: Literal["query", "document"]) -> tuple[list[list[float]], Usage]: ...
    async def rerank(self, query: str, documents: list[str], top_k: int) -> tuple[list[tuple[int, float]], Usage]: ...

class HttpVoyageClient(VoyageClient):     # https://api.voyageai.com/v1, bearer VOYAGE_API_KEY, VOYAGE_TIMEOUT_S, no retries
    ...
class FakeVoyageClient(VoyageClient): ... # deterministic vectors from a hash; scripted failures

def embedded_text(p: Passage) -> str:
    """One header line, then the text (T3.6): '<case name> (<year>), <exact type>, <authors or per curiam>[, Part <section>]'."""

class MeaningIndex:
    @classmethod
    def load(cls, vectors_dir: Path, corpus: Corpus) -> "MeaningIndex": ...
        # reads voyage-law-2.f32 and manifest.json; raises if the model, dimension, count or any
        # passage's embedded-text hash disagrees with the corpus (T3.6). Rows of an excluded case are dropped.
    async def search(self, query: str, f: Filters, limit: int, ctx: RunContext,
                     voyage: VoyageClient) -> "MeaningResult": ...

@dataclass
class MeaningResult:
    hits: list[Hit]                      # best first, at most SEMANTIC_CANDIDATES before the caller's top-up
    status: Literal["ok", "not_reranked", "unavailable"]
    message_for_claude: str | None       # "not reranked" note, or the error saying keyword search still works
```

Search order (T1.4, T3.3): apply `matches` and `excluded_by_none_of`; embed the query (`input_type="query"`); brute-force dot product over unit-normalised rows; take `SEMANTIC_CANDIDATES`; rerank with `rerank-3` over their embedded texts; return the reranked order. Each Voyage request goes through `ctx.before_paid_call("voyage", ...)`, the retry policy of T3.3 (`api/state/retry.py`, §4.E) and `ctx.record_usage`. Rerank failing after retries → embedding order, `not_reranked`. Embed failing after retries → `unavailable`, no hits. A 401 → `unavailable` for the rest of the run (logged as configuration fault).

`scripts/embed_corpus.py` embeds every passage's `embedded_text` with `input_type="document"`, in batches paced under Voyage's Tier 1 limits (read from Voyage's docs; the figures go in the script's docstring with their source), caching each batch under `data/cache/voyage/` (gitignored) so a rerun never pays twice. It prints the token count and the cost at list price and **spends only with `--confirm`**. Output: `data/vectors/voyage-law-2.f32` (row-major float32, rows in `Corpus.passages` order) and `data/vectors/manifest.json` (`model`, `dimension`, `count`, `created` as a Chicago date, `units`: `[{id, sha256}]` of each embedded text).

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
def to_exa_arguments(p: WebSearchParams) -> dict  # snake_case to Exa's tool argument names, plus our fixed
                                                  # settings: text cut at EXA_TEXT_CHARS, no highlights, no summaries

class ExaTransport(Protocol):
    async def call(self, arguments: dict, timeout_s: float) -> dict: ...     # Exa's parsed JSON; raises ServiceError
    async def list_tool_schema(self) -> dict: ...                           # free; for the schema check (T2.5)
class McpExaTransport(ExaTransport): ...  # one MCP session per call (T2.5), EXA_MCP_URL, key only in x-api-key
class FakeExaTransport(ExaTransport): ... # scripted results and every failure kind

@dataclass
class WebSearchOutcome:
    kind: Literal["ok", "refused_by_exa", "failed", "unavailable"]
    unavailable_reason: Literal["no_credit", "key_refused"] | None
    pages: list[WebPage]                  # all returned, in Exa's order; repeats carry their first ID
    repeats: list[str]                    # IDs of pages an earlier search returned
    undated: int
    exa_message: str | None               # Exa's own message, for refused_by_exa
    usage: Usage | None                   # costDollars, or list price for failed (T2.4)

class UpdateSearch:
    def __init__(self, transport: ExaTransport, store: "Store"): ...
    async def search(self, p: WebSearchParams, search_no: int, seen_urls: dict[str, str],
                     ctx: RunContext) -> WebSearchOutcome: ...
    async def schema_check(self) -> list[str]: ...    # warnings; never blocks (T2.5)

def format_for_claude(p: WebSearchParams, o: WebSearchOutcome) -> str      # T2.2: opening line, headers, data markers
```

The four failure kinds, the 402 flag (checked before a session opens, set on the first 402, until the 1st of the next Chicago month), the 401 run-only unavailability, the 30 s timeout covering the handshake, and no retries by our code: T2.4 and T2.5. Text inside the data markers has any copy of the closing marker escaped (T2.2). Page text is returned in `WebPage.text` for Claude and the copy guard only; it never reaches an event (T2.2).

### E. Money and state: `api/state/store.py`, `api/state/budget.py`, `api/state/prices.py`, `api/state/retry.py`, `api/state/clock.py`, `scripts/spend_report.py`, `tests/state/`

```python
class Store(Protocol):                    # every Atlas read and write the app makes (§8)
    async def ensure_indexes(self) -> None: ...
    async def append_events(self, run_id: str, events: list[dict]) -> None: ...
    async def read_events(self, run_id: str, after: int) -> list[dict]: ...
    async def put_heartbeat(self, run_id: str, last_event: int) -> None: ...
    async def latest_heartbeat(self, run_id: str) -> datetime | None: ...
    async def upsert_run_record(self, record: dict) -> None: ...
    async def reserve(self, run_id: str, worst_case_usd: float, now: datetime) -> "Reservation | Refusal": ...
    async def settle(self, r: "Reservation", cost_usd: float) -> None: ...
    async def release(self, r: "Reservation") -> None: ...
    async def record_stop(self, kind: str, run_id: str | None, now: datetime, detail: dict) -> None: ...
    async def count_run_started(self, now: datetime) -> None: ...
    async def exa_flag(self, now: datetime) -> bool: ...          # True while out of credit (T2.4)
    async def set_exa_flag(self, now: datetime) -> None: ...
    async def live_status(self, now: datetime, timeout_s: float) -> dict: ...  # for /health (T3.4)
class MongoStore(Store): ...              # pymongo AsyncMongoClient; database ATLAS_DB_LIVE or ATLAS_DB_TEST
class MemoryStore(Store): ...             # the fake every other part tests against

def worst_case_usd() -> float             # from the per-run ceilings and the price table (T3.4); about $1.67
def price(u: Usage) -> float              # list price (T3.4); a failed attempt as T3.3
PRICE_TABLE: dict                         # §10, with source and date

async def with_retries(attempt: Callable[[int], Awaitable[T]], policy: RetryPolicy,
                       before_attempt: Callable[[int], Awaitable[None]],
                       on_retry: Callable[[int, ServiceError, float], Awaitable[None]]) -> T
ANTHROPIC_POLICY: RetryPolicy             # T3.3: which errors, how many, which waits; retry-after honoured
VOYAGE_POLICY: RetryPolicy

def chicago_now() -> datetime; def chicago_day(dt) -> str; def chicago_month(dt) -> str   # "2026-10-24", "2026-10"
```

`reserve` is **one conditional update** of the month's document (T3.4, B1): it succeeds only if, for the Chicago day and for the month, spent + reserved + `worst_case_usd` stays within `DAILY_CAP_USD` and `MONTHLY_CAP_USD`; else it returns `Refusal(kind="daily_cap" | "monthly_cap")` and records the stop. Atlas unreachable → `Refusal(kind="atlas_unreachable")`, recorded as not a budget stop where it can be. `settle` moves a call's cost from reserved to spent; `release` frees the rest at run end; spend counts toward the day and month the run started in. Every budget-stop kind of T3.4 has a `record_stop` kind (§8). `scripts/spend_report.py --day YYYY-MM-DD | --month YYYY-MM` is read-only.

### F. The answer checks: `api/checks/quotations.py`, `api/checks/citations.py`, `api/checks/update_findings.py`, `api/checks/summary.py`, `tests/checks/`

```python
@dataclass
class Flag:
    block: int; start: int; end: int      # position in the answer blocks
    kind: Literal["quotation_not_found", "not_in_corpus"]
    text: str

@dataclass
class CheckResult:
    quotations_checked: int; quotations_found: int
    citations_checked: int; citations_found: int
    not_in_corpus: list[str]              # the names or citations, as written
    flags: list[Flag]

def check_answer(blocks: list[str], kept_texts: list[str], manifest: dict) -> CheckResult
    # quotations of QUOTATION_MIN_WORDS or more words must appear in the kept passages, allowing the quoting
    # conventions of T1.12; every full "X v. Y" name and every U.S. Reports citation ("389 U. S. 347") must
    # resolve to the manifest, else "not in this corpus" (P1.10). Short names are not checked.
def check_line(r: CheckResult) -> dict    # the parts of T5.2's line as numbers and names; the page writes the words

def check_update_findings(findings: list[dict], overview: str | None, returned_ids: set[str],
                          searches_run: int) -> list[str]
    # T2.3 item 2: unknown source ID, a statement with no source, findings with no search run; caps of T2.3
def copy_guard(texts: list[str], page_texts: list[str], n_words: int) -> list[str]
    # T2.3 item 3: n or more consecutive words of any returned page, ignoring case, punctuation and spacing
```

Each returned string is a problem written to Claude, naming the statement and what to fix. The checks run on the text exactly as streamed.

### G. The research loop and composition: `api/loop/`, `api/prompts/` (text by the main session), `tests/loop/`

```python
@dataclass
class LoopDeps:
    corpus: Corpus; keyword: KeywordIndex; meaning: MeaningIndex; voyage: VoyageClient
    updates: UpdateSearch; anthropic: "AnthropicStreamer"; manifest: dict

class AnthropicStreamer(Protocol):        # the one place the SDK is called (streamed, max_retries=0, T3.3)
    async def stream(self, request: dict, deadline_s: float, on_block: Callable | None) -> "StreamResult": ...
class FakeAnthropic(AnthropicStreamer): ...   # scripted turns: tool calls, text blocks with citations, errors

async def execute_run(ctx: RunContext, deps: LoopDeps) -> None
    # emits run_started ... run_ended; never raises for an expected stop; RunStopped ends the run with its state
```

G owns: the six tool definitions and their validation (T1.2 to T1.10, T2.1, T2.3, T3.7; strict mode only where T3.7 allows, counted); result formatting for Claude (T1.6, T2.2) and the per-turn status line (T1.14); the "matched again" top-up (T1.6); the keep rules (T1.7); the rejection rules in order (T1.10, T2.3); the token budget and its estimate before each loop call (T3.3); caching (T1.14: one-hour breakpoint on tools, system prompt and catalog); composition (T1.8, T1.9, T1.11) with custom content documents of our sentences and `context`; mapping each citation's block range back to the passage ID and sentence range; the fallbacks and stop states (T1.11, T3.3, T3.5); running F's checks; working out the band's outcome (T2.3 item 4); and every event of §6 except those H emits. Prompts and tool descriptions are read from `api/prompts/` (`loop_system.md`, `composition_system.md`, `tools.json` descriptions, `rejections.json`); placeholders until the main session's drafts land, and the user reviews them before the first paid run (T1.14).

### H. The API and the run lifecycle: `api/server/`, `api/main.py`, `tests/server/`

```python
def create_app(deps_factory: Callable[[], Awaitable["AppDeps"]]) -> FastAPI
class Run(RunContext): ...                # state, event buffer, Atlas copy queue, heartbeat, deadline, reservation
class RunRegistry: ...                    # runs on this instance; one stream per run
```

H owns the endpoints (§5); start-up loading before the port opens, each step timed and logged with the time since process start (T3.6); the reservation at `POST /runs` and its release at the end (T3.4); the run task starting when the first stream attaches, and expiry of a run never attached (T3.1); the event buffer, numbering, the copy to Atlas in order without blocking the stream, replay from memory or from Atlas on reconnect (T3.1); `Last-Event-ID`; one stream per run; the keep-alive comment (`KEEPALIVE_S`); `X-Accel-Buffering: no`; heartbeats, attended, pause and resume events, abandonment at `ABANDON_AFTER_S` (T3.2); the other-instance heartbeat through Atlas and the `interrupted` end (T3.1, T3.2); the run deadline (T3.5); body size caps and the question cap (T3.7); the per-run record (T3.7). `before_paid_call` checks, in order: abandoned → `RunStopped("abandoned")`; past the deadline → `RunStopped("deadline")`; unattended → emit `paused`, wait for a heartbeat (emit `resumed`) or abandonment.

### I. Images and the deploy script: `deploy/`, `tests/deploy/`

`deploy/api.Dockerfile` (Python 3.13, uv, the committed corpus and vectors, FTS5 checked at build), `deploy/web.Dockerfile` (nginx at an exact pinned version, `web/` as served, the reader files from `scripts/build_reader_files.py`, the replays, the `.woff2` fonts with the OFL text; `Cache-Control: no-cache` on every response; T4.2, T5.5), `deploy/nginx.conf` (written from scratch, no goodnight code, T3.5), `deploy/deploy.sh` (both services, every setting explicit, `--scaling=auto`, Secret Manager references, one service account per service, T3.5; **written, never run** by anyone but the main session on the user's green light), and `deploy/local.sh`, which builds both images and runs them locally on ports 8000 and 8080 against `Probable_Clause_test` for the user's review (P4.1).

## 5. HTTP endpoints (API root; goodnight strips `/probable-clause/api`)

All JSON is UTF-8. Errors are `{"error": "<code>", "message": "<for logs, never shown verbatim>"}`. The page writes its own words from codes (T5.4).

| Method and path | Body | Answers |
|---|---|---|
| `GET /health` | — | `200 {"app": "probable-clause", "ready": true, "live_research": "open" \| "paused_day" \| "paused_month" \| "unknown", "update_check": "available" \| "unavailable" \| "unknown", "commit": "<short sha>"}` only when loading is complete (T3.6); Atlas read with `ATLAS_HEALTH_TIMEOUT_S`, else `"unknown"` |
| `POST /runs` | `{"question": "<text>"}`, at most `REQUEST_BODY_MAX_BYTES` | `201 {"run_id": "<random, unguessable>"}`; `400 question_empty` / `question_too_long`; `413 body_too_large`; `503 paused_day` / `paused_month` / `atlas_unreachable` (authoritative over `/health`, T3.4) |
| `GET /runs/{id}/events` | `Last-Event-ID` header optional | `200 text/event-stream`: each event as `id: <n>`, `event: <kind>`, `data: <JSON envelope>`; a comment line every `KEEPALIVE_S`; the stream closes after `run_ended`. `404 run_unknown` (never existed or expired, T5.4 "no longer stored") |
| `POST /runs/{id}/alive` | `{"last_event": <n>}` | `204`; `404 run_unknown` |

Control characters are stripped from the question and an empty or whitespace-only question is refused before any paid call (T3.7). No cookies are set; no client IP is read (T3.5, T3.7).

## 6. Events (T3.1, T4.3, T4.5)

Every event, live or replayed, is one envelope; `contracts/events.schema.json` is the binding definition and both the backend tests and the frontend's fixtures validate against it (P0.3).

```json
{"v": 1, "run": "<id>", "n": 7, "t_ms": 12840, "at": "2026-10-24T20:31:05.123-05:00", "kind": "tool_result", "data": { } }
```

`n` counts from 1 with no gaps; `t_ms` is since the run started (replays play at this pace); `at` carries its offset.

| Kind | Emitted by | `data` (summary; the schema has every field) |
|---|---|---|
| `run_started` | G | question, limits, coverage dates, `update_check_available`, models, `corpus_label` (`full` or `before_chatrie`) |
| `round_started` | G | round number, the status line sent to Claude (T1.14) |
| `tool_call` | G | `tool_use_id`, tool name, the exact input Claude sent |
| `passage` | G | the first time a passage appears in a run: the passage (§6.1) |
| `tool_result` | G | `tool_use_id`, name, `is_error`, the exact text sent to Claude, and by tool: `found` / `matched_again` IDs (searches), `read` IDs, `kept` / `replaced` / `refused` (keep), `web` (each page's ID, title, URL, domain, published, author: never text), `submit` (`accepted`, `rule` when refused) |
| `paid_call` | G (Claude), C, D via `record_usage` | `call_no` (Claude calls only), service, purpose (`loop`, `composition`, `embed`, `rerank`, `update_search`), attempt, outcome (`ok`, `retrying`, `failed`), `error_kind`, duration, the exact `usage` object for Claude, cost in dollars |
| `api_fragment` | G | for one passage: `call_no`, `role` (`request` or `response`), `path` (`messages[4].content[2]`), the exact JSON at that path (T4.3) |
| `paused`, `resumed` | H | `since_ms` |
| `warning` | G | `meaning_search_degraded` or `meaning_search_unavailable` (T3.3) |
| `composition_started` | G | the kept passage IDs in document order (T1.11) |
| `answer_block` | G | `index`, the block's text, its citations (`passage_id`, first and last sentence index, `cited_text`, the response `call_no` and `path`) |
| `checks` | G (via F) | `CheckResult` as numbers, names and flags |
| `update_band` | G | `outcome` (`found`, `nothing_relevant`, `skipped`, `declined`, `unavailable`, `not_summarised`, `not_run`), `reason`, the searches (every field Claude set, our fixed settings, `status`), findings (statement, source IDs), overview, every page returned (ID, title, URL, domain, published) |
| `run_ended` | G, or H for `abandoned`, `interrupted`, `failed` | `state` (`answered`, `no_sources`, `step_limit`, `token_ceiling`, `time_limit`, `error_stopped`, `abandoned`, `interrupted`, `failed`, `refusal`, `spend_limit`), `no_sources_reason` (`out_of_scope`, `nothing_found`), `note` (Claude's note to the visitor, T1.10), `scope_note`, `answer_end` (`complete`, `cut_off`, `incomplete`, `none`), `failure_reason`, totals (§6.2), `rounds`, `answer_chars` |

### 6.1 A passage in events

`{"id", "kind", "case_key", "case_name", "citation", "decided", "opinion_id", "opinion_type", "authors", "joined_by", "section", "page_start", "page_end", "paragraph_kind", "footnote_label", "footnotes", "cited_by", "text", "sentences"}`: the `Passage` of §3, with `sentences` as `[[start, end], ...]`. Text is the citable text, no markers.

### 6.2 Totals (T4.5)

`{"claude": {"calls", "input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens", "cost_usd": {"loop", "composition"}}, "exa": {"searches", "cost_usd"}, "voyage": {"requests", "cost_usd"}, "prices": {"source", "date"}}`. The page shows Claude and Exa only (T4.5); Voyage is carried for the record and the caps.

## 7. The tools Claude sees (names and fields; descriptions in `api/prompts/`)

| Tool | Input | Rules |
|---|---|---|
| `search_meaning` | `query`, `filters?`, `max_results?` | T1.4; §4.C |
| `search_exact` | `all_of?`, `any_of?`, `none_of?`, `filters?`, `max_results?` | T1.2, T1.4; at least one item in `all_of` or `any_of` |
| `read_passages` | `target`, `before?`, `after?` | T1.3, T1.6; one target a call |
| `keep_passages` | `keep: [{id, reason}]` | T1.7; only IDs already shown; reason ≤ `KEEP_REASON_MAX_CHARS`; cap `KEEP_CAP` |
| `search_web_updates` | the fields of §4.D | T2.1; 3 a run; counting as T2.1 |
| `submit_answer` | `out_of_scope`, `note?`, `update_skip_reason?`, `update_findings?`, `update_overview?` | T1.10, T2.3; rule 1, then the findings checks and copy guard, then rules 2 to 4 |

`filters`: `{cases?, decided_from?, decided_to?, opinion_types?, authors?, none_of?, include_footnotes?}` (T1.4). `max_results`: 1 to 10, default 8, clamped.

## 8. Atlas (T3.4, T3.5, T3.7)

Database `Probable_Clause` (live) or `Probable_Clause_test` (local and test runs, chosen by `PC_ENV=live|test`; default `test`).

| Collection | Document | Index |
|---|---|---|
| `events` | one per event: `run`, `n`, `kind`, `data`, `at`, `created` | unique (`run`, `n`); TTL on `created`, `EVENTS_TTL_S` |
| `runs` | per-run record of T3.7 (no question or answer text): run ID, Chicago start date and time, end state, rounds, searches, keeps, tokens and cost by service, retries, answer length, check flags, the Voyage warning | unique `run` |
| `spend` | one per Chicago month, `_id` `"2026-10"`: `spent`, `reserved`, `days: {"2026-10-24": {spent, reserved, runs_started, stops: {<kind>: n}}}`, `reservations: {<run>: {day, amount}}` | `_id` |
| `budget_stops` | one per refusal or stop: Chicago date and time, run ID or null, `kind`, spent and reserved then, `budget: true\|false` | `at` |
| `heartbeats` | `run`, `last_event`, `at` | TTL on `at`, `HEARTBEATS_TTL_S` |
| `flags` | `_id: "exa_out_of_credit"`, `until` (the 1st of the next Chicago month) | `_id` |

Budget-stop kinds (T3.4): `daily_cap`, `monthly_cap`, `step_limit`, `token_ceiling_input`, `token_ceiling_output`, `composition_max_tokens`, `console_spend_limit`, `tier_spend_cap`, `exa_no_credit`; and `atlas_unreachable` with `budget: false`. Also recorded as a limit stop: `time_limit` (T3.5).

## 9. Settings

`api/settings.py` is the table: every figure, its value and its basis ("PLACEHOLDER" until Phase 5 measures it). Two figures there are the main session's placeholders for gaps the decisions left: `UNATTACHED_RUN_EXPIRY_S` (120 s, T3.1's expiry) and `REQUEST_BODY_MAX_BYTES` (16 KB, T3.7's size cap).

## 10. Prices (T3.4)

In `api/state/prices.py`, each with its source and date:

- **Claude** (Anthropic's pricing page, Oct 24, 2026, as T3.4 records them; per million tokens): Sonnet 5.5: input $2, output $10, 5-minute cache write $2.50, 1-hour cache write $4, cache read $0.10. Opus 5.5: input $4, output $20, 5-minute write $5, 1-hour write $8, read $0.20. The main session re-reads the pricing page before the first paid build test and records the date.
- **Exa** (Phase 2 findings §4, observed): `auto` $0.007 and `lite` $0.004 a search with text; `costDollars` wins when reported.
- **Voyage** (MongoDB's billing page, to be read again before the embedding run): `voyage-law-2` and `rerank-3` per million tokens; the exact figures are filled from the page with its date before `embed_corpus.py --confirm` runs. Until then, `voyage-law-2` $0.12 (the top of the documented range) and `rerank-3` $0.05, marked unconfirmed.

## 11. Static files

### 11.1 Reader files (T4.3)

One per opinion, `opinions/<opinion_id>.json`, generated from `data/corpus/` into the web image:
`{"opinion_id", "case": {"key", "name", "citation", "decided", "slip_opinion", "source_kind", "credit": "courtlistener" | "us_reports" | "slip_opinion"}, "type", "authors", "joined_by", "joined_by_note", "heading", "paragraphs": [{"id" | null for sections, "kind", "text", "page_start", "page_breaks": [{"offset", "page"}], "footnote_refs": [{"offset", "label", "footnote_id"}]}], "footnotes": [{"id", "label", "page", "paragraphs", "page_breaks"}]}`. The `credit` code selects T5.1's reader credit line.

### 11.2 Replay files (brief §7.4, T5.6)

`replays/<slug>.json`: `{"format": 1, "slug", "question", "recorded_at" (Chicago ISO), "commit", "models": {"loop", "composition"}, "prices": {"source", "date"}, "corpus_label": "full" | "before_chatrie", "events": [<envelopes as §6>]}`. Exported from a real run's events by script in Phase 5, never edited (T5.6). Web page text never appears (T2.2).

## 12. Fakes and test seams

Every outside service has a protocol and a fake, owned by the part that owns the real client: `FakeVoyageClient` (C), `FakeExaTransport` (D), `MemoryStore` (E), `FakeAnthropic` (G). `tests/fixtures/events/` (main session) holds hand-written event streams for the frontend session's mock (P0.3): an answered run, a no-sources reply, a step-limit stop, a pause and resume, an abandoned run, an interrupted run, a refused submit, check flags, each band outcome, the Voyage warning, a replay. `tests/contract/test_events_schema.py` (main session) validates every fixture and every event the backend tests emit.

## 13. Ownership

| Part | Builder | Writes only |
|---|---|---|
| A | Opus 5.5, xhigh | `api/corpus/sentences.py`, `scripts/check_sentences.py`, `tests/corpus/test_sentences.py` |
| B | Sonnet 5.5, high | `api/corpus/` except `sentences.py`, `scripts/build_reader_files.py`, `tests/corpus/` except `test_sentences.py` |
| C | Sonnet 5.5, high | `api/search/`, `scripts/embed_corpus.py`, `tests/search/` |
| D | Sonnet 5.5, xhigh | `api/web_updates/`, `tests/web_updates/` |
| E | Sonnet 5.5, xhigh | `api/state/`, `scripts/spend_report.py`, `tests/state/` |
| F | Sonnet 5.5, xhigh | `api/checks/`, `tests/checks/` |
| G | Opus 5.5, xhigh | `api/loop/`, `tests/loop/` |
| H | Opus 5.5, high | `api/server/`, `api/main.py`, `tests/server/` |
| I | Sonnet 5.5, high | `deploy/`, `tests/deploy/` |
| Main session | — | this file, `api/types.py`, `api/settings.py`, `api/errors.py`, `api/__init__.py`, `api/prompts/`, `contracts/`, `tests/contract/`, `tests/fixtures/`, `data/vectors/` (by running C's script), `pyproject.toml`, `uv.lock`, every shared document |
| Frontend session | its own model | `web/`, `docs/sessions/frontend-log.md` |

Wave 1 (A to F) runs in parallel against this contract and the fakes; A and B meet at `split_sentences` (B calls it; until A lands, B's tests use a trivial splitter behind the same signature). Wave 2 (G, H, I) starts after Wave 1 is merged.
