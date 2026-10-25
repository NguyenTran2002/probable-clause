"""Corpus.load and what it carries (contract §3, §4.B)."""

import json
import re
from pathlib import Path

import pytest

from api.corpus.store import Corpus
from api.errors import ToolInputError
from api.settings import READ_AROUND_MAX, value

ROOT = Path(__file__).resolve().parents[2]
RAW_MANIFEST = json.loads((ROOT / "data/corpus/manifest.json").read_text(encoding="utf-8"))


def raw_case(key):
    return json.loads((ROOT / f"data/corpus/cases/{key}.json").read_text(encoding="utf-8"))


def opinions(corpus):
    """opinion_id -> passages in reading order."""
    out = {}
    for p in corpus.passages.values():
        out.setdefault(p.opinion_id, []).append(p)
    return out


# ---- counts and IDs

def test_counts(corpus):
    kinds = [p.kind for p in corpus.passages.values()]
    assert kinds.count("paragraph") == 1964
    assert kinds.count("footnote") == 498
    assert len(corpus.passages) == 2462


def test_counts_match_the_raw_files():
    n_par = n_fn = 0
    for mc in RAW_MANIFEST["cases"]:
        for o in raw_case(mc["key"])["opinions"]:
            n_par += sum(1 for p in o["paragraphs"] if p["kind"] != "section")
            n_fn += len(o["footnotes"])
    assert (n_par, n_fn) == (1964, 498)


def test_opinion_ids_count_from_one(corpus):
    assert "katz-1-p1" in corpus.passages
    assert not any(pid.startswith("katz-0-") for pid in corpus.passages)
    for mc in RAW_MANIFEST["cases"]:
        ids = {p.opinion_id for p in corpus.passages.values() if p.case_key == mc["key"]}
        assert ids == {f"{mc['key']}-{k}" for k in range(1, len(mc["opinions"]) + 1)}


def test_paragraph_and_footnote_numbering(corpus):
    for oid, ps in opinions(corpus).items():
        pars = [p for p in ps if p.kind == "paragraph"]
        fns = [p for p in ps if p.kind == "footnote"]
        assert [p.id for p in pars] == [f"{oid}-p{i}" for i in range(1, len(pars) + 1)]
        assert [p.id for p in fns] == [f"{oid}-n{i}" for i in range(1, len(fns) + 1)]
        assert [p.position for p in pars] == list(range(1, len(pars) + 1))
        assert all(p.of == len(pars) for p in pars)
        assert all(p.of == len(fns) for p in fns)
        assert [p.id for p in ps] == [p.id for p in pars] + [p.id for p in fns]   # paragraphs, then footnotes


def test_reading_order_follows_the_manifest(corpus):
    case_order = list(dict.fromkeys(p.case_key for p in corpus.passages.values()))
    assert case_order == [c["key"] for c in RAW_MANIFEST["cases"]]


def test_text_is_the_corpus_text_exactly(corpus):
    for mc in RAW_MANIFEST["cases"]:
        for k, o in enumerate(raw_case(mc["key"])["opinions"], 1):
            body = [p["text"] for p in o["paragraphs"] if p["kind"] != "section"]
            for i, t in enumerate(body, 1):
                assert corpus.passages[f"{mc['key']}-{k}-p{i}"].text == t
            for i, fn in enumerate(o["footnotes"], 1):
                assert corpus.passages[f"{mc['key']}-{k}-n{i}"].text == "\n\n".join(fn["paragraphs"])


def test_sentences_tile_every_passage(corpus):
    for p in corpus.passages.values():
        spans = p.sentences
        assert spans and spans[0][0] == 0 and spans[-1][1] == len(p.text)
        assert all(a[1] == b[0] and a[0] < a[1] for a, b in zip(spans, spans[1:]))


# ---- footnotes

def test_footnote_references_match_footnotes_one_to_one_in_label_order(corpus):
    for oid, ps in opinions(corpus).items():
        pars = [p for p in ps if p.kind == "paragraph"]
        fns = [p for p in ps if p.kind == "footnote"]
        cited = [fid for p in pars for fid in p.footnotes]
        assert cited == [f.id for f in fns], oid
        for f in fns:
            citing = [p for p in pars if f.id in p.footnotes]
            assert len(citing) == 1 and f.cited_by == (citing[0].id,)
        for p in pars:
            assert [fid for _, fid in p.marker_offsets] == list(p.footnotes)
            offs = [o for o, _ in p.marker_offsets]
            assert offs == sorted(offs) and all(0 < o <= len(p.text) for o in offs)


