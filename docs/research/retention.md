# Retention of what the page sends out

*Read Oct 24, 2026, 19:28 CDT (America/Chicago), by the main session for Area 5, topic 5 (the privacy note, T3.7), at the user's direction: "Read the retention pages yourself, no subagent." Each quote below was string-matched against its page by `scripts/verify_quotes.py` (cache under `data/cache/pages/`, gitignored), except where noted. Labels as in `licensing.md`: **DOC** the page says it; **INF** our reading.*

## What leaves this app, and to whom

| Data | Goes to | Basis |
|---|---|---|
| The question, every tool result, the kept passages, the answer | Anthropic (the Claude API) | T1.14, T1.11 |
| Claude's meaning-search queries | Voyage AI, through MongoDB Atlas | T1.1, T1.4 |
| Claude's update-search queries | Exa | T2.1 |
| The visitor's IP address, the URL, browser headers | the domain's gateway (goodnight) and Google Cloud's request logs; Google Fonts | T3.5; below |

The question itself goes only to Anthropic. Claude's queries to Voyage and Exa are written by Claude and may restate parts of it (INF).

## Anthropic

| Finding | Label | Source |
|---|---|---|
| "we automatically delete inputs and outputs on our backend within 30 days of receipt or generation" | DOC | https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data (page dated July 1, 2026) |
| Exceptions listed on the same page include agreements otherwise, Usage Policy enforcement and "In compliance with the law" | DOC | same |
| Flagged by automated trust and safety systems: "We retain inputs and outputs for up to 2 years" | DOC | same |

## Voyage AI (MongoDB Atlas)

The project's Voyage organisation is managed in the Atlas console (BUILD_LOG, Oct 24, Area 3).

| Finding | Label | Source |
|---|---|---|
| "MongoDB can collect the data that you send to the Atlas Embedding and Reranking API and use it to improve Voyage AI models" | DOC | https://www.mongodb.com/docs/voyageai/management/model-training-data/ |
| The setting is the toggle "Help Improve Voyage AI Models" on the Atlas Organization Settings page; "Free users aren't eligible to opt out" (a payment method on file is required) | DOC | https://www.mongodb.com/docs/atlas/tutorial/manage-organization-settings/ |
| Neither page states the default setting or a retention period | DOC (absence) | both |

## Exa

| Finding | Label | Source |
|---|---|---|
| Terms: a "perpetual and irrevocable license to access, use, host, cache, store, reproduce, transmit, display, publish, distribute, and modify any User Input and Output as needed to provide, develop and improve upon our products and services" | DOC | https://exa.ai/terms (PDF, text extracted with `pdftotext`, matched after whitespace normalisation) |
| Privacy policy: "Query Data is used to improve our products and technology, including by training and fine-tuning models" | DOC | https://exa.ai/privacy-policy (dated June 29, 2026) |
| The privacy policy "does not apply to content or other information that we process on behalf of customers" acting as processor; that processing follows the customer agreements, here the Terms above | DOC + INF | same |
| No retention period is stated; zero data retention is offered on Enterprise plans | DOC (absence); THIRD-PARTY search summary of Exa's docs, not string-matched | https://docs.exa.ai/reference/security |

## Google Cloud and the gateway

| Finding | Label | Source |
|---|---|---|
| Cloud Run request logs: "These logs are created automatically" | DOC | https://docs.cloud.google.com/run/docs/logging |
| Cloud Logging "retains the log entries in the _Default bucket for 30 days, unless you configure custom retention for the bucket" | DOC | https://docs.cloud.google.com/logging/docs/store-log-entries |
| goodnight is a Cloud Run service (Phase 2 findings §6), so its request logs, which see the visitor's address, follow its own project's `_Default` bucket; whether that project sets custom retention is not recorded | INF | — |
| This app's own services sit behind goodnight, which forwards no client IP (T3.5), so their request logs see the gateway's address | INF | T3.5 |

## Google Fonts (the page's three faces, T4.1)

| Finding | Label | Source |
|---|---|---|
| "the Google Fonts API does not set or log cookies" | DOC | https://fonts.google.com/faq (rendered by JavaScript; read in the browser, matched in the rendered text) |
| Font requests include "the IP address used by the respective user to access the Internet", the requested URL, and HTTP headers including the user agent | DOC | same |
