#!/usr/bin/env bash
#
# Test whether a GitHub PAT can register self-hosted runners on given repos.
# It calls the SAME endpoint the runner entrypoint uses
# (POST /repos/{owner}/{repo}/actions/runners/registration-token), so a PASS
# here means the runner WILL register. The created token is short-lived and
# registers nothing on its own — calling this is harmless.
#
# Usage:
#   ACCESS_TOKEN=ghp_xxx ./test-pat.sh                 # token from env, default repos
#   ./test-pat.sh                                       # prompts for token (hidden)
#   ./test-pat.sh owner/repo [owner/repo ...]           # explicit repos
#
# The token is read from $ACCESS_TOKEN or an interactive hidden prompt — never
# passed as an argument, so it can't leak into shell history.
set -u

API="https://api.github.com"
BODY="$(mktemp)"
trap 'rm -f "$BODY"' EXIT

green() { printf '\033[32m%s\033[0m' "$1"; }
red()   { printf '\033[31m%s\033[0m' "$1"; }
yellow(){ printf '\033[33m%s\033[0m' "$1"; }

# ── token ─────────────────────────────────────────────────────────────────
TOKEN="${ACCESS_TOKEN:-}"
if [ -z "$TOKEN" ]; then
    printf 'GitHub PAT (input hidden): ' >&2
    stty -echo 2>/dev/null; read -r TOKEN; stty echo 2>/dev/null; echo >&2
fi
[ -z "$TOKEN" ] && { echo "No token provided." >&2; exit 1; }

# ── repos ─────────────────────────────────────────────────────────────────
if [ "$#" -gt 0 ]; then
    REPOS=("$@")
else
    REPOS=(
        zefriyazid-hash/borma-copro
        zefriyazid-hash/nusitek-web
        zefriyazid-hash/hcis-fe
        PolyLvst/hcis-borma-be
    )
fi

# ── helpers ───────────────────────────────────────────────────────────────
# api METHOD PATH -> prints HTTP code, writes response body to $BODY
api() {
    curl -s -o "$BODY" -w '%{http_code}' -X "$1" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "$API$2"
}
# json_get DOTTED.KEY -> prints value from $BODY (empty if missing/not JSON)
json_get() {
    python3 -c '
import sys, json
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print(""); sys.exit()
v = d
for k in sys.argv[2].split("."):
    if isinstance(v, dict) and k in v:
        v = v[k]
    else:
        print(""); sys.exit()
print(v)' "$BODY" "$1"
}

# ── identity ──────────────────────────────────────────────────────────────
code=$(api GET /user)
if [ "$code" = "200" ]; then
    echo "Token belongs to: $(green "$(json_get login)")"
else
    echo "Token identity: $(yellow "/user returned HTTP $code") (fine-grained tokens may restrict this — not fatal)"
fi
echo "Testing $(printf '%s' "${#REPOS[@]}") repo(s)..."
echo

# ── per-repo checks ───────────────────────────────────────────────────────
fail=0
for repo in "${REPOS[@]}"; do
    printf '── %s\n' "$repo"

    # 1) Can the token see the repo, and with what permission?
    code=$(api GET "/repos/$repo")
    case "$code" in
        200)
            admin=$(json_get permissions.admin)
            if [ "$admin" = "True" ]; then
                printf '   visibility: %s   admin: %s\n' "$(green ok)" "$(green True)"
            else
                printf '   visibility: %s   admin: %s  (push=%s)\n' \
                    "$(green ok)" "$(red "${admin:-False}")" "$(json_get permissions.push)"
            fi
            ;;
        404) printf '   visibility: %s — wrong name or token has no access\n' "$(red 'not found')" ;;
        401) printf '   %s — token invalid or expired\n' "$(red 'HTTP 401')" ;;
        *)   printf '   visibility: %s (HTTP %s) %s\n' "$(red fail)" "$code" "$(json_get message)" ;;
    esac

    # 2) The decisive test: actually request a registration token.
    code=$(api POST "/repos/$repo/actions/runners/registration-token")
    case "$code" in
        201) printf '   register:   %s — runner will register here\n' "$(green PASS)" ;;
        403) printf '   register:   %s (HTTP 403) — token lacks admin on this repo\n' "$(red FAIL)"; fail=1 ;;
        404) printf '   register:   %s (HTTP 404) — no admin access (GitHub hides 403 as 404)\n' "$(red FAIL)"; fail=1 ;;
        *)   printf '   register:   %s (HTTP %s) %s\n' "$(red FAIL)" "$code" "$(json_get message)"; fail=1 ;;
    esac
    echo
done

if [ "$fail" = "0" ]; then
    echo "$(green 'All repos OK') — this token can register every runner listed."
else
    echo "$(red 'Some repos failed') — see FAIL lines above. Registering a runner needs"
    echo "Administration: write (admin) on the repo; the token's account must have it."
    exit 1
fi
