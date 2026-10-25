"""`api/main.py` (contract §4.H): `app` imports without `api.loop`; the environment is read and refused as T5.6 says.
No test here loads the real dependencies, reads `.env`, or touches the network."""

import subprocess
import sys

import pytest

from api.main import ConfigError, read_config
from tests.server.support import ROOT

KEYS = {"ANTHROPIC_API_KEY": "sk-ant-test-value", "VOYAGE_API_KEY": "pa-test-value", "EXA_API_KEY": "exa-test-value",
        "MONGODB_URI": "mongodb+srv://user:pw@cluster.example.invalid/"}


def test_main_imports_without_the_loop_and_exposes_app():
    code = ("import sys, api.main; from fastapi import FastAPI; "
            "assert isinstance(api.main.app, FastAPI); "
            "print(sorted(m for m in sys.modules if m.startswith('api.loop') or m in "
            "('api.corpus.store', 'api.search.meaning', 'api.state.store', 'numpy')))")
    out = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(ROOT)!r}); {code}"],
                         capture_output=True, text=True, cwd=ROOT, env={"PATH": ""}, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    loaded = eval(out.stdout.strip())
    assert not [m for m in loaded if m.startswith("api.loop")], "api.loop is imported only by the deps factory"


def test_config_defaults_to_test_and_the_full_corpus():
    cfg = read_config(dict(KEYS))
    assert (cfg.env, cfg.corpus_label, cfg.commit) == ("test", "full", "unknown")
    cfg = read_config(dict(KEYS, PC_ENV="live", PC_COMMIT="ab12cd3"))
    assert (cfg.env, cfg.corpus_label, cfg.commit) == ("live", "full", "ab12cd3")
    assert read_config(dict(KEYS, PC_CORPUS="before_chatrie")).corpus_label == "before_chatrie"
    assert read_config(dict(KEYS, PC_COMMIT="<script>")).commit == "unknown"


def test_before_chatrie_is_refused_when_live():
    with pytest.raises(ConfigError, match="T5.6"):
        read_config(dict(KEYS, PC_ENV="live", PC_CORPUS="before_chatrie"))


@pytest.mark.parametrize("env", [{"PC_ENV": "prod"}, {"PC_ENV": "LIVE"}, {"PC_CORPUS": "no_chatrie"}])
def test_unknown_values_are_refused(env):
    with pytest.raises(ConfigError):
        read_config(dict(KEYS, **env))


def test_a_missing_secret_is_named_never_shown():
    env = dict(KEYS)
    del env["EXA_API_KEY"]
    env["VOYAGE_API_KEY"] = "  "
    with pytest.raises(ConfigError) as e:
        read_config(env)
    msg = str(e.value)
    assert "EXA_API_KEY" in msg and "VOYAGE_API_KEY" in msg
    assert not any(v in msg for v in KEYS.values())


@pytest.mark.anyio
async def test_build_deps_refuses_before_loading_anything(monkeypatch):
    import api.main as main
    monkeypatch.setattr(main, "ROOT", ROOT / "does-not-exist")     # loading would fail loudly if it started
    with pytest.raises(ConfigError):
        await main.build_deps(dict(KEYS, PC_ENV="live", PC_CORPUS="before_chatrie"))


@pytest.mark.anyio
async def test_a_failed_start_up_never_serves():
    from api.server import create_app
    from tests.server.support import lifespan

    async def factory():
        raise ConfigError("PC_CORPUS=before_chatrie is recording-only and refused when PC_ENV=live (T5.6)")

    app = create_app(factory)
    with pytest.raises(RuntimeError):
        async with lifespan(app):
            pass
    assert app.state.pc.ready is False
