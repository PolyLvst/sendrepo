# SendRepo reference

Deep detail for the `sendrepo` skill. Paths are relative to the tool repo
(where `sr` resolves to) unless absolute.

## Repo map

| File | Purpose |
|---|---|
| `sendrepo.py` | The whole tool: `SendRepo` class + `check_for_updates()` + `main()` |
| `sr`, `sendrepo` | Symlinks to `sendrepo.py` |
| `sr.bat`, `sendrepo.bat` | Windows shims: `python "%~dp0sendrepo.py" %*` |
| `setup_path.py` | Adds the repo dir to PATH (`~/.bashrc`/`~/.zshrc`, or the Windows registry) |
| `install.sh` | POSIX installer for containers/hosts: apt/apk/dnf/yum deps, PyYAML, copies the script to `$PREFIX/lib/sendrepo/`, symlinks `sendrepo`/`sr` into `$PREFIX/bin` (`PREFIX=/usr/local`, `SKIP_PKGS=1` skips packages) |
| `.sr-ignore-global.txt` | Default global excludes (VCS, env files, secrets, Python, Node, build dirs, logs/tmp, IDE, `.sendrepo/`, `.rsync-cache/`) |
| `config-example.yaml` | Documented sample config, incl. `include` and `ssh_jump_host` |
| `Dockerfile.cli`, `cli-entrypoint.sh`, `ssh-wrapper.sh`, `sr-docker`, `sr-docker.ps1`, `docker-compose.cli.yaml` | One-shot CLI container (deploy client) |
| `Dockerfile.runner`, `runner-entrypoint.sh`, `docker-compose.yaml`, `.env.example.runner`, `examples/deploy-on-tag.yml` | Self-hosted GitHub Actions runner with `sr` preinstalled |
| `test-pat.sh` | Checks a PAT can mint runner registration tokens for given repos. Token from `$ACCESS_TOKEN` or hidden prompt |
| `README.md` | User docs; keep in sync with behaviour |

## Config lookup (`_find_config_file`)

First existing of:
1. explicit path (unused by `main()`)
2. `$SENDREPO_CONFIG_PATH`
3. `~/.config/sendrepo/config.yaml` (Windows: `%APPDATA%\sendrepo\config.yaml`)
4. `<realpath(script) dir>/../sendrepo-config/config.yaml`
5. `<script dir>/config.yaml`

The script dir is resolved through symlinks, so `sr` on PATH still finds the adjacent
config.

Global ignore (`_find_global_exclude_file`) is searched **independently**, in the
directories of: `$SENDREPO_CONFIG_PATH`, `~/.config/sendrepo/`, `../sendrepo-config/`,
script dir. First file named `.sr-ignore-global.txt` wins. It is not necessarily next
to the config actually loaded.

`_load_config`: `yaml.safe_load`, then `path = path.format(root=expanduser(root))` for
each project. A `path` containing other `{...}` braces will raise `KeyError`.

## Argument parsing (`main`)

A first `parse_known_args` pass pulls out `--sync-config`, `--open`,
`--check-update`, `--pre-send P`, `--post-send P`:
- `--check-update` runs before the config is even loaded, then returns.
- Otherwise the config is loaded (prints `[info] Config:`), then `--open`,
  `--pre-send`, `--post-send` each run and return.
- `--sync-config` runs the sync and reloads, then parsing continues, so
  `sr --sync-config proj` deploys with the fresh config.

The second parser takes `project` (positional, `choices=` project names), `--dry-run`,
`--include-env`, `-c/--checksum`, `-o/--only PATH...` (`nargs='+'`, so put the project
name before `-o` or end the list with another flag), `--with-hooks`,
`--skip-pre-send`, `--skip-post-send`. No project prints help and exits 0.

## `sync_project` order of operations

1. Validate `--only` paths: reject absolute, `.`, anything escaping with `..`, or
   missing locally. Store as POSIX relative paths.
2. `run_hooks = not partial or with_hooks`.
3. Print warnings (dry run, partial, hooks skipped).
4. Expand `{timestamp}` in `backup_dir` as `%Y-%m-%d_%H-%M-%S` (local time of the
   machine running `sr`).
5. `pre_send` if present, not dry-run, `run_hooks`, not skipped. `shell=True`,
   `cwd=path`, inherits the terminal (interactive). Non-zero → print error and return
   (exit code still 0).
6. Build the rsync argv in this exact order:
   `rsync -avz --itemize-changes` → `--delete` (unless partial) → `--dry-run` →
   `rsync_args` (stringified) → `--checksum` → `--backup --backup-dir=…` →
   `-e 'ssh -J <jump> -p <port>'` or `-e 'ssh -p <port>'` (no `-e` if no port and no
   jump) → `--include .env --include .env.*` (if `--include-env`) → project
   `--include`s → `--exclude-from <global>` → project `--exclude`s → sources → remote.
   Partial mode adds `--relative` and sources like `<path>/./<rel>`.
7. On Windows: requires WSL (`wsl --list --quiet`), converts `C:\x` to `/mnt/c/x` for
   the source and global-ignore path, and runs `wsl rsync ...`. macOS (`darwin`) is
   rejected with "Unsupported platform" (only `win32` and `linux` are accepted).
8. Print a header with source/remote/only/jump/port/backup/include and the full
   command, then run rsync interactively.
