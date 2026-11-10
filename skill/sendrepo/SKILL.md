---
name: sendrepo
description: Deploy or sync a project to its server with SendRepo (`sr` / `sendrepo`), an rsync-over-SSH deploy tool with per-project pre/post hooks. Use whenever the user mentions sendrepo, `sr <project>`, "send/sync/deploy/push it to the server" for a project listed in their SendRepo config, a dry run of a deploy, sending .env files or a single file to a server, adding/changing a SendRepo project entry, debugging an exclude/include or a failed deploy, the sendrepo Docker CLI image (`sr-docker`), the self-hosted GitHub Actions runner, or changing the SendRepo tool itself.
---

# SendRepo (`sr`)

`sr <project>` rsyncs a local project folder to a remote server over SSH, then
runs that project's hooks. It is usually the user's real deploy path, so a run
changes a live server: treat it like a production deploy.

- **Tool**: `sendrepo.py`, a single file. `sr` and `sendrepo` are symlinks to it.
  Find the repo with `dirname "$(readlink -f "$(command -v sr)")"`.
- **Config**: first existing of `$SENDREPO_CONFIG_PATH`,
  `~/.config/sendrepo/config.yaml`, `<tool repo>/../sendrepo-config/config.yaml`,
  `<tool repo>/config.yaml`. Every run prints `[info] Config: <path>`.
- **Global excludes**: `.sr-ignore-global.txt`, searched independently in the same
  directories; the first one found wins, which is not necessarily next to the config
  that was loaded.
- **Project list**: `sr --help` (argparse `choices`), or the `projects:` keys.

## Local notes (read first)

Machine-specific facts (which config and ignore file are in effect, hosts, per-project
hazards) live outside this public skill, in **`skill-local.md` in the config
directory** (the directory of the `[info] Config:` path). Read it before running or
editing any project. If it doesn't exist, rely on the config itself.

For internals (exact rsync command, filter order, lookup code), the Docker CLI image,
the GitHub runner, installers and known bugs, read [reference.md](reference.md).

## What a run does

1. **`pre_send`** runs locally via `/bin/sh` with cwd = project `path` (commonly
   `git pull` or a build). Non-zero exit stops the run before rsync.
2. **rsync** (Linux runs it directly; Windows wraps it in `wsl`):
   `rsync -avz --itemize-changes --delete [--dry-run] <rsync_args> [--checksum]
   --backup --backup-dir=<backup_dir> -e "ssh [-J jump] -p <port>"
   [--include .env --include .env.*] <--include each project include>
   --exclude-from <global ignore> <--exclude each project exclude> <path> <remote>`.
   - Filters are first-match-wins, so includes (and `--include-env`) beat every
     exclude. A project `exclude` can only add exclusions; to undo a global exclude,
     use `include`.
   - `--delete` without `--delete-excluded`: excluded files on the remote (its `.env`,
     `node_modules`, `.sendrepo/` backups) are never touched.
   - `--backup` moves both deleted **and overwritten** remote files into
     `backup_dir`. A relative `backup_dir` such as `.sendrepo/backups/{timestamp}/`
     resolves inside the remote folder (and `.sendrepo/` is globally excluded, so
     backups survive later runs). A project **without** `backup_dir` loses deleted and
     overwritten files permanently.
3. **`post_send`** runs only if rsync exited 0. It runs locally via `/bin/sh` with the
   **caller's** cwd (not the project path), and is usually an `ssh` to the server
   (restart, `docker compose pull/up`, env file rename). A failed `post_send` only
   prints `[err] post-send failed`.

**`sr` exits 0 even when pre_send, rsync or post_send fails.** Judge success from the
output (`Done: sync completed`, `[err] ...`), never from the exit code. Only a missing
config, a `--sync-config` failure or a bad CLI argument give a non-zero exit.

`.env` and `.env.*` files are never sent unless `--include-env` is given (then at
any depth, nested ones included).

## Flags

| Flag | Effect |
|---|---|
| `--dry-run` | rsync `--dry-run`: lists changes, sends nothing, runs **no hooks** (so a `pre_send: git pull` has not happened yet; the list reflects the tree as it is now) |
| `--include-env` | also sends `.env` / `.env.*`, which can **overwrite the server's `.env`** |
| `-o/--only PATH...` | send only these paths (relative to the project root, must exist locally); uses `--relative`, so structure is kept; disables `--delete`; skips hooks; excludes still apply |
| `--with-hooks` | with `--only`, run the hooks anyway |
| `--skip-pre-send` / `--skip-post-send` | skip one hook for this run |
| `-c/--checksum` | compare by content, not mtime+size (use after a fresh clone, or when files came from another machine) |
| `--sync-config` | run `config_sync.command` in the config dir, reload, then continue (may be combined with a project) |
| `--pre-send P` / `--post-send P` | run only that project's hook, then exit; no rsync |
| `--check-update` | `git fetch` the tool repo and prompt (interactive `input()`) to pull |
| `--open` | open the tool dir in a file manager |

`--check-update`, `--open`, `--pre-send`, `--post-send` short-circuit: anything after
them is ignored. `-o` takes one or more values, so put the project name before it.

## How to run one

