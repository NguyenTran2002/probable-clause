# Phase 2 research findings

*Written Oct 24, 2026, from 13:31 CDT. Brief §9; plan approved as P2.5.*

**How this was done.** Six research agents (Sonnet 5.5, high or extra-high effort) read current documentation on Oct 24, 2026, each claim with its source and an exact quote. The main session then ran paid checks on the product's own model and effort (Sonnet 5.5, high; P2.1), from committed scripts: `scripts/probe_loop.py` (a simulated research loop on the real corpus), `scripts/probe_exa.py` (Exa's hosted MCP server), with `scripts/probe_common.py` keeping the spend ledger. Every quote was then re-checked: `scripts/verify_quotes.py` re-fetched each page, and an agent not told the conclusions checked by hand the quotes a plain string match could not read (tables, PDFs, registry replies). The agents' notes, quotes and the probe outputs stay local under `data/verification/phase2/` (gitignored).

**Tags.** **DOC**: the vendor's own documentation, pricing or terms. **OBSERVED**: our paid checks, Oct 24, 2026. **PREVIOUS BUILD**: the previous build's own records (its repository). **THIRD-PARTY**: someone else's page. **INFERRED**: reasoning, not a source.

**Spend.** Anthropic: 16 calls, $0.5541 (ledger total; ceiling $2). Exa: 9 requests from the free credit; the five successful responses report $0.029 in all; two failed requests and two error replies reported no cost (whether the two failed requests were billed is not known).

---

## What this changes, for the user

1. **The disconnect rule needs a way to see a disconnect.** Cloud Run does not pass a client's disconnect to the container over HTTP/1.1, its default (DOC, below, §6). The §2 rule "no new paid call while nobody is connected" therefore cannot rely on the server noticing the stream close. It needs an application-level signal (for example the page sending a heartbeat the loop checks before each paid call) or end-to-end HTTP/2. To decide in Phase 3; the rule itself stands.
2. **The gateway's own timeout is unknown.** goodnight is itself a Cloud Run service; its request timeout is not recorded anywhere the research could read (PREVIOUS BUILD). Cloud Run's default is 300 s (DOC). Measured runs took about 30 to 45 s (OBSERVED, §3), so a 300 s cut is unlikely to bite, but the setting should be read before Phase 4.
3. **A run costs less than planned.** Two measured runs cost $0.14 and $0.24 of Claude (OBSERVED, §3), against the brief's planning estimate of $0.35 to $0.45 uncached and $0.15 to $0.25 cached. This feeds §8.2.
4. **Exa: three things for the wrapper.**
   - Its MCP server always requests page text, and full text for 10 results overflowed the MCP client's 1 MB event limit; the wrapper must cap text per result (OBSERVED).
   - It retries Exa's server errors (500, 502, 503 and 504) twice on its own side, which we cannot turn off (DOC, code). That conflicts with "a paid request is never retried automatically" (brief §10.7); the user decides whether to accept it.
   - A published-date filter appears to leave out pages with no published date (OBSERVED).
5. **Sentence-level citations work.** With one text block per sentence, citations narrowed to one or two sentences, and every `cited_text` was exactly the cited blocks' text (OBSERVED). This informs the paragraph-or-sentence choice left to Phase 3 (P2.4).
6. **The brief's contradicted price is settled:** Sonnet 5.5 cache reads are $0.10 per million tokens, not $0.20 (DOC).
7. **The loop's history must stay append-only.** Sonnet 5.5 ties thinking blocks to an unchanged history (DOC). Returning a rejection as an error tool result is append-only and safe. Removing passages that were not kept from the history (an idea raised with P2.3) safely needs a server-side feature: the clearing beta, or compaction. Removing them in our own code invalidates every later thinking block. Server-side clearing costs a cache rewrite each time (DOC).

Nothing found here changes the model (P2.1).

---

## 1. Citations with tool results (brief §9 item 1)

