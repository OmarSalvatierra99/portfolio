#!/usr/bin/env python3
"""
git_sync.py - Automated Git synchronization and backup

Features:
- Auto-commit with timestamps
- Safe force-push with --force-with-lease
- Automatic .gitignore updates
- Backup creation before operations
- Dry-run mode for safety
- Multi-project support
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# === CONFIGURATION ===
ROOT = Path("/home/gabo/portfolio")
PROJECTS_DIR = ROOT / "projects"
BACKUP_DIR = Path.home() / "portfolio_backups"

GITIGNORE_CONTENT = """# Python cache
__pycache__/
*.py[cod]
*$py.class

# AI agents
AGENTS.md
CLAUDE.md
GEMINI.md
.cursorrules
.cursor/
.aider*
*.aider*
*.gemini*
*.claude*

# Virtual env
venv/
.venv/
env/
.env/

# Environment variables
.env
.env.*
!.env.example

# Flask
instance/
*.db
*.sqlite*
*.log
*.pid

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.sublime-*

# Build
build/
dist/
*.egg-info/

# Test
.coverage
htmlcov/
.pytest_cache/

# Temp
tmp/
temp/
*.tmp
*~
*.bak

# Logs
logs/
*.log
"""


# === UTILITIES ===
def setup_colors():
    """Terminal color codes."""
    return {
        "R": "\033[91m",
        "G": "\033[92m",
        "Y": "\033[93m",
        "B": "\033[94m",
        "N": "\033[0m"
    }


def log(msg, color="B", colors=None):
    """Print colored log message."""
    if colors is None:
        colors = setup_colors()
    print(f"{colors[color]}{msg}{colors['N']}")


def run_command(cmd, cwd=None, check=False):
    """Execute shell command and return result."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=check
    )


def get_all_projects():
    """
    Get list of all project paths (root + projects/*).

    Returns:
        list: Paths to all projects
    """
    projects = [ROOT]

    if PROJECTS_DIR.exists():
        for item in PROJECTS_DIR.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                projects.append(item)

    return projects


def is_git_repo(path):
    """Check if path is a git repository."""
    return (path / ".git").exists()


# === BACKUP OPERATIONS ===
def create_backup(project_path, dry_run=False, verbose=False):
    """
    Create timestamped backup of project.

    Args:
        project_path: Path to project
        dry_run: If True, only show what would be backed up
        verbose: Show detailed output

    Returns:
        str: Backup path or None
    """
    colors = setup_colors()

    if not project_path.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{project_path.name}_{timestamp}"
    backup_path = BACKUP_DIR / backup_name

    if dry_run:
        if verbose:
            log(f"  [Would backup] {project_path.name} -> {backup_path}", "Y", colors)
        return str(backup_path)

    # Create backup directory
    BACKUP_DIR.mkdir(exist_ok=True)

    # Copy project (excluding venv and cache)
    def ignore_patterns(dir, files):
        """Patterns to ignore during backup."""
        return {
            f for f in files
            if f in ['venv', '.venv', '__pycache__', 'node_modules', '.git']
            or f.endswith('.pyc')
            or f.endswith('.log')
        }

    try:
        shutil.copytree(
            project_path,
            backup_path,
            ignore=ignore_patterns,
            symlinks=False
        )

        if verbose:
            log(f"  [Backed up] {project_path.name} -> {backup_path}", "G", colors)

        return str(backup_path)

    except Exception as e:
        log(f"  ✗ Backup failed for {project_path.name}: {e}", "R", colors)
        return None


def cleanup_old_backups(keep=10, dry_run=False, verbose=False):
    """
    Remove old backups, keeping only the most recent.

    Args:
        keep: Number of backups to keep per project
        dry_run: If True, only show what would be deleted
        verbose: Show detailed output

    Returns:
        int: Number of backups removed
    """
    colors = setup_colors()

    if not BACKUP_DIR.exists():
        return 0

    # Group backups by project
    backups_by_project = {}

    for backup in BACKUP_DIR.iterdir():
        if backup.is_dir():
            # Extract project name (before timestamp)
            parts = backup.name.rsplit('_', 2)
            if len(parts) >= 3:
                project_name = parts[0]
                if project_name not in backups_by_project:
                    backups_by_project[project_name] = []
                backups_by_project[project_name].append(backup)

    # Remove old backups
    removed_count = 0

    for project_name, backups in backups_by_project.items():
        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Remove old backups
        for backup in backups[keep:]:
            if dry_run:
                if verbose:
                    log(f"  [Would delete] {backup.name}", "Y", colors)
                removed_count += 1
            else:
                try:
                    shutil.rmtree(backup)
                    if verbose:
                        log(f"  [Deleted] {backup.name}", "Y", colors)
                    removed_count += 1
                except Exception as e:
                    log(f"  ✗ Failed to delete {backup.name}: {e}", "R", colors)

    return removed_count


