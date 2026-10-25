# The API image (contract 4.I, T3.5, T3.6). Build from the repository root:
#   docker build --file deploy/api.Dockerfile --build-arg PC_COMMIT=<short sha> .
# Versions are exact tags (P0.1 pins Python 3.13), read on Oct 24, 2026 from:
#   python:  https://hub.docker.com/_/python/tags?name=3.13       (3.13.17-slim-trixie)
#   uv:      https://github.com/astral-sh/uv/pkgs/container/uv    (0.13.5)
# The uv steps follow https://docs.astral.sh/uv/guides/integration/docker/ (read Oct 24, 2026).

FROM python:3.13.17-slim-trixie AS build

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies first, so this layer is reused until the lock changes
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project


FROM python:3.13.17-slim-trixie

# Set by deploy.sh and local.sh; the build fails without it
ARG PC_COMMIT
RUN test -n "$PC_COMMIT"

WORKDIR /app
COPY --from=build /app/.venv /app/.venv

# What the API reads at start (T3.6): the frozen corpus and the committed vectors
COPY api/ ./api/
COPY contracts/ ./contracts/
COPY data/corpus/ ./data/corpus/
COPY data/vectors/ ./data/vectors/

# T3.6: the keyword index is FTS5 in the image's Python. Fail the build if SQLite lacks it.
RUN /app/.venv/bin/python -c "import sqlite3; c = sqlite3.connect(':memory:'); c.execute('CREATE VIRTUAL TABLE t USING fts5(x)'); c.execute(\"INSERT INTO t VALUES ('probable clause')\"); assert c.execute(\"SELECT count(*) FROM t WHERE t MATCH 'clause'\").fetchone()[0] == 1" \
 && /app/.venv/bin/python -m compileall -q api

# PC_ENV is not set here: it defaults to test, and only deploy.sh sets live (contract 4.H)
ENV PATH="/app/.venv/bin:$PATH" \
    PC_COMMIT=$PC_COMMIT \
    PORT=8080 \
    PYTHONUNBUFFERED=1

# Non-root. The app writes nothing under /app.
RUN groupadd --system --gid 10001 pc && useradd --system --uid 10001 --gid pc --no-create-home --shell /usr/sbin/nologin pc
USER 10001:10001

EXPOSE 8080

# One process, one worker: runs live in memory on the instance (T3.1). Cloud Run sets $PORT.
# --no-access-log: uvicorn's access line carries the client address and the run ID path (T3.7).
# --timeout-graceful-shutdown: SHUTDOWN_GRACE_S, so reservations are released before Cloud Run's SIGKILL (contract v1.2).
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port \"${PORT:-8080}\" --no-access-log --no-server-header --timeout-graceful-shutdown 5"]
