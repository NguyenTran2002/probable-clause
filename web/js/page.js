// The site's own pages (sources-and-credits.html, privacy.html): the same words the landing page used to fold
// away, from text.js, each on a page of its own. The credits need corpus.json's counts and dates.

import { h, $, rich } from './dom.js';
import * as T from './text.js';

async function credits() {
  const r = await fetch('corpus.json', { cache: 'no-cache' });
  if (!r.ok) throw new Error(`corpus.json: ${r.status}`);
  const corpus = await r.json();
  return [h('p', null, ...rich(T.creditsSources(corpus))), h('p', null, T.CREDITS_BUILT), h('p', null, T.CREDITS_LICENCE),
    h('p', null, T.coverageDates(corpus.coverage)), h('p', null, T.TEXT_STATUS)];
}

// the note's bold lead ("Privacy.") is the page's heading here
function privacy() {
  return T.PRIVACY.map(par => h('p', null, ...rich(par[0].b ? [par[1].trimStart(), ...par.slice(2)] : par)));
}

const body = $('#doc-body');
try {
  body.append(...(document.body.dataset.doc === 'privacy' ? privacy() : await credits()));
} catch {
  body.append(h('p', null, T.PAGE_FAILURE));
}
