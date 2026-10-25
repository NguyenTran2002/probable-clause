// The update-check band (T2.3, T4.3 #4, T5.3; outcomes by contract §6, step 0's unavailable lines). It sits in the
// conversation above the answer, kept apart from the corpus evidence. It never shows page text: only titles,
// domains, URLs and dates as Exa gave them (T2.2). Links are built here from Exa's URL fields, opened apart from
// the page with noopener noreferrer (T3.7). It is never called verified.

import { h, webLink } from './dom.js';
import { withheld } from './steps.js';
import * as T from './text.js';

const FIELDS = [['query', 'query'], ['start_published_date', 'published from'], ['end_published_date', 'published to'],
  ['include_domains', 'include domains'], ['exclude_domains', 'exclude domains'], ['category', 'category'],
  ['type', 'search type'], ['num_results', 'results']];

export function renderBand(band, cfg) {
  const sec = h('section', { class: 'update', attrs: { 'aria-label': T.BAND_HEADING } });
  sec.append(h('h2', null, T.BAND_HEADING), h('p', { class: 'label' }, T.BAND_HONESTY));
  const pages = new Map((band.pages || []).map(p => [p.id, p]));
  const o = band.outcome;

  if (o === 'found') {
    sec.append(h('p', { class: 'label' }, T.BAND_GUARANTEE));
    sec.append(h('h3', null, T.BAND_FINDINGS));
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
  } else if (o === 'not_run') {
    sec.append(h('p', { class: 'outcome' }, T.BAND_NOT_RUN));
  }
  if (band.overview) {
    sec.append(h('p', { class: 'summary' }, h('span', { class: 'whose' }, T.BAND_OVERVIEW), ...withheld(band.overview)));
  }

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
      if (s.status !== 'ok') block.append(h('p', { class: 'meta' }, s.status === 'unavailable' ? T.WEB_STATUS.unavailable : T.BAND_INCOMPLETE));
      sec.append(block);
    }
    sec.append(h('p', { class: 'meta fixed' }, T.bandFixed(cfg)));
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
