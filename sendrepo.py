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

    def _run_command(self, command, cwd=None):
        """Runs a command and streams its output."""
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

    def sync_project(self, project_name, dry_run=False):
        """Syncs a single project."""
        project = self.config['projects'][project_name]

        source_path = project['path']
        remote_path = project['remote']
        exclude_patterns = project.get('exclude', [])
        port = project.get('port')
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
            return_code = self._run_command(pre_send_cmd, cwd=source_path)
            if return_code != 0:
                print(f"\nPre-send command failed with return code: {return_code}")
                return

        # Base rsync command
        rsync_cmd = [
            'rsync',
            '-avz',
            '--delete'
        ]

        if dry_run:
            rsync_cmd.append('--dry-run')

        # Add backup directory if specified
        if backup_dir:
            rsync_cmd.extend(['--backup', f'--backup-dir={backup_dir}'])

        # Add ssh port if specified
        if port:
            rsync_cmd.extend(['-e', f'ssh -p {port}'])

        # Add global exclude file if it exists
        if global_exclude_file:
            rsync_cmd.extend(['--exclude-from', global_exclude_file])

        # Add project-specific exclude patterns
        for pattern in exclude_patterns:
            rsync_cmd.extend(['--exclude', pattern])

        # Add source and destination
        rsync_cmd.extend([source_path, remote_path])

        # Platform-specific command execution
        if sys.platform == "win32":
            # On Windows, use WSL
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
        if port:
            print(f"Port: {port}")
        if backup_dir:
            print(f"Backup Dir: {backup_dir}")
        print(f"Executing command: {' '.join(command)}")

        return_code = self._run_command(command)

        if return_code == 0:
            print("\nSync completed successfully.")
            # Handle post-send commands if any
            if 'post_send' in project and not dry_run:
                print("Executing post-send command...")
                post_send_cmd = project['post_send']
                post_return_code = self._run_command(post_send_cmd)
                if post_return_code != 0:
                    print(f"\nPost-send command failed with return code: {post_return_code}")
        else:
            print(f"\nSync failed with return code: {return_code}")

def main():
    """Main function to run the sendrepo script."""
    
    # We need to handle --sync-config before fully parsing to get updated project choices
    # A bit of a chicken-and-egg problem. We create a temporary parser for this one argument.
    temp_parser = argparse.ArgumentParser(add_help=False)
    temp_parser.add_argument('--sync-config', action='store_true')
    temp_parser.add_argument('--open', action='store_true')
    temp_args, remaining_argv = temp_parser.parse_known_args()

    syncer = SendRepo()

    # Handle --open flag (opens sendrepo folder and exits)
    if temp_args.open:
        syncer.open_sendrepo_folder()
        return

    if temp_args.sync_config:
        syncer.sync_config()
    
    parser = argparse.ArgumentParser(description="Sync a project to a remote server using rsync (SSH key authentication).")
    parser.add_argument('--sync-config', action='store_true', help="Sync the configuration from its source before running the project sync.")
    parser.add_argument('--open', action='store_true', help="Open the SendRepo directory in file explorer for easy access to global ignore file and git operations.")
    parser.add_argument('project', nargs='?', help="The name of the project to sync.", choices=syncer.projects)
    parser.add_argument('--dry-run', action='store_true', help="Perform a dry run without making any changes.")
    
    # We parse the *remaining* arguments after pulling out --sync-config, but we need to add it back
    # for the help message to be correct. The actual value has already been handled.
    args = parser.parse_args(remaining_argv)

    # If no project specified and not using --open, show help
    if not args.project:
        parser.print_help()
        return

    syncer.sync_project(args.project, args.dry_run)

if __name__ == '__main__':
    main()
