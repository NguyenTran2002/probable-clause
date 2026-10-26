// The later-developments box, the web search's result (T2.3, T4.3 #4, T5.3; outcomes by contract §6, step 0's
// unavailable lines; renamed and moved under the answer by the user, round 23). It is kept apart from the corpus
// evidence, and shows only Claude's accepted summary: a summary the copy guard sent back is never shown (the user,
// Oct 26, 2026). It never shows page text: only titles,
// domains, URLs and dates as Exa gave them (T2.2). Links are built here from Exa's URL fields, opened apart from
// the page with noopener noreferrer (T3.7). It is never called verified.

import { h, webLink } from './dom.js';
import { withheld } from './steps.js';
import * as T from './text.js';

const FIELDS = [['query', 'query'], ['start_published_date', 'published from'], ['end_published_date', 'published to'],
  ['include_domains', 'include domains'], ['exclude_domains', 'exclude domains'], ['category', 'category'],
  ['type', 'search type'], ['num_results', 'results']];

// null when there is nothing to show: no search reached the check and nothing stopped it (T2.3 #5: the band shows
// for a run with no answer only if an update search ran).
export function renderBand(band, cfg, limits) {
  // a search that met an out-of-credit or refused key never ran (T2.4), so it does not count as searching
  const searched = (band.searches || []).some(x => x.status !== 'unavailable');
  if (band.outcome === 'not_run' && !searched) return null;
  const sec = h('section', { class: 'update', attrs: { 'aria-label': T.BAND_HEADING } });
  sec.append(h('h2', null, T.BAND_HEADING));
  // T5.3's label says Claude searched the web, so it stands only where a search did (main session's reading)
  if (searched) sec.append(h('p', { class: 'label' }, T.BAND_HONESTY));
  const pages = new Map((band.pages || []).map(p => [p.id, p]));
  const o = band.outcome;

  // the overview first, under its own heading, then the findings with the line on what this site checks (the user,
  // round 29, Oct 26, 2026); a short outcome line still comes before the overview it explains
  const overview = () => { if (band.overview) sec.append(h('h3', null, T.BAND_OVERVIEW), h('p', { class: 'summary' }, ...withheld(band.overview))); };

  if (o === 'found') {
    overview();
    sec.append(h('h3', null, T.BAND_FINDINGS));
    sec.append(h('p', { class: 'label' }, T.BAND_GUARANTEE));
    sec.append(h('ul', { class: 'findings' }, (band.findings || []).map(f => h('li', null,
      h('p', null, ...withheld(f.statement)),
      h('ul', { class: 'links' }, (f.sources || []).map(id => pages.get(id)).filter(Boolean).map(linkItem))))));
  } else if (o === 'nothing_relevant') {
    sec.append(h('p', { class: 'outcome' }, T.BAND_NOTHING));
  } else if (o === 'skipped') {
    const reason = band.reason || '';
    // T5.3 #4 keeps T1.10's line, which already carries Claude's reason; it is not repeated
    sec.append(h('p', { class: 'outcome' }, ...withheld(T.BAND_SKIPPED(reason))));
  } else if (o === 'unavailable') {
    sec.append(h('p', { class: 'outcome' }, T.bandUnavailable(band.reason)));
  } else if (o === 'not_summarised') {
    sec.append(h('p', { class: 'outcome' }, T.BAND_NOT_SUMMARISED));
  }
  if (o !== 'found') overview();

  const searches = band.searches || [];
  if (searches.length) {
    sec.append(h('h3', null, T.BAND_SETTINGS));
    for (const s of searches) {
      const dl = h('dl', { class: 'params', attrs: { 'aria-label': `${T.BAND_SETTINGS}, search ${s.search_no}` } });
      for (const [k, label] of FIELDS) {
        const v = s.params ? s.params[k] : null;
        dl.append(h('dt', null, label), h('dd', null, ...withheld(v == null || (Array.isArray(v) && !v.length) ? T.NOT_SET : Array.isArray(v) ? v.join(', ') : String(v))));
      }
      const block = h('div', { class: 'search' }, dl);
      if (s.status !== 'ok') block.append(h('p', { class: 'meta' }, s.status === 'unavailable' ? T.WEB_UNAVAILABLE : T.BAND_INCOMPLETE));
      sec.append(block);
    }
    // the settings the run itself recorded, so a replay states what it ran with, not today's figures
    const fixed = searches.find(x => x.fixed) ? searches.find(x => x.fixed).fixed : {};
    sec.append(h('p', { class: 'meta fixed' }, T.bandFixed({ ...cfg,
      ...(limits && limits.update_searches != null ? { UPDATE_SEARCHES_PER_RUN: limits.update_searches } : {}),
      ...(fixed.text_max_characters != null ? { EXA_TEXT_CHARS: fixed.text_max_characters } : {}) })));
  }
  const all = band.pages || [];
  if (all.length) {
    sec.append(h('details', { class: 'all-pages', attrs: o === 'not_summarised' ? { open: true } : null },
      h('summary', null, T.BAND_ALL_PAGES(all.length)), h('ul', { class: 'links' }, all.map(linkItem))));
  }
  return sec;
}

function linkItem(p) {
  const [title, domain, date] = T.pageLine(p);
  return h('li', null, webLink(p.url, title), h('span', null, `${domain} · ${date}`));
}

// The box arrives the way the landing's notes write themselves: its dashed edge is inked around it from the top left,
// then its lines come up one by one (the user, round 23, Oct 26, 2026). With reduced motion, a plain fade.
const NS = 'http://www.w3.org/2000/svg';
export function inkIn(sec) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
    sec.classList.add('fresh');
    setTimeout(() => sec.classList.remove('fresh'), 450);
    return;
  }
  const { width: w, height: ht } = sec.getBoundingClientRect();
  if (!w || !ht) return;
  const r = parseFloat(getComputedStyle(sec).borderTopLeftRadius) || 0;
  const a = 0.5, b = w - 0.5, c = ht - 0.5;
  const d = `M${a + r},${a} H${b - r} A${r},${r} 0 0 1 ${b},${a + r} V${c - r} A${r},${r} 0 0 1 ${b - r},${c} H${a + r} `
    + `A${r},${r} 0 0 1 ${a},${c - r} V${a + r} A${r},${r} 0 0 1 ${a + r},${a}`;
  const svg = document.createElementNS(NS, 'svg');
  for (const [k, v] of [['class', 'ink'], ['width', w], ['height', ht], ['aria-hidden', 'true']]) svg.setAttribute(k, v);
  // the dashed edge shows only where the pen, a solid stroke in the mask, has already passed
  const mask = document.createElementNS(NS, 'mask'), pen = document.createElementNS(NS, 'path'), edge = document.createElementNS(NS, 'path');
  mask.id = 'ink-mask';
  pen.setAttribute('d', d); pen.setAttribute('class', 'pen');
  edge.setAttribute('d', d); edge.setAttribute('class', 'edge'); edge.setAttribute('mask', 'url(#ink-mask)');
  mask.append(pen);
  svg.append(mask, edge);
  [...sec.children].forEach((e, i) => e.style.setProperty('--i', i));
  sec.append(svg);
  pen.style.setProperty('--len', pen.getTotalLength());
  sec.classList.add('inking');
  setTimeout(() => sec.classList.add('inked'), 950);
  setTimeout(() => { sec.classList.remove('inking', 'inked'); svg.remove(); }, 1500);
}
