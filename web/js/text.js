// Every wording the page shows, in one place. T5.1 to T5.6 are final text and are used exactly; lines marked
// "main session's" are written under P4.31 where T5 has none, logged in BUILD_LOG, for the user to refine.
// Figures come from config.json and corpus.json, never typed here. No DOM: Node's tests import this file.

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
  'November', 'December'];
const SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve'];

// A calendar date as written, "2026-06-29", never converted between zones (T2.2; brief §10.7: dates from the
// corpus and Exa are dates, not instants).
export function longDate(iso) {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return `${MONTHS[m - 1]} ${d}, ${y}`;
}
export function shortDate(iso) {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return `${SHORT[m - 1]} ${d}, ${y}`;
}
// A recorded time carries its offset (contract §6: Chicago ISO); its date part is the Chicago date.
export function chicagoDate(isoWithOffset) { return shortDate(isoWithOffset); }
export function year(iso) { return iso.slice(0, 4); }
export function capitalWord(n) { const w = WORDS[n] ?? String(n); return w[0].toUpperCase() + w.slice(1); }
export function num(n) { return Math.round(n).toLocaleString('en-US'); }
export function plural(n, one, many) { return `${num(n)} ${n === 1 ? one : (many ?? one + 's')}`; }
export function minutesWord(s) { return s % 60 === 0 ? String(s / 60) : (s / 60).toFixed(1); }
function hoursPhrase(s) { return s % 3600 === 0 ? plural(s / 3600, 'hour') : plural(Math.round(s / 60), 'minute'); }
function overPhrase(s) { return s === 60 ? 'over a minute' : s % 60 === 0 ? `over ${plural(s / 60, 'minute')}` : `over ${plural(s, 'second')}`; }

export const REPO_URL = 'https://github.com/NguyenTran2002/probable-clause';

// ---------- T5.1, the standing lines ----------
// two lines (the user's wording, Oct 25, 2026): the lead in bold, then the rest, quieter, with its last two words marked
export function pitch(corpus) {
  return {
    lead: 'See Claude Citations in action. Ask anything about the Fourth Amendment and surveillance technology, from wiretaps to phone location data.',
    more: [`Claude searches ${num(corpus.case_count)} Supreme Court cases, keeps the passages that bear on your question, and writes an answer with `, { em: 'precise citations' }, '.'],
  };
}
// the first screen's pointer to the figure below it, and the figure's heading
export const HOW_IT_WORKS = 'How the citations work';
export const TRACE_CAPTION = 'Each cited sentence carries a citation the Claude API returned: which kept passage it rests on, and exactly which of that passage’s sentences. Follow one from the answer, to those sentences in the passage, to the part of the API response that links them.';
export const NOT_ADVICE = 'Research, not legal advice: it shows what the Court said and never applies it to your situation. It does not tell you whether a case is still good law, and it can miss relevant passages.';
export const AI_DISCLOSURE = 'This is AI. Claude, Anthropic’s AI model, does the research and writes the answers through the Claude API. Check what it says against the opinions and linked sources before relying on it.';
export const AFFILIATION = 'Independent project. Not affiliated with Anthropic.';
export const REPO_LINK_TEXT = 'Source code on GitHub';   // one of three links on a line, so no full stop
export function creditsSources(corpus) {
  const c = corpus.source_counts;
  return [
    'Opinion text: ', `${num(c.courtlistener)} cases from CourtListener (Free Law Project), ${num(c.us_reports)} from the official U.S. Reports on GovInfo (U.S. Government Publishing Office), and `,
    { i: 'Chatrie' }, ' from the Court’s slip opinion (supremecourt.gov). Free Law Project did not produce, review or endorse this analysis.',
  ];
}
// T5.1 #6 follows T1.8, which P4.20 amends: answers are on Sonnet 5.5 too (step 0's call, BUILD_LOG 16:52).
export const CREDITS_BUILT = 'Built with the Claude API (research and answers on Claude Sonnet 5.5), Voyage AI for meaning search (voyage-law-2, rerank-3), and Exa’s MCP server for the update check.';
export const CREDITS_LICENCE = 'Code under the Apache License 2.0. The opinion text is public domain and not covered by that licence.';
export const READER_CREDIT = {
  courtlistener: 'Text from CourtListener (Free Law Project), checked against the official U.S. Reports. Unofficial.',
  us_reports: 'Text from the official U.S. Reports (GovInfo), normalised. Unofficial.',
  slip_opinion: 'Text from the Court’s slip opinion (supremecourt.gov), subject to formal revision. Unofficial.',
};

