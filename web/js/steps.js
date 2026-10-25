// The step log (T4.1, T4.3, T4.4; step 0's call under P4.31): research's steps, then two groups stacked in the one
// column, "Writing the answer" and "Update check, running beside the answer", each with its own spinner. Items come
// from the run model; each one's element is kept and refreshed in place, so nothing already shown moves.

import { h, fresh, clear } from './dom.js';
import { callVisible, hueOf } from './model.js';
import { quoted } from './sources.js';
import * as T from './text.js';

const WITHHELD = /(\[statement withheld: it repeated a page's words\]|\[field withheld [^\]]*\])/;

// Text that may carry the copy guard's withheld markers (contract §4.G.2): shown as it is, in the muted style.
export function withheld(str) {
  return String(str).split(WITHHELD).filter(s => s !== '').map(s => (WITHHELD.test(s) ? h('span', { class: 'withheld' }, s) : s));
}

export function createSteps(container, { cfg, onGoto }) {
  const els = new Map();       // item -> {li, sig}
  let groups = null;            // {composition: {sec, ol, head}, update: {...}}
  const research = h('ol', { class: 'steps', attrs: { 'aria-label': 'Research steps' } });
  const pre = h('ol', { class: 'steps pre' });     // the waking step and refusals before any event
  const post = h('ol', { class: 'steps post' });   // the run's last step
  container.append(pre, research);
  const tail = h('div', { class: 'groups' });
  container.append(tail, post);
  const pages = new Map();      // web page id -> page, for counting a search's undated pages

  function group(key, title) {
    const head = h('h3', { class: 'group-head working' }, title);
    const ol = h('ol', { class: 'steps' });
    const sec = h('section', { class: 'group', attrs: { 'aria-label': title } }, head, ol);
    return { sec, ol, head };
  }

  function ensureGroups(run) {
    if (groups || !run.researchDone) return;
    if (!run.composition.started && !run.update.started) return;
    groups = {};
    if (run.update.started) {
      groups.composition = group('composition', T.GROUP_ANSWER);
      groups.update = group('update', T.GROUP_UPDATE);
      tail.append(fresh(h('p', { class: 'group-intro' }, T.UPDATE_STARTED(run.update.kept.length))),
        groups.composition.sec, groups.update.sec);
    } else {
      groups.composition = { ol: research };           // only the answer follows: no groups to tell apart
    }
  }

  function listEl(step) {
    if (step === 'research') return research;
    if (!groups) return research;
    return (groups[step] || groups.composition).ol;
  }

  function sync(run) {
    ensureGroups(run);
    for (const [step, list] of Object.entries(run.lists)) {
      for (const it of list) {
        const show = it.type !== 'call' || callVisible(it);
        const sig = signature(run, it);
        let rec = els.get(it);
        if (!show) { if (rec) { rec.li.remove(); els.delete(it); } continue; }
        if (!rec) {
          const li = h('li', { class: 'step' });
          rec = { li, sig: null };
          els.set(it, rec);
          // a Claude call's item sits before the tools it led to
          const parent = listEl(step);
          parent.append(fresh(li));
        }
        if (rec.sig !== sig) { render(run, it, rec.li); rec.sig = sig; }
      }
    }
    if (groups && groups.update) {
      groups.composition.head.classList.toggle('working', run.open.composition);
      groups.update.head.classList.toggle('working', run.open.update);
    }
  }

  function signature(run, it) {
    const kept = it.result && it.result.found ? it.result.found.map(id => hueOf(run, id)).join() : '';
    return `${it.state}|${it.lines.length}|${it.result ? 1 : 0}|${kept}|${run.keepOrder.length}|${run.blocks.length}`;
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
    } else if (it.type === 'composition') {
      li.append(h('h3', null, it.state === 'working' ? T.WRITING(it.documents) : T.WROTE(it.documents)),
        h('p', { class: 'meta' }, T.WRITING_META));
    } else if (it.type === 'checks') {
      li.append(h('h3', null, T.CHECKED));
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
      class: `pill ${hueOf(run, id) || ''}`.trim(), attrs: { type: 'button', 'data-goto': id }, on: { click: () => onGoto(id) },
    }, id)));
  }

  function renderTool(run, it, li) {
    const r = it.result;
    const [working, done] = T.STEP_TITLES[it.name] || [it.name, it.name];
    const refusedSubmit = r && r.submit && !r.submit.accepted;
    let title = it.state === 'working' || it.state === 'stopped' ? working : done;
    if (refusedSubmit) title = T.REFUSED_TITLE;
    else if (r && r.wrong_step) title = T.WRONG_STEP_TITLE;
    else if (r && r.is_error && it.name !== 'search_web_updates') title = T.TOOL_ERROR_TITLE;
    const head = h('h3', null, title);
    li.append(head);
    const inp = it.input || {};
    switch (it.name) {
      case 'search_meaning':
        if (inp.query != null) li.append(h('p', { class: 'query' }, '“', ...withheld(inp.query), '”'));
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
      case 'read_passages':
        li.append(h('p', { class: 'query mono' }, ...withheld(String(inp.target ?? ''))),
          h('p', { class: 'meta' }, `${inp.before ? `${inp.before} before` : 'none before'}, ${inp.after ? `${inp.after} after` : 'none after'}`));
        break;
      case 'search_web_updates':
        li.append(h('p', { class: 'query' }, '“', ...withheld(String(inp.query ?? '')), '”'),
          h('p', { class: 'meta' }, webMeta(inp)));
        break;
      case 'submit_answer':
        if (inp.note != null) li.append(h('p', { class: 'say' }, ...withheld(String(inp.note))));
        break;
      case 'submit_update':
        if (Array.isArray(inp.update_findings)) {
          li.append(h('ul', { class: 'said' }, inp.update_findings.map(f => h('li', null,
            ...withheld(typeof f === 'object' && f ? String(f.statement ?? '') : String(f)),
            f && Array.isArray(f.sources) && f.sources.length ? h('span', { class: 'mono src' }, ` ${f.sources.join(', ')}`) : null))));
        }
        if (inp.update_overview != null) li.append(h('p', { class: 'say' }, ...withheld(String(inp.update_overview))));
        if (inp.update_skip_reason != null) li.append(h('p', { class: 'say' }, ...withheld(String(inp.update_skip_reason))));
        break;
      default:
        break;
    }
    if (!r) return;
    if (refusedSubmit || r.wrong_step || (r.is_error && it.name !== 'search_web_updates')) {
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
    } else if (it.name === 'search_web_updates') {
      for (const p of r.web || []) pages.set(p.id, p);
      if (r.web_status === 'ok') {
        const ids = [...(r.web || []).map(p => p.id), ...(r.web_repeats || [])];
        const undated = ids.filter(id => pages.get(id) && !pages.get(id).published).length;
        const line = T.webSearched(ids.length, undated);
        const cut = line.indexOf(' Linked');
        head.textContent = line.slice(0, cut);
        li.append(h('p', { class: 'meta' }, line.slice(cut + 1)));
      } else {
        head.textContent = T.WEB_SEARCHING;
        li.append(h('p', { class: 'meta' }, T.WEB_STATUS[r.web_status] || T.BAND_INCOMPLETE));
        if (r.web_status === 'refused_by_us' || r.web_status === 'refused_by_exa') li.append(h('p', { class: 'refused' }, ...withheld(r.content || '')));
      }
      li.append(h('p', { class: 'meta' }, T.bandFixed(cfg)));
    }
  }

  function stateClass(s) {
    return { working: 'working', done: 'done', rejected: 'rejected', failed: 'rejected', stopped: 'stopped' }[s] || 'done';
  }

  // the run's first step, before any event: waking (T4.4 #1)
  function waking() {
    const li = h('li', { class: 'step working' }, h('h3', null, T.WAKING));
    pre.append(fresh(li));
    return {
      long(chipsEl) { if (!li.querySelector('.wake-long')) li.append(h('p', { class: 'meta wake-long' }, T.WAKE_LONG), chipsEl); },
      done() { li.className = 'step done'; },
      gaveUp(onTry, chipsEl) {
        li.className = 'step rejected';
        li.querySelectorAll('.wake-long, .chips-replay').forEach(e => e.remove());
        li.append(h('p', { class: 'meta' }, T.WAKE_GAVE_UP), h('p', { class: 'actions' }, h('button', { class: 'ghost', attrs: { type: 'button' }, on: { click: onTry } }, T.TRY_AGAIN)), chipsEl);
      },
      remove() { li.remove(); },
    };
  }

  // the run's last step: a refusal, an end the visitor must be told about (T4.4 #2, #5)
  function last(text, kind = 'rejected') {
    post.append(fresh(h('li', { class: `step ${kind}` }, h('h3', null, text))));
  }

  return { sync, waking, last, pre, post };
}

