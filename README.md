# SendRepo

SendRepo is a powerful and flexible Python script that automates the process of synchronizing local project directories with a remote server using `rsync`. It is designed to be highly configurable and works seamlessly across both Linux and Windows (via WSL).

## Features

-   **Multi-Project Configuration**: Manage multiple project sync configurations from a single `config.yaml` file.
-   **Cross-Platform**: Works on Linux and Windows (using Windows Subsystem for Linux).
-   **Pre-send and Post-send Hooks**: Execute custom shell commands on your local machine before syncing and on the remote server after a successful sync.
-   **Automated Backups**: Instead of just deleting files on the remote that don't exist locally, `rsync` can automatically back them up to a timestamped directory on the remote server.
-   **Dry Run Mode**: See what changes would be made without actually modifying any files using the `--dry-run` flag.
-   **Flexible Exclusions**: Easily specify files and directories to exclude from the sync with both project-specific and global exclude patterns.
-   **Partial Sync**: Send only specific files or folders with `--only` for quick one-off pushes (e.g. a single favicon) without disturbing the rest of the remote.
-   **Easy Setup**: Includes a helper script to add the tool to your system's PATH for easy access from anywhere.
-   **Container-Friendly**: A POSIX `install.sh` installs SendRepo and its dependencies into Docker images, plus a ready-made GitHub Actions self-hosted runner for rsync-over-SSH deploys.
-   **Config Sync Hook**: Automatically update your configuration from a Git repository or cloud storage before syncing projects using the `--sync-config` flag.
-   **Quick Access**: Use `--open` to instantly open the SendRepo directory in your file manager for easy editing of global excludes or git operations.

## Requirements

-   **Python 3.6+**
-   **PyYAML**: `pip install pyyaml`
-   **rsync**: Must be installed on the local machine (or WSL on Windows) and on the remote server.
-   **SSH Access**: SSH key-based authentication to the remote server is required.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/PolyLvst/sendrepo.git
    cd sendrepo
    ```

2.  **Install dependencies:**
    ```bash
    pip install pyyaml
    ```

3.  **Make the script executable (Linux/macOS):**
    ```bash
    chmod +x sendrepo.py
    ```

4.  **Add to your system's PATH:**
    Run the setup script to make `sendrepo.py` accessible from any directory.
    ```bash
    python setup_path.py
    ```
    After running, **restart your terminal** or run `source ~/.bashrc` (or `~/.zshrc`) for the changes to take effect.

## Docker / Container Install

For containers (or any Linux host), use `install.sh` instead of `setup_path.py`. It
installs the system dependencies (`python3`, `rsync`, `openssh-client`) and PyYAML,
then places the `sendrepo` and `sr` commands on `PATH` (`/usr/local/bin`) — which works
in a non-login container shell, unlike editing `~/.bashrc`.

```bash
./install.sh                 # install to /usr/local
PREFIX=/opt ./install.sh     # custom prefix
SKIP_PKGS=1 ./install.sh     # skip the system package manager
```

It auto-detects the package manager (apt / apk / dnf / yum) and uses `sudo` only when
not already root.

**In a Dockerfile:**
```dockerfile
FROM python:3.12-slim
COPY . /tmp/sendrepo
RUN cd /tmp/sendrepo && ./install.sh && rm -rf /tmp/sendrepo
```

At runtime, mount your config and an SSH key so rsync can reach your servers:
```bash
docker run --rm -it \
  -v "$PWD/config.yaml:/root/.config/sendrepo/config.yaml:ro" \
  -v "$HOME/.ssh:/root/.ssh:ro" \
  your-image sr my-project
