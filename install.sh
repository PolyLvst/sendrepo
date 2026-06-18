#!/usr/bin/env sh
#
# SendRepo installer — designed to work inside a Docker container (or any Linux host).
#
# Installs:
#   - System packages: python3, pip, rsync, openssh-client  (via apt/apk/dnf/yum)
#   - Python dependency: PyYAML
#   - The sendrepo script into PREFIX/lib/sendrepo, with `sendrepo` and `sr`
#     symlinks on PATH (PREFIX/bin).
#
# Usage:
#   ./install.sh                 # install to /usr/local
#   PREFIX=/opt ./install.sh     # install under a custom prefix
#   SKIP_PKGS=1 ./install.sh     # don't touch the system package manager
#
# In a Dockerfile:
#   COPY . /tmp/sendrepo
#   RUN cd /tmp/sendrepo && ./install.sh && rm -rf /tmp/sendrepo
#
set -eu

PREFIX="${PREFIX:-/usr/local}"
LIBDIR="$PREFIX/lib/sendrepo"
BINDIR="$PREFIX/bin"
SKIP_PKGS="${SKIP_PKGS:-0}"

# Directory this installer lives in (where sendrepo.py sits).
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

log()  { printf '\033[34m[install]\033[0m %s\n' "$1"; }
warn() { printf '\033[33m[warn]\033[0m %s\n'    "$1"; }
err()  { printf '\033[31m[err]\033[0m %s\n'     "$1" >&2; }

# Run a command as root if we aren't already (containers usually run as root).
as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        err "Need root to run: $*"
        err "Re-run as root or install sudo."
        exit 1
    fi
}

install_system_packages() {
    if [ "$SKIP_PKGS" = "1" ]; then
        log "SKIP_PKGS=1 — skipping system package install."
        return
    fi

    if command -v apt-get >/dev/null 2>&1; then
        log "Detected apt (Debian/Ubuntu)."
        as_root apt-get update
        as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
            python3 python3-pip python3-yaml rsync openssh-client
    elif command -v apk >/dev/null 2>&1; then
        log "Detected apk (Alpine)."
        as_root apk add --no-cache python3 py3-pip py3-yaml rsync openssh-client
    elif command -v dnf >/dev/null 2>&1; then
        log "Detected dnf (Fedora/RHEL)."
        as_root dnf install -y python3 python3-pip python3-pyyaml rsync openssh-clients
    elif command -v yum >/dev/null 2>&1; then
        log "Detected yum (CentOS/RHEL)."
        as_root yum install -y python3 python3-pip python3-pyyaml rsync openssh-clients
    else
        warn "No supported package manager found (apt/apk/dnf/yum)."
        warn "Ensure python3, rsync and ssh are installed manually."
    fi
}

ensure_pyyaml() {
    if python3 -c 'import yaml' >/dev/null 2>&1; then
        log "PyYAML already available."
        return
    fi
    log "Installing PyYAML via pip."
    # --break-system-packages is needed on newer distros (PEP 668); ignore if unsupported.
    python3 -m pip install --no-cache-dir pyyaml --break-system-packages 2>/dev/null \
        || python3 -m pip install --no-cache-dir pyyaml \
        || { err "Could not install PyYAML."; exit 1; }
}

install_files() {
    if [ ! -f "$SRC_DIR/sendrepo.py" ]; then
        err "sendrepo.py not found next to this installer ($SRC_DIR)."
        exit 1
    fi

    log "Installing script to $LIBDIR"
    as_root mkdir -p "$LIBDIR" "$BINDIR"
    as_root cp "$SRC_DIR/sendrepo.py" "$LIBDIR/sendrepo.py"
    as_root chmod 755 "$LIBDIR/sendrepo.py"

    # sendrepo resolves symlinks (os.path.realpath) so config next to the real
    # script and the `../sendrepo-config/` lookup keep working through these links.
    log "Linking $BINDIR/sendrepo and $BINDIR/sr"
    as_root ln -sf "$LIBDIR/sendrepo.py" "$BINDIR/sendrepo"
    as_root ln -sf "$LIBDIR/sendrepo.py" "$BINDIR/sr"
}

main() {
    log "Installing SendRepo to prefix: $PREFIX"
    install_system_packages
    ensure_pyyaml
    install_files

    echo
    log "Done. 'sendrepo' and 'sr' are installed in $BINDIR"
    case ":$PATH:" in
        *":$BINDIR:"*) : ;;
        *) warn "$BINDIR is not on PATH — add it: export PATH=\"$BINDIR:\$PATH\"" ;;
    esac
    echo
    log "Next: provide a config.yaml in one of these locations:"
    printf '       - \$SENDREPO_CONFIG_PATH\n'
    printf '       - ~/.config/sendrepo/config.yaml\n'
    printf '       - %s/config.yaml  (next to the installed script)\n' "$LIBDIR"
    log "See config-example.yaml for the format."
}

main "$@"
