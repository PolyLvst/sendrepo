#!/usr/bin/env python3
import os
import sys
import yaml
import subprocess
import argparse
from datetime import datetime

class SendRepo:
    def __init__(self, config_path=None):
        if config_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, 'config.yaml')
        
        self.config = self._load_config(config_path)
        self.projects = self._get_project_choices()

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

    def _run_command(self, command, cwd=None):
        """Runs a command and streams its output."""
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, cwd=cwd, shell=isinstance(command, str))
        for line in process.stdout:
            print(line, end='')
        process.wait()
        return process.returncode

    def sync_project(self, project_name, dry_run=False):
        """Syncs a single project."""
        project = self.config['projects'][project_name]

        source_path = project['path']
        remote_path = project['remote']
        exclude_patterns = project.get('exclude', [])
        port = project.get('port')
        backup_dir = project.get('backup_dir')

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

        # Add exclude patterns
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
    
    syncer = SendRepo()
    
    parser = argparse.ArgumentParser(description="Sync a project to a remote server using rsync (SSH key authentication).")
    parser.add_argument('project', help="The name of the project to sync.", choices=syncer.projects)
    parser.add_argument('--dry-run', action='store_true', help="Perform a dry run without making any changes.")
    args = parser.parse_args()

    syncer.sync_project(args.project, args.dry_run)

if __name__ == '__main__':
    main()