1. **Read the project's entry** in the config: `path`, `remote`, `port`,
   `ssh_jump_host`, `exclude`, `include`, `rsync_args`, `pre_send`, `post_send`. The
   hooks are where the risk is. When showing it, mask anything that looks like a token
   or password. Check the local notes for hazards on this project.
2. **Check the local repo**: `git status` in `path`. Uncommitted work is sent as-is,
   untracked files included unless excluded. `pre_send: git pull` can fail or merge
   on a dirty or diverged tree. If `pre_send` builds something, the dry run will not
   show the build output yet.
3. **Dry run**: `sr <project> --dry-run` (add `--include-env` if the real run will use
   it). Read the itemized list: `*deleting` lines are remote files about to be moved
   to the backup dir, `<f+++++++++` lines are new files, `<f.st......` are changed.
   A huge list of changes on an unchanged project usually means mtimes differ: use
   `-c`. A huge `*deleting` list usually means the wrong `path`, a missing trailing
   slash, or a stale checkout: stop and investigate.
4. **Confirm with the user** before the real run, unless they already asked for this
   exact deploy. Say what will change and what `post_send` will do (restart, image
   pulls, env rename). Ask separately before using `--include-env`, `--skip-*`, or
   anything beyond what they asked for.
5. **Run it** (`sr <project> ...`) and read the output through the post-send section.
   `ssh -t` in hooks prints "Pseudo-terminal will not be allocated"; that is harmless.
   Hooks that prompt (sudo password, interactive `ssh -t`) will hang without a TTY:
   ask the user to run it themselves with `! sr <project>`.
6. **Verify on the server** over SSH (`docker ps`, logs, health endpoint, file
   timestamps), then report what changed and how it was checked.

To send a single file without hooks or deletions: `sr <project> -o path/to/file`.
To restart without resending: `sr --post-send <project>`.

**Rollback**: files that a run replaced or deleted are in
`<remote>/<backup_dir>` (e.g. `.sendrepo/backups/<YYYY-mm-dd_HH-MM-SS>/`) with their
relative paths. Copy them back over SSH (`rsync -a` or `cp -a` from the backup dir
into the remote folder), then rerun the restart (`sr --post-send <project>`). New
files a run added are not in the backup; delete them by hand if needed.

## Troubleshooting

- **Times out / `Connection refused`**: check the host is up. For Tailscale (100.x)
  remotes, `tailscale status`; an offline node just times out. Jump-host projects need
  the jump host reachable too.
- **`Host key verification failed`**: unknown or changed host key. Check with a plain
  `ssh -p <port> <user@host>`; don't disable host checking without asking.
- **A file isn't sent**: it matches a global exclude. Common surprises: `.gitignore`,
  `.github/`, `build/`, `out/`, `target/`, `logs/`, `tmp/`, `temp/`, `env/`,
  `*.log`, `*.key`, `*.pem`, `.vscode/`. Fix with a project `include:` entry. A bare
  filename matches at any depth, a path anchors it. Including a file inside an
  excluded directory needs the directory included too (e.g. `build/` and
  `build/**`), because rsync never descends into an excluded dir. Confirm with
  `--dry-run`.
- **`invalid choice: '<name>'`**: the project isn't in the config that was loaded.
  Check the `[info] Config:` line, then `sr --sync-config` if it was added elsewhere.
- **`Resource temporarily unavailable` to a Windows (cwRsync) host**: needs
  `rsync_args: [--blocking-io, --no-perms, --no-owner, --no-group]`.
- **Files land in a subfolder on the server**: `path` lacks a trailing `/` (rsync then
  copies the directory itself). End both `path` and `remote` with `/`.

## Changing the config

Edit the loaded `config.yaml`, following the neighbouring entries:

```yaml
root: ~/Dev
projects:
  my-project:
    path: "{root}/projects/my-project/"          # keep the trailing /
    remote: user@host:/home/user/my-project/      # trailing / too
    port: 22
    backup_dir: .sendrepo/backups/{timestamp}/    # relative = inside the remote folder
    exclude: [data/, uploads/]                    # remote-only state you must not delete
    # include: [certs/home-ca.key]                # re-include a globally excluded file
    # ssh_jump_host: "user@bastion:22"            # becomes ssh -J
    # rsync_args: [--no-perms]                    # extra rsync flags, appended as-is
    pre_send: |
      git pull
    post_send: |
      ssh -t user@host -p 22 "cd /home/user/my-project && docker compose up -d --build"
```

Before the first deploy of a new entry, make sure everything that lives only on the
server (uploads, DB data, `data/`, generated certs) is excluded or globally excluded,
because `--delete` removes anything the local tree doesn't have. Run `--dry-run` and
read every `*deleting` line.

`path` only supports `{root}`; `backup_dir` only supports `{timestamp}`. No keys
other than those above are read. If the config is its own git repo, commit or push it
only when the user asks. Never paste secrets from it into chat or commits.

## Changing the tool

The tool repo is public. Keep `README.md` and `config-example.yaml` in step with any
behaviour or flag change, and never commit `config.yaml`, `.env`, `ssh/` (all in
`.gitignore` and `.dockerignore`) or machine-specific facts (hosts, IPs, project
hazards: those go in `skill-local.md` in the config repo). This skill lives in the
repo at `skill/sendrepo/`. There are no tests; check changes with
`python3 -m py_compile sendrepo.py` and a `--dry-run` against a real project.