// ---------- T5.2 ----------
export const GUARANTEE = 'This passage appears word for word in this opinion, as normalised from the official text.';
export function coverageLine(corpus) {
  return `The corpus holds ${num(corpus.case_count)} Supreme Court cases decided from ${year(corpus.earliest_decided)} to ${longDate(corpus.coverage.latest_decision_in_corpus)}, pulled from its sources ${shortDate(corpus.coverage.ingested)}.`;
}
export function coverageDates(cov) {
  return `Latest decision in everything pulled: ${longDate(cov.latest_decision_full_pull)}. Latest in the corpus: ${longDate(cov.latest_decision_in_corpus)}. Pulled: ${shortDate(cov.ingested)}.`;
}
export const ANSWER_KEY = 'Underlined sentences cite a passage Claude kept; hover or tap one to see the exact sentences it cites. A citation shows where the words are, not that they prove the point, so read the passage. Sentences without a line are Claude’s own synthesis and have no source.';
export const FLAG_QUOTATION = 'Quotation not found in the passages Claude kept. Check it against the opinions before relying on it.';
export function flagCitation(corpus) {
  return `Not in this corpus. This check knows only the ${num(corpus.case_count)} cases here, so a real case outside them is flagged too.`;
}
export function costLine(t) {
  const calls = t.claude.calls + t.exa.searches;
  return `This run: ${plural(calls, 'call')} · ${num(t.claude.input_tokens)} input tokens, ${num(t.claude.cache_read_tokens)} from cache · ${num(t.claude.output_tokens)} output · about ${usd(totalUsd(t))} at list prices (Claude and Exa).`;
}
export function totalUsd(t) {
  const c = t.claude.cost_usd;
  return (c.loop || 0) + (c.update || 0) + (c.composition || 0) + (t.exa.cost_usd || 0);
}
export function usd(x) { return x < 0.005 && x > 0 ? '$' + x.toFixed(3) : '$' + x.toFixed(2); }
// Expanded: T5.2 #5's three parts, with the update check as its own part (step 0's call under P4.31).
export function costParts(t) {
  const c = t.claude.cost_usd;
  return [['Research (Claude)', c.loop || 0], ['Update check (Claude)', c.update || 0], ['Answer (Claude)', c.composition || 0],
    [`Exa (${plural(t.exa.searches, 'search', 'searches')})`, t.exa.cost_usd || 0]];
}
export const COST_NOTE = 'Computed by this site from each response’s token counts and the providers’ list prices; not an invoice. Voyage AI, used for meaning search, is not included.';
export const COST_REPLAY = date => `Recorded ${date}, priced at that date’s list prices.`;
export const TEXT_STATUS = 'The opinion text is unofficial; only the U.S. Reports are authoritative. It was normalised from the sources above: page numbers and running heads were removed (U.S. Reports pages are shown in the margin instead), words broken across lines were rejoined, and every quotation mark was made straight. The syllabus, counsel listings and lineup are left out, since they are not the Court’s words. A few misreadings in the sources were corrected against the printed page.';

