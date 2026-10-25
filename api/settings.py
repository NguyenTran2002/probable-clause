"""Every tunable figure in the API, with its basis (brief §10.7; contract §9).

Owned by the main session. Builders read from here and never write a figure of
their own into code: a value that needs changing changes here, with its basis.
"PLACEHOLDER" means placeholder until measured (Phase 5 measures it).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Setting:
    value: float | int | str
    basis: str


def _s(value, basis):
    return Setting(value, basis)


# Models (P2.1, T1.8)
LOOP_MODEL = _s("claude-sonnet-5-5", "P2.1")
LOOP_EFFORT = _s("high", "P2.1")
COMPOSITION_MODEL = _s("claude-opus-5-5", "T1.8")
COMPOSITION_EFFORT = _s("high", "T1.8")
EMBED_MODEL = _s("voyage-law-2", "T1.1")
RERANK_MODEL = _s("rerank-3", "T1.1")
EMBED_DIMENSION = _s(1024, "voyage-law-2's output dimension (phase3-working, Area 3 topic 6)")
VOYAGE_BASE_URL = _s("https://api.voyageai.com/v1", "T5.5: the key is a Voyage platform key, accepted here and checked with scripts/probe_voyage.py, Oct 24, 2026")

# Run limits (P2.7, T1.11, T3.3, T3.5)
MAX_ROUNDS = _s(12, "P2.7")
RUN_INPUT_TOKENS = _s(400_000, "P2.7; counts uncached, cache writes and cache reads (T3.3)")
RUN_OUTPUT_TOKENS = _s(20_000, "P2.7")
COMPOSITION_RESERVE_INPUT = _s(30_000, "PLACEHOLDER (T1.11)")
COMPOSITION_RESERVE_OUTPUT = _s(12_000, "T1.11 (max_tokens of the composition call)")
LOOP_INPUT_BUDGET = _s(370_000, "T3.3: RUN_INPUT_TOKENS - COMPOSITION_RESERVE_INPUT")
LOOP_OUTPUT_BUDGET = _s(8_000, "T3.3: RUN_OUTPUT_TOKENS - COMPOSITION_RESERVE_OUTPUT")
COMPOSITION_MAX_TOKENS = _s(12_000, "T1.11")
RUN_DEADLINE_S = _s(600, "PLACEHOLDER (T3.5, 10 minutes)")
FIXED_PREFIX_TOKENS_ESTIMATE = _s(12_000, "estimate (T1.14: tools, system prompt and catalog); used by the worst case (T3.4)")
VOYAGE_RUN_BOUND_USD = _s(0.03, "T3.4 (Voyage under $0.03 a run); used by the worst case")
UPDATE_SEARCHES_PER_RUN = _s(3, "P2.7, T2.1")

# Search tools (T1.4, T1.7)
MAX_RESULTS_DEFAULT = _s(8, "T1.4")
MAX_RESULTS_CAP = _s(10, "T1.4")
SEMANTIC_CANDIDATES = _s(50, "PLACEHOLDER (T1.4)")
KEYWORD_ITEMS_PER_LIST = _s(10, "PLACEHOLDER (T1.4)")
READ_AROUND_MAX = _s(10, "T1.6")
KEEP_REASON_MAX_CHARS = _s(300, "PLACEHOLDER (T1.7)")
KEEP_CAP = _s(40, "PLACEHOLDER (T1.7)")

# Update check (T2.1 to T2.5)
EXA_MCP_URL = _s("https://mcp.exa.ai/mcp?tools=web_search_advanced_exa", "T2.5")
EXA_TIMEOUT_S = _s(30, "PLACEHOLDER (T2.4); covers the handshake (T2.5)")
EXA_DOMAINS_MAX = _s(100, "T2.1 (the user's limit against overrun)")
EXA_NUM_RESULTS_DEFAULT = _s(10, "T2.1")
EXA_TEXT_CHARS = _s(4_000, "PLACEHOLDER (T2.2)")
UPDATE_FINDINGS_MAX = _s(20, "PLACEHOLDER against overrun (T2.3)")
UPDATE_STATEMENT_MAX_CHARS = _s(600, "PLACEHOLDER against overrun (T2.3)")
UPDATE_SOURCES_PER_STATEMENT = _s(10, "PLACEHOLDER against overrun (T2.3)")
UPDATE_OVERVIEW_MAX_CHARS = _s(600, "PLACEHOLDER against overrun (T2.3)")
COPY_GUARD_WORDS = _s(10, "PLACEHOLDER (T2.3)")
EXA_HEADER_FIELD_MAX_CHARS = _s(300, "PLACEHOLDER, main session's: a page's title or author line, cut to one line of at most this many characters (T2.2)")
EXA_MESSAGE_MAX_CHARS = _s(500, "PLACEHOLDER, main session's: Exa's own error message passed to Claude and stored in events (T2.4), cut to this length")

# Answer checks (T1.12)
QUOTATION_MIN_WORDS = _s(4, "PLACEHOLDER (T1.12)")
QUOTATION_BRACKET_MAX_SOURCE_WORDS = _s(3, "PLACEHOLDER, main session's: how many source words one bracketed alteration may stand for (T1.12); held low because a wider bracket can hide a change of meaning. The corpus's 1,932 quotations need at most 1 (measured by part F, Oct 24, 2026)")

# Calls, deadlines and retries (T3.3)
LOOP_CALL_DEADLINE_S = _s(120, "PLACEHOLDER (T3.3)")
COMPOSITION_CALL_DEADLINE_S = _s(300, "PLACEHOLDER (T3.3)")
ANTHROPIC_RETRIES = _s(2, "T3.3")
ANTHROPIC_RETRY_WAITS_S = _s("2,8", "PLACEHOLDER (T3.3); retry-after wins when sent")
VOYAGE_TIMEOUT_S = _s(10, "PLACEHOLDER (T3.3)")
VOYAGE_RETRIES = _s(2, "T3.3")
VOYAGE_RETRY_WAITS_S = _s("1,3", "PLACEHOLDER (T3.3)")
RETRY_AFTER_MAX_S = _s(30, "PLACEHOLDER, main session's: a retry-after longer than this is not waited out; the call fails as out of retries, so a run never sleeps past its checks (T3.2, T3.5)")
VOYAGE_BATCH_TIMEOUT_S = _s(120, "PLACEHOLDER, main session's: one embedding batch in scripts/embed_corpus.py, which is never retried, so a slow batch is not cut off after it was billed")
VOYAGE_CHARS_PER_TOKEN_ESTIMATE = _s(3, "main session's: prices a failed Voyage attempt that reported no usage (T3.3). Measured 3.73 on the corpus embedding (1,956,650 characters, 524,853 tokens, Oct 24, 2026), rounded down so the estimate over-counts")

# Lifecycle (T3.1, T3.2)
HEARTBEAT_INTERVAL_S = _s(10, "PLACEHOLDER (T3.2); the page's interval")
ATTENDED_WINDOW_S = _s(25, "PLACEHOLDER (T3.2)")
ABANDON_AFTER_S = _s(60, "PLACEHOLDER (T3.2)")
PAGE_WATCHDOG_S = _s(45, "PLACEHOLDER (T3.2); the page's")
KEEPALIVE_S = _s(15, "PLACEHOLDER (T3.1)")
UNATTACHED_RUN_EXPIRY_S = _s(120, "PLACEHOLDER, main session's (T3.1: a run no stream attaches to expires with no spend)")
HEARTBEAT_POLL_S = _s(2, "PLACEHOLDER, main session's: how often a paused run reads Atlas for a heartbeat sent to another instance (T3.2)")

# The wake protocol, on the page (brief §8.5, T3.6); served to the page in config.json (contract §5.1)
WAKE_CHECK_TIMEOUT_S = _s(60, "PLACEHOLDER (brief §8.5)")
WAKE_CHECK_GAP_S = _s(1, "PLACEHOLDER (brief §8.5)")
LONG_WAIT_S = _s(90, "PLACEHOLDER (T3.6)")
WAKE_GIVE_UP_S = _s(300, "PLACEHOLDER (T3.6, 5 minutes)")

# Protections and retention (T3.7)
QUESTION_MAX_CHARS = _s(2_000, "PLACEHOLDER (T3.7)")
REQUEST_BODY_MAX_BYTES = _s(16_384, "PLACEHOLDER, main session's (T3.7: POST /runs and heartbeat bodies size-capped)")
EVENTS_TTL_S = _s(86_400, "T3.7 (24 hours)")
HEARTBEATS_TTL_S = _s(600, "T3.7 (10 minutes)")
ATLAS_HEALTH_TIMEOUT_S = _s(2, "PLACEHOLDER, main session's (T3.4: a short timeout)")
ATLAS_RESERVE_TRIES = _s(5, "PLACEHOLDER, main session's: compare-and-swap rounds in reserve, settle and release before Atlas counts as unreachable")
ATLAS_OP_TIMEOUT_S = _s(5, "PLACEHOLDER, main session's: every other Atlas operation, so a reservation never waits pymongo's 30 s default")

# Caps (P2.7, T3.4)
DAILY_CAP_USD = _s(10.0, "P2.7")
MONTHLY_CAP_USD = _s(60.0, "P2.7")

# Atlas (T3.4, T3.5)
ATLAS_DB_LIVE = _s("Probable_Clause", "T3.5")
ATLAS_DB_TEST = _s("Probable_Clause_test", "T3.4, T3.5")

# Cloud Run (T3.5); used by deploy/deploy.sh, never changed without the user's green light
GCP_PROJECT = _s("probable-clause", "T3.5 (project number 1066460440617)")
GCP_REGION = _s("us-central1", "T3.5")
API_MAX_INSTANCES = _s(1, "brief §2, T3.5")
API_MIN_INSTANCES = _s(0, "brief §2, T3.5")
API_CONCURRENCY = _s(80, "T3.5")
API_CPU = _s(1, "T3.5")
API_MEMORY = _s("512Mi", "PLACEHOLDER (T3.5, until measured)")
API_REQUEST_TIMEOUT_S = _s(900, "PLACEHOLDER (T3.5)")
WEB_MAX_INSTANCES = _s(2, "PLACEHOLDER (T3.5)")
WEB_MIN_INSTANCES = _s(0, "T3.5")

TIME_ZONE = _s("America/Chicago", "brief §10.7")


def value(setting: Setting):
    return setting.value


def waits(setting: Setting) -> list[float]:
    """A comma-separated list of waits, in seconds."""
    return [float(x) for x in str(setting.value).split(",")]