def test_footnote_labels_match_the_references(corpus):
    for mc in RAW_MANIFEST["cases"]:
        for k, o in enumerate(raw_case(mc["key"])["opinions"], 1):
            refs = [r for p in o["paragraphs"] for r in p["footnote_refs"]]
            assert [r["label"] for r in refs] == [f["label"] for f in o["footnotes"]]
            for i, f in enumerate(o["footnotes"], 1):
                assert corpus.passages[f"{mc['key']}-{k}-n{i}"].footnote_label == f["label"]


def test_boyd_repeated_labels_get_distinct_ids(corpus):
    fns = [p for p in corpus.passages.values() if p.case_key == "boyd" and p.kind == "footnote"]
    labels = [p.footnote_label for p in fns]
    assert len(labels) != len(set(labels))
    assert len({p.id for p in fns}) == len(fns)


def test_footnote_passage_fields(corpus):
    fn = corpus.passages["katz-1-n1"]
    assert fn.kind == "footnote" and fn.paragraph_kind is None and fn.footnote_label
    para = corpus.passages[fn.cited_by[0]]
    assert fn.section == para.section
    assert para.paragraph_kind in ("text", "quote", "appendix") and para.footnote_label is None


def test_multi_paragraph_footnote_joins_with_blank_line(corpus):
    multi = [p for p in corpus.passages.values() if p.kind == "footnote" and "\n\n" in p.text]
    assert multi, "the corpus has footnotes of more than one paragraph"
    for p in multi:
        # the join is always a sentence boundary
        starts = {a for a, _ in p.sentences}
        assert all(m.end() in starts for m in re.finditer(r"\n\n", p.text))


def test_loop_text_markers(corpus):
    p = corpus.passages["katz-1-p1"]
    t = corpus.loop_text("katz-1-p1")
    assert re.search(r"\[n\. 1\]", t)
    # removing every marker gives the citable text back
    assert re.sub(r"\[n\. [^\]]+\]", "", t) == p.text
    # a marker sits right after the text before its offset
    off, fid = p.marker_offsets[0]
    label = corpus.passages[fid].footnote_label
    assert t.startswith(p.text[:off] + f"[n. {label}]")
    # no markers in a footnote's own text and none for a paragraph without references
    assert corpus.loop_text("katz-1-n1") == corpus.passages["katz-1-n1"].text
    plain = next(q for q in corpus.passages.values() if q.kind == "paragraph" and not q.footnotes)
    assert corpus.loop_text(plain.id) == plain.text
    with pytest.raises(KeyError):
        corpus.loop_text("nope-1-p1")


def expected_loop_text(p, raw_para, label_of):
    out, last = [], 0
    for r in raw_para["footnote_refs"]:
        out.append(raw_para["text"][last:r["offset"]])
        out.append(f"[n. {r['label']}]")
        last = r["offset"]
    out.append(raw_para["text"][last:])
    return "".join(out)


@pytest.mark.parametrize("key,k", [("katz", 1), ("boyd", 1), ("carpenter", 1), ("chatrie", 1)])
def test_loop_text_exact_markers(corpus, key, k):
    op = raw_case(key)["opinions"][k - 1]
    paras = [p for p in op["paragraphs"] if p["kind"] != "section"]
    n_markers = 0
    for i, raw in enumerate(paras, 1):
        pid = f"{key}-{k}-p{i}"
        got = corpus.loop_text(pid)
        want = "".join(
            raw["text"][a:b] + (f"[n. {r['label']}]" if r is not None else "")
            for (a, b, r) in _pieces(raw))
        assert got == want, pid
        assert got.count("[n. ") == len(raw["footnote_refs"]), pid
        # each marker sits at its offset plus the markers before it
        shift = 0
        for r in raw["footnote_refs"]:
            m = f"[n. {r['label']}]"
            assert got[r["offset"] + shift: r["offset"] + shift + len(m)] == m, pid
            shift += len(m)
        n_markers += len(raw["footnote_refs"])
    assert n_markers == len(op["footnotes"])


def _pieces(raw):
    last = 0
    for r in raw["footnote_refs"]:
        yield last, r["offset"], r
        last = r["offset"]
    yield last, len(raw["text"]), None


