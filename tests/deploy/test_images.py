"""The two Dockerfiles and their ignore files (contract 4.I, T3.5, T3.6, T3.7)."""

import re

import pytest

from tests.deploy.helpers import DEPLOY, instructions, read

FORBIDDEN = (".env", "data/raw", "data/cache", "data/verification", "tests", "webdev", "web/_generated",
             "web/looktests", ".git", ".venv", "docs", "BUILD_LOG")
API_COPY_ALLOWED = {"pyproject.toml", "uv.lock", ".python-version", "api/", "contracts/", "data/corpus/", "data/vectors/"}
WEB_COPY_ALLOWED = {"pyproject.toml", "uv.lock", ".python-version", "api/", "data/corpus/", "scripts/build_web_data.py",
                    "deploy/nginx.conf", "deploy/nginx.local.conf", "web/"}
EXACT = re.compile(r":\d+(\.\d+){1,3}([-.][A-Za-z0-9.]+)*$")


def _sources(dockerfile: str) -> list[str]:
    srcs = []
    for ins, rest in instructions(dockerfile):
        if ins != "COPY":
            continue
        parts = [p for p in rest.split() if not p.startswith("--")]
        if any(p.startswith("--from=") for p in rest.split()):
            continue
        srcs += parts[:-1]
    return srcs


@pytest.mark.parametrize("name", ["api.Dockerfile", "web.Dockerfile"])
def test_images_have_exact_versions(name):
    text = read(name)
    refs = []
    for ins, rest in instructions(text):
        if ins == "FROM":
            ref = rest.split()[0]
            if ref not in {"build", "data"}:
                refs.append(ref)
        if ins == "COPY":
            for tok in rest.split():
                if tok.startswith("--from=") and "/" in tok:
                    refs.append(tok[len("--from="):])
    assert refs
    for ref in refs:
        assert EXACT.search(ref), f"{ref} is not an exact version"
        assert "latest" not in ref
    assert "python:3.13." in text          # P0.1: 3.13, at an exact patch version
    assert re.search(r"astral-sh/uv:\d+\.\d+\.\d+ ", text)


def test_nginx_version_is_exact_and_stable_line():
    text = read("web.Dockerfile")
    assert re.search(r"^FROM nginx:\d+\.\d+\.\d+-alpine[0-9.]*-slim$", text, re.M)


def test_api_image_checks_fts5_and_bakes_the_commit():
    text = read("api.Dockerfile")
    ins = instructions(text)
    fts = [rest for i, rest in ins if i == "RUN" and "fts5" in rest.lower()]
    assert fts and "assert" in fts[0], "the build must fail if SQLite lacks FTS5 (T3.6)"
    assert "uv sync --locked --no-dev" in text
    assert "--frozen" not in text
    assert ("ARG", "PC_COMMIT") in ins
    assert any(i == "ENV" and "PC_COMMIT=$PC_COMMIT" in r for i, r in ins)
    assert any(i == "RUN" and 'test -n "$PC_COMMIT"' in r for i, r in ins)
    # PC_ENV must not be baked: only deploy.sh sets live
    assert not any(i == "ENV" and "PC_ENV" in r for i, r in ins)


def test_api_image_runs_non_root_uvicorn_on_port():
    ins = instructions(read("api.Dockerfile"))
    users = [r for i, r in ins if i == "USER"]
    assert users and not users[-1].startswith(("root", "0"))
    cmd = [r for i, r in ins if i == "CMD"][-1]
    assert "uvicorn api.main:app" in cmd
    assert "${PORT" in cmd


def test_api_image_copies_only_what_it_needs():
    srcs = _sources(read("api.Dockerfile"))
    assert set(srcs) <= API_COPY_ALLOWED, set(srcs) - API_COPY_ALLOWED
    assert {"api/", "data/corpus/", "data/vectors/"} <= set(srcs)
    for s in srcs:
        assert s not in (".", "./")
        assert not any(s.startswith(f) for f in FORBIDDEN), s