// ---------- T5.3, the update-check band ----------
export const BAND_HEADING = 'Update check';
export const BAND_HONESTY = 'A convenience, kept apart from the evidence above. Claude searched the web for later developments, with the settings listed below. Finding nothing does not mean nothing has changed: a web search can miss pages, and a date filter skips pages with no published date.';
export const BAND_GUARANTEE = 'Each statement is Claude’s own summary, linked to the pages it names. This site’s code confirms only that those pages came back from the search in this run, not that they say what the statement reports. Open the links to check.';
export const BAND_FINDINGS = 'What the search found, in Claude’s words';
export const BAND_OVERVIEW = 'Claude’s overview (its own synthesis)';
export const BAND_SETTINGS = 'Settings Claude chose';
export const NOT_SET = 'not set';
export function bandFixed(cfg) {
  return `Set by this site: up to ${num(cfg.EXA_NUM_RESULTS_DEFAULT)} results a search, at most ${num(cfg.UPDATE_SEARCHES_PER_RUN)} searches a run, each page’s text cut at ${num(cfg.EXA_TEXT_CHARS)} characters before Claude reads it, no Exa highlights or summaries.`;
}
export const BAND_ALL_PAGES = n => `Every page the search returned (${num(n)}), including those Claude did not mention`;
export function pageLine(p) {
  return [p.title, p.domain, p.published ? `published ${longDate(p.published)} (Exa’s estimate)` : 'no published date'];
}
export const BAND_NOTHING = 'Nothing relevant found. That does not mean nothing has changed.';
export const BAND_SKIPPED = reason => `Update check skipped: ${reason}`;
export const CLAUDES_REASON = reason => `Claude’s reason: ${reason}`;
export const BAND_INCOMPLETE = 'This search did not complete; nothing came back.';
export const BAND_NOT_SUMMARISED = 'Not summarised: the run stopped before Claude summarised these searches. The pages they returned are listed below.';
const UNAVAILABLE = 'Update check unavailable';
// T5.3's two lines, then step 0's for the update step's own stops and errors (main session's, BUILD_LOG 16:52).
export function bandUnavailable(reason) {
  const lines = {
    no_credit: `${UNAVAILABLE}: this month’s web search credit is used up. It returns on the 1st.`,
    key_refused: `${UNAVAILABLE}: the web search service refused this site’s key.`,
    update_step_limit: `${UNAVAILABLE}: it stopped at its step limit before summarising.`,
    update_time_limit: `${UNAVAILABLE}: the run reached its time limit first.`,
    update_token_ceiling_input: `${UNAVAILABLE}: it reached its token limit.`,
    update_token_ceiling_output: `${UNAVAILABLE}: it reached its token limit.`,
  };
  if (lines[reason]) return lines[reason];
  if (['console_spend_limit', 'tier_spend_cap', 'spend_limit', 'spend_cap'].includes(reason)) {
    return `${UNAVAILABLE}: this site’s monthly API spending limit was reached.`;
  }
  const words = T54_WORDS[reason];
  return words ? `${UNAVAILABLE}: the check failed (${words}).` : `${UNAVAILABLE}.`;
}
export const BAND_POINTER = 'The update check found later material that may bear on this. It is not part of the evidence for this answer; see the update check above.';
export const WEB_SEARCHING = 'Searching the web for later developments';
export function webSearched(n, k) {
  return `Searched the web: ${plural(n, 'page')} returned, ${num(k)} with no published date. Linked in the update check, never quoted.`;
}
// The search statuses that are not ok (T2.4), in the step log; main session's except "did not complete" (T5.3).
export const WEB_STATUS = {
  refused_by_us: 'Not sent: this site refused the search as written.',
  refused_by_exa: 'The search service refused the search.',
  failed: BAND_INCOMPLETE,
  unavailable: UNAVAILABLE + '.',
};

// ---------- T5.4, run states and stop labels ----------
export const WAKING = 'Starting the research server';
export const seconds = s => `${num(s)} s`;
export const WAKE_LONG = 'This is taking longer than usual. After a quiet spell the server starts from cold. While you wait, you can watch a recorded run:';
export const WAKE_GAVE_UP = 'The research server did not start. Try again, or watch a recorded run.';
export const TRY_AGAIN = 'Try again';
export const WAKE_LONG_NONE = 'This is taking longer than usual. After a quiet spell the server starts from cold.';
export const WAKE_GAVE_UP_NONE = 'The research server did not start. Try again.';
export const PAUSED_DAY = 'Live research is paused for today. Recorded runs are still available. It reopens at midnight, Chicago time.';
export const PAUSED_MONTH = 'Live research is paused for the rest of this month. Recorded runs are still available. It reopens on the 1st.';
export const ATLAS_UNREACHABLE = 'Live research is unavailable right now: this site cannot reach its spending records, so it will not start a paid run. Recorded runs are still available.';
export const SPEND_LIMIT_ENDED = 'The run ended: this site’s monthly API spending limit was reached. Live research is paused; recorded runs are still available.';
// POST /runs refusals T5.4 has no line for: contract §5's texts (v2.0, the main session's, design §5).
export function busy(cfg) {
  return `${capitalWord(cfg.MAX_CONCURRENT_RUNS)} questions are being researched right now, the most this site handles at once. Please try again in a minute.`;
}
export const RECONNECTING = 'Reconnecting…';
export const PAUSED = 'Paused while this page was away. No new calls were made.';
export const RESUMED = 'Resumed.';
export function abandoned(cfg) {
  return `This run stopped because the page was away for ${overPhrase(cfg.ABANDON_AFTER_S)}. No answer was written, and nothing more was spent. What was gathered is shown above.`;
}
export const INTERRUPTED = 'This run was interrupted: the server that held it is no longer running. The steps it recorded are shown above. Ask again to start a new run.';
export function expired(cfg) { return `This run is no longer stored. Runs are kept for ${hoursPhrase(cfg.EVENTS_TTL_S)}.`; }
// T5.4 #4's four words; the band uses only these (BUILD_LOG 16:52)
const T54_WORDS = { overloaded: 'overloaded', rate_limited: 'rate limited', server_error: 'server error', gateway_timeout: 'server error',
  connection: 'connection lost', stream_broken: 'connection lost' };
