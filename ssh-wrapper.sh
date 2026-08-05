#!/usr/bin/env sh
#
# Installed as /usr/local/bin/ssh in the CLI image, ahead of /usr/bin/ssh on PATH.
#
# Why: OpenSSH resolves `~/.ssh/config` from the passwd database (pw_dir), NOT
# from $HOME. The entrypoint stages keys and known_hosts into a writable run
# dir so the container works under any --user, and ssh would simply ignore
# them — you'd get "Host key verification failed" with a perfectly good config
# sitting right there. Forcing -F makes the staged config authoritative.
#
# Options the caller passes still win: with -F, explicit command-line options
# take precedence over the config file, so a post_send hook doing
# `ssh -o StrictHostKeyChecking=no ...` behaves as written.
CFG="${SENDREPO_SSH_CONFIG:-}"
if [ -n "$CFG" ] && [ -f "$CFG" ]; then
    exec /usr/bin/ssh -F "$CFG" "$@"
fi
exec /usr/bin/ssh "$@"
