"""scripts/spend_report.py: read-only reports for a day and a month (T3.4, T3.5; contract §4.E). Exit 0 or 2."""

import asyncio
import importlib.util
import io
import json
from pathlib import Path

import pytest

from api import settings
from api.protocols import Admission, Refusal
from api.state.store import MemoryStore, StoreUnavailable
from tests.state.cases import DAY, MONTH, T, at

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("spend_report_under_test", ROOT / "scripts" / "spend_report.py")
sr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sr)

URI_WITH_SECRET = "mongodb://someuser:SUPERSECRETPASSWORD@cluster.example.mongodb.net/?retryWrites=true"


class ReadOnly:
    """Wraps a store and fails the test if the script calls anything that writes."""
    WRITES = {"ensure_indexes", "append_events", "put_heartbeat", "upsert_run_record", "admit", "record_spend",
              "record_stop", "set_flag"}

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        if name in self.WRITES:
            raise AssertionError(f"spend_report called {name}")
        return getattr(self._inner, name)


async def populated():
    s = MemoryStore()
    a1 = await s.admit("run-a", T)
    await s.record_spend(a1, 0.75)
    for i in range(5):
        a = await s.admit(f"run-{i}", at("05-14", 12, i))
        await s.record_spend(a, 1.85)                                        # $9.25 more: the day reaches $10.00
    assert await s.admit("refused", at("05-14", 13, 0)) == Refusal("daily_cap")
    await s.record_stop("step_limit", "run-a", at("05-14", 12, 30), {})
    a2 = await s.admit("next-day", at("05-15", 9, 0))
    await s.record_spend(a2, 2.0)
    return s


def run(argv, store, env=None):
    out, err = io.StringIO(), io.StringIO()
    code = sr.main(argv, store_factory=lambda uri, db: store, out=out, err=err, env=env if env is not None else {"MONGODB_URI": URI_WITH_SECRET})
    return code, out.getvalue(), err.getvalue()


def test_day_report_in_text():
    store = ReadOnly(asyncio.run(populated()))
    code, out, err = run(["--day", DAY], store)
    assert code == 0 and err == ""
    assert "2030-05-14" in out
    assert "runs started" in out.lower()
    assert "daily_cap" in out and "step_limit" in out
    assert "refused" in out                                                    # the run that was turned away
    assert "$10.0000" in out                                                   # day spent
    assert "reserved" not in out.lower()                                       # no reservation output (v2.0)
    assert "SUPERSECRET" not in out


def test_day_report_in_json():
    store = ReadOnly(asyncio.run(populated()))
    code, out, _ = run(["--day", DAY, "--json"], store)
    d = json.loads(out)
    assert code == 0 and d["day"] == DAY
    assert d["figures"]["runs_started"] == 6
    assert d["figures"]["stops"] == {"daily_cap": 1, "step_limit": 1}
    assert d["figures"]["spent"] == pytest.approx(10.0)
    assert set(d["figures"]) == {"spent", "runs_started", "stops"}
    assert [s["kind"] for s in d["stops"]] == ["step_limit", "daily_cap"]        # by time: 12:30, then 13:00
    assert all(set(s) == {"date", "time", "run", "kind", "budget", "month_spent", "day_spent", "detail", "at"} for s in d["stops"])


def test_month_report_lists_every_day():
    store = ReadOnly(asyncio.run(populated()))
    code, out, _ = run(["--month", MONTH, "--json"], store)
    d = json.loads(out)
    assert code == 0 and d["month"] == MONTH
    assert set(d["days"]) == {"2030-05-14", "2030-05-15"}
    assert d["spent"] == pytest.approx(12.0) and "reserved" not in d
    assert all("reserved" not in f for f in d["days"].values())
    text_code, text, _ = run(["--month", MONTH], store)
    assert text_code == 0 and "2030-05-15" in text and "2030-05" in text and "reserved" not in text.lower()


def test_an_empty_day_and_month_say_so_and_exit_zero():
    store = ReadOnly(MemoryStore())
    for argv in (["--day", "2030-07-01"], ["--month", "2030-07"]):
        code, out, _ = run(argv, store)
        assert code == 0 and "no spend recorded" in out.lower()


def test_old_months_with_reservation_fields_are_reported_without_them():
    s = MemoryStore()
    s._spend[MONTH] = {"_id": MONTH, "spent": 1.0, "reserved": 9.0,
                       "days": {DAY: {"spent": 1.0, "reserved": 9.0, "runs_started": 3, "stops": {"daily_cap": 1}}},
                       "reservations": {"old-run": {"day": DAY, "amount": 9.0, "at": T}}}
    store = ReadOnly(s)
    for argv in (["--day", DAY], ["--month", MONTH]):
        code, out, err = run(argv, store)
        assert code == 0 and err == "" and "reserved" not in out.lower() and "$9" not in out and "old-run" not in out
    _, out, _ = run(["--day", DAY, "--json"], store)
    d = json.loads(out)
    assert d["figures"] == {"spent": 1.0, "runs_started": 3, "stops": {"daily_cap": 1}} and d["anomalies"] == []


