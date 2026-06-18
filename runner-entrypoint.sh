#!/usr/bin/env bash
#
# Registers this container as a GitHub self-hosted Actions runner, runs it,
# and de-registers cleanly on shutdown.
#
# Required:
#   REPO_URL       Repo or org URL, e.g. https://github.com/org/repo
#                  (org-level URL like https://github.com/org also works)
# Auth — provide ONE of:
#   RUNNER_TOKEN   A short-lived registration token
#                  (Settings > Actions > Runners > New self-hosted runner)
#   ACCESS_TOKEN   A PAT with repo (or org) admin scope; a registration token
#                  is fetched from the GitHub API automatically.
# Optional:
#   RUNNER_NAME    Defaults to the container hostname
#   RUNNER_LABELS  Defaults to: self-hosted,sendrepo
#   RUNNER_GROUP   Runner group name (org/enterprise runners)
#   RUNNER_WORKDIR Work directory, defaults to _work
set -euo pipefail

: "${REPO_URL:?Set REPO_URL to the repo or org URL}"
RUNNER_NAME="${RUNNER_NAME:-$(hostname)}"
RUNNER_LABELS="${RUNNER_LABELS:-self-hosted,sendrepo}"
RUNNER_WORKDIR="${RUNNER_WORKDIR:-_work}"

cd "$HOME"

# Stage SSH material with correct perms. ssh/rsync reject keys that are
# group/world-readable, and bind-mounted files inherit host permissions, so we
# copy from a read-only mount (/ssh-keys) into ~/.ssh and tighten the modes.
if [ -d /ssh-keys ]; then
    mkdir -p "$HOME/.ssh"
    cp -r /ssh-keys/. "$HOME/.ssh/"
    chmod 700 "$HOME/.ssh"
    chmod 600 "$HOME"/.ssh/* 2>/dev/null || true
fi

# Resolve a registration token from RUNNER_TOKEN or by exchanging a PAT.
get_reg_token() {
    if [ -n "${RUNNER_TOKEN:-}" ]; then
        printf '%s' "$RUNNER_TOKEN"
        return
    fi
    if [ -z "${ACCESS_TOKEN:-}" ]; then
        echo "Need RUNNER_TOKEN or ACCESS_TOKEN" >&2
        exit 1
    fi
    # repo-level URL (owner/repo) vs org-level URL (owner) -> different API paths.
    local path="${REPO_URL#https://github.com/}"
    path="${path%/}"
    local api
    case "$path" in
        */*) api="https://api.github.com/repos/${path}/actions/runners/registration-token" ;;
        *)   api="https://api.github.com/orgs/${path}/actions/runners/registration-token" ;;
    esac
    curl -fsSL -X POST \
        -H "Authorization: Bearer ${ACCESS_TOKEN}" \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "$api" \
        | python3 -c 'import sys, json; print(json.load(sys.stdin)["token"])'
}

REG_TOKEN="$(get_reg_token)"

# De-register on container stop so GitHub doesn't accumulate offline runners.
cleanup() {
    echo "Removing runner registration..."
    ./config.sh remove --token "$REG_TOKEN" || true
}
trap cleanup EXIT INT TERM

./config.sh \
    --unattended \
    --replace \
    --url "$REPO_URL" \
    --token "$REG_TOKEN" \
    --name "$RUNNER_NAME" \
    --labels "$RUNNER_LABELS" \
    --work "$RUNNER_WORKDIR" \
    ${RUNNER_GROUP:+--runnergroup "$RUNNER_GROUP"}

# Exec via run.sh in the background + wait so SIGTERM reaches it and the trap fires.
./run.sh &
wait $!
