"""The mock server for building the page (frontend brief §4). Development only; never served in production.

Python standard library only. Serves, on one port (8765 by default):
- web/ as the site root, exactly as the web image does;
- web/_generated/ (scripts/build_web_data.py's output) at the same root: opinions/, corpus.json, config.json;
- replays/: an index of the fixture streams marked as replays below, and each one as a replay file (contract §11.2);
- api/...: contract §5's endpoints, played from tests/fixtures/ (events/ and http/).

Which fixture a run plays, and which failure each endpoint answers, is a dev-only switch held here, never in web/:
    /__dev/                  a page listing the switches and fixtures
    /__dev/set?k=v&...       set switches (fixture, health, runs, events, speed, drop_after, keepalive_s)
    /__dev/state             the switches as JSON

Run: .venv/bin/python webdev/serve.py [--port 8765]
"""

import argparse
import json
import mimetypes
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
GENERATED = WEB / "_generated"
EVENTS = ROOT / "tests" / "fixtures" / "events"
HTTP = ROOT / "tests" / "fixtures" / "http"
REPLAYS = ROOT / "replays"            # the real ones, once recorded (P4.32); used when present
FIXTURE_REPLAYS = ["replay-geofence-before-chatrie"]

TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".mjs": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
         ".svg": "image/svg+xml", ".ico": "image/x-icon", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8"}

# The switches. health: ready | paused-day | paused-month | unknown | cloud-run-429 | cloud-run-500 | cloud-run-503 |
# gateway-502 | cold:<s> (plain-text 503 for <s> seconds after the first check, then ready) | hang (never answers) |
# slow:<s> (ready after <s> seconds). runs: ok | busy | paused-day | paused-month | atlas-unreachable |
# question-empty | question-too-long | body-too-large | cloud-run-503. events: ok | expired.
STATE = {"fixture": "answered-phone-location-records", "health": "ready", "runs": "ok", "events": "ok",
         "speed": 1.0, "drop_after": 0, "keepalive_s": 15}
LOCK = threading.Lock()
RUNS = {}          # run_id -> {"fixture", "started": monotonic of the first attach or None, "dropped": bool}
COLD = {"since": None}


def fixture_names():
    return sorted(p.stem for p in EVENTS.glob("*.json") if not p.stem.endswith(tuple(f"-after-n{i}" for i in range(1000))))


def load_fixture(name):
    return json.loads((EVENTS / f"{name}.json").read_text(encoding="utf-8"))