def test_open_reservations_and_exit_one_are_gone():
    with pytest.raises(SystemExit) as e:
        sr.main(["--open-reservations"], store_factory=lambda u, d: MemoryStore(), out=io.StringIO(), err=io.StringIO(),
                env={"MONGODB_URI": "x"})
    assert e.value.code == 2                                                   # argparse: an unknown option
    assert not hasattr(sr, "report_open")


def test_a_successful_read_exits_zero_even_when_a_cap_was_reached():
    store = ReadOnly(asyncio.run(populated()))
    for argv in (["--day", DAY], ["--month", MONTH], ["--day", DAY, "--json"], ["--month", MONTH, "--json"]):
        assert run(argv, store)[0] == 0


def test_an_unreachable_store_exits_two_and_names_no_secret():
    s = MemoryStore()
    s.unreachable = True
    for argv in (["--day", DAY], ["--month", MONTH], ["--month", MONTH, "--json"]):
        code, out, err = run(argv, s)
        assert code == 2 and out == "" and "SUPERSECRET" not in out + err and "someuser" not in out + err
        assert "unreachable" in err.lower() or "could not" in err.lower()      # the deploy script must not read this as "nothing spent"


def test_exactly_one_report_must_be_chosen():
    for argv in ([], ["--day", DAY, "--month", MONTH]):
        with pytest.raises(SystemExit) as e:
            sr.main(argv, store_factory=lambda u, d: MemoryStore(), out=io.StringIO(), err=io.StringIO(), env={"MONGODB_URI": "x"})
        assert e.value.code == 2


@pytest.mark.parametrize("argv", [["--day", "2030-5-1"], ["--day", "2030-02-30"], ["--day", "May 1"], ["--month", "2030-13"],
                                  ["--month", "2030-05-01"], ["--month", "30-05"]])
def test_dates_are_validated(argv):
    with pytest.raises(SystemExit) as e:
        sr.main(argv, store_factory=lambda u, d: MemoryStore(), out=io.StringIO(), err=io.StringIO(), env={"MONGODB_URI": "x"})
    assert e.value.code == 2


def test_missing_uri_is_a_clear_error_that_names_the_variable_not_a_value():
    out, err = io.StringIO(), io.StringIO()
    code = sr.main(["--month", MONTH], store_factory=lambda u, d: MemoryStore(), out=out, err=err, env={})
    assert code == 2 and "MONGODB_URI" in err.getvalue()


def test_env_chooses_the_database_and_the_uri_is_never_printed():
    seen = []

    def factory(uri, db):
        seen.append((uri, db))
        return MemoryStore()

    for env, argv, expected in (({"MONGODB_URI": URI_WITH_SECRET}, [], settings.ATLAS_DB_TEST.value),
                                ({"MONGODB_URI": URI_WITH_SECRET, "PC_ENV": "live"}, [], settings.ATLAS_DB_LIVE.value),
                                ({"MONGODB_URI": URI_WITH_SECRET, "PC_ENV": "live"}, ["--env", "test"], settings.ATLAS_DB_TEST.value),
                                ({"MONGODB_URI": URI_WITH_SECRET}, ["--env", "live"], settings.ATLAS_DB_LIVE.value)):
        out, err = io.StringIO(), io.StringIO()
        sr.main(["--month", MONTH, *argv], store_factory=factory, out=out, err=err, env=env)
        assert seen[-1] == (URI_WITH_SECRET, expected)
        assert "SUPERSECRET" not in out.getvalue() + err.getvalue()
        assert expected in out.getvalue()                                      # says which database it read


def test_a_bad_pc_env_is_refused():
    out, err = io.StringIO(), io.StringIO()
    code = sr.main(["--month", MONTH], store_factory=lambda u, d: MemoryStore(), out=out, err=err,
                   env={"MONGODB_URI": URI_WITH_SECRET, "PC_ENV": "prod"})
    assert code == 2 and "PC_ENV" in err.getvalue()


# --- failure is exit 2 with a fixed message, never a traceback or a secret ---------------------------------------------------

FIXED_MESSAGES = ("Could not read from the store", "The report could not be produced")


class Strange:
    """A store that answers with the wrong shapes, or raises something that mentions the URI."""
    def __init__(self, month=None, stops=None, boom=None):
        self._month, self._stops, self._boom = month, stops or [], boom

    async def read_month(self, month):
        if self._boom:
            raise self._boom
        return self._month

    async def read_stops(self, *, day=None, month=None):
        return self._stops


def failed(argv, store, env=None):
    code, out, err = run(argv, store, env)
    assert code == 2
    assert out == "", "nothing half-printed on failure"
    assert "Traceback" not in err and "File \"" not in err
    assert any(m in err for m in FIXED_MESSAGES)
    for leak in ("SUPERSECRET", "someuser", "mongodb.net", "cluster.example", "secret-question", "KeyError", "AttributeError"):
        assert leak not in out + err
    return err


