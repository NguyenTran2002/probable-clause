"""setup.sh (P4.30, P5.1): syntax, the names it shares with deploy.sh, and its calls under stub tools.

setup.sh only ever runs here under stubs for uv and gcloud in a temporary directory, on a PATH that holds
nothing else of the project's. Nothing reaches the cloud. The secret values are fakes set in the test's
environment, and the checks below show they reach gcloud's standard input and nowhere else.
"""

import re
import stat
import subprocess
import sys

import pytest

from tests.deploy.helpers import DEPLOY, read

BASH = "/bin/bash"

FAKES = {
    "ANTHROPIC_API_KEY_LIVE": "fake-live-key-1111",
    "ANTHROPIC_API_KEY": "fake-dev-key-2222",
    "VOYAGE_API_KEY": "fake-voyage-3333",
    "EXA_API_KEY": "fake-exa-4444",
    "MONGODB_URI": "mongodb+srv://fake:5555@example.invalid/",
}
SECRETS = {
    "pc-anthropic-api-key": "ANTHROPIC_API_KEY_LIVE",
    "pc-voyage-api-key": "VOYAGE_API_KEY",
    "pc-exa-api-key": "EXA_API_KEY",
    "pc-mongodb-uri": "MONGODB_URI",
}

STUBS = {
    "uv": r"""#!/bin/sh
echo "uv	$*" >> "$PC_TEST_LOG"
while [ "$#" -gt 0 ] && [ "$1" != "python" ]; do shift; done
shift
exec "$PC_TEST_PYTHON" "$@"
""",
    "gcloud": r"""#!/bin/sh
for a in "$@"; do args="$args	$a"; done
echo "gcloud$args" >> "$PC_TEST_LOG"
case "$*" in
  *" describe "*) exit "${PC_TEST_DESCRIBE_RC:-1}" ;;
  "secrets versions list"*) [ -n "${PC_TEST_HAS_VERSION:-}" ] && echo "projects/1/secrets/$4/versions/1" ;;
  "secrets versions add"*) cat > "$PC_TEST_LOG.stdin.$4" ;;
esac
exit 0
""",
}


@pytest.fixture
def sandbox(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in STUBS.items():
        p = bin_dir / name
        p.write_text(body)
        p.chmod(p.stat().st_mode | stat.S_IXUSR)
    log = tmp_path / "calls.log"
    log.write_text("")
    env = {
        "PATH": f"{bin_dir}:/bin:/usr/bin",
        "PC_TEST_LOG": str(log),
        "PC_TEST_PYTHON": sys.executable,
        "HOME": str(tmp_path),
        **FAKES,
    }

    def run(drop=(), **extra):
        e = {k: v for k, v in {**env, **extra}.items() if k not in drop}
        r = subprocess.run([BASH, str(DEPLOY / "setup.sh")], env=e, capture_output=True, text=True,
                           cwd=tmp_path, timeout=60)
        calls = [l.split("\t") for l in log.read_text().splitlines() if l]
        stdin = {p.name.rsplit(".", 1)[1]: p.read_text() for p in tmp_path.glob("calls.log.stdin.*")}
        return r, calls, stdin, log.read_text()

    return run


def _gcloud(calls):
    return [c[1:] for c in calls if c[0] == "gcloud"]


def test_setup_parses():
    r = subprocess.run([BASH, "-n", str(DEPLOY / "setup.sh")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    text = read("setup.sh")
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text


def test_names_match_deploy_sh():
    pattern = re.compile(r'^(API_SA|WEB_SA|REGISTRY_REPO|SECRET_[A-Z]+)="([^"]+)"$', re.M)
    deploy = dict(pattern.findall(read("deploy.sh")))
    setup = dict(pattern.findall(read("setup.sh")))
    assert setup and setup == deploy


def test_happy_path_creates_everything_in_order(sandbox):
    r, calls, stdin, _ = sandbox()
    assert r.returncode == 0, r.stderr
    g = _gcloud(calls)
    assert g[0][:2] == ["services", "enable"]
    assert {"run.googleapis.com", "artifactregistry.googleapis.com", "secretmanager.googleapis.com"} <= set(g[0])
    assert all("--project=probable-clause" in c for c in g if c[:2] != ["auth", "configure-docker"])
    kinds = [" ".join(c[:3]) for c in g]
    assert "artifacts repositories create" in kinds
    assert ["iam", "service-accounts", "create", "pc-api"] in [c[:4] for c in g]
    assert ["iam", "service-accounts", "create", "pc-web"] in [c[:4] for c in g]
    for name in SECRETS:
        assert ["secrets", "create", name] in [c[:3] for c in g]
        binding = next(c for c in g if c[:3] == ["secrets", "add-iam-policy-binding", name])
        assert "--member=serviceAccount:pc-api@probable-clause.iam.gserviceaccount.com" in binding
        assert "--role=roles/secretmanager.secretAccessor" in binding
    assert not any("pc-web" in a for c in g if c[1] == "add-iam-policy-binding" for a in c)
    assert g[-1][:2] == ["auth", "configure-docker"] and g[-1][2] == "us-central1-docker.pkg.dev"


def test_each_secret_gets_its_value_on_stdin_only(sandbox):
    r, calls, stdin, log = sandbox()
    assert r.returncode == 0, r.stderr
    assert stdin == {name: FAKES[var] for name, var in SECRETS.items()}    # no newline, the live key for Anthropic
    for value in FAKES.values():
        assert value not in r.stdout and value not in r.stderr and value not in log


def test_the_development_anthropic_key_is_never_used(sandbox):
    r, calls, stdin, _ = sandbox()
    assert FAKES["ANTHROPIC_API_KEY"] not in stdin.values()
    assert not any(c[0] == "uv" and re.search(r"\bANTHROPIC_API_KEY\b(?!_LIVE)", c[1]) for c in calls)


def test_a_missing_value_stops_before_its_secret_is_made(sandbox):
    r, calls, stdin, _ = sandbox(drop=("EXA_API_KEY",))
    assert r.returncode == 1
    assert "EXA_API_KEY is not set" in r.stderr
    g = _gcloud(calls)
    assert not any("pc-exa-api-key" in c for c in g)
    assert not any("pc-mongodb-uri" in c for c in g)                   # it stops, nothing after it runs
    assert set(stdin) == {"pc-anthropic-api-key", "pc-voyage-api-key"}


def test_rerun_with_everything_present_creates_nothing(sandbox):
    r, calls, stdin, _ = sandbox(PC_TEST_DESCRIBE_RC="0", PC_TEST_HAS_VERSION="1")
    assert r.returncode == 0, r.stderr
    g = _gcloud(calls)
    assert not any(c[1] == "create" or c[2:3] == ["create"] for c in g if len(c) > 2)
    assert not any(c[:3] == ["secrets", "versions", "add"] for c in g)
    assert stdin == {}
    assert r.stdout.count("already has an enabled version") == 4


def test_setup_never_reads_env_and_has_no_absolute_paths():
    text = read("setup.sh")
    assert not re.search(r"\b(cat|source|grep|\.)\s+\.env\b", text)
    assert "--env-file .env" in text                                    # only uv loads it
    assert "/Users/" not in text and "/home/" not in text
    assert "echo \"$" not in text.replace('echo "setup', "")            # no variable echoed on its own
    assert "set -x" not in text