```

## GitHub Actions Self-Hosted Runner

`Dockerfile.runner` and `docker-compose.yaml` build a GitHub self-hosted Actions runner
with SendRepo preinstalled, so workflows can deploy with a single `sr <project>` step.
It is built on the official `ghcr.io/actions/actions-runner` image (lean — no bundled
Docker-in-Docker), with `runner-entrypoint.sh` handling runner registration and clean
de-registration on shutdown.

**Setup:**

1.  Put your sendrepo `config.yaml` at `./config.yaml` (next to the compose file).
2.  Put the deploy SSH key + `known_hosts` in `./ssh/` (copied into the runner with
    correct `600`/`700` perms at startup).
3.  Create a `.env` file:
    ```bash
    REPO_URL=https://github.com/your-org/your-repo
    ACCESS_TOKEN=ghp_xxx          # PAT with admin scope (auto-fetches a registration token)
    # --- or instead of ACCESS_TOKEN, a short-lived registration token: ---
    # RUNNER_TOKEN=AXXXXXXXXXXXXXXXXXXXXXXXXX
    RUNNER_NAME=sendrepo-runner
    RUNNER_LABELS=self-hosted,sendrepo
    ```
4.  Bring it up:
    ```bash
    docker compose up -d --build
    ```

**Use it in a workflow:**
```yaml
jobs:
  deploy:
    runs-on: [self-hosted, sendrepo]
    steps:
      - run: sr my-project
```

> **Security:** `config.yaml`, `.env`, and your `ssh/` keys are secrets — keep them out
> of version control (add them to `.gitignore`). The runner de-registers on shutdown; a
> PAT-derived removal token can expire on long-lived containers, so if cleanup fails you
> may need to prune a stale runner in the GitHub UI.

## Configuration

The script is controlled by a `config.yaml` file. To keep your configuration private when using this public repository, you should store your `config.yaml` outside of the script directory and use one of the loading methods below.

It is highly recommended to add `config.yaml` to a `.gitignore` file in your local clone of this repository.

### Configuration Loading Priority

The script searches for `config.yaml` in the following order, using the first one it finds:

1.  **Environment Variable**: The path specified in the `SENDREPO_CONFIG_PATH` environment variable. This is the most flexible method.
    ```bash
    export SENDREPO_CONFIG_PATH="/path/to/your/synced/folder/config.yaml"
    ```

2.  **User-Specific Directory**: A standard, user-level configuration directory.
    -   **Linux/macOS**: `~/.config/sendrepo/config.yaml`
    -   **Windows**: `%APPDATA%\sendrepo\config.yaml` (e.g., `C:\Users\YourUser\AppData\Roaming\sendrepo\config.yaml`)

3.  **Adjacent Directory**: A folder named `sendrepo-config` located at the same level as the script's parent directory. This is useful for syncing your config in a separate Git repository.
    ```
    /some/path/
    ├── sendrepo/         (The script repo)
    │   └── sendrepo.py
    └── sendrepo-config/  (Your private config repo)
        └── config.yaml
    ```

4.  **Same Directory**: Next to the `sendrepo.py` script itself (the original behavior).

### Example `config.yaml`

```yaml
# Command to sync this config file from its source.
config_sync:
  # Example using git:
  command: "git pull"
  # Example using rclone (syncs a cloud folder to the config directory):
  # command: "rclone sync gdrive:sendrepo_config ."

root: ~/Dev
projects:
  my-project:
    path: "{root}/projects/my-project/"
    remote: user@your-server.com:/home/user/my-project/
    port: 22
    backup_dir: /home/user/backups/my-project/{timestamp}/
    exclude:
      - .git
      - node_modules
      - .env
      - __pycache__
    pre_send: |
      echo "Building project..."
      npm run build
    post_send: |
      echo "Restarting remote service..."
      ssh -t user@your-server.com -p 22 "cd /home/user/my-project && sudo systemctl restart my-service"
```

### Configuration Options

-   `config_sync`: (Optional) A command to sync your configuration file itself. When you run the script with the `--sync-config` flag, this command will be executed in the directory containing your `config.yaml`. This is useful for pulling the latest version from a Git repository or syncing from a cloud storage provider.
    -   **Git Example**: `command: "git pull"`
    -   **rclone Example**: `command: "rclone sync gdrive:sendrepo_config ."` (This syncs the contents of the `sendrepo_config` folder from a Google Drive remote to the current directory).
-   `root`: (Optional) A base path that can be referenced in your project paths.
-   `projects`: A dictionary of all your projects.
    -   `<project-name>`: A unique name for your project.
        -   `path`: The absolute path to your local project directory. Can use `{root}`.
        -   `remote`: The SSH destination and path on the remote server.
        -   `port`: (Optional) The SSH port to use for the connection. Defaults to 22.
        -   `backup_dir`: (Optional) A directory on the remote server where files that are deleted from the destination will be moved. Use `{timestamp}` to create a unique, timestamped backup folder for each run.
        -   `exclude`: A list of files or directories to exclude from the sync.
        -   `pre_send`: (Optional) A shell command to run locally *before* the sync starts. The script will stop if this command fails.
        -   `post_send`: (Optional) A shell command to run *after* a successful sync.

### Global Excludes

SendRepo supports a global exclude file that applies common exclusion patterns to all projects, reducing the need to repeat common excludes like `.git`, `node_modules`, or IDE files in each project configuration.

The global exclude file is named `.sr-ignore-global.txt` and is searched for in the same locations as the `config.yaml` file (following the same priority order).

The repository ships with a sensible default `.sr-ignore-global.txt` covering version
control, env files, **secrets/credentials** (`.ssh/`, `*.pem`, `*.key`, `id_rsa*`),
Python, Node, build artifacts, logs, IDE files, and SendRepo's own working directories.
An excerpt:

```
# ─── Env Files ─────────────────────────────────────
**/.env
**/.env.*
**/env/