// T5.4's four, then the main session's words for the kinds a retry line or a failure line still has to name
export const FAILURE_WORDS = { overloaded: 'overloaded', rate_limited: 'rate limited', server_error: 'server error',
  gateway_timeout: 'server error', connection: 'connection lost', stream_broken: 'connection lost', timeout: 'timed out',
  deadline: 'timed out', internal: 'an error on this site', unreadable: 'an unreadable reply', protocol: 'connection lost' };
export function failureWords(kind) { return FAILURE_WORDS[kind] || 'an error'; }
export function retryLine(pc) {
  const who = pc.service === 'voyage' ? 'Meaning search call' : 'Claude call';
  return `${who} failed (${failureWords(pc.error_kind)}); retrying, attempt ${pc.attempt + 1} of ${pc.max_attempts}`;
}
export const outOfRetries = max => `Failed after ${num(max)} attempts.`;
export const NOT_RERANKED = 'Results in embedding order: reranking failed.';
export const REFUSAL_ENDED = 'The run ended: Claude declined to continue with this question.';
export const VOYAGE_DEGRADED = 'Meaning search was degraded for part of this research: some results were not reranked.';
export const VOYAGE_UNAVAILABLE = 'Meaning search was unavailable for part of this research, so Claude searched by keyword only for that part.';
export const STOP_TOP = {
  step_limit: 'Stopped at step limit. Answer built from the evidence gathered so far.',
  token_ceiling: 'Stopped at this run’s token limit. Answer built from the evidence gathered so far.',
  error_stopped: 'Stopped by an error after retries. Answer built from the evidence gathered so far.',
};
export function stopTop(state, cfg) {
  if (state === 'time_limit') return `Stopped at this run’s ${minutesWord(cfg.RUN_DEADLINE_S)}-minute time limit. Answer built from the evidence gathered so far.`;
  return STOP_TOP[state] || null;
}
export function stopNothingKept(state, cfg) {
  const limit = { step_limit: 'the step limit', token_ceiling: 'this run’s token limit',
    time_limit: `this run’s ${minutesWord(cfg.RUN_DEADLINE_S)}-minute time limit`, error_stopped: 'an error after retries' }[state];
  return `Stopped at ${limit} before Claude kept any passages, so no answer was written.`;
}
export const CUT_OFF = 'Cut off at the answer’s length limit.';
// T5.4's line without its sentence on the checks (P4.34)
export const INCOMPLETE = 'Incomplete: the answer stopped partway because of an error.';
export const COMPOSITION_FAILED = reason => `The answer could not be written: ${reason}. The passages Claude kept are still in the sources panel. Asking again starts a new run.`;
export const FAILED_NOTHING_KEPT = reason => `The run failed: ${reason}. Nothing was kept, so no answer was written.`;
export const NO_SOURCES_LABEL = 'Claude’s reply · no sources';
export const OUT_OF_SCOPE = 'This question is outside what the corpus covers: Supreme Court opinions on the Fourth Amendment and surveillance technology.';
export const NOTHING_FOUND = 'Claude found no passages in the corpus that bear on this question.';
export const REPLAY_BANNER = date => `Recorded run, ${date}. A real run, replayed at its recorded pace. It makes no new calls.`;
export const FROM_SCRATCH = 'Each question is researched from scratch; Claude does not see your earlier questions.';
export const REFUSED_TITLE = 'Submission refused by this site’s rules';
export const finished = (rounds, s) => `Finished: ${plural(rounds, 'tool round')} and the answer, ${num(s)} s.`;
// main session's: T5.4 #9's line for a no-sources reply, and the label for an answer cut short by a failed or
// interrupted run; neither label mentions the checks (P4.34)
export const finishedReply = (rounds, s) => `Finished: ${plural(rounds, 'tool round')} and Claude\u2019s reply, ${num(s)} s.`;
export const PARTIAL_UNCHECKED = 'Incomplete: the run ended before the answer was finished.';
// T5.6 #2's label for the replay recorded on the corpus without Chatrie.
export const BEFORE_CHATRIE = ['Recorded with a corpus that ends before ', { i: 'Chatrie v. United States' }, ' (June 29, 2026), to show the update check finding it. Live research uses the full corpus.'];

