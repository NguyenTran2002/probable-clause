#!/usr/bin/env bash
# Deploys both Cloud Run services (contract 4.I, T3.5). WRITTEN, NEVER RUN except by the main session,
# on the user's explicit green light (brief section 12, P4.1). Run from anywhere; it works from the repo root.
#
# Nothing for goodnight is here: its block is the user's, on their own green light (T3.5).
#
# Needs beforehand (all reported, none created by this script):
#   - Docker with BuildKit, and `gcloud auth configure-docker <region>-docker.pkg.dev`
#   - the Artifact Registry repository, the two service accounts and the four secrets named below
#   - secretmanager.secretAccessor on each secret for the API's service account only
# Flags are from https://docs.cloud.google.com/sdk/gcloud/reference/run/deploy, and secrets from
# https://docs.cloud.google.com/run/docs/configuring/services/secrets, both read Oct 24, 2026.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# 1. The spend gate comes before anything else (T3.5): stop on open reservations (exit 1), an
#    unreadable store (exit 2), or any other failure. --env live: the report defaults to the test database.
#    It runs again right before the API is replaced (step 5), because a run started while the images were
#    building would be lost when the revision changes.
spend_gate() {
    local spend_rc=0
    uv run --frozen --env-file .env python scripts/spend_report.py --open-reservations --env live || spend_rc=$?
    if [ "$spend_rc" -ne 0 ]; then
        echo "deploy.sh: stopping ($1). Spend report exit $spend_rc (1: a reservation is open; 2: unreadable)." >&2
        exit "$spend_rc"
    fi
}
spend_gate "first check"

# 2. A clean tree only; the image is named by the commit it was built from
if [ -n "$(git status --porcelain)" ]; then
    echo "deploy.sh: stopping. The git tree is not clean; commit or stash first." >&2
    exit 1
fi
PC_COMMIT="$(git rev-parse --short HEAD)"

# Every Cloud Run figure comes from api/settings.py, never copied here
setting() {
    uv run --frozen python -c "import sys; from api import settings; print(getattr(settings, sys.argv[1]).value)" "$1"
}
GCP_PROJECT="$(setting GCP_PROJECT)"
GCP_REGION="$(setting GCP_REGION)"
API_MAX_INSTANCES="$(setting API_MAX_INSTANCES)"
API_MIN_INSTANCES="$(setting API_MIN_INSTANCES)"
API_CONCURRENCY="$(setting API_CONCURRENCY)"
API_CPU="$(setting API_CPU)"
API_MEMORY="$(setting API_MEMORY)"
API_REQUEST_TIMEOUT_S="$(setting API_REQUEST_TIMEOUT_S)"
WEB_MAX_INSTANCES="$(setting WEB_MAX_INSTANCES)"
WEB_MIN_INSTANCES="$(setting WEB_MIN_INSTANCES)"

# Names chosen here (not in settings): the services, one service account each, the registry, the secrets
API_SERVICE="probable-clause-api"
WEB_SERVICE="probable-clause-web"
API_SA="pc-api@${GCP_PROJECT}.iam.gserviceaccount.com"
WEB_SA="pc-web@${GCP_PROJECT}.iam.gserviceaccount.com"
REGISTRY_REPO="probable-clause"
REGISTRY="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/${REGISTRY_REPO}"
API_IMAGE="${REGISTRY}/api:${PC_COMMIT}"
WEB_IMAGE="${REGISTRY}/web:${PC_COMMIT}"
SECRET_ANTHROPIC="pc-anthropic-api-key"
SECRET_VOYAGE="pc-voyage-api-key"
SECRET_EXA="pc-exa-api-key"
SECRET_MONGODB="pc-mongodb-uri"
# The port both containers listen on; set explicitly so Cloud Run, nginx.conf and uvicorn agree
CONTAINER_PORT="8080"

# 3. Checks of what must already exist (reads only). A missing piece stops the deploy with its fix.
need() {
    echo "deploy.sh: stopping. Missing: $1" >&2
    echo "  create it first: $2" >&2
    exit 1
}
gcloud artifacts repositories describe "$REGISTRY_REPO" \
    --project="$GCP_PROJECT" \
    --location="$GCP_REGION" \
    > /dev/null || need "Artifact Registry repository $REGISTRY_REPO" "gcloud artifacts repositories create $REGISTRY_REPO --repository-format=docker --location=$GCP_REGION --project=$GCP_PROJECT"
