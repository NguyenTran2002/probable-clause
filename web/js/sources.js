// The sources panel (T4.1, T4.3 #1 to #3): one card per passage a search or read returned, or Claude kept. A card
// starts Found and becomes Kept with Claude's reason; when the run is over it ends kept and cited (its hue), kept and
// not cited (its hue, labelled) or not kept (grey, folded to one line). A paragraph's attached footnotes sit folded
// inside its card. Hues follow keep order, four repeating, with the passage-ID pill to tell same-hued ones apart.

import { h, fresh, clear } from './dom.js';
import { cardState, hueOf } from './model.js';
import { rangesToUnits } from './cp.js';
import * as T from './text.js';

// The passage's text as sentence spans, so a citation can light exactly its sentences (T1.9).
export function sentenceSpans(p) {
  const units = rangesToUnits(p.text, p.sentences);
  return units.map(([a, b], i) => h('span', { class: 'sb', attrs: { 'data-s': i } }, p.text.slice(a, b)));
}

export function createSources({ list, countEl, tabCount, onApi, onRead }) {
  const cards = new Map();     // id -> {li, sig}

  function sync(run) {
    for (const id of run.cards) {
      const p = run.passages.get(id);
      if (!p) continue;
      const state = cardState(run, id);
      const keep = run.keeps.get(id);
      const sig = `${state}|${keep ? keep.reason : ''}|${hueOf(run, id)}|${(run.foundBy.get(id) || []).length}`;
      let rec = cards.get(id);
      if (!rec) {
        const li = h('li', { attrs: { id: `src-${id}`, 'data-id': id } });
        rec = { li, sig: null, open: false };
        cards.set(id, rec);
        list.append(fresh(li));
      }
      if (rec.sig !== sig) { render(run, id, p, state, rec); rec.sig = sig; }
    }
    const found = run.cards.length, kept = run.keepOrder.length;
    countEl.textContent = found ? T.sourcesCount(found, kept) : T.SOURCES_EMPTY;
    tabCount.textContent = found ? `${kept} of ${found}` : '';
  }

  function render(run, id, p, state, rec) {
    const li = rec.li;
    const hue = hueOf(run, id);
    // kept, cited and not cited share .kept (the hue stripe); the state itself is .st-<state>, never .cited, which
    // belongs to the answer's underlined sentences
    const cls = state === 'found' || state === 'notkept' ? state : `kept st-${state}`;
    li.className = `card ${cls}${hue ? ' ' + hue : ''}${rec.open ? ' open' : ''}`;
    clear(li);
    li.append(cardBody(run, id, p, state));
    const actions = h('div', { class: 'card-actions' },
      h('button', { class: 'ghost api-btn', attrs: { type: 'button' }, on: { click: () => onApi(id) } }, T.API_BUTTON),
      h('button', { class: 'ghost read-btn', attrs: { type: 'button' }, on: { click: () => onRead(id) } }, T.READ_BUTTON));
    if (state === 'notkept') {
      const t = h('button', { class: 'toggle', attrs: { type: 'button', 'aria-expanded': String(rec.open) } }, rec.open ? T.HIDE : T.SHOW);
      t.addEventListener('click', () => {
        rec.open = !rec.open;
        li.classList.toggle('open', rec.open);
        t.textContent = rec.open ? T.HIDE : T.SHOW;
        t.setAttribute('aria-expanded', String(rec.open));
      });
      actions.append(t);
    }
    li.append(actions);
  }

  function cardBody(run, id, p, state) {
    const keep = run.keeps.get(id);
    const frag = document.createDocumentFragment();
    frag.append(h('p', { class: 'verdict' }, h('span', { class: 'pid' }, id), h('span', { class: 'mark' }, T.MARK[state]),
      keep && state !== 'notkept' ? h('span', { class: 'reason' }, keep.reason) : null));
    frag.append(h('p', { class: 'case' }, h('i', null, p.case_name), `, ${p.citation}`));
    frag.append(h('p', { class: 'meta' }, `${T.decided(p.decided)} ${T.lineup(p)}`,
      p.kind === 'footnote' ? ` ${T.footnoteLabel(p)}.` : '', p.section ? ` Section ${p.section}.` : ''));
    const body = h('div', { class: 'body' });
    body.append(h('p', { class: 'text' }, ...sentenceSpans(p), ' ', h('span', { class: 'pin' }, T.pin(p))));
    // attached footnotes, folded (T4.3 #1); a footnote kept or matched alone has its own card as well
    const notes = (p.footnotes || []).map(fid => run.passages.get(fid)).filter(Boolean);
    if (notes.length) {
      body.append(h('details', { class: 'fns' }, h('summary', null, T.FOOTNOTES_IN(notes.length)),
        ...notes.map(n => h('p', { class: 'fn' }, h('span', { class: 'fn-label' }, `${n.footnote_label} `), n.text, ' ', h('span', { class: 'pid' }, n.id)))));
    }
    body.append(h('p', { class: 'small guarantee' }, T.GUARANTEE));
    if (p.slip_opinion) body.append(h('p', { class: 'slip' }, T.SLIP_NOTE));
    const by = (run.foundBy.get(id) || []).map(tid => run.tools.get(tid)).filter(Boolean).map(foundByLabel);
    if (by.length) body.append(h('p', { class: 'small' }, T.FOUND_BY, by.join('; ')));
    frag.append(body);
    return frag;
  }

  function reset() { cards.clear(); clear(list); }

  return { sync, reset, cards };
}

// a term Claude already put in quotation marks (an exact phrase) keeps its own and gets no more
export function quoted(s) { s = String(s); return /^".*"$/.test(s) ? s : `“${s}”`; }

export function foundByLabel(it) {
  const i = it.input || {};
  if (it.name === 'search_meaning') return quoted(i.query);
  if (it.name === 'search_exact') return [i.all_of, i.any_of].filter(Boolean).flat().map(quoted).join(', ');
  if (it.name === 'read_passages') return `reading around ${i.target}`;
  return it.name;
}

// Light a citation's sentences inside a card (or any element holding sentence spans): the rest of the paragraph dims.
// ranges: [[first, last], ...], both inclusive (contract §6); only those sentences light, never their neighbours.
export function lightSentences(root, ranges) {
  root.classList.add('focus');
  for (const sb of root.querySelectorAll('.sb')) {
    const i = Number(sb.dataset.s);
    sb.classList.toggle('hit', ranges.some(([a, z]) => i >= a && i <= z));
  }
}
export function unlightSentences(root) {
  root.classList.remove('focus');
  for (const sb of root.querySelectorAll('.sb.hit')) sb.classList.remove('hit');
}