def test_loop_text_literal_positions(corpus):
    t = corpus.loop_text("katz-1-p1")
    p = corpus.passages["katz-1-p1"]
    assert t.count("[n. ") == 3
    assert [t.index(f"[n. {n}]") for n in "123"] == [260, 810 + 6, 898 + 12]
    assert len(t) == len(p.text) + 18
    boyd = [q for q in corpus.passages.values() if q.opinion_id == "boyd-1" and q.kind == "paragraph" and len(q.footnotes) == 2]
    assert len(boyd) == 1
    bt = corpus.loop_text(boyd[0].id)
    assert bt.count("[n. ") == 2
    assert bt.index("[n. *]") == 1645 and bt.index("[n. \u2020]") == 2670 + 6
    assert len(bt) == len(boyd[0].text) + 6 + 6


def test_attached_footnotes(corpus):
    p = corpus.passages["katz-1-p1"]
    got = corpus.attached_footnotes("katz-1-p1")
    assert [f.id for f in got] == list(p.footnotes) and got
    assert corpus.attached_footnotes("katz-1-n1") == []


# ---- pages

def test_pages(corpus):
    p = corpus.passages["katz-1-p1"]
    assert (p.page_start, p.page_end) == (348, 349)     # one break inside, at page 349
    q = corpus.passages["katz-1-p2"]
    assert q.page_start == q.page_end == 349
    for p in corpus.passages.values():
        assert p.page_end >= p.page_start >= 1


def test_page_end_for_every_paragraph_is_the_last_break(corpus):
    for mc in RAW_MANIFEST["cases"]:
        for k, o in enumerate(raw_case(mc["key"])["opinions"], 1):
            i = 0
            for p in o["paragraphs"]:
                if p["kind"] == "section":
                    continue
                i += 1
                want = p["page_breaks"][-1]["page"] if p["page_breaks"] else p["page_start"]
                got = corpus.passages[f"{mc['key']}-{k}-p{i}"]
                assert (got.page_start, got.page_end) == (p["page_start"], want)


# ---- slip opinion and reads

def test_chatrie_is_a_slip_opinion(corpus):
    assert all(p.slip_opinion for p in corpus.passages.values() if p.case_key == "chatrie")
    assert not any(p.slip_opinion for p in corpus.passages.values() if p.case_key != "chatrie")
    got = corpus.read("chatrie-1:1", 0, 0)
    assert got and all(p.opinion_id == "chatrie-1" and p.page_start <= 1 <= p.page_end for p in got)
    got2 = corpus.read("chatrie-2:1", 0, 0)
    assert got2 and all(p.opinion_id == "chatrie-2" for p in got2)   # pages restart in each opinion


def test_case_level_page_target_refused_for_a_slip_opinion(corpus):
    with pytest.raises(ToolInputError) as e:
        corpus.read("chatrie:3", 0, 0)
    assert "chatrie-1:" in e.value.message or "<opinion_id>" in e.value.message
    assert "slip" in e.value.message.lower()


def test_read_a_passage_with_context(corpus):
    got = corpus.read("katz-1-p5", 2, 1)
    assert [p.id for p in got] == ["katz-1-p3", "katz-1-p4", "katz-1-p5", "katz-1-p6"]
    assert [p.id for p in corpus.read("katz-1-p5", 0, 0)] == ["katz-1-p5"]


def test_read_around_stops_at_the_opinion_and_kind(corpus):
    got = corpus.read("katz-1-p1", 5, 0)
    assert [p.id for p in got] == ["katz-1-p1"]
    n_par = corpus.passages["katz-1-p1"].of
    got = corpus.read(f"katz-1-p{n_par}", 0, 5)
    assert [p.id for p in got] == [f"katz-1-p{n_par}"]
    fgot = corpus.read("katz-1-n1", 1, 1)
    assert all(p.kind == "footnote" and p.opinion_id == "katz-1" for p in fgot)


def test_read_a_case_page(corpus):
    got = corpus.read("katz:349", 0, 0)
    assert got and all(p.case_key == "katz" and p.page_start <= 349 <= p.page_end for p in got)
    order = {pid: i for i, pid in enumerate(corpus.passages)}
    assert [order[p.id] for p in got] == sorted(order[p.id] for p in got)
    # every passage on the page is there, footnotes included
    want = [p.id for p in corpus.passages.values()
            if p.case_key == "katz" and p.page_start <= 349 <= p.page_end]
    assert [p.id for p in got] == want


