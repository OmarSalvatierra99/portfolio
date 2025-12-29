#!/usr/bin/env python3
"""
clean_pycache.py - Clean Python cache files and AI agent instruction files

Removes all __pycache__ directories, compiled Python files (.pyc, .pyo),
and AI agent instruction files (AGENTS.md, CLAUDE.md, GEMINI.md) from the
portfolio and all projects. Supports dry-run mode for safe previewing.
"""

import argparse
import shutil
import sys
from pathlib import Path


def setup_colors():
    """Terminal color codes for output formatting."""
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


def clean_python_cache(root_dir, dry_run=False, verbose=False):
    """
    Recursively clean Python cache files.

    Args:
        root_dir: Root directory to start cleaning from
        dry_run: If True, only show what would be deleted
        verbose: If True, show detailed output

    Returns:
        Tuple of (directories_removed, files_removed)
    """
    colors = setup_colors()
    root = Path(root_dir)

    if not root.exists():
        log(f"✗ Directory not found: {root}", "R", colors)
        return 0, 0

    dir_count = 0
    file_count = 0

    # Patterns to clean
    cache_patterns = [
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo",
        "**/*$py.class"
    ]

    # AI agent instruction files to clean
    ai_files = ["AGENTS.md", "CLAUDE.md", "GEMINI.md"]

    log(f"{'🔍 DRY RUN' if dry_run else '🧹 CLEANING'}: {root}", "B", colors)

    # Clean Python cache files
    for pattern in cache_patterns:
        for item in root.glob(pattern):
            try:
                if item.is_dir():
                    if dry_run:
                        if verbose:
                            log(f"  [Would delete dir] {item}", "Y", colors)
                        dir_count += 1
                    else:
                        if verbose:
                            log(f"  [Deleting dir] {item}", "Y", colors)
                        shutil.rmtree(item)
                        dir_count += 1
                elif item.is_file():
                    if dry_run:
                        if verbose:
                            log(f"  [Would delete file] {item}", "Y", colors)
                        file_count += 1
                    else:
                        if verbose:
                            log(f"  [Deleting file] {item}", "Y", colors)
                        item.unlink()
                        file_count += 1
            except Exception as e:
                log(f"  ✗ Error processing {item}: {e}", "R", colors)

    # Clean AI agent instruction files
    for filename in ai_files:
        ai_file = root / filename
        if ai_file.exists() and ai_file.is_file():
            try:
                if dry_run:
                    if verbose:
                        log(f"  [Would delete file] {ai_file}", "Y", colors)
                    file_count += 1
                else:
                    if verbose:
                        log(f"  [Deleting file] {ai_file}", "Y", colors)
                    ai_file.unlink()
                    file_count += 1
            except Exception as e:
                log(f"  ✗ Error processing {ai_file}: {e}", "R", colors)

    return dir_count, file_count


def main():
    """Main entry point for clean_pycache script."""
    parser = argparse.ArgumentParser(
        description="Clean Python cache files and AI agent instruction files from portfolio projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Clean all cache and AI instruction files
  %(prog)s --dry-run                # Preview what would be deleted
  %(prog)s --verbose                # Show detailed output
  %(prog)s --path /custom/path      # Clean specific directory
        """
    )

    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output for each file/directory"
    )

    parser.add_argument(
        "--path", "-p",
        type=str,
        default="/home/gabo/portfolio",
        help="Root directory to clean (default: /home/gabo/portfolio)"
    )

    args = parser.parse_args()
    colors = setup_colors()

    # Clean main directory
    log("🚀 Python Cache Cleaner", "B", colors)
    log(f"{'=' * 60}", "B", colors)

    main_dirs, main_files = clean_python_cache(
        args.path,
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    # Clean projects directory
    projects_dir = Path(args.path) / "projects"
    proj_dirs = 0
    proj_files = 0

    if projects_dir.exists():
        for project in projects_dir.iterdir():
            if project.is_dir() and not project.name.startswith("."):
                d, f = clean_python_cache(
                    project,
                    dry_run=args.dry_run,
                    verbose=args.verbose
                )
                proj_dirs += d
                proj_files += f

    # Summary
    total_dirs = main_dirs + proj_dirs
    total_files = main_files + proj_files

    log(f"\n{'=' * 60}", "B", colors)
    log(f"📊 Summary:", "B", colors)
    log(f"  Directories: {total_dirs}", "G" if total_dirs > 0 else "Y", colors)
    log(f"  Files: {total_files}", "G" if total_files > 0 else "Y", colors)

    if args.dry_run:
        log("\n💡 This was a dry run. Use without --dry-run to actually delete.", "Y", colors)
    else:
        log(f"\n✅ Cleanup {'completed' if total_dirs + total_files > 0 else 'complete (nothing to clean)'}!", "G", colors)

    return 0


if __name__ == "__main__":
    sys.exit(main())
