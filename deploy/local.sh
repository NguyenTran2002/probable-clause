#!/usr/bin/env bash
# Runs both images locally for the user's review (P4.1, contract 4.I). WRITTEN, NEVER RUN by an agent.
#   API  : http://localhost:8000   (PC_ENV=test: Probable_Clause_test, never the live database)
#   Page : http://localhost:8080   (the local nginx profile proxies /api/ to the API, prefix stripped)
# Keys reach the API from .env through `uv run --env-file` (which parses it, quotes stripped) and
# `docker run -e NAME` with no value, so only those four variables are passed; this script never reads .env. Ctrl-C stops and cleans up.
# This run spends real money on live keys when a question is asked; the user decides what to ask.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

NETWORK="pc-local-net"
API_NAME="pc-api-local"        # nginx.local.conf proxies to this name on this network
WEB_NAME="pc-web-local"
API_IMAGE="probable-clause-api:local"
WEB_IMAGE="probable-clause-web:local"

PC_COMMIT="local-$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

cleanup() {
    docker rm --force "$WEB_NAME" > /dev/null 2>&1 || true
    docker rm --force "$API_NAME" > /dev/null 2>&1 || true
    docker network rm "$NETWORK" > /dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM

export DOCKER_BUILDKIT=1
docker build \
    --file="deploy/api.Dockerfile" \
    --build-arg="PC_COMMIT=${PC_COMMIT}" \
    --tag="$API_IMAGE" \
    .
docker build \
    --file="deploy/web.Dockerfile" \
    --tag="$WEB_IMAGE" \
    .

cleanup
docker network create "$NETWORK" > /dev/null

# Published on 127.0.0.1 only. PC_ENV=test is explicit, whatever .env says. No other variable of .env reaches the container.
uv run --frozen --env-file .env -- docker run \
    --detach \
    --name "$API_NAME" \
    --network "$NETWORK" \
    --publish "127.0.0.1:8000:8080" \
    -e ANTHROPIC_API_KEY \
    -e VOYAGE_API_KEY \
    -e EXA_API_KEY \
    -e MONGODB_URI \
    -e PC_ENV=test \
    -e PORT=8080 \
    "$API_IMAGE" > /dev/null

docker run \
    --detach \
    --name "$WEB_NAME" \
    --network "$NETWORK" \
    --publish "127.0.0.1:8080:8080" \
    "$WEB_IMAGE" \
    nginx -c /etc/nginx/nginx.local.conf -g "daemon off;" > /dev/null

echo "API  http://localhost:8000/health   (loads corpus and vectors first; its log follows)"
echo "Page http://localhost:8080/"
echo "Ctrl-C stops both and removes them."
docker logs --follow "$API_NAME"
