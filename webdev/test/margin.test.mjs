// The landing's margin notes (text.js MARGIN_NOTES, margin.js): every quote is the Court's majority, copied from its
// passage with any omission marked; its citation is the page the quote starts on; and where a note goes never covers
// the hero or another note.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { AMENDMENT, MARGIN_NOTES, noteQuote, passageTag } from '../../web/js/text.js';
import { parseAmendment, findSpot, leaderPath, hit } from '../../web/js/margin.js';

const CASES = new URL('../../data/corpus/cases/', import.meta.url);
const pieces = q => q.split(' … ');
// the pieces in order inside one text; returns the first piece's offset, or -1
function inOrder(text, parts) {
  for (let s = text.indexOf(parts[0]); s >= 0; s = text.indexOf(parts[0], s + 1)) {
    let end = s + parts[0].length, ok = true;
    for (const p of parts.slice(1)) { const i = text.indexOf(p, end); if (i < 0) { ok = false; break; } end = i + p.length; }
    if (ok) return s;
  }
  return -1;
}

test('the amendment is the Constitution\'s text, and every note points to one of its anchors', () => {
  const segs = parseAmendment(AMENDMENT);
  assert.equal(segs.map(s => s.text).join(''), 'The right of the people to be secure in their persons, houses, papers, and effects, against unreasonable searches and seizures, shall not be violated, and no Warrants shall issue, but upon probable cause, supported by Oath or affirmation, and particularly describing the place to be searched, and the persons or things to be seized.');
  const keys = new Set(segs.filter(s => s.key).map(s => s.key));
  for (const n of MARGIN_NOTES) assert.ok(keys.has(n.at), n.at);
  assert.equal(segs.filter(s => s.exit).map(s => s.text).join(), 'probable cause');
});

test('every note: at most 60 characters, omissions marked " … " (two at most), no banned word, no repeat', () => {
  const banned = /exhaustive|comprehensive|settled law|guaranteed accurate|citator|no hallucinations/i;
  for (const n of MARGIN_NOTES) {
    assert.ok(n.quote.length <= 60, `${n.quote} (${n.quote.length})`);
    assert.ok(pieces(n.quote).length <= 3 && pieces(n.quote).every(p => p && !p.includes('…')), n.quote);
    assert.ok(!/\.\.\.|\[|\]/.test(n.quote), n.quote);
    assert.ok(!banned.test(n.quote), n.quote);
  }
  assert.equal(new Set(MARGIN_NOTES.map(n => n.quote)).size, MARGIN_NOTES.length);
});

test('every note is copied from a majority opinion of its case in the committed corpus', () => {
  for (const n of MARGIN_NOTES) {
    const [, key, op] = /^(.+)-(\d+)-[pn]\d+$/.exec(n.id);
    const o = JSON.parse(readFileSync(new URL(`${key}.json`, CASES), 'utf8')).opinions[Number(op) - 1];
    assert.equal(o.type, 'majority', n.id);
    const texts = [...o.paragraphs.map(p => p.text), ...o.footnotes.map(f => f.paragraphs.join(' '))];
    assert.ok(texts.some(t => inOrder(t, pieces(n.quote)) >= 0), `${n.id}: ${n.quote}`);
  }
});

// the exact passage, its page and its citation, from build_web_data.py's local output when it is there (gitignored)
const OPS = new URL('../../web/_generated/opinions/', import.meta.url);
test('every note sits in its passage, cited to the page the quote starts on', { skip: !existsSync(OPS) }, () => {
  for (const n of MARGIN_NOTES) {
    const opId = n.id.replace(/-[pn]\d+$/, '');
    const o = JSON.parse(readFileSync(new URL(`${opId}.json`, OPS), 'utf8'));
    const c = { case_key: o.case.key, case_name: o.case.name, slip_opinion: !!o.case.slip_opinion, opinion_type: o.type, authors: o.authors };
    const para = o.paragraphs.find(p => p.id === n.id), fn = o.footnotes.find(f => f.id === n.id);
    const p = para ? { ...c, id: n.id, kind: 'paragraph', page_start: para.page_start, breaks: para.page_breaks || [], text: para.text }
      : { ...c, id: n.id, kind: 'footnote', page_start: fn.page, footnote_label: fn.label, breaks: [], text: fn.paragraphs.join(' ') };
    const at = inOrder(p.text, pieces(n.quote));
    assert.ok(at >= 0, `${n.id}: ${n.quote}`);
    let page = p.page_start;
    for (const b of p.breaks) if (b.offset <= at) page = b.page;
    assert.equal(n.cite, passageTag({ ...p, page_start: page }), n.quote);
  }
});

test('a note as shown: curly marks around it, the opinion\'s own marks single inside, the words unchanged', () => {
  assert.equal(noteQuote('It is beyond dispute that a vehicle is an "effect"'), '“It is beyond dispute that a vehicle is an ‘effect’”');
  assert.equal(noteQuote('"conversation" was within the Fourth Amendment\'s protections'), '“‘conversation’ was within the Fourth Amendment’s protections”');
  assert.equal(noteQuote('the ultimate touchstone … is \'reasonableness.\''), '“the ultimate touchstone … is ‘reasonableness.’”');
  for (const n of MARGIN_NOTES) assert.equal(noteQuote(n.quote).replace(/[“”‘’]/g, '').replace(/["']/g, ''), n.quote.replace(/["']/g, ''));
});

test('a note\'s spot: clear of the hero, its word and other notes, inside the view, else none', () => {
  const bounds = { x: 0, y: 0, w: 1440, h: 900 }, hero = { x: 310, y: 330, w: 820, h: 500 };
  const word = { x: 400, y: 40, w: 180, h: 80 }, size = { w: 220, h: 90 };
  const r = findSpot(word, size, { bounds, hero });
  assert.ok(r && !hit(r, hero, 10) && !hit(r, word, 6) && r.x >= 12 && r.y >= 12 && r.x + r.w <= 1428 && r.y + r.h <= 888);
  const r2 = findSpot(word, size, { bounds, hero, notes: [{ r, w: word }] });
  assert.ok(!r2 || !hit(r2, r, 20));
  assert.equal(findSpot({ x: 600, y: 500, w: 100, h: 60 }, size, { bounds: { x: 0, y: 0, w: 400, h: 300 }, hero: { x: 0, y: 0, w: 400, h: 300 } }), null);
});

test('a leader from below ends on the underline; from above it stops over the word', () => {
  const w = { x: 100, y: 100, w: 200, h: 80 };
  const end = d => d.split(' ').at(-1).split(',').map(Number);
  assert.deepEqual(end(leaderPath({ x: 120, y: 220, w: 200, h: 60 }, w, 168, 64))[1], 168);
  assert.ok(end(leaderPath({ x: 120, y: 0, w: 200, h: 60 }, w, 168, 64))[1] < w.y + 20);
});
