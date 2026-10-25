"""scripts/spend_report.py: read-only reports for a day, a month, and the deploy check (T3.4, T3.5)."""

import asyncio
import importlib.util
import io
import json
from pathlib import Path

import pytest

from api import settings
from api.protocols import Reservation
from api.state.store import MemoryStore, StoreUnavailable
from tests.state.cases import DAY, MONTH, T, W, at

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("spend_report_under_test", ROOT / "scripts" / "spend_report.py")
sr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sr)

URI_WITH_SECRET = "mongodb://someuser:SUPERSECRETPASSWORD@cluster.example.mongodb.net/?retryWrites=true"


class ReadOnly:
    """Wraps a store and fails the test if the script calls anything that writes."""
    WRITES = {"ensure_indexes", "append_events", "put_heartbeat", "upsert_run_record", "reserve", "settle", "release",
              "record_stop", "set_flag"}

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        if name in self.WRITES:
            raise AssertionError(f"spend_report called {name}")
        return getattr(self._inner, name)


async def populated():
    s = MemoryStore()
    r1 = await s.reserve("run-a", W, T)
    await s.settle(r1, 0.75)
    await s.release(r1)
    for i in range(5):
        await s.reserve(f"held-{i}", W, at("05-14", 12, i))
    await s.reserve("refused", W, at("05-14", 13, 0))                       # daily_cap
    await s.record_stop("step_limit", "run-a", at("05-14", 12, 30), {})
    await s.reserve("next-day", 2.0, at("05-15", 9, 0))
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
    assert "$0.75" in out or "0.7500" in out                                    # day spent
    assert "SUPERSECRET" not in out


def test_day_report_in_json():
    store = ReadOnly(asyncio.run(populated()))
    code, out, _ = run(["--day", DAY, "--json"], store)
    d = json.loads(out)
    assert code == 0 and d["day"] == DAY
    assert d["figures"]["runs_started"] == 6
    assert d["figures"]["stops"] == {"daily_cap": 1, "step_limit": 1}
    assert d["figures"]["spent"] == pytest.approx(0.75)
    assert d["figures"]["reserved"] == pytest.approx(5 * W)
    assert [s["kind"] for s in d["stops"]] == ["daily_cap", "step_limit"] or {s["kind"] for s in d["stops"]} == {"daily_cap", "step_limit"}


def test_month_report_lists_every_day():
    store = ReadOnly(asyncio.run(populated()))
    code, out, _ = run(["--month", MONTH, "--json"], store)
    d = json.loads(out)
    assert code == 0 and d["month"] == MONTH
    assert set(d["days"]) == {"2030-05-14", "2030-05-15"}
    assert d["spent"] == pytest.approx(0.75) and d["reserved"] == pytest.approx(5 * W + 2.0)
    text_code, text, _ = run(["--month", MONTH], store)
    assert text_code == 0 and "2030-05-15" in text and "2030-05" in text


def test_an_empty_day_and_month_say_so_and_exit_zero():
    store = ReadOnly(MemoryStore())
    for argv in (["--day", "2030-07-01"], ["--month", "2030-07"]):
        code, out, _ = run(argv, store)
        assert code == 0 and "no spend recorded" in out.lower()


def test_open_reservations_exit_nonzero_for_the_deploy_check():
    store = ReadOnly(asyncio.run(populated()))
    code, out, _ = run(["--open-reservations"], store)
    assert code == 1
    for run_id in ("held-0", "held-4", "next-day"):
        assert run_id in out
    assert "run-a" not in out                                                  # released
    code, out, _ = run(["--open-reservations", "--json"], store)
    d = json.loads(out)
    assert code == 1 and {o["run"] for o in d["open_reservations"]} == {"held-0", "held-1", "held-2", "held-3", "held-4", "next-day"}


def test_no_open_reservations_exits_zero():
    s = MemoryStore()

    async def go():
        r = await s.reserve("run-a", W, T)
        await s.release(r)

    asyncio.run(go())
    code, out, _ = run(["--open-reservations"], ReadOnly(s))
    assert code == 0 and "no open reservations" in out.lower()


def test_an_unreachable_store_exits_two_and_names_no_secret():
    s = MemoryStore()
    s.unreachable = True
    code, out, err = run(["--open-reservations"], s)
    assert code == 2 and "SUPERSECRET" not in out + err and "someuser" not in out + err
    assert "unreachable" in err.lower() or "could not" in err.lower()          # the deploy script must not read this as "none open"


def test_exactly_one_report_must_be_chosen():
    for argv in ([], ["--day", DAY, "--month", MONTH], ["--day", DAY, "--open-reservations"]):
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
    code = sr.main(["--open-reservations"], store_factory=lambda u, d: MemoryStore(), out=out, err=err, env={})
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
        sr.main(["--open-reservations", *argv], store_factory=factory, out=out, err=err, env=env)
        assert seen[-1] == (URI_WITH_SECRET, expected)
        assert "SUPERSECRET" not in out.getvalue() + err.getvalue()
        assert expected in out.getvalue()                                      # says which database it read


