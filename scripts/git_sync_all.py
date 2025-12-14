#!/usr/bin/env python3
"""
Git Sync All Projects
=====================
Automatically commits and pushes all projects in the portfolio.
Prioritizes local state as source of truth (uses force push).
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import argparse

# Base directory
PORTFOLIO_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = PORTFOLIO_ROOT / "projects"

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def get_all_projects() -> List[Path]:
    """Get all project directories (excluding venv, .git, etc.)"""
    excluded = {".git", "venv", "static", "templates", "__pycache__", "node_modules"}
    projects = []

    for item in sorted(PROJECTS_DIR.iterdir()):
        if item.is_dir() and item.name not in excluded and not item.name.startswith("."):
            # Check if it has a .git directory
            if (item / ".git").exists():
                projects.append(item)

    return projects


def run_git_command(project_dir: Path, command: List[str], check=True) -> Tuple[bool, str]:
    """
    Run a git command in a project directory.
    Returns (success, output/error)
    """
    try:
        result = subprocess.run(
            command,
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=check
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()


def get_git_status(project_dir: Path) -> Dict[str, any]:
    """Get git status information for a project"""
    status = {
        "has_changes": False,
        "has_remote": False,
        "remote_url": "",
        "current_branch": "",
        "has_uncommitted": False,
        "has_unpushed": False,
        "ahead": 0,
        "behind": 0,
    }

    # Get current branch
    success, branch = run_git_command(project_dir, ["git", "rev-parse", "--abbrev-ref", "HEAD"], check=False)
    if success:
        status["current_branch"] = branch

    # Check for uncommitted changes
    success, output = run_git_command(project_dir, ["git", "status", "--porcelain"], check=False)
    if success and output:
        status["has_uncommitted"] = True
        status["has_changes"] = True

    # Get remote URL
    success, remote_url = run_git_command(project_dir, ["git", "remote", "get-url", "origin"], check=False)
    if success and remote_url:
        status["has_remote"] = True
        status["remote_url"] = remote_url

    # Check if ahead/behind remote
    if status["has_remote"] and status["current_branch"]:
        success, output = run_git_command(
            project_dir,
            ["git", "rev-list", "--left-right", "--count", f"origin/{status['current_branch']}...HEAD"],
            check=False
        )
        if success and output:
            parts = output.split()
            if len(parts) == 2:
                status["behind"] = int(parts[0])
                status["ahead"] = int(parts[1])
                if status["ahead"] > 0:
                    status["has_unpushed"] = True
                    status["has_changes"] = True

    return status


def show_status():
    """Show git status for all projects"""
    projects = get_all_projects()

    print("\n" + "=" * 80)
    print(f"{Colors.HEADER}{Colors.BOLD}GIT STATUS - ALL PROJECTS{Colors.ENDC}")
    print("=" * 80 + "\n")

    if not projects:
        print(f"{Colors.WARNING}No git projects found in {PROJECTS_DIR}{Colors.ENDC}")
        return

    for project in projects:
        status = get_git_status(project)
        proj_name = project.name

        # Status indicator
        if status["has_uncommitted"]:
            indicator = f"{Colors.WARNING}●{Colors.ENDC}"
        elif status["has_unpushed"]:
            indicator = f"{Colors.OKCYAN}↑{Colors.ENDC}"
        else:
            indicator = f"{Colors.OKGREEN}✓{Colors.ENDC}"

        print(f"{indicator} {Colors.BOLD}{proj_name:<30}{Colors.ENDC}", end="")

        if status["current_branch"]:
            print(f" [{status['current_branch']}]", end="")

        if status["has_uncommitted"]:
            print(f" {Colors.WARNING}uncommitted changes{Colors.ENDC}", end="")

        if status["ahead"] > 0:
            print(f" {Colors.OKCYAN}↑{status['ahead']} ahead{Colors.ENDC}", end="")

        if status["behind"] > 0:
            print(f" {Colors.WARNING}↓{status['behind']} behind{Colors.ENDC}", end="")

        if status["has_remote"]:
            # Shorten GitHub URL
            remote = status["remote_url"].replace("https://github.com/", "gh:")
            remote = remote.replace("git@github.com:", "gh:")
            remote = remote.replace(".git", "")
            print(f" → {Colors.OKBLUE}{remote}{Colors.ENDC}", end="")
        else:
            print(f" {Colors.FAIL}no remote{Colors.ENDC}", end="")

        print()

    print("\n" + "=" * 80)
    print(f"{Colors.OKGREEN}●{Colors.ENDC} Clean  {Colors.WARNING}●{Colors.ENDC} Uncommitted  {Colors.OKCYAN}↑{Colors.ENDC} Unpushed")
    print("=" * 80)


def commit_project(project_dir: Path, message: str, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Stage all changes and commit them.
    Returns (success, message)
    """
    proj_name = project_dir.name

    # Check if there are any changes
    success, output = run_git_command(project_dir, ["git", "status", "--porcelain"], check=False)
    if not success:
        return False, "Failed to check git status"

    if not output:
        return True, "No changes to commit"

    # Stage all changes
    if not dry_run:
        success, output = run_git_command(project_dir, ["git", "add", "."], check=False)
        if not success:
            return False, f"Failed to stage changes: {output}"

    # Create commit
    if not dry_run:
        success, output = run_git_command(
            project_dir,
            ["git", "commit", "-m", message],
            check=False
        )
        if not success:
            # Check if it's because there's nothing to commit
            if "nothing to commit" in output.lower():
                return True, "No changes to commit"
            return False, f"Failed to commit: {output}"
        return True, f"Committed: {message}"
    else:
        return True, f"Would commit: {message}"


