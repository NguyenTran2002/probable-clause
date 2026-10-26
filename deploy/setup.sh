#!/usr/bin/env bash
# Creates what deploy.sh needs and never creates itself (P4.30, T3.5): the cloud services it calls, the Artifact
# Registry repository, one service account per Cloud Run service, the four secrets from .env, and the API's
# service account's read access to them. Run only by the main session, on the user's explicit green light
# (P5.1). Run from anywhere; it works from the repo root.
#
# Safe to run again: each piece is created only when missing, and a secret gets a version only when it has no
# enabled one. A step that fails stops the script; running it again picks up from there (a service account just
# created can take a moment to be visible to IAM, and the rerun is the remedy, not a retry here).
#
# The secret values never pass through this script's output or its variables: each is written by a Python process
# that uv starts with .env loaded, straight into gcloud's standard input. This script never reads .env itself.
# The Anthropic secret takes the live workspace's key, ANTHROPIC_API_KEY_LIVE (P4.24, P4.29), never the
# development key.
#
# Flags are from https://docs.cloud.google.com/sdk/gcloud/reference/services/enable,
# .../artifacts/repositories/create, .../iam/service-accounts/create, .../secrets/create,
# .../secrets/versions/add and .../secrets/add-iam-policy-binding, read Oct 26, 2026.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

setting() {
    uv run --frozen python -c "import sys; from api import settings; print(getattr(settings, sys.argv[1]).value)" "$1"
}
GCP_PROJECT="$(setting GCP_PROJECT)"
GCP_REGION="$(setting GCP_REGION)"

# The same names as deploy.sh (tests/deploy/test_setup.py checks that they match)
API_SA="pc-api@${GCP_PROJECT}.iam.gserviceaccount.com"
WEB_SA="pc-web@${GCP_PROJECT}.iam.gserviceaccount.com"
REGISTRY_REPO="probable-clause"
SECRET_ANTHROPIC="pc-anthropic-api-key"
SECRET_VOYAGE="pc-voyage-api-key"
SECRET_EXA="pc-exa-api-key"
SECRET_MONGODB="pc-mongodb-uri"

# 1. The cloud services deploy.sh and this script call
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    iam.googleapis.com \
    --project="$GCP_PROJECT"

# 2. The image registry
if ! gcloud artifacts repositories describe "$REGISTRY_REPO" \
    --project="$GCP_PROJECT" \
    --location="$GCP_REGION" \
    > /dev/null 2>&1; then
    gcloud artifacts repositories create "$REGISTRY_REPO" \
        --project="$GCP_PROJECT" \
        --location="$GCP_REGION" \
        --repository-format="docker" \
        --description="Probable Clause images (deploy/deploy.sh)"
fi

# 3. One service account per service; the web service's holds no role at all
service_account() {
    if ! gcloud iam service-accounts describe "$1" \
        --project="$GCP_PROJECT" \
        > /dev/null 2>&1; then
        gcloud iam service-accounts create "${1%%@*}" \
            --project="$GCP_PROJECT" \
            --display-name="$2"
    fi
}
service_account "$API_SA" "Probable Clause API"
service_account "$WEB_SA" "Probable Clause web"

# 4. The secrets. has_value exits 0 only when the variable is set and not blank, and prints nothing;
#    write_value writes the value with no newline. Neither ever prints the value anywhere else.
has_value() {
    uv run --frozen --env-file .env python -c "import os, sys; sys.exit(0 if os.environ.get(sys.argv[1], '').strip() else 1)" "$1"
}
write_value() {
    uv run --frozen --env-file .env python -c "import os, sys; sys.stdout.write(os.environ[sys.argv[1]].strip())" "$1"
}
secret() {
    local name="$1" var="$2" enabled
    if ! has_value "$var"; then
        echo "setup.sh: stopping. $var is not set in .env (check with: uv run python scripts/check_env.py --phase 5)" >&2
        exit 1
    fi
    if ! gcloud secrets describe "$name" \
        --project="$GCP_PROJECT" \
        > /dev/null 2>&1; then
        gcloud secrets create "$name" \
            --project="$GCP_PROJECT" \
            --replication-policy="automatic"
    fi
    enabled="$(gcloud secrets versions list "$name" \
        --project="$GCP_PROJECT" \
        --filter="state=ENABLED" \
        --limit=1 \
        --format="value(name)")"
    if [ -z "$enabled" ]; then
        write_value "$var" | gcloud secrets versions add "$name" \
            --project="$GCP_PROJECT" \
            --data-file=-
    else
        echo "setup.sh: $name already has an enabled version; left as it is"
    fi
    gcloud secrets add-iam-policy-binding "$name" \
        --project="$GCP_PROJECT" \
        --member="serviceAccount:${API_SA}" \
        --role="roles/secretmanager.secretAccessor" \
        --condition=None \
        > /dev/null
}
secret "$SECRET_ANTHROPIC" ANTHROPIC_API_KEY_LIVE
secret "$SECRET_VOYAGE" VOYAGE_API_KEY
secret "$SECRET_EXA" EXA_API_KEY
secret "$SECRET_MONGODB" MONGODB_URI

# 5. Docker's credentials for the registry (adds one entry to ~/.docker/config.json)
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

echo "setup done in ${GCP_PROJECT}: registry ${REGISTRY_REPO}, service accounts pc-api and pc-web, four secrets readable by pc-api only"
