#!/usr/bin/env sh
#
# Entrypoint for the SendRepo CLI container (Dockerfile.cli).
#
# It makes a container behave like a local `sr` install:
#   1. Gives the process a writable HOME (and a passwd entry, which ssh insists
#      on) so the image works as root or under --user.
#   2. Copies the mounted config to a writable run dir and repoints the project
#      you named at /workspace, so the host paths in config.yaml
#      ({root}/projects/foo) don't have to exist inside the container.
#   3. Stages SSH material from /ssh-keys (or $SSH_PRIVATE_KEY) with the strict
#      permissions ssh demands — bind mounts inherit host modes, which are often
#      too loose, and a read-only mount can't be chmod'ed in place.
#   4. execs `sendrepo "$@"`.
#
# Mounts:
#   /workspace   the project to send   (required unless SENDREPO_NO_WORKSPACE=1)
#   /config      dir holding config.yaml (+ optional .sr-ignore-global.txt)
#   /ssh-keys    dir holding the deploy key (+ optional known_hosts)
#
# Env:
#   SENDREPO_PROJECT          force which project gets repointed at /workspace
#   SENDREPO_NO_WORKSPACE=1   use the paths in config.yaml as-is (no repoint)
#   SENDREPO_SSH_ACCEPT_NEW=1 trust unknown hosts on first connect
#   SSH_PRIVATE_KEY           key contents, for CI where mounting a file is awkward
#   SSH_AUTH_SOCK             honoured as-is if you forward an agent socket
set -eu

RUNDIR=/tmp/sendrepo-run
CONFIG_MOUNT="${SENDREPO_CONFIG_MOUNT:-/config}"
SSH_MOUNT="${SENDREPO_SSH_MOUNT:-/ssh-keys}"
WORKSPACE="${SENDREPO_WORKSPACE_MOUNT:-/workspace}"

warn() { printf '\033[33m[warn]\033[0m %s\n' "$1" >&2; }
err()  { printf '\033[31m[err]\033[0m %s\n'  "$1" >&2; }

# ── 1. Identity: writable HOME + a passwd entry ─────────────────────────────
# Always run out of the run dir: with `docker run --user 1000:1000` the image's
# HOME (/root) is not writable, and ssh and git both need somewhere to write.
HOME="$RUNDIR/home"
export HOME
mkdir -p "$HOME"

# OpenSSH aborts with "No user exists for uid N" if getpwuid() finds nothing,
# which is exactly what happens with an arbitrary --user. /etc/passwd is group-
# writable (group 0) in this image, so uid:0 can add itself.
if ! getent passwd "$(id -u)" >/dev/null 2>&1; then
    if [ ! -w /etc/passwd ]; then
        err "uid $(id -u) has no passwd entry and /etc/passwd is not writable."
        err "ssh refuses to run like this. Use the root default, or pass the"
        err "group as 0:  --user \$(id -u):0"
        exit 1
    fi
    printf 'sendrepo:x:%s:%s:SendRepo:%s:/bin/sh\n' \
        "$(id -u)" "$(id -g)" "$HOME" >> /etc/passwd
fi

# The workspace is usually owned by a different uid than the container user;
# without this, any `git` in a pre_send hook dies on "dubious ownership".
git config --global --add safe.directory '*' >/dev/null 2>&1 || true

# ── 2. Config ───────────────────────────────────────────────────────────────
# Copy the whole config dir: sendrepo looks for .sr-ignore-global.txt next to
# the config file, and we need the copy writable to repoint the project path.
SRC_CONFIG="${SENDREPO_CONFIG_PATH:-$CONFIG_MOUNT/config.yaml}"
if [ ! -f "$SRC_CONFIG" ]; then
    err "No config.yaml found at $SRC_CONFIG"
    err "Mount your sendrepo config dir at $CONFIG_MOUNT, e.g."
    err '  -v "$HOME/.config/sendrepo:/config:ro"'
    exit 1
fi

mkdir -p "$RUNDIR/config"
cp -L "$SRC_CONFIG" "$RUNDIR/config/config.yaml"
SRC_DIR="$(dirname "$SRC_CONFIG")"
if [ -f "$SRC_DIR/.sr-ignore-global.txt" ]; then
    cp -L "$SRC_DIR/.sr-ignore-global.txt" "$RUNDIR/config/.sr-ignore-global.txt"
fi

SENDREPO_CONFIG_PATH="$RUNDIR/config/config.yaml"
export SENDREPO_CONFIG_PATH