# === GITIGNORE MANAGEMENT ===
def update_gitignore(project_path, dry_run=False):
    """
    Ensure .gitignore is up to date.

    Args:
        project_path: Path to project
        dry_run: If True, only check without updating

    Returns:
        bool: True if updated/needed update
    """
    colors = setup_colors()
    gitignore_path = project_path / ".gitignore"

    # Check if update needed
    needs_update = False

    if not gitignore_path.exists():
        needs_update = True
    else:
        current_content = gitignore_path.read_text()
        if "CLAUDE.md" not in current_content:
            needs_update = True

    if not needs_update:
        return False

    if dry_run:
        log(f"  [Would update] .gitignore in {project_path.name}", "Y", colors)
        return True

    # Update .gitignore
    gitignore_path.write_text(GITIGNORE_CONTENT)
    log(f"  ✓ Updated .gitignore in {project_path.name}", "G", colors)
    return True


# === GIT OPERATIONS ===
def git_status(project_path):
    """
    Get git status for project.

    Args:
        project_path: Path to project

    Returns:
        dict: Status information
    """
    if not is_git_repo(project_path):
        return {"is_repo": False}

    # Check for changes
    status_result = run_command(["git", "status", "--porcelain"], cwd=project_path)
    has_changes = bool(status_result.stdout.strip())

    # Get current branch
    branch_result = run_command(["git", "branch", "--show-current"], cwd=project_path)
    current_branch = branch_result.stdout.strip()

    # Check remote status
    run_command(["git", "fetch"], cwd=project_path)
    ahead_behind = run_command([
        "git", "rev-list", "--left-right", "--count",
        f"HEAD...origin/{current_branch}"
    ], cwd=project_path)

    ahead, behind = 0, 0
    if ahead_behind.returncode == 0 and ahead_behind.stdout.strip():
        parts = ahead_behind.stdout.strip().split()
        if len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])

    return {
        "is_repo": True,
        "has_changes": has_changes,
        "branch": current_branch,
        "ahead": ahead,
        "behind": behind
    }


def git_commit_and_push(project_path, message=None, dry_run=False, verbose=False):
    """
    Commit changes and push to remote.

    Args:
        project_path: Path to project
        message: Commit message (auto-generated if None)
        dry_run: If True, only show what would be done
        verbose: Show detailed output

    Returns:
        str: Status message
    """
    colors = setup_colors()

    if not is_git_repo(project_path):
        log(f"  ⚠ Not a git repository: {project_path.name}", "Y", colors)
        return "not-a-repo"

    # Get status
    status = git_status(project_path)

    if not status["has_changes"] and status["ahead"] == 0:
        if verbose:
            log(f"  → No changes in {project_path.name}", "Y", colors)
        return "no-changes"

    if dry_run:
        if status["has_changes"]:
            log(f"  [Would commit] Changes in {project_path.name}", "Y", colors)
        if status["ahead"] > 0 or status["has_changes"]:
            log(f"  [Would push] {project_path.name}", "Y", colors)
        return "dry-run"

    # Add all changes
    if status["has_changes"]:
        run_command(["git", "add", "."], cwd=project_path)

        # Generate commit message
        if not message:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"Auto-sync: {timestamp}"

        # Commit
        commit_result = run_command(
            ["git", "commit", "-m", message],
            cwd=project_path
        )

        if commit_result.returncode != 0:
            if "nothing to commit" in commit_result.stdout:
                if verbose:
                    log(f"  → Nothing to commit in {project_path.name}", "Y", colors)
            else:
                log(f"  ✗ Commit failed for {project_path.name}", "R", colors)
                if verbose:
                    log(f"    {commit_result.stderr}", "R", colors)
                return "commit-failed"
        else:
            if verbose:
                log(f"  ✓ Committed changes in {project_path.name}", "G", colors)

    # Push to remote
    push_result = run_command(
        ["git", "push", "--force-with-lease", "origin", "HEAD"],
        cwd=project_path
    )

    if push_result.returncode == 0:
        log(f"  ✓ Pushed {project_path.name} to remote", "G", colors)
        return "success"
    else:
        log(f"  ✗ Push failed for {project_path.name}", "R", colors)
        if verbose:
            log(f"    {push_result.stderr}", "R", colors)
        return "push-failed"