// ---------- T5.5, the privacy note: each provider's name links to the page its claim comes from ----------
export const PRIVACY = [
  [{ b: 'Privacy.' }, ' Your question is sent to ', { a: 'Anthropic', href: 'https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data' },
    ', whose Claude model researches and answers it; Anthropic deletes it within 30 days, unless its safety systems flag it (up to 2 years) or the law requires otherwise. Claude’s searches go to ',
    { a: 'Voyage AI', href: 'https://www.voyageai.com/terms-of-service' }, ' (meaning search; opted out of training Voyage’s future models) and, for the update check, to ',
    { a: 'Exa', href: 'https://exa.ai/privacy-policy' }, ', which may keep and use search queries to improve its services; Claude is told to leave personal details out of them. Avoid putting anything in a question you would not want stored.'],
  ['This site keeps each run’s steps, your question and the answer for 24 hours, so a dropped connection can resume, then deletes them. It keeps a record of each run without the question or answer (times, steps, tokens and cost) to track spending. No accounts, no cookies, no analytics; your browser holds only the current run’s ID, until you close the tab. This site does not use or store IP addresses; the gateway in front of it and ',
    { a: 'Google Cloud', href: 'https://docs.cloud.google.com/logging/docs/store-log-entries' }, ' keep standard request logs, which include them, for 30 days. Recorded runs use questions chosen by the site’s author; no visitor’s run is ever recorded.'],
];