def push_project(project_dir: Path, force: bool = False, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Push changes to remote.
    Returns (success, message)
    """
    status = get_git_status(project_dir)

    if not status["has_remote"]:
        return False, "No remote configured"

    if not status["current_branch"]:
        return False, "Cannot determine current branch"

    # Build push command
    cmd = ["git", "push"]

    if force:
        cmd.append("--force-with-lease")  # Safer than --force, won't overwrite if remote changed

    cmd.extend(["origin", status["current_branch"]])

    if not dry_run:
        success, output = run_git_command(project_dir, cmd, check=False)
        if not success:
            # If --force-with-lease failed, try with regular --force if explicitly requested
            if force and "force-with-lease" in " ".join(cmd):
                cmd = ["git", "push", "--force", "origin", status["current_branch"]]
                success, output = run_git_command(project_dir, cmd, check=False)
                if success:
                    return True, f"{Colors.WARNING}Force pushed (overrode remote){Colors.ENDC}"
                else:
                    return False, f"Failed to push: {output}"
            return False, f"Failed to push: {output}"

        return True, "Pushed successfully"
    else:
        force_flag = "--force" if force else ""
        return True, f"Would push {force_flag} to {status['remote_url']}"


def sync_all_projects(commit_message: str = None, force: bool = False, dry_run: bool = False):
    """Commit and push all projects"""
    projects = get_all_projects()

    if not projects:
        print(f"{Colors.WARNING}No git projects found in {PROJECTS_DIR}{Colors.ENDC}")
        return

    # Generate commit message if not provided
    if not commit_message:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_message = f"Update {timestamp}"

    print("\n" + "=" * 80)
    print(f"{Colors.HEADER}{Colors.BOLD}GIT SYNC - ALL PROJECTS{Colors.ENDC}")
    print("=" * 80)

    if dry_run:
        print(f"\n{Colors.WARNING}⚠️  DRY RUN MODE - No changes will be made{Colors.ENDC}\n")

    if force and not dry_run:
        print(f"\n{Colors.WARNING}⚠️  FORCE MODE ENABLED - Local state will override remote{Colors.ENDC}\n")

    print(f"Commit message: {Colors.OKCYAN}\"{commit_message}\"{Colors.ENDC}\n")

    results = {
        "committed": [],
        "pushed": [],
        "no_changes": [],
        "errors": []
    }

    for project in projects:
        proj_name = project.name
        print(f"\n{Colors.BOLD}{'─' * 80}{Colors.ENDC}")
        print(f"{Colors.BOLD}📁 {proj_name}{Colors.ENDC}")
        print(f"{Colors.BOLD}{'─' * 80}{Colors.ENDC}")

        # Stage and commit
        success, msg = commit_project(project, commit_message, dry_run)
        if success:
            if "No changes" in msg:
                print(f"   {Colors.OKBLUE}ℹ{Colors.ENDC}  {msg}")
                results["no_changes"].append(proj_name)
            else:
                print(f"   {Colors.OKGREEN}✓{Colors.ENDC}  {msg}")
                results["committed"].append(proj_name)

                # Push to remote
                success, msg = push_project(project, force, dry_run)
                if success:
                    print(f"   {Colors.OKGREEN}✓{Colors.ENDC}  {msg}")
                    results["pushed"].append(proj_name)
                else:
                    print(f"   {Colors.FAIL}✗{Colors.ENDC}  {msg}")
                    results["errors"].append(f"{proj_name}: {msg}")
        else:
            print(f"   {Colors.FAIL}✗{Colors.ENDC}  {msg}")
            results["errors"].append(f"{proj_name}: {msg}")

    # Summary
    print("\n" + "=" * 80)
    print(f"{Colors.HEADER}{Colors.BOLD}SUMMARY{Colors.ENDC}")
    print("=" * 80 + "\n")

    print(f"{Colors.OKGREEN}✓ Committed:{Colors.ENDC} {len(results['committed'])} project(s)")
    if results["committed"]:
        for proj in results["committed"]:
            print(f"  - {proj}")

    print(f"\n{Colors.OKGREEN}✓ Pushed:{Colors.ENDC} {len(results['pushed'])} project(s)")
    if results["pushed"]:
        for proj in results["pushed"]:
            print(f"  - {proj}")

    print(f"\n{Colors.OKBLUE}ℹ No changes:{Colors.ENDC} {len(results['no_changes'])} project(s)")
    if results["no_changes"]:
        for proj in results["no_changes"]:
            print(f"  - {proj}")

    if results["errors"]:
        print(f"\n{Colors.FAIL}✗ Errors:{Colors.ENDC} {len(results['errors'])}")
        for error in results["errors"]:
            print(f"  - {error}")

    print("\n" + "=" * 80)

    if dry_run:
        print(f"\n{Colors.WARNING}✓ Dry run completed. Use without --dry-run to apply changes.{Colors.ENDC}")
    elif not results["errors"]:
        print(f"\n{Colors.OKGREEN}✓ All operations completed successfully!{Colors.ENDC}")
    else:
        print(f"\n{Colors.WARNING}⚠ Completed with {len(results['errors'])} error(s){Colors.ENDC}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Git Sync Tool - Commit and push all portfolio projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status                              # Show git status for all projects
  %(prog)s sync                                # Commit and push all projects
  %(prog)s sync -m "Custom message"            # Commit with custom message
  %(prog)s sync --force                        # Force push (local overrides remote)
  %(prog)s sync --dry-run                      # Preview changes
  %(prog)s sync --force --dry-run              # Preview force push

Warning:
  --force will override remote changes with local state. Use with caution!
  The script uses --force-with-lease first for safety, then falls back to --force.
        """
    )

    parser.add_argument(
        "command",
        choices=["status", "sync"],
        help="Command to execute"
    )

    parser.add_argument(
        "-m", "--message",
        help="Custom commit message (default: 'Update YYYY-MM-DD HH:MM:SS')"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force push (local state overrides remote)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )

    args = parser.parse_args()

    print(f"\n{'=' * 80}")
    print(f"{Colors.HEADER}{Colors.BOLD}GIT SYNC TOOL - PORTFOLIO{Colors.ENDC}")
    print(f"{'=' * 80}")

    try:
        if args.command == "status":
            show_status()

        elif args.command == "sync":
            # Safety confirmation for force push
            if args.force and not args.dry_run:
                print(f"\n{Colors.WARNING}{Colors.BOLD}⚠️  WARNING ⚠️{Colors.ENDC}")
                print(f"{Colors.WARNING}You are about to FORCE PUSH all projects.{Colors.ENDC}")
                print(f"{Colors.WARNING}This will overwrite remote changes with your local state.{Colors.ENDC}\n")

                response = input(f"Type 'YES' to continue: ")
                if response != "YES":
                    print(f"\n{Colors.FAIL}Aborted.{Colors.ENDC}")
                    sys.exit(0)

            sync_all_projects(
                commit_message=args.message,
                force=args.force,
                dry_run=args.dry_run
            )

    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Interrupted by user.{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.FAIL}Error: {e}{Colors.ENDC}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