def test_read_a_page_across_opinions(corpus):
    # on_lee's opinions overlap on a page in the U.S. Reports; at least one case has two opinions on a page
    found = False
    for mc in RAW_MANIFEST["cases"]:
        if mc["slip_opinion"]:
            continue
        pages = {}
        for p in corpus.passages.values():
            if p.case_key == mc["key"]:
                for pg in range(p.page_start, p.page_end + 1):
                    pages.setdefault(pg, set()).add(p.opinion_id)
        for pg, ids in pages.items():
            if len(ids) > 1:
                got = corpus.read(f"{mc['key']}:{pg}", 0, 0)
                assert {p.opinion_id for p in got} == ids
                found = True
                break
        if found:
            break
    assert found


def test_read_errors_name_the_valid_range(corpus):
    n = corpus.passages["katz-1-p1"].of
    with pytest.raises(ToolInputError) as e:
        corpus.read(f"katz-1-p{n + 1}", 0, 0)
    assert f"katz-1-p1" in e.value.message and f"katz-1-p{n}" in e.value.message
    with pytest.raises(ToolInputError) as e:
        corpus.read("katz-9-p1", 0, 0)
    assert "katz-1" in e.value.message and "katz-5" in e.value.message
    with pytest.raises(ToolInputError) as e:
        corpus.read("katz:9999", 0, 0)
    pages = [(p.page_start, p.page_end) for p in corpus.passages.values() if p.case_key == "katz"]
    assert str(min(a for a, _ in pages)) in e.value.message and str(max(b for _, b in pages)) in e.value.message
    with pytest.raises(ToolInputError) as e:
        corpus.read("nope:5", 0, 0)
    assert "katz" in e.value.message                       # lists the valid case keys
    with pytest.raises(ToolInputError):
        corpus.read("garbage", 0, 0)
    with pytest.raises(ToolInputError):
        corpus.read("katz:abc", 0, 0)


def test_read_before_after_range(corpus):
    top = value(READ_AROUND_MAX)
    corpus.read("katz-1-p5", top, top)
    for b, a in ((top + 1, 0), (0, top + 1), (-1, 0), (0, -1)):
        with pytest.raises(ToolInputError) as e:
            corpus.read("katz-1-p5", b, a)
        assert f"0 to {top}" in e.value.message


def test_opinion_form_refused_for_a_non_slip_opinion(corpus):
    with pytest.raises(ToolInputError) as e:
        corpus.read("katz-1:350", 0, 0)
    assert "katz:350" in e.value.message


def test_read_targets_are_case_insensitive(corpus):
    assert [p.id for p in corpus.read("Katz-1-P3", 0, 0)] == ["katz-1-p3"]
    assert [p.id for p in corpus.read("  KATZ-1-N1 ", 0, 0)] == ["katz-1-n1"]
    assert [p.id for p in corpus.read("KATZ:349", 0, 0)] == [p.id for p in corpus.read("katz:349", 0, 0)]
    assert corpus.read("CHATRIE-1:1", 0, 0) == corpus.read("chatrie-1:1", 0, 0)
    with pytest.raises(ToolInputError) as e:
        corpus.read("CHATRIE:3", 0, 0)
    assert "slip" in e.value.message.lower()


# ---- metadata

def test_opinion_groups(corpus):
    groups = {p.opinion_type: p.opinion_groups for p in corpus.passages.values()}
    assert groups["majority"] == ("majority",)
    assert groups["plurality"] == ("plurality",)
    assert groups["dissent"] == ("dissent",)
    assert groups["concurrence"] == ("concurrence",)
    assert groups["concurrence in the judgment"] == ("concurrence",)
    assert groups["concurrence in part"] == ("concurrence",)
    assert groups["concurrence in part and in the judgment"] == ("concurrence",)
    assert set(groups["concurrence in part and dissent in part"]) == {"concurrence", "dissent"}


def test_joined_by_source_is_carried(corpus):
    p = corpus.passages["berger-1-p1"]
    assert p.joined_by_source == "not printed" and p.joined_by == ()
    seen = {p.joined_by_source for p in corpus.passages.values()}
    assert seen <= {"heading", "lineup", "not printed", "per curiam"} and "lineup" in seen
    chatrie_maj = corpus.passages["chatrie-1-p1"]
    assert chatrie_maj.joined_by_source == "lineup" and "Kavanaugh" in chatrie_maj.joined_by