# ── 3. Point the named project at /workspace ────────────────────────────────
# config.yaml holds host paths ({root}/projects/foo) that don't exist in here,
# so rewrite the path of whichever project was named on the command line.
if [ "${SENDREPO_NO_WORKSPACE:-0}" != "1" ]; then
    # Empty counts as "not mounted": the image's own WORKDIR creates the dir, and
    # a full sync runs rsync --delete — an empty source would wipe the remote.
    if { [ ! -d "$WORKSPACE" ] || [ -z "$(ls -A "$WORKSPACE" 2>/dev/null)" ]; } \
            && [ "${SENDREPO_ALLOW_EMPTY_WORKSPACE:-0}" != "1" ]; then
        err "Nothing mounted at $WORKSPACE — mount the project you want to send:"
        err '  -v "$PWD:/workspace"'
        err "Refusing to continue: syncing an empty source would delete the remote."
        err "(SENDREPO_NO_WORKSPACE=1 uses the paths in config.yaml as-is;"
        err " SENDREPO_ALLOW_EMPTY_WORKSPACE=1 sends the empty dir anyway.)"
        exit 1
    fi
    python3 - "$RUNDIR/config/config.yaml" "$WORKSPACE" "$@" <<'PY'
import os, sys, yaml

cfg_path, workspace = sys.argv[1], sys.argv[2].rstrip('/') + '/'
argv = sys.argv[3:]

with open(cfg_path) as f:
    cfg = yaml.safe_load(f) or {}
projects = cfg.get('projects') or {}

# Match against known project names rather than "first bare argument": flags
# like `-o a/b c/d` take values, so positional guessing misfires.
target = os.getenv('SENDREPO_PROJECT') or next((a for a in argv if a in projects), None)

if not target:
    # No project named (e.g. plain `sr` for help, or --check-update). Nothing to do.
    sys.exit(0)
if target not in projects:
    print(f"\033[31m[err]\033[0m Project '{target}' is not in config.yaml "
          f"(have: {', '.join(projects) or 'none'})", file=sys.stderr)
    sys.exit(1)

projects[target]['path'] = workspace
with open(cfg_path, 'w') as f:
    yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)

print(f"\033[34m[info]\033[0m Sending the mount at {workspace} as project '{target}'")
PY
fi

# ── 4. SSH material ─────────────────────────────────────────────────────────
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

if [ -d "$SSH_MOUNT" ]; then
    # -L dereferences symlinked keys; sockets and odd files in a mounted ~/.ssh
    # are not fatal, so don't let one abort the copy.
    cp -rL "$SSH_MOUNT/." "$HOME/.ssh/" 2>/dev/null || true
fi

if [ -n "${SSH_PRIVATE_KEY:-}" ]; then
    printf '%s\n' "$SSH_PRIVATE_KEY" > "$HOME/.ssh/id_sendrepo"
fi

# Private keys must be 0600; public material stays readable.
find "$HOME/.ssh" -type f -exec chmod 600 {} + 2>/dev/null || true
for f in "$HOME"/.ssh/*.pub "$HOME"/.ssh/known_hosts "$HOME"/.ssh/known_hosts.*; do
    if [ -f "$f" ]; then chmod 644 "$f"; fi
done

# Build the ssh config that the wrapper (/usr/local/bin/ssh) forces with -F.
# Everything is listed explicitly because ssh resolves ~ from the passwd
# database rather than $HOME, so it will not find these files on its own.
SSH_CONFIG="$HOME/.ssh/config"
KNOWN_HOSTS="$HOME/.ssh/known_hosts"
touch "$KNOWN_HOSTS"
chmod 644 "$KNOWN_HOSTS"

KEY_COUNT=0
{
    printf 'Host *\n'
    printf '    UserKnownHostsFile %s\n' "$KNOWN_HOSTS"
    if [ "${SENDREPO_SSH_ACCEPT_NEW:-0}" = "1" ]; then
        # Convenience for a first run; the host key is still pinned afterwards.
        printf '    StrictHostKeyChecking accept-new\n'
    fi
} > "$SSH_CONFIG"

for key in "$HOME"/.ssh/*; do
    case "$key" in
        *.pub|*/known_hosts|*/known_hosts.*|*/config|*/authorized_keys) continue ;;
    esac
    if [ -f "$key" ] && head -n 1 "$key" 2>/dev/null | grep -q 'PRIVATE KEY'; then
        printf '    IdentityFile %s\n' "$key" >> "$SSH_CONFIG"
        KEY_COUNT=$((KEY_COUNT + 1))
    fi
done
chmod 600 "$SSH_CONFIG"

SENDREPO_SSH_CONFIG="$SSH_CONFIG"
export SENDREPO_SSH_CONFIG

if [ "$KEY_COUNT" -eq 0 ] && [ -z "${SSH_AUTH_SOCK:-}" ]; then
    warn "No SSH key staged and no agent forwarded — authentication will fail."
    warn "Mount your key dir at $SSH_MOUNT (read-only is fine)."
fi
if [ ! -s "$KNOWN_HOSTS" ] && [ "${SENDREPO_SSH_ACCEPT_NEW:-0}" != "1" ]; then
    warn "No known_hosts staged — ssh will refuse the unknown host."
    warn "Mount one into $SSH_MOUNT, or pass -e SENDREPO_SSH_ACCEPT_NEW=1."
fi

exec sendrepo "$@"