# === MAIN OPERATIONS ===
def sync_project(project_path, args):
    """
    Sync a single project with git remote.

    Args:
        project_path: Path to project
        args: Parsed command-line arguments

    Returns:
        tuple: (project_name, status)
    """
    colors = setup_colors()
    project_name = project_path.name

    log(f"\n{'━' * 60}", "B", colors)
    log(f"📦 {project_name}", "B", colors)

    # Create backup if requested
    if args.backup:
        create_backup(project_path, args.dry_run, args.verbose)

    # Update .gitignore if requested
    if args.update_gitignore:
        update_gitignore(project_path, args.dry_run)

    # Sync with git
    status = git_commit_and_push(
        project_path,
        args.message,
        args.dry_run,
        args.verbose
    )

    return (project_name, status)


def main():
    """Main entry point for git_sync script."""
    parser = argparse.ArgumentParser(
        description="Automated Git synchronization and backup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Sync all projects
  %(prog)s --dry-run                    # Preview without changes
  %(prog)s --backup                     # Create backups before sync
  %(prog)s --project portfolio          # Sync specific project
  %(prog)s --message "Feature update"   # Custom commit message
  %(prog)s --update-gitignore           # Update .gitignore files
  %(prog)s --cleanup-backups            # Remove old backups (keep 10)
        """
    )

    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Show what would be done without making changes"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )

    parser.add_argument(
        "--backup", "-b",
        action="store_true",
        help="Create backup before syncing"
    )

    parser.add_argument(
        "--message", "-m",
        type=str,
        help="Custom commit message (default: auto-generated)"
    )

    parser.add_argument(
        "--project", "-p",
        type=str,
        help="Sync only specific project by name"
    )

    parser.add_argument(
        "--update-gitignore",
        action="store_true",
        help="Update .gitignore files to latest template"
    )

    parser.add_argument(
        "--cleanup-backups",
        action="store_true",
        help="Clean up old backups (keeps 10 most recent per project)"
    )

    parser.add_argument(
        "--keep-backups",
        type=int,
        default=10,
        help="Number of backups to keep when cleaning up (default: 10)"
    )

    args = parser.parse_args()
    colors = setup_colors()

    # Start
    log("🚀 Git Sync & Backup Tool", "B", colors)
    log("=" * 60, "B", colors)

    if args.dry_run:
        log("💡 DRY RUN MODE - No changes will be made\n", "Y", colors)

    # Cleanup backups if requested
    if args.cleanup_backups:
        log("\n🗑️  Cleaning up old backups...", "B", colors)
        removed = cleanup_old_backups(
            args.keep_backups,
            args.dry_run,
            args.verbose
        )
        log(f"  ✓ Removed {removed} old backups", "G", colors)

    # Get projects to sync
    projects = get_all_projects()

    if args.project:
        # Filter for specific project
        projects = [p for p in projects if p.name == args.project]
        if not projects:
            # Try to find in projects directory
            specific_path = PROJECTS_DIR / args.project
            if specific_path.exists():
                projects = [specific_path]
            else:
                log(f"✗ Project not found: {args.project}", "R", colors)
                return 1

    # Sync each project
    report = []
    for project_path in projects:
        result = sync_project(project_path, args)
        report.append(result)

    # Print report
    log(f"\n{'=' * 60}", "B", colors)
    log("📋 SYNC REPORT", "B", colors)
    log("=" * 60, "B", colors)

    for name, status in report:
        if status == "success":
            color = "G"
            icon = "✓"
        elif status in ["no-changes", "not-a-repo", "dry-run"]:
            color = "Y"
            icon = "→"
        else:
            color = "R"
            icon = "✗"

        print(f"{colors[color]}{icon} {name:<25} {status}{colors['N']}")

    log("=" * 60, "B", colors)

    if args.dry_run:
        log("\n💡 Dry run complete. Use without --dry-run to sync.", "Y", colors)
    else:
        log("\n✅ Sync complete!", "G", colors)

    return 0


if __name__ == "__main__":
    sys.exit(main())
