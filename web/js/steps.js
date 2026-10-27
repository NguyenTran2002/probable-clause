// The step log (T4.1, T4.3, T4.4; step 0's call under P4.31): research's steps only. The answer writing itself below
// and the later-developments box are progress enough, so neither has steps here (the user, round 23, Oct 26, 2026);
// a pause or resume after research still shows. Items come from the run model; each one's element is kept and
// refreshed in place, so nothing already shown moves.

import { h, fresh, clear } from './dom.js';
import { callVisible, hueOf, tagOf, readTarget } from './model.js';
import { quoted } from './sources.js';
import * as T from './text.js';

const WITHHELD = /(\[statement withheld: it repeated a page's words\]|\[field withheld [^\]]*\])/;

// Text that may carry the copy guard's withheld markers (contract §4.G.2): shown as it is, in the muted style.
export function withheld(str) {
  return String(str).split(WITHHELD).filter(s => s !== '').map(s => (WITHHELD.test(s) ? h('span', { class: 'withheld' }, s) : s));
}

export function createSteps(container, { onGoto }) {
  const els = new Map();       // item -> {li, sig}
  const research = h('ol', { class: 'steps', attrs: { 'aria-label': 'Research steps' } });
  const pre = h('ol', { class: 'steps pre' });     // the waking step and refusals before any event
  const post = h('ol', { class: 'steps post' });   // the run's last step
  container.append(pre, research, post);
  let wakeLi = null;   // the waking step, until research's first step takes its place

  function sync(run) {
    for (const [step, list] of Object.entries(run.lists)) {
      for (const it of list) {
        const show = step === 'research' ? it.type !== 'call' || callVisible(it) : it.type === 'paused' || it.type === 'resumed';
        const sig = signature(run, it);
        let rec = els.get(it);
        if (!show) { if (rec) { rec.li.remove(); els.delete(it); } continue; }
        if (!rec) {
          const li = h('li', { class: 'step' });
          rec = { li, sig: null };
          els.set(it, rec);
          // a Claude call's item sits before the tools it led to
          research.append(fresh(li));
          if (wakeLi) { wakeLi.remove(); wakeLi = null; }
        }
        if (rec.sig !== sig) { render(run, it, rec.li); rec.sig = sig; }
      }
    }
  }

  // what an item shows, so it is redrawn only when that changes (a redraw would drop keyboard focus from its chips)
  function signature(run, it) {
    const r = it.result;
    const ids = r ? [...(r.found || []), ...(r.read || []), ...(r.kept || []).map(k => k.id)] : [];
    return `${it.state}|${it.lines.length}|${r ? 1 : 0}|${ids.map(id => hueOf(run, id)).join()}`;
  }

  function render(run, it, li) {
    li.className = `step ${stateClass(it.state)}`;
    clear(li);
    if (it.type === 'call') {
      li.append(h('h3', null, it.state === 'working' ? T.THINKING : T.THOUGHT));
    } else if (it.type === 'paused') {
      li.append(h('h3', null, T.PAUSED));
    } else if (it.type === 'resumed') {
      li.append(h('h3', null, T.RESUMED));
    } else if (it.type === 'tool') {
      renderTool(run, it, li);
    }
    for (const l of it.lines) {
      if (l.kind === 'retry') li.append(h('p', { class: 'retry' }, T.retryLine(l.pc)));
      else if (l.kind === 'failed') li.append(h('p', { class: 'retry failed' }, T.outOfRetries(l.pc.max_attempts)));
      else if (l.kind === 'not_reranked') li.append(h('p', { class: 'retry' }, T.NOT_RERANKED));
    }
    if (it.state === 'stopped' && it.type === 'tool') li.append(h('p', { class: 'meta' }, T.NOT_FINISHED));
  }

  function chips(run, ids) {
    return h('p', { class: 'chips' }, ids.map(id => h('button', {
      class: `pill ${hueOf(run, id) || ''}`.trim(), attrs: { type: 'button', 'data-goto': id, title: id }, on: { click: () => onGoto(id) },
    }, tagOf(run, id))));
  }

  function renderTool(run, it, li) {
    const r = it.result;
    const [working, done] = T.STEP_TITLES[it.name] || [it.name, it.name];
    const refusedSubmit = r && r.submit && !r.submit.accepted;
    let title = it.state === 'working' || it.state === 'stopped' ? working : done;
    if (refusedSubmit) title = T.REFUSED_TITLE;
    else if (r && r.wrong_step) title = T.WRONG_STEP_TITLE;
    // a service that failed after its retries (meaning search unavailable) is not this site refusing the call
    const failedService = r && r.is_error && it.lines.some(l => l.kind === 'failed');
    if (failedService) title = done;
    else if (r && r.is_error) title = T.TOOL_ERROR_TITLE;
    const head = h('h3', null, title);
    li.append(head);
    const inp = it.input || {};
    switch (it.name) {
      case 'search_meaning':
        if (inp.query != null) li.append(queryLine(inp.query));
        li.append(h('p', { class: 'meta' }, searchMeta(inp)));
        break;
      case 'search_exact': {
        const parts = [];
        for (const [k, label] of [['all_of', 'all of'], ['any_of', 'any of'], ['none_of', 'none of']]) {
          if (Array.isArray(inp[k]) && inp[k].length) parts.push(`${label} ${inp[k].map(quoted).join(', ')}`);
        }
        if (parts.length) li.append(h('p', { class: 'query' }, ...withheld(parts.join(' · '))));
        li.append(h('p', { class: 'meta' }, searchMeta(inp)));
        break;
      }
      case 'read_passages': {
        // the target as a citation reads (P4.35), the ID Claude sent as its hover text
        const t = readTarget(run, String(inp.target ?? ''));
        li.append(h('p', { class: 'query', attrs: { title: inp.target } }, ...(t.tag ? [t.tag] : withheld(t.raw))),
          h('p', { class: 'meta' }, T.readAround(inp.before, inp.after, t.footnote)));
        break;
      }
      case 'submit_answer':
        if (inp.note != null) li.append(h('p', { class: 'say' }, ...withheld(String(inp.note))));
        break;
      default:
        break;
    }
    if (!r) return;
    if (failedService) { li.append(h('p', { class: 'meta' }, ...withheld(r.content || ''))); return; }
    if (refusedSubmit || r.wrong_step || r.is_error) {
      li.append(h('p', { class: 'refused' }, ...withheld(r.content || '')));
      return;
    }
    if (it.name === 'search_meaning' || it.name === 'search_exact') {
      li.append(h('p', { class: 'meta' }, T.MATCHED(r.found.length, r.matched_again.length)));
      if (r.found.length) li.append(chips(run, r.found));
    } else if (it.name === 'read_passages') {
      if (r.read && r.read.length) li.append(chips(run, r.read));
    } else if (it.name === 'keep_passages') {
      const ids = (r.kept || []).map(k => k.id);
      const again = (r.kept || []).filter(k => k.replaced).length;
      head.textContent = `${T.STEP_TITLES.keep_passages[1]}: ${ids.length}${again ? `, ${again} with a new reason` : ''}`;
      if (ids.length) li.append(chips(run, ids));
      if (r.refused && r.refused.length) li.append(h('p', { class: 'refused' }, ...withheld(r.content || '')));
    }
  }

  function stateClass(s) {
    return { working: 'working', done: 'done', rejected: 'rejected', failed: 'rejected', stopped: 'stopped' }[s] || 'done';
  }

  // the run's first step, before any event: waking (T4.4 #1). Unnumbered, like the run's last step (style.css), and
  // removed when research's first step shows, "Claude is thinking" included (the user, Oct 27, 2026)
  function waking() {
    const li = h('li', { class: 'step working' }, h('h3', null, T.WAKING));
    wakeLi = li;
    pre.append(fresh(li));
    return {
      // with no recorded runs to offer, the lines leave out their pointer to them (main session's trim of T5.4 #1)
      long(chipsEl) { if (!li.querySelector('.wake-long')) li.append(h('p', { class: 'meta wake-long' }, chipsEl ? T.WAKE_LONG : T.WAKE_LONG_NONE), chipsEl || ''); },
      done() { li.className = 'step done'; },
      gaveUp(onTry, chipsEl) {
        li.className = 'step rejected';
        li.querySelectorAll('.wake-long, .chips-replay').forEach(e => e.remove());
        li.append(h('p', { class: 'meta' }, chipsEl ? T.WAKE_GAVE_UP : T.WAKE_GAVE_UP_NONE), h('p', { class: 'actions' }, h('button', { class: 'ghost', attrs: { type: 'button' }, on: { click: onTry } }, T.TRY_AGAIN)), chipsEl || '');
      },
      remove() { li.remove(); if (wakeLi === li) wakeLi = null; },
    };
  }

  // the run's last step: a refusal, an end the visitor must be told about (T4.4 #2, #5)
  function last(text, kind = 'rejected') {
    post.append(fresh(h('li', { class: `step ${kind}` }, h('h3', null, text))));
  }

  return { sync, waking, last, pre, post };
}

// a query in quotation marks, as Claude sent it; a withheld one is shown as it is, never quoted as if searched for
function queryLine(q) {
  q = String(q);
  return WITHHELD.test(q) ? h('p', { class: 'query' }, ...withheld(q)) : h('p', { class: 'query' }, '\u201c', q, '\u201d');
}

function searchMeta(inp) {
  // the search tools are not strict (Claude's input is stored exactly as sent), so any field may be any type
  const f = inp.filters && typeof inp.filters === 'object' ? inp.filters : {};
  const list = x => (Array.isArray(x) ? x.join(', ') : String(x));
  const bits = [];
  if (f.cases != null) bits.push(`cases ${list(f.cases)}`);
  if (f.decided_from != null) bits.push(`decided from ${f.decided_from}`);
  if (f.decided_to != null) bits.push(`decided to ${f.decided_to}`);
  if (f.opinion_types != null) bits.push(`opinion types ${list(f.opinion_types)}`);
  if (f.authors != null) bits.push(`authors ${list(f.authors)}`);
  if (f.none_of != null) bits.push(`none of ${list(f.none_of)}`);
  if (f.include_footnotes === false) bits.push('no footnotes');
  if (inp.max_results != null) bits.push(`up to ${inp.max_results} results`);
  return bits.join(' \u00b7 ');
}
