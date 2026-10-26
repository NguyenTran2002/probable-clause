"""The nginx configuration, both profiles (contract 4.I, T3.5, T4.2, T5.5)."""

import re
import shutil
import subprocess

import pytest

from api import settings
from tests.deploy.helpers import DEPLOY, read


def _strip(text: str) -> str:
    """Config text without comments and blank lines."""
    return "\n".join(l.rstrip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#"))


def _block(text: str, header: str) -> str:
    """The body of the brace block that starts at `header` (balanced braces)."""
    start = text.index(header)
    i = text.index("{", start)
    depth = 0
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return text[i + 1:j]
    raise AssertionError("unbalanced braces")


def _locations(text: str) -> dict[str, str]:
    server = _block(_strip(text), "server {")
    out = {}
    for m in re.finditer(r"^\s*location\s+([^{]+?)\s*\{", server, re.M):
        out[m.group(1)] = _block(server[m.start():], "location")
    return out


PROFILES = ["nginx.conf", "nginx.local.conf"]


@pytest.mark.parametrize("name", PROFILES)
def test_cache_control_everywhere(name):
    text = _strip(read(name))
    server = _block(text, "server {")
    server_level = re.sub(r"location\s+[^{]+\{[^{}]*\}", "", server)
    assert re.search(r'add_header Cache-Control "no-cache" always;', server_level)
    # add_header is inherited only by a location with no add_header of its own
    # (nginx.org, ngx_http_headers_module, read Oct 24, 2026): each location either has none or repeats Cache-Control
    locs = _locations(read(name))
    assert locs
    for path, body in locs.items():
        if "add_header" in body:
            assert "Cache-Control" in body, f"location {path} defines add_header without Cache-Control"


@pytest.mark.parametrize("name", PROFILES)
def test_basics(name):
    text = _strip(read(name))
    assert "server_tokens off;" in text
    assert "charset utf-8;" in text and "gzip_vary on;" in text and "worker_processes 1;" in text
    assert "autoindex off;" in text and "autoindex on" not in text
    assert re.search(r"listen 8080\b", text)               # deploy.sh passes --port=8080
    assert "try_files $uri $uri.html $uri/index.html =404;" in text  # no directory listing, no fall-through to a directory
    assert "access_log off;" in text                       # T3.7: no client address kept by us
    assert "X-Forwarded-For" not in text or 'X-Forwarded-For ""' in text


@pytest.mark.parametrize("name", PROFILES)
def test_types(name):
    types = _block(_strip(read(name)), "types {")
    pairs = {}
    for line in types.splitlines():
        parts = line.strip().rstrip(";").split()
        for ext in parts[1:]:
            pairs[ext] = parts[0]
    assert pairs["js"] == "text/javascript" and pairs["mjs"] == "text/javascript"
    assert pairs["json"] == "application/json"
    assert pairs["woff2"] == "font/woff2"
    assert pairs["html"] == "text/html" and pairs["css"] == "text/css"


@pytest.mark.parametrize("name", PROFILES)
def test_csp_allows_only_own_origin(name):
    text = read(name)
    m = re.search(r'add_header Content-Security-Policy "([^"]+)"', text)
    assert m
    policy = m.group(1)
    assert "default-src 'none'" in policy
    assert not re.search(r"https?:|\*", policy)
    for directive in ("script-src", "font-src", "connect-src"):
        assert f"{directive} 'self';" in policy                 # scripts: own origin only, nothing inline
    assert "style-src 'self' 'unsafe-inline';" in policy        # inline style attributes set by the page's code
    assert policy.count("unsafe-") == 1


def test_production_has_no_proxy():
    text = _strip(read("nginx.conf"))
    assert "proxy_pass" not in text and "/api" not in text   # goodnight routes /probable-clause/api/ (T3.5)


def test_local_profile_proxies_api_for_server_sent_events():
    text = read("nginx.local.conf")
    loc = _locations(text)["/api/"]
    assert "rewrite ^/api/(.*)$ /$1 break;" in loc           # prefix stripped
    assert "proxy_pass http://$api_upstream;" in loc
    assert "proxy_buffering off;" in loc and "proxy_cache off;" in loc and "gzip off;" in loc
    assert "proxy_http_version 1.1;" in loc
    m = re.search(r"proxy_read_timeout (\d+)s;", loc)
    assert m
    # longer than a stream connection can live: the API's own request timeout (api/settings.py)
    assert int(m.group(1)) >= settings.API_REQUEST_TIMEOUT_S.value
    # the upstream is the container local.sh names, on its port
    upstream = re.search(r"set \$api_upstream (\S+):(\d+);", loc)
    assert f'API_NAME="{upstream.group(1)}"' in read("local.sh")
    assert upstream.group(2) == "8080"


def test_profiles_differ_only_by_the_api_proxy():
    prod = _strip(read("nginx.conf"))
    local = _strip(read("nginx.local.conf"))
    body = _block(local, "location /api/")
    without = local.replace("location /api/ {" + body + "}", "")
    assert without != local
    without = re.sub(r"\n\s*resolver [^\n]+", "", without)
    norm = lambda s: re.sub(r"\s+", " ", s)
    assert norm(without) == norm(prod)


@pytest.mark.skipif(shutil.which("nginx") is None, reason="no nginx binary installed")
@pytest.mark.parametrize("name", PROFILES)
def test_nginx_t(name, tmp_path):
    r = subprocess.run(["nginx", "-t", "-c", str(DEPLOY / name), "-p", str(tmp_path)],
                       capture_output=True, text=True)
    emerg = [l for l in r.stderr.splitlines() if "[emerg]" in l and "Permission denied" not in l
             and "open()" not in l]
    assert not emerg, r.stderr