function searchMeta(inp) {
  const f = inp.filters || {};
  const bits = [];
  if (f.cases) bits.push(`cases ${f.cases.join(', ')}`);
  if (f.decided_from) bits.push(`decided from ${f.decided_from}`);
  if (f.decided_to) bits.push(`decided to ${f.decided_to}`);
  if (f.opinion_types) bits.push(`opinion types ${f.opinion_types.join(', ')}`);
  if (f.authors) bits.push(`authors ${f.authors.join(', ')}`);
  if (f.none_of) bits.push(`none of ${f.none_of.join(', ')}`);
  if (f.include_footnotes === false) bits.push('no footnotes');
  if (inp.max_results != null) bits.push(`up to ${inp.max_results} results`);
  return bits.join(' · ');
}

function webMeta(inp) {
  const v = x => (x == null || (Array.isArray(x) && !x.length) ? T.NOT_SET : Array.isArray(x) ? x.join(', ') : String(x));
  return [`published from ${v(inp.start_published_date)}`, `to ${v(inp.end_published_date)}`, `category ${v(inp.category)}`,
    `type ${v(inp.type)}`, `results ${v(inp.num_results)}`, `include domains ${v(inp.include_domains)}`,
    `exclude domains ${v(inp.exclude_domains)}`].join(' · ');
}
