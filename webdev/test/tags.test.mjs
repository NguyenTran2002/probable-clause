// A passage's tag (P4.35): the case's short name and page, as a citation reads, instead of its ID; the paragraph's
// number, then the author, only when two tags would otherwise read the same.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { passageTag, SHORT_NAMES } from '../../web/js/text.js';
import { createRun, apply, tagsFor, tagOf } from '../../web/js/model.js';

const DIR = new URL('../../tests/fixtures/events/', import.meta.url);
const NAMES = readdirSync(DIR).filter(f => f.endsWith('.json')).map(f => f.slice(0, -5));
const load = name => JSON.parse(readFileSync(new URL(`${name}.json`, DIR), 'utf8'));
function play(events) { const run = createRun(); for (const ev of events) apply(run, ev); return run; }

const base = { case_key: 'kyllo', case_name: 'Kyllo v. United States', slip_opinion: false, opinion_type: 'majority', authors: ['Scalia'] };

test('the tag reads as a citation: page, footnote, the opinion when not the majority, a slip opinion', () => {
  assert.equal(passageTag({ ...base, id: 'kyllo-1-p1', kind: 'paragraph', page_start: 29 }), 'Kyllo at 29');
  assert.equal(passageTag({ ...base, id: 'kyllo-1-n1', kind: 'footnote', page_start: 32, footnote_label: '1' }), 'Kyllo at 32 n.1');
  const dissent = { ...base, id: 'kyllo-2-p4', kind: 'paragraph', page_start: 41, opinion_type: 'dissent', authors: ['Stevens'] };
  assert.equal(passageTag(dissent), 'Kyllo at 41 (dissenting)');
  assert.equal(passageTag(dissent, 1), 'Kyllo at 41, ¶4 (dissenting)');
  assert.equal(passageTag(dissent, 2), 'Kyllo at 41, ¶4 (Stevens, dissenting)');
  assert.equal(passageTag({ ...base, case_key: 'chatrie', case_name: 'Chatrie v. United States', slip_opinion: true, id: 'chatrie-1-p3', kind: 'paragraph', page_start: 4 }), 'Chatrie, slip op. at 4');
});

test('every case in the corpus has a short name, and no two share one', () => {
  const keys = readdirSync(new URL('../../data/corpus/cases/', import.meta.url)).filter(f => f.endsWith('.json')).map(f => f.slice(0, -5));
  assert.equal(keys.length, 32);
  for (const k of keys) assert.ok(SHORT_NAMES[k], k);
  assert.equal(new Set(Object.values(SHORT_NAMES)).size, Object.keys(SHORT_NAMES).length);
});

test('the paragraph mark appears only on tags that would otherwise read the same', () => {
  const run = createRun();
  const ps = [
    { ...base, id: 'kyllo-1-p1', kind: 'paragraph', page_start: 29 },
    { ...base, id: 'kyllo-1-p2', kind: 'paragraph', page_start: 29 },
    { ...base, id: 'kyllo-1-p9', kind: 'paragraph', page_start: 34 },
  ];
  for (const p of ps) run.passages.set(p.id, p);
  const tags = tagsFor(run, ['kyllo-1-p1', 'kyllo-1-p2', 'kyllo-1-p9', 'kyllo-1-p1']);
  assert.deepEqual([...tags.values()], ['Kyllo at 29, ¶1', 'Kyllo at 29, ¶2', 'Kyllo at 34']);
  assert.equal(tagsFor(run, ['kyllo-1-p1', 'kyllo-1-p9']).get('kyllo-1-p1'), 'Kyllo at 29');
  assert.equal(tagsFor(run, ['katz-3-p2']).get('katz-3-p2'), 'katz-3-p2', 'an unknown passage keeps its ID');
  assert.equal(tagOf(run, 'kyllo-1-p9'), 'Kyllo at 34, ¶9', 'cards and the step log always carry the paragraph');
});

test('every fixture: the answer\'s tags are distinct, and so are the tags of every passage a run shows', () => {
  for (const name of NAMES) {
    const run = play(load(name).events);
    const cited = run.blocks.filter(Boolean).flatMap(b => b.citations.map(c => c.passage_id));
    const tags = tagsFor(run, cited);
    assert.equal(new Set(tags.values()).size, tags.size, name);
    const all = [...run.passages.keys()].map(id => tagOf(run, id));
    assert.equal(new Set(all).size, all.length, name);
  }
});

// the whole corpus, from build_web_data.py's local output when it is there (gitignored, so skipped otherwise)
const OPS = new URL('../../web/_generated/opinions/', import.meta.url);
test('the whole corpus: at the top level, no two passages share a tag', { skip: !existsSync(OPS) }, () => {
  const ps = [];
  for (const f of readdirSync(OPS)) {
    const o = JSON.parse(readFileSync(new URL(f, OPS), 'utf8'));
    const c = { case_key: o.case.key, case_name: o.case.name, slip_opinion: !!o.case.slip_opinion, opinion_type: o.type, authors: o.authors };
    for (const p of o.paragraphs) if (p.id) ps.push({ ...c, id: p.id, kind: 'paragraph', page_start: p.page_start });
    for (const n of o.footnotes) ps.push({ ...c, id: n.id, kind: 'footnote', page_start: n.page, footnote_label: n.label });
  }
  assert.equal(ps.length, 2462);
  const tags = ps.map(p => passageTag(p, 2));
  assert.equal(new Set(tags).size, tags.length);
});
