#!/usr/bin/env python3
import os
import sys
import yaml
import subprocess
import argparse
from datetime import datetime

class SendRepo:
    def __init__(self, config_path=None):
        self.config_path = self._find_config_file(config_path)
        if not self.config_path:
            print("Error: Could not find config.yaml.")
            print("Please place it in one of the documented locations")
            sys.exit(1)
        
        print(f"Loading config from: {self.config_path}")
        self.config = self._load_config(self.config_path)
        self.projects = self._get_project_choices()

    def _find_config_file(self, specified_path):
        """Finds the config file in a prioritized list of locations."""
        if specified_path and os.path.exists(specified_path):
            return specified_path

        # Path specified by environment variable
        env_path = os.getenv('SENDREPO_CONFIG_PATH')
        if env_path and os.path.exists(env_path):
            return env_path

        # User-specific config directory
        if sys.platform == "win32":
            user_config_path = os.path.join(os.getenv('APPDATA'), 'sendrepo', 'config.yaml')
        else: # Linux, macOS
            user_config_path = os.path.expanduser("~/.config/sendrepo/config.yaml")
        
        if os.path.exists(user_config_path):
            return user_config_path

        # In an adjacent directory: ../sendrepo-config/config.yaml
        script_dir = os.path.dirname(os.path.realpath(__file__))
        adjacent_config_path = os.path.join(script_dir, '..', 'sendrepo-config', 'config.yaml')
        if os.path.exists(adjacent_config_path):
            return os.path.normpath(adjacent_config_path)

        # In the same directory as the script
        script_config_path = os.path.join(script_dir, 'config.yaml')
        if os.path.exists(script_config_path):
            return script_config_path
        
        return None

    def _load_config(self, config_path):
        """Loads the configuration from a YAML file."""
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Expand root path
        root = os.path.expanduser(config.get('root', ''))
        if 'projects' in config:
            for name, project in config['projects'].items():
                project['path'] = project['path'].format(root=root)
        
        return config

    def _get_project_choices(self):
        """Returns a list of project names from the config."""
        return list(self.config.get('projects', {}).keys())

    def _find_global_exclude_file(self):
        """Finds the global exclude file (.sr-ignore-global.txt) using the same search logic as config"""
        possible_paths = []
        
        # Check environment variable path directory
        env_config_path = os.environ.get('SENDREPO_CONFIG_PATH')
        if env_config_path:
            config_dir = os.path.dirname(os.path.abspath(env_config_path))
            possible_paths.append(os.path.join(config_dir, '.sr-ignore-global.txt'))
        
        # Check user config directory
        if sys.platform == "win32":
            user_config_dir = os.path.join(os.environ.get('APPDATA', ''), 'sendrepo')
        else:
            user_config_dir = os.path.expanduser('~/.config/sendrepo')
        possible_paths.append(os.path.join(user_config_dir, '.sr-ignore-global.txt'))
        
        # Check adjacent config directory
        script_dir = os.path.dirname(os.path.realpath(__file__))
        parent_dir = os.path.dirname(script_dir)
        adjacent_config_dir = os.path.join(parent_dir, 'sendrepo-config')
        possible_paths.append(os.path.join(adjacent_config_dir, '.sr-ignore-global.txt'))
        
        # Check script directory
        possible_paths.append(os.path.join(script_dir, '.sr-ignore-global.txt'))
        
        # Return the first file that exists
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None

    def sync_config(self):
        """Syncs the configuration file itself based on 'config_sync' settings."""
        if 'config_sync' not in self.config:
            print("Warning: --sync-config was passed, but 'config_sync' section is not defined in config.yaml.")
            return

        sync_settings = self.config['config_sync']
        command = sync_settings.get('command')
        
        if not command:
            print("Error: 'config_sync' section is missing the 'command' key.")
            return

        # The working directory should be where the config file is.
        config_dir = os.path.dirname(self.config_path)

        print(f"Syncing configuration using command: '{command}' in '{config_dir}'")
        return_code = self._run_command(command, cwd=config_dir)

        if return_code == 0:
            print("Configuration sync completed successfully.")
            # Reload config after sync
            print("Reloading configuration...")
            self.config = self._load_config(self.config_path)
            self.projects = self._get_project_choices()
        else:
            print(f"Configuration sync failed with return code: {return_code}")
            sys.exit(1) # Exit if config sync fails

    def _run_command(self, command, cwd=None, interactive=False):
        """Runs a command and streams its output."""
        if interactive:
            process = subprocess.Popen(command, cwd=cwd, shell=isinstance(command, str))
            process.wait()
            return process.returncode
        else:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, cwd=cwd, shell=isinstance(command, str))
            for line in process.stdout:
                print(line, end='')
            process.wait()
            return process.returncode

    def open_sendrepo_folder(self):
        """Opens the sendrepo script directory in the file explorer."""
        script_dir = os.path.dirname(os.path.realpath(__file__))
        
        print(f"Opening SendRepo directory: {script_dir}")
        
        try:
            if sys.platform == "win32":
                # Windows - use explorer
                subprocess.run(['explorer', script_dir], check=True)
            elif sys.platform == "darwin":
                # macOS - use Finder
                subprocess.run(['open', script_dir], check=True)
            elif sys.platform == "linux":
                # Linux - try various file managers
                file_managers = ['xdg-open', 'nautilus', 'dolphin', 'thunar', 'nemo', 'pcmanfm']
                opened = False
                
                for fm in file_managers:
                    try:
                        subprocess.run([fm, script_dir], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        opened = True
                        break
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue
                
                if not opened:
                    print("Could not find a suitable file manager. Directory path:")
                    print(f"  {script_dir}")
                    print("\nFiles in this directory:")
                    for item in sorted(os.listdir(script_dir)):
                        if os.path.isdir(os.path.join(script_dir, item)):
                            print(f"  📁 {item}/")
                        else:
                            print(f"  📄 {item}")
                    return
            else:
                print(f"Unsupported platform: {sys.platform}")
                print(f"SendRepo directory: {script_dir}")
                return
            
        except subprocess.CalledProcessError as e:
            print(f"Error opening folder: {e}")
            print(f"SendRepo directory: {script_dir}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            print(f"SendRepo directory: {script_dir}")

    def run_pre_send(self, project_name):
        """Manually runs the pre-send command for a project."""
        if project_name not in self.projects:
            print(f"Error: Project '{project_name}' not found in config.")
            return

        project = self.config['projects'][project_name]
        source_path = project['path']

        if 'pre_send' in project:
            print(f"Executing pre-send command for project '{project_name}'...")
            pre_send_cmd = project['pre_send']
            return_code = self._run_command(pre_send_cmd, cwd=source_path, interactive=True)
            if return_code == 0:
                print(f"\nPre-send command completed successfully for '{project_name}'.")
            else:
                print(f"\nPre-send command failed with return code: {return_code}")
        else:
            print(f"No pre-send command defined for project '{project_name}'.")

    def run_post_send(self, project_name):
        """Manually runs the post-send command for a project."""
        if project_name not in self.projects:
            print(f"Error: Project '{project_name}' not found in config.")
            return

        project = self.config['projects'][project_name]

        if 'post_send' in project:
            print(f"Executing post-send command for project '{project_name}'...")
            post_send_cmd = project['post_send']
            if sys.platform == "win32":
                post_send_cmd = ['wsl', 'bash', '-c', post_send_cmd]
            return_code = self._run_command(post_send_cmd, interactive=True)
            if return_code == 0:
                print(f"\nPost-send command completed successfully for '{project_name}'.")
            else:
                print(f"\nPost-send command failed with return code: {return_code}")
        else:
            print(f"No post-send command defined for project '{project_name}'.")

    def _check_wsl_available(self):
        """Checks if WSL is available and has at least one distribution installed."""
        try:
            subprocess.run(['wsl', '--list', '--quiet'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _windows_to_wsl_path(self, path):
        """Converts a Windows path to a WSL-compatible path."""
        if sys.platform == "win32" and path and (path[1:3] == ':\\' or path[1:3] == ':/'):
            drive = path[0].lower()
            rest = path[3:].replace('\\', '/')
            return f"/mnt/{drive}/{rest}"
        return path

    def sync_project(self, project_name, dry_run=False, include_env=False):
        """Syncs a single project."""
        project = self.config['projects'][project_name]

        source_path = project['path']
        remote_path = project['remote']
        exclude_patterns = project.get('exclude', [])
        port = project.get('port')
        ssh_jump_host = project.get('ssh_jump_host')
        backup_dir = project.get('backup_dir')

        # Find global exclude file
        global_exclude_file = self._find_global_exclude_file()

        if dry_run:
            print("****** DRY RUN ******")
            print("No changes will be made.")

        # Format backup_dir with timestamp if placeholder exists
        if backup_dir and '{timestamp}' in backup_dir:
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            backup_dir = backup_dir.format(timestamp=timestamp)

        # Handle pre-send commands if any
        if 'pre_send' in project and not dry_run:
            print("Executing pre-send command...")
            pre_send_cmd = project['pre_send']
            return_code = self._run_command(pre_send_cmd, cwd=source_path, interactive=True)
            if return_code != 0:
                print(f"\nPre-send command failed with return code: {return_code}")
                return

        # Base rsync command
        rsync_cmd = [
            'rsync',
            '-avz',
            '--itemize-changes',
            '--delete'
        ]

        if dry_run:
            rsync_cmd.append('--dry-run')

        # Add backup directory if specified
        if backup_dir:
            rsync_cmd.extend(['--backup', f'--backup-dir={backup_dir}'])

        # Add ssh port if specified
        if ssh_jump_host:
            # Build SSH command with jump host for reverse tunnel
            ssh_cmd = f'ssh -J {ssh_jump_host}'
            if port:
                ssh_cmd += f' -p {port}'
            rsync_cmd.extend(['-e', ssh_cmd])
        elif port:
            rsync_cmd.extend(['-e', f'ssh -p {port}'])

        # Temporarily include .env files if requested
        if include_env:
            print("WARNING: Including .env files in this sync!")
            rsync_cmd.extend(['--include', '.env', '--include', '.env.*'])

        # Add global exclude file if it exists
        if global_exclude_file:
            wsl_exclude_file = self._windows_to_wsl_path(global_exclude_file) if sys.platform == "win32" else global_exclude_file
            rsync_cmd.extend(['--exclude-from', wsl_exclude_file])

        # Add project-specific exclude patterns
        for pattern in exclude_patterns:
            rsync_cmd.extend(['--exclude', pattern])

        # Add source and destination
        wsl_source_path = self._windows_to_wsl_path(source_path) if sys.platform == "win32" else source_path
        rsync_cmd.extend([wsl_source_path, remote_path])

        # Platform-specific command execution
        if sys.platform == "win32":
            if not self._check_wsl_available():
                print("Windows Subsystem for Linux (WSL) is not available or no distributions are installed.")
                print("Please install WSL and a Linux distribution using one of the following methods:")
                print("1. Use 'wsl.exe --list --online' to list available distributions")
                print("   and 'wsl.exe --install <Distro>' to install.")
                print("2. Visit the Microsoft Store: https://aka.ms/wslstore")
                return
            command = ['wsl'] + rsync_cmd
        elif sys.platform == "linux":
            # On Linux, run directly
            command = rsync_cmd
        else:
            print(f"Unsupported platform: {sys.platform}")
            return

        print(f"Syncing project '{project_name}'...")
        print(f"Source: {source_path}")
        print(f"Remote: {remote_path}")
        if ssh_jump_host:
            print(f"SSH Jump Host: {ssh_jump_host}")
        if port:
            print(f"Port: {port}")
        if backup_dir:
            print(f"Backup Dir: {backup_dir}")
        if include_env:
            print(f"Include .env: YES")
        print(f"Executing command: {' '.join(command)}")

        return_code = self._run_command(command, interactive=True)

        if return_code == 0:
            print("\nSync completed successfully.")
            # Handle post-send commands if any
            if 'post_send' in project and not dry_run:
                print("Executing post-send command...")
                post_send_cmd = project['post_send']
                if sys.platform == "win32":
                    post_send_cmd = ['wsl', 'bash', '-c', post_send_cmd]
                post_return_code = self._run_command(post_send_cmd, interactive=True)
                if post_return_code != 0:
                    print(f"\nPost-send command failed with return code: {post_return_code}")
        else:
            print(f"\nSync failed with return code: {return_code}")

def check_for_updates(tool_name):
    """Checks if there are updates available on the remote git repository."""
    script_dir = os.path.dirname(os.path.realpath(__file__))

    try:
        # Check if it's a git repo
        result = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            cwd=script_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"{tool_name} is not installed as a git repository. Cannot check for updates.")
            return

        # Get current branch
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=script_dir, capture_output=True, text=True
        )
        branch = result.stdout.strip()

        # Get current local commit
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=script_dir, capture_output=True, text=True
        )
        local_hash = result.stdout.strip()

        # Fetch latest from remote
        print(f"Checking for {tool_name} updates...")
        result = subprocess.run(
            ['git', 'fetch'],
            cwd=script_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Failed to fetch updates: {result.stderr.strip()}")
            return

        # Get remote commit
        result = subprocess.run(
            ['git', 'rev-parse', f'origin/{branch}'],
            cwd=script_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Could not find remote branch 'origin/{branch}'.")
            return
        remote_hash = result.stdout.strip()

        if local_hash == remote_hash:
            print(f"{tool_name} is up to date. ({local_hash[:7]})")
            return

        # Show commits behind
        result = subprocess.run(
            ['git', 'log', '--oneline', f'HEAD..origin/{branch}'],
            cwd=script_dir, capture_output=True, text=True
        )
        commits = result.stdout.strip()
        commit_count = len(commits.splitlines())

        print(f"\n{tool_name} is {commit_count} commit(s) behind origin/{branch}:\n")
        print(commits)
        print()

        # Ask user if they want to update
        try:
            answer = input("Do you want to update now? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if answer in ('y', 'yes'):
            result = subprocess.run(
                ['git', 'pull'],
                cwd=script_dir, text=True
            )
            if result.returncode == 0:
                print(f"\n{tool_name} updated successfully!")
            else:
                print(f"\nUpdate failed. You can manually update by running 'git pull' in {script_dir}")
        else:
            print(f"Skipped. You can update later by running 'git pull' in {script_dir}")

    except FileNotFoundError:
        print("git is not installed or not in PATH. Cannot check for updates.")


def main():
    """Main function to run the sendrepo script."""
    
    # We need to handle special arguments before fully parsing
    temp_parser = argparse.ArgumentParser(add_help=False)
    temp_parser.add_argument('--sync-config', action='store_true')
    temp_parser.add_argument('--open', action='store_true')
    temp_parser.add_argument('--check-update', action='store_true')
    temp_parser.add_argument('--pre-send', dest='pre_send_project', metavar='PROJECT')
    temp_parser.add_argument('--post-send', dest='post_send_project', metavar='PROJECT')
    temp_args, remaining_argv = temp_parser.parse_known_args()

    # Handle --check-update before loading config
    if temp_args.check_update:
        check_for_updates("SendRepo")
        return

    syncer = SendRepo()

    # Handle --open flag (opens sendrepo folder and exits)
    if temp_args.open:
        syncer.open_sendrepo_folder()
        return

    # Handle manual pre-send execution
    if temp_args.pre_send_project:
        syncer.run_pre_send(temp_args.pre_send_project)
        return
        
    # Handle manual post-send execution
    if temp_args.post_send_project:
        syncer.run_post_send(temp_args.post_send_project)
        return

    if temp_args.sync_config:
        syncer.sync_config()
    
    parser = argparse.ArgumentParser(description="Sync a project to a remote server using rsync (SSH key authentication).")
    parser.add_argument('--sync-config', action='store_true', help="Sync the configuration from its source before running the project sync.")
    parser.add_argument('--open', action='store_true', help="Open the SendRepo directory in file explorer for easy access to global ignore file and git operations.")
    parser.add_argument('--check-update', action='store_true', help="Check if a newer version is available on the remote git repository.")
    parser.add_argument('--pre-send', metavar='PROJECT', help="Manually run the pre-send command for a specific project.")
    parser.add_argument('--post-send', metavar='PROJECT', help="Manually run the post-send command for a specific project.")
    parser.add_argument('project', nargs='?', help="The name of the project to sync.", choices=syncer.projects)
    parser.add_argument('--dry-run', action='store_true', help="Perform a dry run without making any changes.")
    parser.add_argument('--include-env', action='store_true', help="Temporarily include .env files in the sync.")
    
    # We parse the *remaining* arguments after pulling out special flags
    args = parser.parse_args(remaining_argv)

    # If no project specified and not using --open, show help
    if not args.project:
        parser.print_help()
        return

    syncer.sync_project(args.project, args.dry_run, args.include_env)

if __name__ == '__main__':
    main()
