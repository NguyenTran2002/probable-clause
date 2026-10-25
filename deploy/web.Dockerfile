# The web image (contract 4.I, T3.5, T4.2, T5.5). Build from the repository root:
#   docker build --file deploy/web.Dockerfile .
# Exact tags, read on Oct 24, 2026 from:
#   python:  https://hub.docker.com/_/python/tags?name=3.13       (3.13.17-slim-trixie; build stage only)
#   uv:      https://github.com/astral-sh/uv/pkgs/container/uv    (0.13.5; build stage only)
#   nginx:   https://hub.docker.com/_/nginx/tags?name=alpine      (1.30.6, the stable line; its alpine3.24-slim image)

# Stage 1: the reader files, corpus.json and config.json, from the committed corpus (contract 11.1, 11.3)
FROM python:3.13.17-slim-trixie AS data

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY api/ ./api/
COPY data/corpus/ ./data/corpus/
COPY scripts/build_web_data.py ./scripts/build_web_data.py
RUN /app/.venv/bin/python scripts/build_web_data.py --out /out


# Stage 2: nginx, serving the page as it is committed plus stage 1's output
FROM nginx:1.30.6-alpine3.24-slim

# The image ships nginx's own welcome page; empty the site root so only our files can be served
RUN find /usr/share/nginx/html -mindepth 1 -delete

# Both profiles (T3.5). The default CMD runs the production one; deploy/local.sh runs the local one.
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/nginx.local.conf /etc/nginx/nginx.local.conf

# web/ as committed (index, modules, vendored markdown-it, fonts/ with the OFL text: T4.2, T5.5).
# web/looktests, web/_generated and webdev/ are left out by deploy/web.Dockerfile.dockerignore,
# and removed again below in case the ignore file is bypassed.
COPY web/ /usr/share/nginx/html/

# Guard 1, on web/ alone: the page and its self-hosted fonts with the OFL text (T4.2, T5.5)
RUN test -f /usr/share/nginx/html/index.html \
 && find /usr/share/nginx/html/fonts -name '*.woff2' | grep -q . \
 && find /usr/share/nginx/html/fonts \( -iname '*OFL*' -o -iname '*licen*' \) | grep -q .

COPY --from=data /out/ /usr/share/nginx/html/

# replays/ is written in Phase 5 and may not exist yet: a bind mount of the build context
# copies it only when it is there, so the image builds either way.
RUN --mount=type=bind,source=.,target=/ctx \
    rm -rf /usr/share/nginx/html/looktests /usr/share/nginx/html/_generated /usr/share/nginx/html/webdev \
 && mkdir -p /usr/share/nginx/html/replays \
 && if [ -d /ctx/replays ]; then cp -R /ctx/replays/. /usr/share/nginx/html/replays/; fi \
 && chmod -R a+rX /usr/share/nginx/html

# Guard 2, on build_web_data.py's output: the build fails without these
RUN test -f /usr/share/nginx/html/config.json \
 && test -f /usr/share/nginx/html/corpus.json \
 && test -d /usr/share/nginx/html/opinions \
 && nginx -t -c /etc/nginx/nginx.conf \
 && nginx -t -c /etc/nginx/nginx.local.conf

EXPOSE 8080
