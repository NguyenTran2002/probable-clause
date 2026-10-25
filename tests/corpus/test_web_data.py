"""scripts/build_web_data.py and api/corpus/web_data.py (contract §11.1, §11.3, §5.1)."""

import json
import runpy
import sys
from pathlib import Path

from api import settings
from api.corpus import web_data

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_build_writes_every_file(tmp_path):
    web_data.build_web_data(ROOT / "data" / "corpus", tmp_path)
    files = sorted(p.name for p in (tmp_path / "opinions").glob("*.json"))
    assert len(files) == 102
    assert "katz-1.json" in files and "katz-0.json" not in files
    assert (tmp_path / "corpus.json").exists() and (tmp_path / "config.json").exists()


def test_reader_file_shape(tmp_path, corpus):
    web_data.build_web_data(ROOT / "data" / "corpus", tmp_path)
    r = load(tmp_path / "opinions" / "katz-1.json")
    assert set(r) == {"opinion_id", "case", "type", "authors", "joined_by", "joined_by_source", "joined_by_note", "heading",
                      "paragraphs", "footnotes"}
    assert r["opinion_id"] == "katz-1" and r["type"] == "majority" and r["authors"] == ["Stewart"]
    assert r["case"] == {"key": "katz", "name": "Katz v. United States", "citation": "389 U.S. 347", "decided": "1967-12-18",
                         "slip_opinion": False, "credit": "courtlistener"}
    first = r["paragraphs"][0]
    assert set(first) == {"id", "kind", "text", "page_start", "page_breaks", "footnote_refs"}
    assert first["id"] == "katz-1-p1" and first["page_start"] == 348
    assert first["page_breaks"] == [{"offset": 724, "page": 349}]
    assert first["footnote_refs"][0]["footnote_id"] == "katz-1-n1"
    assert set(first["footnote_refs"][0]) == {"offset", "label", "footnote_id"}
    fn = r["footnotes"][0]
    assert {"id", "label", "page", "paragraphs", "page_breaks"} <= set(fn) and fn["id"] == "katz-1-n1"
    assert isinstance(fn["paragraphs"], list) and all(isinstance(t, str) for t in fn["paragraphs"])


def test_reader_ids_match_the_passages(tmp_path, corpus):
    web_data.build_web_data(ROOT / "data" / "corpus", tmp_path)
    seen_ids = set()
    n_sections = 0
    for f in (tmp_path / "opinions").glob("*.json"):
        r = load(f)
        for p in r["paragraphs"]:
            if p["kind"] == "section":
                assert p["id"] is None
                n_sections += 1
            else:
                assert p["id"] in corpus.passages and corpus.passages[p["id"]].text == p["text"]
                seen_ids.add(p["id"])
                for ref in p["footnote_refs"]:
                    assert ref["footnote_id"] in corpus.passages
        for fn in r["footnotes"]:
            assert corpus.passages[fn["id"]].text == "\n\n".join(fn["paragraphs"])
            seen_ids.add(fn["id"])
    assert seen_ids == set(corpus.passages) and n_sections == 287


def test_credit_codes(tmp_path):
    web_data.build_web_data(ROOT / "data" / "corpus", tmp_path)
    assert load(tmp_path / "opinions" / "chatrie-1.json")["case"]["credit"] == "slip_opinion"
    assert load(tmp_path / "opinions" / "chatrie-1.json")["case"]["slip_opinion"] is True
    assert load(tmp_path / "opinions" / "carpenter-1.json")["case"]["credit"] == "us_reports"
    assert load(tmp_path / "opinions" / "berger-1.json")["case"]["credit"] == "courtlistener"


def test_corpus_json(tmp_path):
    web_data.build_web_data(ROOT / "data" / "corpus", tmp_path)
    c = load(tmp_path / "corpus.json")
    assert len(c["cases"]) == 32
    assert c["earliest_decided"] == "1878-05-13"
    assert c["coverage"] == {"latest_decision_full_pull": "2026-06-29", "latest_decision_in_corpus": "2026-06-29",
                             "ingested": "2026-10-23"}
    assert c["source_counts"] == {"courtlistener": 25, "us_reports": 6, "slip_opinion": 1}
    k = next(x for x in c["cases"] if x["key"] == "katz")
    assert k["name"] == "Katz v. United States" and k["citation"] == "389 U.S. 347" and k["credit"] == "courtlistener"
    assert [o["opinion_id"] for o in k["opinions"]] == ["katz-1", "katz-2", "katz-3", "katz-4", "katz-5"]


def test_config_json(tmp_path):
    web_data.build_web_data(ROOT / "data" / "corpus", tmp_path)
    cfg = load(tmp_path / "config.json")
    names = ["WAKE_CHECK_TIMEOUT_S", "WAKE_CHECK_GAP_S", "LONG_WAIT_S", "WAKE_GIVE_UP_S", "HEARTBEAT_INTERVAL_S",
             "PAGE_WATCHDOG_S", "QUESTION_MAX_CHARS"]
    assert cfg == {n: getattr(settings, n).value for n in names}


def test_always_the_full_corpus(tmp_path):
    web_data.build_web_data(ROOT / "data" / "corpus", tmp_path)
    assert (tmp_path / "opinions" / "chatrie-1.json").exists()


def test_the_script_writes_where_asked(tmp_path, monkeypatch):
    out = tmp_path / "web-data"
    # in-process, so the splitter stand-in of conftest.py is in effect while builder A's module is absent
    monkeypatch.setattr(sys, "argv", ["build_web_data.py", "--out", str(out)])
    monkeypatch.chdir(tmp_path)
    runpy.run_path(str(ROOT / "scripts" / "build_web_data.py"), run_name="__main__")
    assert len(list((out / "opinions").glob("*.json"))) == 102 and (out / "config.json").exists()