def test_web_image_copies_only_what_it_needs():
    text = read("web.Dockerfile")
    srcs = _sources(text)
    assert set(srcs) <= WEB_COPY_ALLOWED, set(srcs) - WEB_COPY_ALLOWED
    for s in srcs:
        assert s not in (".", "./")
        assert not any(s.startswith(f) for f in FORBIDDEN), s
    assert "scripts/build_web_data.py --out" in text           # reader files, corpus.json, config.json
    assert "COPY webdev" not in text and "_generated" not in " ".join(srcs)
    # the image builds without replays/ (it may not exist yet): never a plain COPY of it
    assert not any(s.startswith("replays") for s in srcs)
    assert "if [ -d /ctx/replays ]" in text


def test_web_image_clears_the_welcome_page_and_guards_the_build():
    text = read("web.Dockerfile")
    final = text[text.index("FROM nginx"):]
    clear = final.index("find /usr/share/nginx/html -mindepth 1 -delete")
    copy_web = final.index("COPY web/ /usr/share/nginx/html/")
    copy_data = final.index("COPY --from=data /out/")
    assert clear < copy_web < copy_data                    # nginx's own index.html is gone before ours lands
    guard1 = final[copy_web:copy_data]                     # web/ alone: its own index.html, fonts, OFL text
    assert "test -f /usr/share/nginx/html/index.html" in guard1
    assert "fonts -name '*.woff2'" in guard1 and "OFL" in guard1
    guard2 = final[copy_data:]                             # build_web_data.py's output
    for need in ("test -f /usr/share/nginx/html/config.json", "test -f /usr/share/nginx/html/corpus.json",
                 "test -d /usr/share/nginx/html/opinions"):
        assert need in guard2


def _ignore_lines(name):
    return [l.strip() for l in read(name).splitlines() if l.strip() and not l.startswith("#")]


@pytest.mark.parametrize("name", ["api.Dockerfile.dockerignore", "web.Dockerfile.dockerignore"])
def test_ignore_files_exclude_secrets_and_local_data(name):
    lines = _ignore_lines(name)
    assert "**/.DS_Store" in lines
    for needed in (".env", "data/raw", "data/cache", "data/verification", ".venv", ".git"):
        assert needed in lines, f"{name} must list {needed}"
        # an exclusion must not be undone by a later allow
        assert not any(l == f"!{needed}" for l in lines)
    assert lines[0] == "*"                         # an allow-list, not a deny-list
    last_allow = max(i for i, l in enumerate(lines) if l.startswith("!"))
    assert lines.index(".env") > last_allow        # denials come last, so they win


def test_web_ignore_leaves_out_looktests_generated_and_webdev():
    lines = _ignore_lines("web.Dockerfile.dockerignore")
    for p in ("web/looktests", "web/_generated", "webdev"):
        assert p in lines
        assert lines.index(p) > lines.index("!web")
    assert "!replays" in lines


def test_api_ignore_allows_only_runtime_paths():
    allowed = {l[1:] for l in _ignore_lines("api.Dockerfile.dockerignore") if l.startswith("!")}
    assert allowed == {"api", "contracts", "data/corpus", "data/vectors", "pyproject.toml", "uv.lock", ".python-version"}


def test_no_absolute_local_paths_in_deploy_files():
    for p in DEPLOY.iterdir():
        if p.is_file():
            assert "/Users/" not in p.read_text() and "/home/" not in p.read_text(), p.name


def test_api_image_shuts_down_within_cloud_runs_grace():
    # contract v1.2: the lifespan shutdown releases reservations before Cloud Run's SIGKILL, 10 s after SIGTERM
    from api import settings
    grace = int(settings.SHUTDOWN_GRACE_S.value)
    assert f"--timeout-graceful-shutdown {grace}" in read("api.Dockerfile")
    assert 0 < grace < 10
