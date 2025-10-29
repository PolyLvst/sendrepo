# SendRepo

SendRepo is a powerful and flexible Python script that automates the process of synchronizing local project directories with a remote server using `rsync`. It is designed to be highly configurable and works seamlessly across both Linux and Windows (via WSL).

## Features

-   **Multi-Project Configuration**: Manage multiple project sync configurations from a single `config.yaml` file.
-   **Cross-Platform**: Works on Linux and Windows (using Windows Subsystem for Linux).
-   **Pre-send and Post-send Hooks**: Execute custom shell commands on your local machine before syncing and on the remote server after a successful sync.
-   **Automated Backups**: Instead of just deleting files on the remote that don't exist locally, `rsync` can automatically back them up to a timestamped directory on the remote server.
-   **Dry Run Mode**: See what changes would be made without actually modifying any files using the `--dry-run` flag.
-   **Flexible Exclusions**: Easily specify files and directories to exclude from the sync (e.g., `.git`, `node_modules`).
-   **Easy Setup**: Includes a helper script to add the tool to your system's PATH for easy access from anywhere.

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

## Configuration

The script is controlled by a `config.yaml` file in the same directory.

### Example `config.yaml`

```yaml
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

## Usage

Once installed and configured, you can sync your projects from any directory.

-   **Sync a project:**
    ```bash
    sendrepo.py my-project
    ```

-   **Perform a dry run:**
    To see what files would be changed without making any modifications, use the `--dry-run` flag. This will not execute `pre_send` or `post_send` hooks.
    ```bash
    sendrepo.py my-project --dry-run
    ```

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
