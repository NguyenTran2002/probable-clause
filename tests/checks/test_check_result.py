"""CheckResult is the `checks` event's data, field for field (contract §6); check_answer's whole shape."""

import dataclasses
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from api.checks import CheckResult, Flag, check_answer
from tests.checks.helpers import MANIFEST, ROOT

SCHEMA = json.loads((ROOT / "contracts" / "events.schema.json").read_text())
CHECKS = Draft202012Validator({"$ref": "#/$defs/checks", "$defs": SCHEMA["$defs"]})
KEPT = ["For the Fourth Amendment protects people, not places. What a person knowingly exposes to the public is not protected."]


def test_fields_match_the_schema_field_for_field():
    props = set(SCHEMA["$defs"]["checks"]["properties"])
    assert {f.name for f in dataclasses.fields(CheckResult)} == props
    flag_props = set(SCHEMA["$defs"]["checks"]["properties"]["flags"]["items"]["properties"])
    assert {f.name for f in dataclasses.fields(Flag)} == flag_props


def test_a_result_with_every_kind_of_flag_validates():
    blocks = ['The Court held "the Fourth Amendment protects people, not places" in Katz v. United States, 389 U. S. 347. ',
              'It also said "searches always need a warrant of some kind" citing Entick v. Carrington ',
              "and 12 U.S. 3."]
    r = check_answer(blocks, KEPT, MANIFEST)
    d = dataclasses.asdict(r)
    CHECKS.validate(d)
    kinds = {f["kind"] for f in d["flags"]}
    assert kinds == {"quotation_not_found", "not_in_corpus"}
    assert d["quotations_checked"] == 2 and d["quotations_found"] == 1
    assert d["citations_checked"] == 4 and d["citations_found"] == 2
    assert d["not_in_corpus"] == ["Entick v. Carrington", "12 U.S. 3"]
    json.dumps(d)


def test_a_clean_result_validates():
    d = dataclasses.asdict(check_answer(["Nothing to check here."], [], MANIFEST))
    CHECKS.validate(d)
    assert d == {"quotations_checked": 0, "quotations_found": 0, "citations_checked": 0, "citations_found": 0,
                 "not_in_corpus": [], "flags": []}


def test_flag_offsets_are_valid_for_the_schema_minimums():
    d = dataclasses.asdict(check_answer(['A "quotation that cannot be found" at the very start'], [], MANIFEST))
    CHECKS.validate(d)


def test_empty_blocks_and_empty_input():
    for blocks in ([], [""], ["", ""]):
        d = dataclasses.asdict(check_answer(blocks, KEPT, MANIFEST))
        CHECKS.validate(d)
        assert d["flags"] == []


def test_flags_are_sorted_by_position_across_blocks():
    blocks = ["See 99 U.S. 9. ", 'Then "a made up quotation of words" ', "and Entick v. Carrington."]
    r = check_answer(blocks, [], MANIFEST)
    keys = [(f.block, f.start) for f in r.flags]
    assert keys == sorted(keys) and len(keys) == 3


def test_check_answer_does_not_mutate_its_inputs():
    blocks = ['A "quote that is nowhere to be found" here']
    kept = list(KEPT)
    manifest_before = json.dumps(MANIFEST, sort_keys=True)
    check_answer(blocks, kept, MANIFEST)
    assert blocks == ['A "quote that is nowhere to be found" here'] and kept == KEPT
    assert json.dumps(MANIFEST, sort_keys=True) == manifest_before


def test_a_manifest_without_cases_resolves_nothing():
    r = check_answer(["See Katz v. United States, 389 U.S. 347."], [], {"cases": []})
    assert (r.citations_checked, r.citations_found) == (2, 0)
    assert r.not_in_corpus == ["Katz v. United States", "389 U.S. 347"]


def test_random_text_never_breaks_the_invariants():
    """Seeded fuzz: stray marks, brackets, dots, names and cites in random blocks. No exception, every flag's
    offsets slice back to its text, the counts add up, and the result validates."""
    import random

    rng = random.Random(20261024)
    pieces = ['"', "“", "”", "'", "’", "[", "]", ".", "...", ". . .", "…", ",", " ", "  ", "\n", "\n\n", "—", "--",
              "the", "Fourth", "Amendment", "protects", "people", "not", "places", "[t]he", "Katz", "v.", "United",
              "States", "Entick", "Carrington", "389", "U.S.", "U. S.", "347", "___", "*", "(", ")", "Co.", "Inc.",
              "In", "See", "and", "of", "é", "Ünited", ">", "\n> ", "\n\n\"", "5\"", "not", "[not]", "[un]", "[n't]",
              "unreasonable", "[reasonable]", "Co.", "Chem.", "Ass'n", "Assn."]
    for _ in range(400):
        blocks = ["".join(rng.choice(pieces) + rng.choice(["", " ", " "]) for _ in range(rng.randint(0, 40)))
                  for _ in range(rng.randint(0, 4))]
        kept = [KEPT[0]] if rng.random() < 0.7 else []
        r = check_answer(blocks, kept, MANIFEST)
        joined = "".join(blocks)
        starts = [sum(len(b) for b in blocks[:i]) for i in range(len(blocks))]
        for f in r.flags:
            assert 0 <= f.block <= f.end_block < len(blocks)
            g0, g1 = starts[f.block] + f.start, starts[f.end_block] + f.end
            assert joined[g0:g1] == f.text and g1 > g0
        assert r.quotations_found <= r.quotations_checked and r.citations_found <= r.citations_checked
        assert len([f for f in r.flags if f.kind == "quotation_not_found"]) == r.quotations_checked - r.quotations_found
        assert len([f for f in r.flags if f.kind == "not_in_corpus"]) == r.citations_checked - r.citations_found
        assert set(r.not_in_corpus) == {f.text for f in r.flags if f.kind == "not_in_corpus"}
        CHECKS.validate(dataclasses.asdict(r))