def test_a_malformed_document_exits_two_with_a_fixed_message():
    for month in ({"days": "oops", "spent": "x"}, {"days": {"2030-05-14": "not a dict"}}, {"days": {"2030-05-14": {"spent": "a"}}},
                  {"spent": object(), "days": {}}, [1, 2, 3]):
        for argv in (["--day", DAY], ["--month", MONTH], ["--day", DAY, "--json"], ["--month", MONTH, "--json"]):
            failed(argv, Strange(month=month, stops=[{"at": None}]))
    failed(["--day", DAY], Strange(month={"days": {DAY: {"spent": 1.0, "runs_started": 1}}},
                                   stops=[{"kind": "daily_cap"}]))                      # a stop with no date, time or at


def test_an_unexpected_exception_from_the_store_exits_two_without_its_text():
    boom = RuntimeError("mongodb://someuser:SUPERSECRET@cluster.example.mongodb.net/ secret-question")
    for argv in (["--day", DAY], ["--month", MONTH], ["--day", DAY, "--json"], ["--month", MONTH, "--json"]):
        failed(argv, Strange(boom=boom))


def test_a_store_that_cannot_be_built_exits_two():
    def factory(uri, db):
        raise ValueError("bad uri " + uri)

    out, err = io.StringIO(), io.StringIO()
    code = sr.main(["--month", MONTH], store_factory=factory, out=out, err=err, env={"MONGODB_URI": URI_WITH_SECRET})
    assert code == 2 and "SUPERSECRET" not in out.getvalue() + err.getvalue() and "Traceback" not in err.getvalue()


def test_an_invalid_uri_through_the_real_store_class_exits_two():
    for uri in ("mongodb://someuser:SUPERSECRET@cluster.example:notaport/", "mongodb://[::1", "nonsense://x"):
        out, err = io.StringIO(), io.StringIO()
        code = sr.main(["--month", MONTH], out=out, err=err, env={"MONGODB_URI": uri})
        assert code == 2
        assert "Traceback" not in err.getvalue() and "SUPERSECRET" not in out.getvalue() + err.getvalue()
        assert "cluster.example" not in out.getvalue() + err.getvalue() and "someuser" not in out.getvalue() + err.getvalue()
        assert any(m in err.getvalue() for m in FIXED_MESSAGES)
        assert out.getvalue() == ""


# --- negative figures are shown, not clamped (T3.4) ----------------------------------------------------------------------------

def corrupt(store, spent=-0.5):
    inner = store._inner if isinstance(store, ReadOnly) else store
    doc = inner._spend[MONTH]
    doc["spent"] = spent
    doc["days"][DAY]["spent"] = spent


def test_usd_shows_negatives():
    assert sr._usd(-0.5) == "-$0.5000"
    assert sr._usd(0.5) == "$0.5000"
    assert sr._usd(None) == "unknown"
    assert sr._usd(-1e-12) == "$0.0000"                      # float noise is not shown as a negative zero


def test_a_negative_spent_is_shown_and_flagged_in_text():
    store = ReadOnly(asyncio.run(populated()))
    corrupt(store)
    for argv in (["--day", DAY], ["--month", MONTH]):
        code, out, _ = run(argv, store)
        assert code == 0
        assert "-$0.5000" in out
        assert "ANOMALY" in out and "spent" in out.split("ANOMALY", 1)[1].lower()


def test_a_negative_spent_is_in_the_json_unclamped_with_an_anomaly_list():
    store = ReadOnly(asyncio.run(populated()))
    corrupt(store)
    _, out, _ = run(["--day", DAY, "--json"], store)
    d = json.loads(out)
    assert d["figures"]["spent"] == pytest.approx(-0.5) and d["anomalies"]
    _, out, _ = run(["--month", MONTH, "--json"], store)
    d = json.loads(out)
    assert d["spent"] == pytest.approx(-0.5) and d["days"][DAY]["spent"] == pytest.approx(-0.5) and d["anomalies"]


def test_float_noise_is_not_an_anomaly():
    store = ReadOnly(asyncio.run(populated()))
    corrupt(store, spent=-1e-12)
    for argv in (["--day", DAY], ["--month", MONTH]):
        _, out, _ = run(argv, store)
        assert "ANOMALY" not in out and "-$" not in out
    _, out, _ = run(["--month", MONTH, "--json"], store)
    assert json.loads(out)["anomalies"] == []


def test_a_healthy_report_has_no_anomalies():
    store = ReadOnly(asyncio.run(populated()))
    _, out, _ = run(["--day", DAY, "--json"], store)
    assert json.loads(out)["anomalies"] == []
    _, text, _ = run(["--day", DAY], store)
    assert "ANOMALY" not in text