# ─── Secrets / Credentials ─────────────────────────
**/.ssh/
**/*.pem
**/*.key
**/id_rsa
**/id_rsa.*

# ─── Python ────────────────────────────────────────
**/__pycache__/
**/*.pyc
**/venv*/

# ─── Node / Frontend ───────────────────────────────
**/node_modules/

# ─── Deployment Tool ───────────────────────────────
**/.sendrepo/
```

**How it works:**
- Global excludes are automatically loaded and applied to all projects using rsync's `--exclude-from` option
- They are combined with project-specific excludes defined in `config.yaml`
- Global excludes use the same pattern syntax as rsync's `--exclude` option
- Use `**/` for recursive matching at any depth (e.g., `**/node_modules/` excludes any `node_modules` directory anywhere in the tree)

The secrets patterns are especially useful if you ever sync SendRepo onto another host
(e.g. to bootstrap a new VPS) — they keep keys and credentials from being shipped to the
remote. Note that `config.yaml` is **not** globally excluded, so if it lives inside a
project you sync, add it to that project's `exclude` list.

## Usage

Once installed and configured, you can sync your projects from any directory.

-   **Sync a project:**
    ```bash
    sendrepo.py my-project
    ```

-   **Update your configuration and then sync a project:**
    If you store your `config.yaml` in a separate repository, you can first pull the latest changes and then immediately run the sync.
    ```bash
    sendrepo.py --sync-config my-project
    ```

-   **Perform a dry run:**
    To see what files would be changed without making any modifications, use the `--dry-run` flag. This will not execute `pre_send` or `post_send` hooks.
    ```bash
    sendrepo.py my-project --dry-run
    ```

-   **Send only specific files or folders (partial sync):**
    For one-off pushes (e.g. just a favicon) use `--only` / `-o` with one or more paths *relative to the project root*. The paths keep their directory structure on the remote.
    ```bash
    sendrepo.py my-project --only static/favicon.ico
    sendrepo.py my-project -o static/favicon.ico assets/logo.png
    sendrepo.py my-project -o public/        # whole subdirectory
    ```
    In partial mode:
    -   `--delete` is **disabled**, so the rest of the remote is left untouched.
    -   `pre_send` and `post_send` hooks are **skipped by default**. Pass `--with-hooks` if you want them to run (e.g. when you need a post-send service restart).
    -   `--dry-run`, `--checksum`, `--include-env`, project excludes, and global excludes all still apply.

-   **Open SendRepo directory:**
    To easily access the script directory for editing global excludes, updating the script, or performing git operations.
    ```bash
    sendrepo.py --open
    ```
    This opens the SendRepo directory in your system's file manager, giving you quick access to:
    - `.sr-ignore-global.txt` - Edit global exclude patterns
    - `sendrepo.py` - The main script file  
    - `README.md` - Documentation
    - `.git/` - Git repository for updates (run `git pull` to update)

### Creating an Alias (Optional)

For even easier access, you can create a shell alias.

**On Linux/macOS:**

Add this to your `~/.bashrc` or `~/.zshrc`:
```bash
alias sr='sendrepo.py'
```

**On Windows (PowerShell):**

Add this to your PowerShell profile (`notepad $PROFILE`):
```powershell
function sr { python (Get-Command sendrepo.py).Source @args }
```
