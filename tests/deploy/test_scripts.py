"""deploy.sh and local.sh: syntax, settings tracing, and the spend gate under stub tools (contract 4.I, T3.5).

deploy.sh only ever runs here, under stubs for uv, git, gcloud and docker in a temporary directory, on a
PATH that holds nothing else of the project's. Nothing reaches the cloud, Docker or Atlas.
"""

import os
import re
import stat
import subprocess
import sys

import pytest

from api import settings
from tests.deploy.helpers import DEPLOY, ROOT, read

BASH = "/bin/bash"

STUBS = {
    "uv": r"""#!/bin/sh
echo "uv	$*" >> "$PC_TEST_LOG"
case "$*" in
  *spend_report.py*)
    n=0
    [ -f "$PC_TEST_LOG.n" ] && read n < "$PC_TEST_LOG.n"
    n=$((n + 1))
    echo "$n" > "$PC_TEST_LOG.n"
    if [ "$n" -ge 2 ]; then exit "${PC_TEST_SPEND_RC_2:-${PC_TEST_SPEND_RC:-0}}"; fi
    exit "${PC_TEST_SPEND_RC:-0}" ;;
esac
while [ "$#" -gt 0 ] && [ "$1" != "python" ]; do shift; done
shift
exec "$PC_TEST_PYTHON" "$@"
""",
    "git": r"""#!/bin/sh
echo "git	$*" >> "$PC_TEST_LOG"
case "$*" in
  "status --porcelain") printf '%s' "${PC_TEST_PORCELAIN:-}" ;;
  "rev-parse --short HEAD") echo abc1234 ;;
esac
exit 0
""",
    "gcloud": r"""#!/bin/sh
for a in "$@"; do args="$args	$a"; done
echo "gcloud$args" >> "$PC_TEST_LOG"
case "$*" in
  *"artifacts repositories describe"*) exit "${PC_TEST_REPO_RC:-0}" ;;
  *"secrets versions list"*) echo "projects/1/secrets/s/versions/7" ;;
esac
exit 0
""",
    "docker": r"""#!/bin/sh
for a in "$@"; do args="$args	$a"; done
echo "docker$args" >> "$PC_TEST_LOG"
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
    }

    def run(**extra):
        r = subprocess.run([BASH, str(DEPLOY / "deploy.sh")], env={**env, **extra}, capture_output=True,
                           text=True, cwd=tmp_path, timeout=60)
        calls = [l.split("\t") for l in log.read_text().splitlines() if l]
        return r, calls

    run.env = env
    run.bin = bin_dir
    return run


def test_scripts_parse():
    for name in ("deploy.sh", "local.sh"):
        r = subprocess.run([BASH, "-n", str(DEPLOY / name)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        text = read(name)
        assert text.startswith("#!/usr/bin/env bash")
        assert "set -euo pipefail" in text


def test_stubs_shadow_the_real_tools(sandbox):
    for tool in ("uv", "git", "gcloud", "docker"):
        r = subprocess.run(["/bin/sh", "-c", f"command -v {tool}"], env=sandbox.env, capture_output=True, text=True)
        assert r.stdout.strip() == str(sandbox.bin / tool), f"{tool} is not the stub"


@pytest.mark.parametrize("rc", [1, 2, 3])
def test_spend_gate_stops_before_anything_else(sandbox, rc):
    r, calls = sandbox(PC_TEST_SPEND_RC=str(rc))
    assert r.returncode == rc
    assert [c[0] for c in calls] == ["uv"], calls      # not even git: the gate is first
    assert "spend_report.py" in calls[0][1] and "--open-reservations" not in calls[0][1]


@pytest.mark.parametrize("rc", [1, 2])
def test_spend_gate_runs_again_right_before_the_api_deploy(sandbox, rc):
    r, calls = sandbox(PC_TEST_SPEND_RC_2=str(rc))
    assert r.returncode == rc
    gates = [i for i, c in enumerate(calls) if c[0] == "uv" and "spend_report.py" in c[1]]
    assert len(gates) == 2
    assert not _deploys(calls), "nothing may be deployed once the second check fails"
    # the images were built and pushed in between, and the second check is the last call
    assert any(c[0] == "docker" and c[1] == "push" for c in calls[gates[0]:gates[1]])
    assert gates[1] == len(calls) - 1


def test_second_spend_check_is_immediately_before_the_api_deploy(sandbox):
    r, calls = sandbox()
    assert r.returncode == 0, r.stderr
    gates = [i for i, c in enumerate(calls) if c[0] == "uv" and "spend_report.py" in c[1]]
    first_deploy = next(i for i, c in enumerate(calls) if c[0] == "gcloud" and c[1:3] == ["run", "deploy"])
    assert len(gates) == 2 and gates[1] == first_deploy - 1
    assert calls[first_deploy][3] == "probable-clause-api"


def test_spend_gate_command(sandbox):
    r, calls = sandbox()
    assert calls[0][0] == "uv"
    cmd = calls[0][1]
    # v2.0 (P4.21): no reservations to check; the live month must be readable
    assert re.match(r"run --frozen --env-file \.env python scripts/spend_report\.py --month \d{4}-\d{2} --env live$", cmd), cmd
    assert "--env live" in cmd                          # the report defaults to the test database


def test_dirty_tree_is_refused_before_cloud_or_docker(sandbox):
    r, calls = sandbox(PC_TEST_PORCELAIN=" M api/settings.py\n")
    assert r.returncode != 0
    tools = [c[0] for c in calls]
    assert "gcloud" not in tools and "docker" not in tools
    assert tools[0] == "uv" and "git" in tools


def test_missing_registry_stops_before_docker(sandbox):
    r, calls = sandbox(PC_TEST_REPO_RC="1")
    assert r.returncode != 0
    tools = [c[0] for c in calls]
    assert "docker" not in tools
    assert not any(c[0] == "gcloud" and c[1:3] == ["run", "deploy"] for c in calls)
    assert "Artifact Registry" in r.stderr


def _deploys(calls):
    return [c for c in calls if c[0] == "gcloud" and c[1:3] == ["run", "deploy"]]


def test_happy_path_order_and_flags(sandbox):
    r, calls = sandbox()
    assert r.returncode == 0, r.stderr
    tools = [c[0] for c in calls]
    first_deploy = next(i for i, c in enumerate(calls) if c[0] == "gcloud" and c[1:3] == ["run", "deploy"])
    last_push = max(i for i, c in enumerate(calls) if c[0] == "docker" and c[1] == "push")
    builds = [c for c in calls if c[0] == "docker" and c[1] == "build"]
    assert len(builds) == 2 and last_push < first_deploy       # both images built and pushed before any deploy
    for b in builds:
        assert "--platform=linux/amd64" in b                   # Cloud Run's platform, whatever machine runs this
    api_build = next(b for b in builds if "--file=deploy/api.Dockerfile" in b)
    assert "--build-arg=PC_COMMIT=abc1234" in api_build
    deploys = _deploys(calls)
    assert len(deploys) == 2
    api = dict(a.split("=", 1) for a in next(d for d in deploys if d[3] == "probable-clause-api")[4:] if "=" in a)
    web = dict(a.split("=", 1) for a in next(d for d in deploys if d[3] == "probable-clause-web")[4:] if "=" in a)
    s = settings
    # every Cloud Run value is read from api/settings.py, not typed in the script
    assert api["--project"] == web["--project"] == s.GCP_PROJECT.value
    assert api["--region"] == web["--region"] == s.GCP_REGION.value
    assert api["--min"] == str(s.API_MIN_INSTANCES.value) and api["--max"] == str(s.API_MAX_INSTANCES.value)
    assert api["--concurrency"] == str(s.API_CONCURRENCY.value)
    assert api["--cpu"] == str(s.API_CPU.value) and api["--memory"] == s.API_MEMORY.value
    assert api["--timeout"] == str(s.API_REQUEST_TIMEOUT_S.value)
    assert web["--min"] == str(s.WEB_MIN_INSTANCES.value) and web["--max"] == str(s.WEB_MAX_INSTANCES.value)
    # T3.5 and brief 8.5
    for d in deploys:
        assert "--scaling=auto" in d and "--allow-unauthenticated" in d and "--cpu-throttling" in d
    assert "--cpu-boost" in next(d for d in deploys if d[3] == "probable-clause-api")
    assert api["--set-env-vars"] == "PC_ENV=live"
    assert api["--image"].endswith("/api:abc1234") and web["--image"].endswith("/web:abc1234")
    assert api["--service-account"] != web["--service-account"]       # one service account per service
    assert "--set-secrets" not in web and "--set-env-vars" not in web
    secrets = dict(p.split("=", 1) for p in api["--set-secrets"].split(","))
    assert set(secrets) == {"ANTHROPIC_API_KEY", "VOYAGE_API_KEY", "EXA_API_KEY", "MONGODB_URI"}
    assert all(v.endswith(":7") for v in secrets.values())           # pinned to the newest enabled version
    assert api["--port"] == web["--port"] == "8080"
    assert "goodnight" not in " ".join(" ".join(c) for c in calls).lower()


def test_deploy_script_has_no_copied_settings_values_and_no_flag_arrays():
    text = read("deploy.sh")
    for name in dir(settings):
        if re.match(r"(GCP_|API_|WEB_)", name) and not name.startswith("_"):
            if name in ("API_MIN_INSTANCES", "API_MAX_INSTANCES", "API_CONCURRENCY", "API_CPU", "API_MEMORY",
                        "API_REQUEST_TIMEOUT_S", "WEB_MIN_INSTANCES", "WEB_MAX_INSTANCES", "GCP_PROJECT",
                        "GCP_REGION"):
                assert f'{name}="$(setting {name})"' in text, f"{name} is not read from api/settings.py"
    # every Cloud Run block name in settings is used (a new one must not be forgotten)
    block = [n for n in dir(settings) if re.match(r"(GCP_|API_|WEB_)", n) and not n.startswith("_")]
    for n in block:
        assert f"setting {n})" in text, f"{n} is in settings but not used by deploy.sh"
    for line in text.splitlines():
        m = re.match(r'\s+(--[a-z-]+)="([^"]*)"', line)
        if m and line.strip().endswith("\\"):
            value = m.group(2)
            assert "$" in value or value in {"auto", "all", "PC_ENV=live", "linux/amd64", "deploy/api.Dockerfile",
                                              "deploy/web.Dockerfile", "state=ENABLED", "~createTime", "value(name)"} \
                or m.group(1) == "--format", f"literal value on {line.strip()}"
    assert not re.search(r"=\(|declare -a|FLAGS=|ARGS=", text), "flags are written out, not built in an array or string"
    assert "goodnight" in text and "Nothing for goodnight" in text    # stated, and nothing is deployed for it
    assert not re.search(r"gcloud .*(goodnight|compute|iam policy)", text)


def test_deploy_never_reads_env_and_has_no_absolute_paths():
    for name in ("deploy.sh", "local.sh"):
        text = read(name)
        assert not re.search(r"\b(cat|source|\.)\s+\.env\b", text)
        assert "/Users/" not in text and "/home/" not in text


def test_local_script_contract():
    text = read("local.sh")
    assert '--publish "127.0.0.1:8000:8080"' in text and '--publish "127.0.0.1:8080:8080"' in text
    assert "uv run --frozen --env-file .env -- docker run" in text.replace("\\\n", "")   # uv parses .env
    for name in ("ANTHROPIC_API_KEY", "VOYAGE_API_KEY", "EXA_API_KEY", "MONGODB_URI"):
        assert f"-e {name} " in text.replace("\\\n", " ") or f"-e {name} \\" in text
    assert "COURTLISTENER" not in text.upper()                   # the token is never passed to the container
    for line in text.replace("\\\n", "").splitlines():
        if "docker" in line and "--env-file" in line and not line.lstrip().startswith("#"):
            assert line.split(" -- ", 1)[0].count("--env-file") == 1    # only uv's, left of `--`
            assert "--env-file" not in line.split(" -- ", 1)[1]
    assert "-e PC_ENV=test" in text and "PC_ENV=live" not in text
    assert "nginx -c /etc/nginx/nginx.local.conf" in text
    assert "trap cleanup EXIT" in text
    assert "docker rm --force" in text and "docker network rm" in text
    assert "gcloud" not in text