def test_case_fields(corpus):
    p = corpus.passages["katz-1-p1"]
    assert (p.case_name, p.citation, p.decided, p.slip_opinion) == ("Katz v. United States", "389 U.S. 347", "1967-12-18", False)
    assert p.authors == ("Stewart",) and p.opinion_type == "majority"
    d = corpus.passages["katz-2-p1"]
    assert d.authors and d.opinion_id == "katz-2"
    pc = corpus.passages["clinton-1-p1"]
    assert pc.authors == () and pc.joined_by_source == "per curiam"


def test_case_keys_and_manifest(corpus):
    assert len(corpus.case_keys) == 32 and "chatrie" in corpus.case_keys
    assert corpus.manifest["core_cases"] == 32 and corpus.manifest["core_opinions"] == 102
    assert corpus.manifest["core_tokens"] == RAW_MANIFEST["core_tokens"]
    assert len(corpus.manifest["cases"]) == 32
    assert corpus.label == "full"


def test_coverage_full(corpus):
    assert corpus.coverage == {"latest_decision_full_pull": "2026-06-29",
                               "latest_decision_in_corpus": "2026-06-29", "ingested": "2026-10-23"}


def test_load_accepts_the_repository_root_too(corpus_dir):
    c = Corpus.load(ROOT)
    assert len(c.passages) == 2462


def test_unsupported_exclusion_is_refused(corpus_dir):
    with pytest.raises(ValueError):
        Corpus.load(corpus_dir, exclude=("katz",))


# ---- the recording-only switch (T5.6)

def test_before_chatrie(corpus, corpus_pre):
    c = corpus_pre
    assert c.label == "before_chatrie"
    assert "chatrie" not in c.case_keys and len(c.case_keys) == 31
    gone = [p for p in corpus.passages.values() if p.case_key == "chatrie"]
    assert gone and len(c.passages) == len(corpus.passages) - len(gone)
    assert not any(p.case_key == "chatrie" for p in c.passages.values())
    assert all(m["key"] != "chatrie" for m in c.manifest["cases"])
    assert c.manifest["core_cases"] == 31 and c.manifest["core_opinions"] == 97
    assert "chatrie" not in c.catalog_text.lower() and "Chatrie" not in c.catalog_text
    assert c.coverage == {"latest_decision_full_pull": "2018-06-22",
                          "latest_decision_in_corpus": "2018-06-22", "ingested": "2026-10-23"}
    with pytest.raises(ToolInputError):
        c.read("chatrie-1-p1", 0, 0)
    with pytest.raises(ToolInputError):
        c.read("chatrie-1:1", 0, 0)


def test_before_chatrie_keeps_the_full_corpus_object_intact(corpus, corpus_pre):
    assert "chatrie" in corpus.case_keys and "Chatrie" in corpus.catalog_text
    assert corpus.coverage["latest_decision_in_corpus"] == "2026-06-29"


# ---- the catalog (T1.6)

def test_catalog_text(corpus):
    t = corpus.catalog_text
    for mc in RAW_MANIFEST["cases"]:
        assert mc["key"] in t and mc["name"] in t and mc["citation"] in t and mc["decided"] in t
    # each opinion: ID, exact type, author, joiners, counts with ID ranges, pages
    n_par = corpus.passages["katz-1-p1"].of
    assert "katz-1" in t and "concurrence in part and dissent in part" in t
    assert f"katz-1-p1 to katz-1-p{n_par}" in t
    assert f"{n_par} paragraphs (katz-1-p1 to katz-1-p{n_par})" in t       # the counts are stated beside the ranges
    assert "1 paragraph (chatrie-5-p1)" in t and "0 footnotes" in t
    assert "not printed" in t                          # joiners the print does not give (P1.18)
    assert "joined by" in t
    assert "348" in t and "slip" in t.lower()          # Katz's page range; Chatrie's pages are slip pages
    assert "groups" in t.lower() and "exact type" in t.lower()   # the filter-groups line (T1.4)
    for o in RAW_MANIFEST["cases"][3]["opinions"]:     # chatrie
        assert o["author"][0] in t


def test_catalog_lists_every_opinion_id(corpus):
    ids = {p.opinion_id for p in corpus.passages.values()}
    assert len(ids) == 102
    for oid in ids:
        assert oid in corpus.catalog_text


def test_catalog_footnote_ranges(corpus):
    n = corpus.passages["katz-1-n1"].of
    assert f"{n} footnotes (katz-1-n1 to katz-1-n{n})" in corpus.catalog_text