9. On rsync success: `post_send` if present, not dry-run, `run_hooks`, not skipped.
   `shell=True`, no `cwd` (caller's cwd), Windows wraps it in `wsl bash -c`.

`_run_command(interactive=True)` inherits stdio; the non-interactive branch (captured
and re-printed) is only used by `--sync-config`.

Colours are ANSI and only emitted when stdout is a TTY.

## Known bugs / gaps (don't fix unless asked)

- Exit code is 0 after a failed `pre_send`, rsync or `post_send`, so a CI job running
  `sr` goes green on a failed deploy.
- `post_send` cwd is the caller's directory, unlike `pre_send`.
- macOS isn't supported by `sync_project` even though the README implies it is.
- `--only` paths that are excluded (e.g. `-o .env` without `--include-env`) silently
  send nothing.
- `rsync_args` are appended before `--backup`/`-e`; an `-e` in `rsync_args` is
  overridden when `port`/`ssh_jump_host` is set.

## Docker CLI image (`Dockerfile.cli`)

Alpine 3.20 + bash, git, openssh-client, rsync, python3, py3-yaml (~100 MB);
`/etc/passwd` is group-0 writable. `install.sh` (with `SKIP_PKGS=1`) installs the
script; the repo's `.sr-ignore-global.txt` is shipped next to it as a fallback.
`ssh-wrapper.sh` is installed as `/usr/local/bin/ssh` and forces
`-F $SENDREPO_SSH_CONFIG`, because OpenSSH finds `~/.ssh` from passwd, not `$HOME`.

`cli-entrypoint.sh`:
1. `HOME=/tmp/sendrepo-run/home`; adds a passwd entry for an unknown uid (needs group
   0, hence `--user $(id -u):0`); `git config --global safe.directory '*'`.
2. Copies `/config/config.yaml` (or `$SENDREPO_CONFIG_PATH`) and its
   `.sr-ignore-global.txt` to `/tmp/sendrepo-run/config/` and exports
   `SENDREPO_CONFIG_PATH` to the copy.
3. Unless `SENDREPO_NO_WORKSPACE=1`: refuses an empty or missing `/workspace`
   (override `SENDREPO_ALLOW_EMPTY_WORKSPACE=1`), then rewrites the `path` of the
   project named on the command line (or `$SENDREPO_PROJECT`) to `/workspace/`. The
   rewrite re-dumps the YAML with `yaml.safe_dump`, which drops comments (harmless,
   it's a copy).
4. Copies `/ssh-keys` (and `$SSH_PRIVATE_KEY` into `id_sendrepo`), sets 600/644 modes,
   writes an ssh config listing every file whose first line has `PRIVATE KEY` as an
   `IdentityFile`, plus `StrictHostKeyChecking accept-new` if
   `SENDREPO_SSH_ACCEPT_NEW=1`. Warns if no key/agent or no known_hosts.
5. `exec sendrepo "$@"`.

Wrappers: `sr-docker` (sh) and `sr-docker.ps1` mount `$PWD`→`/workspace`,
`~/.config/sendrepo`→`/config:ro`, `~/.ssh`→`/ssh-keys:ro`; overridable with
`SENDREPO_IMAGE`, `SENDREPO_CONFIG_DIR`, `SENDREPO_SSH_DIR`, `SENDREPO_WORKSPACE`,
`SENDREPO_DOCKER_ARGS`, `SENDREPO_DOCKER_USER` (sh only). If the config is not in `~/.config/sendrepo`, set `SENDREPO_CONFIG_DIR` to its
directory (if that dir has no `.sr-ignore-global.txt`, the image's built-in copy is
used).

Caveats: `--sync-config` inside the container only updates the throwaway copy;
`pre_send`/`post_send` run inside the container (Alpine `/bin/sh`, no docker CLI), so
hooks that need host tools fail there; `ssh -t` hooks need `-it`.

## GitHub Actions runner (`Dockerfile.runner`)

Based on `ghcr.io/actions/actions-runner:latest`, runs `install.sh` as root, then
`USER runner`. `runner-entrypoint.sh` copies `/ssh-keys` to `~/.ssh` (600), gets a
registration token from `RUNNER_TOKEN` or by POSTing with `ACCESS_TOKEN` (PAT) to
`/repos/{owner}/{repo}/actions/runners/registration-token` (or `/orgs/{org}/…` for an
org URL), runs `config.sh --unattended --replace`, and de-registers on exit via a
trap. `docker-compose.yaml` mounts `./ssh` and `./config.yaml` →
`/home/runner/.config/sendrepo/config.yaml`; env from `.env` (`REPO_URL`,
`ACCESS_TOKEN`|`RUNNER_TOKEN`, `RUNNER_NAME`, `RUNNER_LABELS`, optional
`RUNNER_GROUP`, `RUNNER_WORKDIR`). Workflows target `runs-on: [self-hosted, sendrepo]`
and run `sr <project>` (see `examples/deploy-on-tag.yml`).

Runner caveats: the config `path` must point at the checkout inside the runner
(`_work/...`), since nothing repoints it the way the CLI image does; a failed deploy
still exits 0; `test-pat.sh` is the quick check when registration fails (needs
Administration: write on the repo; GitHub reports missing admin as 404).
