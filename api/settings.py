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


# Models (P2.1, T1.8 amended by P4.20, P4.19)
LOOP_MODEL = _s("claude-sonnet-5-5", "P2.1")
LOOP_EFFORT = _s("high", "P2.1")
UPDATE_MODEL = _s("claude-sonnet-5-5", "P4.19: the update step continues the research conversation, so it must equal LOOP_MODEL for the cache to be shared (contract §4.G)")
UPDATE_EFFORT = _s("high", "P4.19: must equal LOOP_EFFORT, as UPDATE_MODEL")
COMPOSITION_MODEL = _s("claude-sonnet-5-5", "T1.8 amended by P4.20")
COMPOSITION_EFFORT = _s("high", "T1.8, P4.20")
EMBED_MODEL = _s("voyage-law-2", "T1.1")
RERANK_MODEL = _s("rerank-3", "T1.1")
EMBED_DIMENSION = _s(1024, "voyage-law-2's output dimension (phase3-working, Area 3 topic 6)")
VOYAGE_BASE_URL = _s("https://api.voyageai.com/v1", "T5.5: the key is a Voyage platform key, accepted here and checked with scripts/probe_voyage.py, Oct 24, 2026")

# Run limits (P2.7, T1.11, T3.3, T3.5, amended by P4.18). Each step has its own limits; there is no run-wide one.
MAX_ROUNDS = _s(12, "P2.7, P4.18 (unchanged: 8 seen; the graceful stop)")
LOOP_INPUT_BUDGET = _s(2_000_000, "P4.18 (the user): research's input only (uncached, cache writes and cache reads), summed over every research call, checked before each round against an estimate (T3.3). Test 4's re-run used 366,680 in 8 rounds; 2M binds only in a runaway")
LOOP_OUTPUT_BUDGET = _s(16_000, "P4.18: 4,574 seen (57% of the old 8,000)")
UPDATE_MAX_ROUNDS = _s(8, "PLACEHOLDER (P4.18): the update step's rounds")
UPDATE_INPUT_BUDGET = _s(2_000_000, "P4.18 (the user): the update step's input only, summed over its calls; each call re-sends the research conversation, mostly as a cache read (design §3, P4.19: typical about 180k, heaviest plausible about 1.06M)")
UPDATE_OUTPUT_BUDGET = _s(6_000, "PLACEHOLDER (P4.18): the update step's output, summed over its calls")
COMPOSITION_MAX_TOKENS = _s(16_000, "T1.11 amended by P4.18: 5,481 seen (46% of the old 12,000); a cut-off answer is the worst failure a visitor sees")
RUN_DEADLINE_S = _s(600, "PLACEHOLDER (T3.5, 10 minutes)")
RUN_WATCHDOG_S = _s(1_800, "PLACEHOLDER, main session's (H's review, v2.0): a run still in progress this long after its task started is cancelled and ends failed (internal), so a hung run never holds one of the MAX_CONCURRENT_RUNS slots for good. Above RUN_DEADLINE_S plus a composition's three attempts at COMPOSITION_CALL_DEADLINE_S and their waits (600 + 3 x 300 + 10 = 1,510 s)")
VOYAGE_RUN_BOUND_USD = _s(0.03, "T3.4 (Voyage under $0.03 a run); used by the documented worst case")
UPDATE_SEARCHES_PER_RUN = _s(5, "P2.7, T2.1, amended by P4.18: 3 of 3 used once")
WORST_CASE_COMPOSITION_INPUT = _s(66_000, "main session's, for P4.21's documented worst case only, never a gate or a limit: the composition's largest input by G's estimator, 65,188 tokens (KEEP_CAP largest documents with full keep reasons, a question of QUESTION_MAX_CHARS and a note of NOTE_MAX_CHARS; tests/contract/test_composition_worst_case.py, Oct 25, 2026), rounded up. It was COMPOSITION_RESERVE_INPUT, removed as a reserve by P4.18")
MAX_CONCURRENT_RUNS = _s(5, "P4.21 (the user): runs in progress at once on the instance, from POST /runs to run_ended; one count covers the service, which runs at most one instance (API_MAX_INSTANCES)")

# Search tools (T1.4, T1.7)
MAX_RESULTS_DEFAULT = _s(8, "T1.4")
MAX_RESULTS_CAP = _s(10, "T1.4")
SEMANTIC_CANDIDATES = _s(50, "PLACEHOLDER (T1.4)")
KEYWORD_ITEMS_PER_LIST = _s(10, "PLACEHOLDER (T1.4)")
READ_AROUND_MAX = _s(10, "T1.6")
KEEP_REASON_MAX_CHARS = _s(300, "PLACEHOLDER (T1.7)")
KEEP_CAP = _s(40, "PLACEHOLDER (T1.7)")
NOTE_MAX_CHARS = _s(1_000, "P4.6: submit_answer's note (and so the scope note), so the composition's input is bounded")

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
ATLAS_ADMIT_TRIES = _s(5, "PLACEHOLDER, main session's: duplicate-key retries in admit and the store's upserts (two writers creating one month's document at once) before Atlas counts as unreachable (was ATLAS_RESERVE_TRIES; P4.21)")
SHUTDOWN_GRACE_S = _s(5, "main session's: uvicorn's --timeout-graceful-shutdown, so open streams close and the lifespan shutdown records unrecorded spend within Cloud Run's 10 s between SIGTERM and SIGKILL (docs.cloud.google.com/run/docs/container-contract, read Oct 24, 2026)")
ATLAS_OP_TIMEOUT_S = _s(5, "PLACEHOLDER, main session's: every other Atlas operation, so admission never waits pymongo's 30 s default")

# Caps (P2.7, T3.4)
DAILY_CAP_USD = _s(15.0, "P2.7 amended by P4.11; a run is admitted only while the day's spend is under it (P4.21)")
MONTHLY_CAP_USD = _s(60.0, "P2.7; a run is admitted only while the month's spend is under it (P4.21)")

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