def test_a_bad_pc_env_is_refused():
    out, err = io.StringIO(), io.StringIO()
    code = sr.main(["--open-reservations"], store_factory=lambda u, d: MemoryStore(), out=out, err=err,
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

    async def open_reservations(self, now):
        if self._boom:
            raise self._boom
        return self._month


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
    failed(["--day", DAY], Strange(month={"days": {DAY: {"spent": 1.0, "reserved": 0.0, "runs_started": 1}}},
                                   stops=[{"kind": "daily_cap"}]))                      # a stop with no date, time or at
    failed(["--open-reservations"], Strange(month=[{"run": "r1"}]))                    # an entry without its fields


def test_an_unexpected_exception_from_the_store_exits_two_without_its_text():
    boom = RuntimeError("mongodb://someuser:SUPERSECRET@cluster.example.mongodb.net/ secret-question")
    for argv in (["--day", DAY], ["--month", MONTH], ["--open-reservations"], ["--open-reservations", "--json"]):
        failed(argv, Strange(boom=boom))


def test_a_store_that_cannot_be_built_exits_two():
    def factory(uri, db):
        raise ValueError("bad uri " + uri)

    out, err = io.StringIO(), io.StringIO()
    code = sr.main(["--open-reservations"], store_factory=factory, out=out, err=err, env={"MONGODB_URI": URI_WITH_SECRET})
    assert code == 2 and "SUPERSECRET" not in out.getvalue() + err.getvalue() and "Traceback" not in err.getvalue()


def test_an_invalid_uri_through_the_real_store_class_exits_two():
    for uri in ("mongodb://someuser:SUPERSECRET@cluster.example:notaport/", "mongodb://[::1", "nonsense://x"):
        out, err = io.StringIO(), io.StringIO()
        code = sr.main(["--open-reservations"], out=out, err=err, env={"MONGODB_URI": uri})
        assert code == 2
        assert "Traceback" not in err.getvalue() and "SUPERSECRET" not in out.getvalue() + err.getvalue()
        assert "cluster.example" not in out.getvalue() + err.getvalue() and "someuser" not in out.getvalue() + err.getvalue()
        assert any(m in err.getvalue() for m in FIXED_MESSAGES)
        assert out.getvalue() == ""


def test_open_reservations_still_exits_one_not_two():
    store = ReadOnly(asyncio.run(populated()))
    code, _, err = run(["--open-reservations"], store)
    assert code == 1 and err == ""


# --- negative figures are shown, not clamped (T3.4) ----------------------------------------------------------------------------

def corrupt(store, reserved=-0.5):
    inner = store._inner if isinstance(store, ReadOnly) else store
    doc = inner._spend[MONTH]
    doc["reserved"] = reserved
    doc["days"][DAY]["reserved"] = reserved


def test_usd_shows_negatives():
    assert sr._usd(-0.5) == "-$0.5000"
    assert sr._usd(0.5) == "$0.5000"
    assert sr._usd(None) == "unknown"
    assert sr._usd(-1e-12) == "$0.0000"                      # float noise is not shown as a negative zero


def test_a_negative_reserved_is_shown_and_flagged_in_text():
    store = ReadOnly(asyncio.run(populated()))
    corrupt(store)
    for argv in (["--day", DAY], ["--month", MONTH]):
        code, out, _ = run(argv, store)
        assert code == 0
        assert "-$0.5000" in out
        assert "ANOMALY" in out and "reserved" in out.split("ANOMALY", 1)[1].lower()


def test_a_negative_reserved_is_in_the_json_unclamped_with_an_anomaly_list():
    store = ReadOnly(asyncio.run(populated()))
    corrupt(store)
    _, out, _ = run(["--day", DAY, "--json"], store)
    d = json.loads(out)
    assert d["figures"]["reserved"] == pytest.approx(-0.5) and d["anomalies"]
    _, out, _ = run(["--month", MONTH, "--json"], store)
    d = json.loads(out)
    assert d["reserved"] == pytest.approx(-0.5) and d["days"][DAY]["reserved"] == pytest.approx(-0.5) and d["anomalies"]


def test_float_noise_is_not_an_anomaly():
    store = ReadOnly(asyncio.run(populated()))
    corrupt(store, reserved=-1e-12)
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


def test_a_negative_reservation_amount_is_flagged_too():
    store = ReadOnly(asyncio.run(populated()))
    inner = store._inner
    inner._spend[MONTH]["reservations"]["held-0"]["amount"] = -0.25
    code, out, _ = run(["--open-reservations"], store)
    assert code == 1 and "-$0.2500" in out and "ANOMALY" in out