for sa in "$API_SA" "$WEB_SA"; do
    gcloud iam service-accounts describe "$sa" \
        --project="$GCP_PROJECT" \
        > /dev/null || need "service account $sa" "gcloud iam service-accounts create ${sa%%@*} --project=$GCP_PROJECT"
done

# A secret is pinned to its newest enabled version, as Google recommends over `latest`
pinned_version() {
    local v
    v="$(gcloud secrets versions list "$1" \
        --project="$GCP_PROJECT" \
        --filter="state=ENABLED" \
        --sort-by="~createTime" \
        --limit=1 \
        --format="value(name)")" || need "secret $1" "gcloud secrets create $1 --project=$GCP_PROJECT, then add a version"
    if [ -z "$v" ]; then
        need "an enabled version of secret $1" "gcloud secrets versions add $1 --project=$GCP_PROJECT --data-file=-"
    fi
    echo "${v##*/}"
}
V_ANTHROPIC="$(pinned_version "$SECRET_ANTHROPIC")"
V_VOYAGE="$(pinned_version "$SECRET_VOYAGE")"
V_EXA="$(pinned_version "$SECRET_EXA")"
V_MONGODB="$(pinned_version "$SECRET_MONGODB")"

# 4. Build for Cloud Run's platform (linux/amd64, whatever machine this is) and push both images
export DOCKER_BUILDKIT=1
docker build \
    --platform="linux/amd64" \
    --file="deploy/api.Dockerfile" \
    --build-arg="PC_COMMIT=${PC_COMMIT}" \
    --tag="$API_IMAGE" \
    .
docker build \
    --platform="linux/amd64" \
    --file="deploy/web.Dockerfile" \
    --tag="$WEB_IMAGE" \
    .
docker push "$API_IMAGE"
docker push "$WEB_IMAGE"

# 5. The API, after a second spend check. --scaling=auto returns a service switched off by hand (brief 8.5) to automatic scaling.
#    --min/--max are the service-level limits that go with --scaling; --cpu-throttling is request-based
#    billing (T3.5); --cpu-boost is the startup boost. PC_COMMIT is baked into the image.
spend_gate "before replacing the API"
gcloud run deploy "$API_SERVICE" \
    --project="$GCP_PROJECT" \
    --region="$GCP_REGION" \
    --image="$API_IMAGE" \
    --port="$CONTAINER_PORT" \
    --service-account="$API_SA" \
    --scaling="auto" \
    --min="$API_MIN_INSTANCES" \
    --max="$API_MAX_INSTANCES" \
    --concurrency="$API_CONCURRENCY" \
    --cpu="$API_CPU" \
    --memory="$API_MEMORY" \
    --timeout="$API_REQUEST_TIMEOUT_S" \
    --cpu-boost \
    --cpu-throttling \
    --ingress="all" \
    --allow-unauthenticated \
    --set-env-vars="PC_ENV=live" \
    --set-secrets="ANTHROPIC_API_KEY=${SECRET_ANTHROPIC}:${V_ANTHROPIC},VOYAGE_API_KEY=${SECRET_VOYAGE}:${V_VOYAGE},EXA_API_KEY=${SECRET_EXA}:${V_EXA},MONGODB_URI=${SECRET_MONGODB}:${V_MONGODB}" \
    --quiet

# 6. The web service: static, no secrets
gcloud run deploy "$WEB_SERVICE" \
    --project="$GCP_PROJECT" \
    --region="$GCP_REGION" \
    --image="$WEB_IMAGE" \
    --port="$CONTAINER_PORT" \
    --service-account="$WEB_SA" \
    --scaling="auto" \
    --min="$WEB_MIN_INSTANCES" \
    --max="$WEB_MAX_INSTANCES" \
    --cpu-throttling \
    --ingress="all" \
    --allow-unauthenticated \
    --quiet

# 7. Read back what is running (brief 8.5: confirm automatic scaling and the intended limits)
for svc in "$API_SERVICE" "$WEB_SERVICE"; do
    gcloud run services describe "$svc" \
        --project="$GCP_PROJECT" \
        --region="$GCP_REGION" \
        --format="yaml(status.url,metadata.annotations,spec.template.metadata.annotations)"
done
echo "deployed commit ${PC_COMMIT}. goodnight is untouched."