// ---------- the main session's lines (P4.31), where T5 has none ----------
export const OR_WATCH = 'Or watch a recorded run';
export const RESEARCH = 'Research';
export const ASK_PLACEHOLDER = 'Can police get my phone’s location history from my carrier without a warrant?';
export const ASK_ANOTHER = 'Ask another question';
export const WORKING = 'Working…';
export const SKIP = 'Skip to the end';
export const SOURCES = 'Sources';
export const CONVERSATION = 'Conversation';
export const SOURCES_EMPTY = 'Passages appear here as Claude finds them.';
export const sourcesCount = (found, kept) => `${num(found)} found, ${num(kept)} kept`;
export const CREDITS_SUMMARY = 'Sources and credits';
export const PRIVACY_SUMMARY = 'Privacy';
export const PAGE_FAILURE = 'This page could not load its figures. Please try again in a minute.';
export const GROUP_ANSWER = 'Writing the answer';
export const GROUP_UPDATE = 'Update check, running beside the answer';
export const THINKING = 'Claude is thinking';           // the user's words, Oct 25, 2026
export const THOUGHT = 'Claude was thinking';          // shown only when the call needed a retry or failed
export const UPDATE_ONLY = 'Research finished with no passages kept, so no answer is written. The update check runs next.';
export const UPDATE_STARTED = n => `Research finished with ${plural(n, 'passage')} kept. The answer and the update check start side by side.`;
export const WRITING = n => `Writing the answer from ${plural(n, 'kept passage')}`;
export const WROTE = n => `Wrote the answer from ${plural(n, 'kept passage')}`;
export const WROTE_PART = 'Wrote part of the answer before an error';
export const WRITE_FAILED = 'The answer could not be written';
export const WRITING_META = 'No tools in this call, so the only sources Claude can cite are the passages it kept.';
export const CHECKING = 'Checking the answer';
export const CHECKED = 'Checked the answer';
export const NOT_FINISHED = 'Not finished: the run ended first.';
export const STEP_STOPPED = 'Stopped before it finished.';
export const ANSWER_HEADING = 'Answer';
export const ANSWER_BY = 'Written by Claude from the passages it kept.';
export const WHOSE_NOTE = 'Claude’s note on the question’s scope';
export const UPDATE_STEP_ENDED = {
  submitted: 'Update check finished.', stopped: 'Update check stopped before Claude summarised it.',
  failed: 'Update check failed.', abandoned: 'Update check stopped: the page was away.',
};
export const runStatus = {
  research: line => `Research · ${line}`,
  both: 'Writing the answer · the update check runs beside it',
  answer: 'Writing the answer',
  update: 'Update check \u00b7 the answer is written',
  updateOnly: 'Update check',
};
export const ENDED_STATUS = s => `Stopped after ${num(s)} s.`;
export const REPLAY_STATUS = date => `Recorded run, ${date}`;
export const GENERAL_FAILURE = 'Something went wrong on this site, and the question was not started. Please try again in a minute.';
export const QUESTION_EMPTY = 'Type a question first.';
export const questionTooLong = cfg => `Questions are limited to ${num(cfg.QUESTION_MAX_CHARS)} characters.`;
export const ONE_PER_RUN_HINT = FROM_SCRATCH;
export const STEP_TITLES = {
  search_meaning: ['Searching by meaning', 'Searched by meaning'],
  search_exact: ['Searching for exact words', 'Searched for exact words'],
  read_passages: ['Reading in the opinion', 'Read in the opinion'],
  keep_passages: ['Keeping passages', 'Kept passages'],
  submit_answer: ['Finishing research', 'Finished research'],
  search_web_updates: [WEB_SEARCHING, 'Searched the web'],
  submit_update: ['Summarising the update check', 'Summarised the update check'],
};
export const WRONG_STEP_TITLE = 'Refused: not this step’s tool';
export const TOOL_ERROR_TITLE = 'Refused by this site’s checks';
export const FOUND_BY = 'Found by ';
export const MATCHED = (n, again) => `${plural(n, 'passage')} returned${again ? `, ${num(again)} seen before` : ''}`;
export const API_BUTTON = 'View API calls';
export const READ_BUTTON = 'View source';
export const SHOW = 'Show passage';
export const HIDE = 'Hide passage';
export const MARK = { found: 'Found', kept: 'Kept', cited: 'Kept, cited', uncited: 'Kept, not cited', notkept: 'Not kept' };
export const SLIP_NOTE = 'Slip opinion: not yet final in the U.S. Reports, and subject to formal revision.';
export const FOOTNOTES_IN = n => `${plural(n, 'footnote')} in this paragraph`;
export const API_TITLE = id => `${id}: the API calls behind this source`;
export const API_SUB = 'Every Messages API exchange that touched this passage, exactly as sent and received.';
export const API_SOURCE = 'The source as shown';
export const API_TRAFFIC = 'API traffic';
export const API_NOT_KEPT = 'Not sent to the composition call. Claude did not keep this passage, so the call that writes the answer never saw it and cannot cite it.';
export const API_STILL = 'The run is still working. More exchanges appear here as it goes.';
export const API_USAGE = 'usage, as Claude reported it for this response';
export const API_ESTIMATED = 'Our estimate of this attempt’s tokens (it reported none); not Claude’s usage';
export const READER_JUMP = 'Back to the excerpt';
export const CLOSE = 'Close';
export const READER_LOADING = 'Loading the opinion…';
export const READER_FAILED = 'The opinion could not be loaded. Try again in a moment.';
export const EXCERPT = (id, lit) => lit ? `The passage Claude retrieved, ${id}. The sentences the answer cites are lit.` : `The passage Claude retrieved, ${id}.`;
export const PAGE_WORD = slip => slip ? 'Slip opinion page' : 'U.S. Reports page';
export const FOOTNOTES_HEADING = 'Footnotes';

// ---------- a passage's or opinion's lineup and pages (main session's; per curiam and "not printed": P1.18) ----------
const TYPE_LABEL = { majority: 'Majority opinion', plurality: 'Plurality opinion' };
export function typeLabel(type) { return TYPE_LABEL[type] || type[0].toUpperCase() + type.slice(1); }
export function andList(xs) { return xs.length <= 1 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`; }
export function lineup(p) {
  if (p.joined_by_source === 'per curiam' || !p.authors.length) return `${typeLabel(p.opinion_type ?? p.type)}, per curiam.`;
  const head = `${typeLabel(p.opinion_type ?? p.type)} by ${andList(p.authors)}`;
  if (p.joined_by.length) return `${head}, joined by ${andList(p.joined_by)}.`;
  if (p.joined_by_source === 'not printed') return `${head}. Who joined is not printed in the source.`;
  return `${head}, joined by no other Justice.`;
}
export function pin(p) {
  const pages = p.page_end && p.page_end !== p.page_start ? `${p.page_start}–${p.page_end}` : `${p.page_start}`;
  if (p.slip_opinion) return `slip op., at ${pages}`;
  return `${p.citation.replace(/\s+\d+$/, '')}, at ${pages}`;
}
export const decided = iso => `Decided ${longDate(iso)}.`;
export function footnoteLabel(p) { return `Footnote ${p.footnote_label}`; }