def http_fixture(name):
    return json.loads((HTTP / f"{name}.json").read_text(encoding="utf-8"))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "pc-mock"

    def log_message(self, fmt, *args):
        if "/api/" in self.path or "/__dev" in self.path:
            super().log_message(fmt, *args)

    # ---------- plumbing ----------
    def send(self, status, body=b"", ctype="application/json; charset=utf-8", headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_http_fixture(self, name):
        f = http_fixture(name)
        ctype = f["headers"].get("Content-Type", "application/json")
        self.send(f["status"], f["body"], ctype)

    def read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    # ---------- routes ----------
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith("/__dev"):
            return self.dev(path)
        if path.startswith("/api/"):
            return self.api_get(path[4:])
        if path == "/replays/index.json" or path.startswith("/replays/"):
            return self.replays(path)
        return self.static(path)

    def do_POST(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            return self.api_post(path[4:])
        self.send(405, json.dumps({"error": "method_not_allowed", "message": "mock"}))

    def static(self, path):
        rel = path.lstrip("/") or "index.html"
        if rel.endswith("/"):
            rel += "index.html"
        if ".." in Path(rel).parts:
            return self.send(404, "not found", "text/plain")
        # as nginx does: the file, then the page by its name without .html (sources-and-credits, privacy)
        for base, name in ((WEB, rel), (WEB, rel + ".html"), (GENERATED, rel)):
            f = (base / name).resolve()
            if f.is_file() and f.is_relative_to(WEB):
                ctype = TYPES.get(f.suffix, mimetypes.guess_type(f.name)[0] or "application/octet-stream")
                return self.send(200, f.read_bytes(), ctype)
        self.send(404, "<html><body>404</body></html>", "text/html")

    def replays(self, path):
        if REPLAYS.is_dir():
            f = (REPLAYS / path[len("/replays/"):]).resolve()
            if f.is_file() and f.is_relative_to(REPLAYS):
                return self.send(200, f.read_bytes())
            return self.send(404, "not found", "text/plain")
        if path == "/replays/index.json":
            items = []
            for slug in FIXTURE_REPLAYS:
                d = load_fixture(slug)
                items.append({"slug": slug, "question": d["question"], "recorded_at": d["recorded_at"],
                              "corpus_label": d["corpus_label"]})
            return self.send(200, json.dumps(items))
        m = re.fullmatch(r"/replays/([a-z0-9-]+)\.json", path)
        if m and (EVENTS / f"{m.group(1)}.json").is_file():
            return self.send(200, (EVENTS / f"{m.group(1)}.json").read_bytes())
        self.send(404, "not found", "text/plain")

    # ---------- the API ----------
    def api_get(self, path):
        if path == "/health":
            return self.health()
        m = re.fullmatch(r"/runs/([A-Za-z0-9_-]+)/events", path)
        if m:
            return self.events(m.group(1))
        self.send(404, json.dumps({"error": "not_found", "message": "mock"}))

    def api_post(self, path):
        self.read_body()
        if path == "/runs":
            return self.post_run()
        m = re.fullmatch(r"/runs/([A-Za-z0-9_-]+)/alive", path)
        if m:
            if STATE["events"] == "expired" or m.group(1) not in RUNS:
                return self.send_http_fixture("post-alive-404-run-unknown")
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send(404, json.dumps({"error": "not_found", "message": "mock"}))

    def health(self):
        h = STATE["health"]
        if h == "hang":
            time.sleep(3600)
            return
        if h.startswith("slow:"):
            time.sleep(float(h[5:]))
            h = "ready"
        if h.startswith("cold:"):
            with LOCK:
                if COLD["since"] is None:
                    COLD["since"] = time.monotonic()
                warm = time.monotonic() - COLD["since"] >= float(h[5:])
            if not warm:
                time.sleep(1.0)          # a check waits on a starting instance a while before Cloud Run refuses it
                return self.send_http_fixture("cloud-run-503")
            h = "ready"
        name = {"ready": "health-ready", "paused-day": "health-paused-day", "paused-month": "health-paused-month",
                "unknown": "health-unknown"}.get(h, h)
        self.send_http_fixture(name)

    def post_run(self):
        r = STATE["runs"]
        if r != "ok":
            name = {"busy": "post-runs-503-busy", "paused-day": "post-runs-503-paused-day",
                    "paused-month": "post-runs-503-paused-month", "atlas-unreachable": "post-runs-503-atlas-unreachable",
                    "question-empty": "post-runs-400-question-empty",
                    "question-too-long": "post-runs-400-question-too-long",
                    "body-too-large": "post-runs-413-body-too-large"}.get(r, r)
            return self.send_http_fixture(name)
        run_id = secrets.token_urlsafe(16)
        with LOCK:
            RUNS[run_id] = {"fixture": STATE["fixture"], "started": None, "dropped": False}
        self.send(201, json.dumps({"run_id": run_id}))

    def events(self, run_id):
        if STATE["events"] == "expired" or run_id not in RUNS:
            return self.send_http_fixture("get-events-404-run-unknown")
        run = RUNS[run_id]
        d = load_fixture(run["fixture"])
        events = d["events"]
        last = int(self.headers.get("Last-Event-ID") or 0)
        with LOCK:
            if run["started"] is None:
                run["started"] = time.monotonic()
            started = run["started"]
        speed = float(STATE["speed"]) or 1.0
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        keepalive = float(STATE["keepalive_s"])
        last_write = time.monotonic()
        try:
            for ev in events:
                if ev["n"] <= last:
                    continue
                due = started + ev["t_ms"] / 1000 / speed
                while True:
                    now = time.monotonic()
                    if now >= due:
                        break
                    if now - last_write >= keepalive:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
                        last_write = now
                    time.sleep(min(0.05, due - now))
                frame = f"id: {ev['n']}\nevent: {ev['kind']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
                self.wfile.write(frame.encode("utf-8"))
                self.wfile.flush()
                last_write = time.monotonic()
                drop = int(STATE["drop_after"] or 0)
                if drop and ev["n"] == drop and not run["dropped"]:
                    run["dropped"] = True
                    return               # the connection drops once, mid-run; the page reconnects
        except (BrokenPipeError, ConnectionResetError):
            return
        self.close_connection = True

    # ---------- dev switches ----------
    def dev(self, path):
        if path == "/__dev/set":
            q = parse_qs(urlsplit(self.path).query)
            with LOCK:
                for k, v in q.items():
                    if k in STATE:
                        STATE[k] = type(STATE[k])(v[0]) if not isinstance(STATE[k], str) else v[0]
                        if k == "health":
                            COLD["since"] = None
            return self.send(200, json.dumps(STATE))
        if path == "/__dev/state":
            return self.send(200, json.dumps(STATE))
        rows = "".join(f'<li><a href="/__dev/set?fixture={n}">{n}</a></li>' for n in fixture_names())
        page = ("<!doctype html><meta charset=utf-8><title>mock switches</title>"
                "<p>Development only. Set a switch, then load <a href=/>the page</a>.</p>"
                "<p>health: ready, paused-day, paused-month, unknown, cloud-run-429/500/503, gateway-502, cold:&lt;s&gt;, "
                "slow:&lt;s&gt;, hang. runs: ok, busy, paused-day, paused-month, atlas-unreachable, question-empty, "
                "question-too-long, body-too-large, cloud-run-503. events: ok, expired. speed, drop_after, keepalive_s.</p>"
                f"<p>Now: <code>{json.dumps(STATE)}</code></p><ol>{rows}</ol>")
        self.send(200, page, "text/html; charset=utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    if not (GENERATED / "config.json").is_file():
        raise SystemExit("web/_generated/ is missing: run uv run python scripts/build_web_data.py --out web/_generated")
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    srv.daemon_threads = True
    print(f"mock on http://127.0.0.1:{a.port}/ (switches at /__dev/)", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
