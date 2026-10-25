"""MeaningIndex.load: checks against the manifest, drops excluded rows (T3.6, contract §4.C)."""

import json

import numpy as np
import pytest

from api.search.meaning import MeaningIndex
from api.search.voyage import FakeVoyageClient
from tests.search.support import make_passage, write_vectors


def test_loads_and_normalises_rows(tmp_path, passages):
    write_vectors(tmp_path, passages)
    # scale one stored row up: unit normalisation happens at load
    raw = np.fromfile(tmp_path / "voyage-law-2.f32", dtype="<f4").reshape(len(passages), 1024)
    raw[2] *= 5.0
    (tmp_path / "voyage-law-2.f32").write_bytes(raw.astype("<f4").tobytes())
    idx = MeaningIndex.load(tmp_path, passages)
    norms = np.linalg.norm(idx.matrix, axis=1)
    assert idx.matrix.shape == (8, 1024) and np.allclose(norms, 1.0, atol=1e-5)
    assert [p.id for p in idx.passages] == [p.id for p in passages]


def test_rows_of_passages_not_given_are_dropped(tmp_path, passages):
    write_vectors(tmp_path, passages)
    given = [p for p in passages if p.id not in ("katz-1-p2", "katz-1-p5")]
    idx = MeaningIndex.load(tmp_path, given)
    assert [p.id for p in idx.passages] == [p.id for p in given]
    fake = FakeVoyageClient()
    from api.search.meaning import embedded_text
    expect = np.array([fake.vector_for(embedded_text(p)) for p in given])
    assert np.allclose(idx.matrix, expect, atol=1e-5)


def test_a_passage_with_no_row_is_refused(tmp_path, passages):
    write_vectors(tmp_path, passages[:-1])
    with pytest.raises(ValueError, match="katz-1-p8"):
        MeaningIndex.load(tmp_path, passages)


@pytest.mark.parametrize("tamper,match", [
    ({"model": "voyage-3"}, "model"),
    ({"dimension": 512}, "dimension"),
])
def test_model_or_dimension_mismatch_is_refused(tmp_path, passages, tamper, match):
    write_vectors(tmp_path, passages, tamper=tamper)
    with pytest.raises(ValueError, match=match):
        MeaningIndex.load(tmp_path, passages)


def test_changed_text_means_a_hash_mismatch(tmp_path, passages):
    write_vectors(tmp_path, passages)
    changed = list(passages)
    changed[3] = make_passage(4, text="A corrected passage text.")
    with pytest.raises(ValueError, match="katz-1-p4"):
        MeaningIndex.load(tmp_path, changed)


def test_changed_section_label_is_also_a_hash_mismatch(tmp_path, passages):
    write_vectors(tmp_path, passages)
    changed = list(passages)
    changed[0] = make_passage(1, section="II")
    with pytest.raises(ValueError, match="katz-1-p1"):
        MeaningIndex.load(tmp_path, changed)


def test_file_of_the_wrong_size_is_refused(tmp_path, passages):
    write_vectors(tmp_path, passages)
    p = tmp_path / "voyage-law-2.f32"
    p.write_bytes(p.read_bytes()[:-4])
    with pytest.raises(ValueError, match="size"):
        MeaningIndex.load(tmp_path, passages)


def test_manifest_count_must_match_its_units(tmp_path, passages):
    write_vectors(tmp_path, passages, tamper={"count": 99})
    with pytest.raises(ValueError, match="count"):
        MeaningIndex.load(tmp_path, passages)


def test_missing_files_raise(tmp_path, passages):
    with pytest.raises(FileNotFoundError):
        MeaningIndex.load(tmp_path, passages)