- **Search results returned by our tools are cited.** A tool can return `search_result` blocks as its result, and Claude cites them as `search_result_location` with `cited_text`, `source`, `title`, `search_result_index` (counted across every search result in the request), `start_block_index` and `end_block_index` (exclusive). Citations are off by default and must be enabled on every search result in a request or on none. A tool result holding a search result may hold nothing else. DOC: https://platform.claude.com/docs/en/build-with-claude/search-results
- **The final call with no tools works the same way.** Search results can be passed directly in the user message, with no tools and no beta header. DOC: same page ("Method 2").
- **The text block is the smallest citable unit.** A citation is a range of whole blocks; to cite finer, split the content into more blocks. DOC: same page; https://platform.claude.com/docs/en/api/messages/create
- **`cited_text` is extracted by the API, not written by the model**, so citations "are guaranteed to contain valid pointers to the provided documents" (DOC: https://platform.claude.com/docs/en/build-with-claude/citations). For search results it equals the cited blocks' content "joined together" (DOC: https://platform.claude.com/docs/en/build-with-claude/search-results ; https://platform.claude.com/docs/en/api/messages/create). The docs say nothing about byte-level fidelity.
  - OBSERVED: across three answers, 97 of 97 citations' `cited_text` equalled the cited blocks' text exactly, joined with nothing between blocks. Each block keeps its own trailing whitespace, so the concatenation is the stored paragraph.
- **No non-citable metadata slot on a search result.** It has only `source`, `title` and `content`; `source` and `title` come back in every citation. On a document block, `title` and `context` are passed to the model but not cited, and `context` is the documented place for metadata. Whether the model reads a search result's `title` is not documented. DOC: search-results and citations pages.
  - OBSERVED: the probe put each passage's ID, case, citation, date, opinion type, author and page in `title`, and Claude used those IDs correctly in `keep_passages` and `submit_answer`, so it does read the title.
- **Citations and Structured Outputs still cannot be combined** (a 400). No restriction is documented for citations with thinking. DOC: citations page; https://platform.claude.com/docs/en/build-with-claude/structured-outputs
  - OBSERVED: citations worked with Sonnet 5.5's default adaptive thinking.

## 2. Rejected tool calls and thinking blocks (item 2)

- **Error tool results** (`is_error: true`) report a failed call, and the docs advise saying what went wrong and what to try next (DOC: https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls). Every `tool_use` needs a `tool_result`. A call that is deliberately not run still gets one, with `is_error: true` and a brief explanation (DOC: https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use).
- **Thinking blocks:** within a tool-use turn, pass them back complete and unmodified (a modified block is a 400). Sonnet 5.5 checks that the system prompt, the tools and every earlier message are unchanged since a block was produced; for accounts created on or after Aug 31, 2026, a replay after such an edit is a 400 by default. Appending is always fine. DOC: https://platform.claude.com/docs/en/build-with-claude/thinking ; https://platform.claude.com/docs/en/build-with-claude/preserved-thinking
- **Forced tool use is rejected on Sonnet 5.5** (`tool_choice` `any` or `tool` is a 400). The design never forces a tool. DOC: thinking page; https://platform.claude.com/docs/en/build-with-claude/effort
- **Thinking cannot be turned off on Sonnet 5.5** (`disabled` is a 400); adaptive thinking is the default and `between_tools` the lowest setting. DOC: thinking and effort pages.
- **Several tool calls in one turn are on by default.** DOC: https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use
  - OBSERVED: Claude made two or three searches per turn, ran the update check and a keep call together, and once kept and submitted in the same turn.
- OBSERVED:
  - **A rejected `submit_answer` returned as an error result, thinking intact, was accepted by the API**, and Claude complied by running another update search. The trigger was artificial: in both natural runs Claude ran the update check before submitting, so the rejection never fired on its own.
  - **Removing an earlier turn's thinking block was accepted, not refused.** Whether this account is under the Aug 31, 2026 check is not known. The design stays append-only regardless.
- **Clearing old tool results** exists server-side as a beta (`clear_tool_uses_20250919`, header `context-management-2025-06-27`). It invalidates the cached prefix at the clear point, and server-side clearing never invalidates thinking blocks. DOC: https://platform.claude.com/docs/en/build-with-claude/context-editing

## 3. Prompt caching, prices and a measured run (item 3)

- **Sonnet 5.5 prices, per million tokens:**
  - input $2, output $10
  - cache write $2.50 (5-minute) or $4 (1-hour)
  - cache read $0.10, which is 5% of input on Sonnet 5.5 and Opus 5.5
  - no long-context surcharge on its 1M window

  For reference, Opus 5.5 is $4 input and $20 output. DOC: https://platform.claude.com/docs/en/about-claude/pricing ; https://claude.com/pricing
- **Caching:**
  - Automatic caching (one top-level `cache_control`) moves the breakpoint forward as the conversation grows.
  - Up to 4 breakpoints, each with a lookback of 20 blocks.
  - The minimum cacheable prompt on Sonnet 5.5 is 512 tokens.
  - Changing the tools invalidates the whole cache; changing `tool_choice`, thinking settings or effort invalidates the message part.

  DOC: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- **Effort** is `output_config.effort` (low, medium, high, xhigh, max); Sonnet 5.5 defaults to high. DOC: effort page.
- **Thinking is billed as output**, and earlier turns' thinking blocks are billed as input when passed back. DOC: thinking page.
- **Token counting is free**, with its own rate limit. DOC: https://platform.claude.com/docs/en/build-with-claude/token-counting

**Measured (OBSERVED).** Both runs used the real corpus, SQLite FTS5 search returning 8 paragraphs per search, a stubbed update check (no Exa call), Sonnet 5.5 at high effort, and automatic caching. Composition used one text block per sentence. Times are approximate, from the spend ledger's return time for each call; the first run's time counts the loop and one composition (a second, paragraph-block composition ran separately for comparison).

| Question | Steps | Searches | Kept | Input tokens over the loop (mostly cache reads) | Output tokens | Loop | Composition | Claude total | Elapsed |
|---|---|---|---|---|---|---|---|---|---|
| Location data, *Smith* to *Chatrie* | 6 | 12 | 30 | 168,606 | 2,906 | $0.166 | $0.072 | **$0.237** | about 45 s |
| Thermal imaging, *Kyllo* and later cases | 4 | 7 | 14 | 66,132 | 1,622 | $0.100 | $0.044 | **$0.144** | about 30 s |

- Cache reads grew from the third step on: the first two steps each wrote the cache and the later steps read the growing prefix (first run 0, 0, 12,759, 23,714, 35,271, 46,863 tokens read). Most of a step's cost is the cache write for that step's new search results: about 11,000 tokens for three searches of 8 paragraphs.
- The composition call is not cached. It is a new prompt (different system prompt, no tools). Its input was 9,326 tokens for 14 kept passages, and 15,454 (paragraph blocks) or 18,526 (sentence blocks) for 30.
- Two runs on two questions are a small sample. The retrieval design (Phase 3) changes how much each search returns, and with it the cost.

## 4. Exa (item 4)

Prices and plan are the user's console figures (P2.2).

- **Server and auth.** The server is `https://mcp.exa.ai/mcp`, authenticated with an `x-api-key` header (DOC: https://exa.ai/docs/get-started/exa-mcp.md). It runs over streamable HTTP, and `?tools=web_search_advanced_exa` exposes only the advanced tool, replacing the defaults (DOC: the `exa-labs/exa-mcp-server` README).
  - OBSERVED: `tools/list` returned only `web_search_advanced_exa`.
- **Search types.** The MCP tool accepts only `auto`, `lite`, `fast` and `instant`; the Deep types cannot be sent through it. The brief's "deep search types refused" clamp is therefore enforced by the server. DOC (code): https://raw.githubusercontent.com/exa-labs/exa-mcp-server/main/src/tools/webSearchAdvanced.ts
- **Output.** One text block holding JSON: `results[]` (fields `id`, `url`, `title`, `publishedDate`, `author`, `image`, `text`), plus `requestId`, `searchTime` and `costDollars`. DOC (code).
  - OBSERVED, with the same field names; `publishedDate` is absent when unknown.
- **Text is always requested** (DOC, code), and its cost is included in the search price.
  - OBSERVED: lite cost $0.004 and auto $0.007 per request with text, with no content charge.
  - OBSERVED: without a cap, two 10-result requests failed with "Server-sent event exceeded the 1048576 byte limit" in our client. Capped at 2,000 characters per result, they succeeded.
- **Pages with no published date.** Not documented (DOC: absent).
  - OBSERVED: with no date filter, 8 of 10 lite results and 5 of 10 auto results had no published date. With a published-date filter, 0 of 25 results across three requests lacked one. So the filter appears to exclude undated pages. A narrow window can therefore miss commentary that carries no date.
- **Rate limits.** 10 queries per second on the free tier, returning 429 above that; no daily cap is documented for a keyed account. DOC: https://exa.ai/docs/admin/billing.md
- **When credits run out:** HTTP 402, and free credits reset on the 1st of the month (DOC: https://exa.ai/docs/admin/billing.md). The error tag is `NO_MORE_CREDITS` (DOC: https://exa.ai/docs/admin/error-codes.md). Credits are bought by hand or by auto-recharge at a threshold. INFERRED: with neither set up, nothing is charged to a card.
- **Failing combinations.** `company` and `people` reject published-date filters; `people` also rejects `excludeDomains`; `lite` rejects parameters outside its small set. DOC: https://exa.ai/docs/reference/search.md
  - OBSERVED: `company` with a date filter came back as a tool error result with the message "The company category does not support the following filters: startPublishedDate". The raw response carries the error flag set to true. The probe's summary file records it as null because the probe read the field under the wrong name; that was fixed before the later requests.
- **Errors.** Exa API errors come back as tool results with `isError` true. OBSERVED: the 400 above and the 401 for an invalid key. Gateway failures can surface as protocol errors instead, so the client must handle both. DOC (code).
- **Server-side retries.** The server retries Exa 500, 502, 503 and 504 responses twice; its tool timeout is 300 s. DOC (code): `exa-labs/exa-mcp-server`, commit 0b499f09.
- **Crawl-date filters are ignored by the API now.** Use published dates only. DOC: https://exa.ai/docs/search/best-practices.md

## 5. Retrieval (item 5)

Facts for the Phase 3 choice; no recommendation here.

- **Anthropic offers no embeddings model** and points to Voyage AI, recommending `voyage-law-2` for legal text. DOC: https://platform.claude.com/docs/en/build-with-claude/embeddings
- **Anthropic's Contextual Retrieval write-up** reports the top-20 retrieval failure rate falling from 5.7% to:
  - 3.7% with contextual embeddings
  - 2.9% with contextual BM25 added
  - 1.9% with reranking added

  It suggests a knowledge base under 200,000 tokens can go straight into the prompt; this corpus is 599,094. DOC: https://www.anthropic.com/news/contextual-retrieval
- **Keyword search options:**
  - **SQLite FTS5** (bm25 ranking, phrase queries, the porter and unicode61 tokenizers). DOC: https://www.sqlite.org/fts5.html
    - OBSERVED locally: the corpus indexes in 0.04 s into 3.55 MB, and a query takes under 1 ms. `"389 U. S. 347"` and `"third-party doctrine"` match as phrases. The probe used FTS5, and Claude's searches found the leading paragraphs of *Smith*, *Carpenter*, *Jones*, *Kyllo* and *Chatrie*.
    - Whether the Cloud Run image's Python has FTS5 must be checked there.
  - **bm25s**: MIT licence, numpy only, saves and loads an index. DOC: https://github.com/xhluca/bm25s
  - **tantivy-py**: MIT licence (DOC: its PyPI page). The Rust library underneath supports phrase queries (DOC: https://docs.rs/tantivy/latest/tantivy/query/struct.QueryParser.html); the Python package's own docs do not mention them.
  - **rank_bm25**: last released 2022. DOC: https://pypi.org/pypi/rank-bm25/json
- **Embedding options:**
  - **Voyage API:** $0.02 to $0.12 per million tokens; embedding the whole corpus once costs a few cents. Each query needs a network call and a key at run time. DOC: https://www.mongodb.com/docs/voyageai/management/billing/
  - **Local models:** 23 to 133 MB of ONNX weights. CPU time per query is not documented.
- **Hybrid search:** reciprocal rank fusion, the sum of 1/(60 + rank) across rankings. DOC: https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion
- **Rerankers:** Voyage `rerank-3` $0.05 and `rerank-3-lite` $0.02 per million tokens (DOC: https://www.mongodb.com/docs/voyageai/management/billing/). No reranker documents a latency in milliseconds. The local cross-encoders list throughput in documents per second, without stating the hardware (DOC: https://www.sbert.net/docs/cross_encoder/pretrained_models.html).

## 6. Cloud Run and the gateway (item 6)

| Question | Finding | Tag |
|---|---|---|
| Request timeout | Default 300 s, maximum 3,600 s; includes container start | DOC: https://docs.cloud.google.com/run/docs/configuring/request-timeout ; https://docs.cloud.google.com/run/docs/container-contract |
| Streaming (SSE) | Supported. HTTP/2 is downgraded to HTTP/1 before the container unless end-to-end HTTP/2 (h2c) is chosen. Buffering and idle limits on a stream: not documented | DOC: https://docs.cloud.google.com/run/docs/triggering/https-request |
| Concurrency per instance | Maximum 1,000; default 80 (console), or 80 × vCPU (gcloud) | DOC |
| More instances than the maximum | Documented, "a few times per week": surges, maintenance, instance replacement, and deploys (the limit is per revision) | DOC: https://docs.cloud.google.com/run/docs/about-instance-autoscaling ; https://docs.cloud.google.com/run/docs/configuring/max-instances |
| A request while the only instance starts | Queued for the greater of 10 s and 3.5 × the average start time, then 429; the troubleshooting page also lists 500 for "no available instance". Whether the body is plain text: not documented; the previous build's README says it is | DOC: https://docs.cloud.google.com/run/docs/about-instance-autoscaling ; https://docs.cloud.google.com/run/docs/troubleshooting ; PREVIOUS BUILD |
| Idle shutdown | Only an upper bound: an idle instance is kept no longer than 15 minutes, and it can be shut down at any time. Previously observed about 15 minutes | DOC: https://docs.cloud.google.com/run/docs/about-instance-autoscaling ; https://docs.cloud.google.com/run/docs/container-contract ; PREVIOUS BUILD |
| `--scaling=0` | Documented: manual scaling to 0 disables the service ("Service unavailable"); `--scaling=auto` reverses it; no new revision. The gcloud reference's text ("positive integer") contradicts the guide | DOC: https://docs.cloud.google.com/run/docs/configuring/services/manual-scaling ; https://docs.cloud.google.com/sdk/gcloud/reference/run/services/update |
| Startup CPU boost | "Enabled by default when unspecified on new services" (gcloud reference). The previous build set it explicitly | DOC; PREVIOUS BUILD |
| Work after a request ends | Under request-based billing, CPU is allocated only during request processing; after a request, CPU access is "disabled or severely limited" | DOC: https://docs.cloud.google.com/run/docs/configuring/billing-settings ; https://docs.cloud.google.com/run/docs/tips/general |
| Client disconnects | Not propagated to the container over HTTP/1.1 (the default); only WebSockets or HTTP/2 propagate them. uvicorn's HTTP/2 support is experimental and opt-in | DOC: https://docs.cloud.google.com/run/docs/troubleshooting ; THIRD-PARTY: https://uvicorn.dev/concepts/http2/ |
| Cancelling a Claude call | Not documented for streaming. Anthropic's support page says a request the client abandons that was "on track to succeed" is still charged | DOC (support page): https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-claude-api-usage |
| goodnight | Its config is `goodnight/nginx.conf` in the user's `framedbytran` repository, and goodnight runs as a Cloud Run service itself. The previous build's draft block sets `proxy_buffering off`, `proxy_read_timeout 300s` and `X-Forwarded-For` (client IP third from the right). `proxy_ignore_client_abort` is not recorded (nginx's default is off), and goodnight's own Cloud Run timeout is not recorded | PREVIOUS BUILD; nginx defaults THIRD-PARTY: https://nginx.org/en/docs/http/ngx_http_proxy_module.html |
| Previous cold starts | 12.6 to 32.4 s after deploys; 21.5 to 49.5 s after idle; one 85.6 s double start from a wake loop that gave up after 10 s per check | PREVIOUS BUILD |

## 7. Anthropic Console spend limits (item 7)

- **Monthly spend caps by usage tier:** Start $500, Build $1,000, Scale $200,000. An organisation can set its own lower monthly limit on the Billing page, and per-workspace limits (not on the Default Workspace). DOC: https://platform.claude.com/docs/en/api/rate-limits ; https://platform.claude.com/docs/en/manage-claude/workspaces
- **When a limit is hit:**
  - A custom limit returns HTTP 400 `invalid_request_error`.
  - The tier cap returns HTTP 429 `rate_limit_error` (`enforced_spend_limit_reached`), with no `retry-after`.

  DOC: same.
- **No daily limit is documented**, so the $10 daily cap (§8.2) is ours to enforce in code. Whether a Console limit can be overshot before it takes effect is not documented.
- **Sonnet 5.5 rate limits at the Start tier:** 1,000 requests, 2 million input tokens and 400,000 output tokens per minute. Cache reads do not count toward the input limit. DOC: rate-limits page.

## 8. Name collisions (item 8)

For the user to decide.

- **No product, company, newsletter, podcast, book or legal-tech tool named "Probable Clause" was found.** The nearest is the podcast "Probable Causation". The search tools are shallow, so absence is weak evidence. THIRD-PARTY: https://podnews.net/podcast/ioit
- **Domains:** probableclause.com, .org, .app, .dev and .law have no DNS records. The .app, .dev, .org and .law registries answered "not found"; .com's registry returned an empty 404. They look unregistered; price and reserved status were not checked. DOC (registry replies) and INFERRED.
- **Trademarks:** the USPTO search renders by JavaScript and could not be read, so there is no record either way. To check by hand: PROBABLE CLAUSE, PROBABLE CAUSE and PROBABLECLAUSE in classes 9, 41, 42 and 45.
- **Repositories and packages:** no GitHub repository, user or organisation named probableclause or probable-clause; `probable-clause` is free on npm and PyPI. OBSERVED via the GitHub API and the registries.

## 9 and 10. Crediting Claude; CourtListener redistribution

Settled in Phase 1: P1.5 and P1.22.

---

## Re-check of sources (brief §9)

- `scripts/verify_quotes.py` re-fetched 91 pages and matched 439 of 488 web quotes exactly. All 38 quotes from the previous build's files matched them exactly.
- The 49 web quotes a plain string match could not read went to an agent not told the conclusions. It found 48 on their pages word for word, allowing for table formatting, PDF columns and the registries' 404 bodies. The last (a Voyage reranker pricing formula) was the same formula in slightly different words. None was missing.
- A further agent, not told the conclusions, checked each claim in a draft of this document: 126 claims, each against the quotes from the page it cites or, for an observed figure, against the probe outputs. 104 were supported or matched. Corrected in this version:
  - 10 claims cited a neighbouring page of the same vendor's documentation.
  - 7 were worded too strongly.
  - 5 figures were off: the Exa total, a composition token range, a rounding, the step where cache reads began, and an error flag recorded under the wrong field name.

  None was unsupported.
