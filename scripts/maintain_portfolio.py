#!/usr/bin/env python3
"""
Portfolio Maintenance Script
=============================
Unified script to maintain all projects in the portfolio:
- Assign sequential ports to all Flask apps
- Update .gitignore files with standard patterns
- Update requirements.txt files consistently
- Clear caches across all projects
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import argparse

# Base directory
PORTFOLIO_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = PORTFOLIO_ROOT / "projects"

# Port assignment configuration
PORT_START = 5001
FIXED_PORTS = {
    "pasanotas": 5002,  # Fixed requirement
}

# Standard .gitignore patterns
GITIGNORE_PATTERNS = """# Byte-compiled / cache
__pycache__/
*.py[cod]
*$py.class

# AI agent files
AGENTS.md
CLAUDE.md
GEMINI.md
.cursorrules
.cursor/
.aider*

# Virtual environment
venv/
.env/
.env.bak/
.venv/
env/

# Flask cache and instance data
instance/
*.db
*.sqlite3
*.sqlite
*.log
*.pid
*.swp

# Environment variables
*.env
.env.*
!.env.example

# OS junk
.DS_Store
Thumbs.db
.AppleDouble
.LSOverride

# Editor / IDE
.vscode/
.idea/
*.iml
*.sublime-project
*.sublime-workspace

# Python packaging
build/
dist/
*.egg-info/

# Backup files
*~
*.bak

# Temporary files
/tmp/
temp/
*.tmp

# Test coverage
.coverage
htmlcov/
.pytest_cache/

# Logs
gunicorn.log
*.log.*
logs/

# System files
*.sock
*.pid

# Cache or compiled static assets
static/css/*.map
static/js/*.map
"""


def get_all_projects() -> List[Path]:
    """Get all project directories (excluding venv, .git, etc.)"""
    excluded = {".git", "venv", "static", "templates", "__pycache__", "node_modules"}
    projects = []

    for item in sorted(PROJECTS_DIR.iterdir()):
        if item.is_dir() and item.name not in excluded and not item.name.startswith("."):
            projects.append(item)

    return projects


def assign_ports() -> Dict[str, int]:
    """Assign sequential ports to all projects"""
    projects = get_all_projects()
    port_assignments = {}

    # Sort projects alphabetically, but ensure fixed ports are respected
    sorted_projects = sorted([p.name for p in projects])

    # Remove fixed port projects from the list
    for proj_name in FIXED_PORTS:
        if proj_name in sorted_projects:
            sorted_projects.remove(proj_name)

    # Assign ports
    current_port = PORT_START

    # First, assign fixed ports
    for proj_name, port in FIXED_PORTS.items():
        port_assignments[proj_name] = port

    # Then assign sequential ports to the rest
    for proj_name in sorted_projects:
        # Skip the port if it's already taken by a fixed assignment
        while current_port in FIXED_PORTS.values():
            current_port += 1

        port_assignments[proj_name] = current_port
        current_port += 1

    return port_assignments


def update_app_ports(dry_run=False):
    """Update all app.py and config.py files with assigned ports"""
    port_assignments = assign_ports()
    projects = get_all_projects()

    print("=" * 70)
    print("PORT ASSIGNMENT")
    print("=" * 70)

    for project in projects:
        proj_name = project.name
        assigned_port = port_assignments.get(proj_name, PORT_START)

        print(f"\n📁 {proj_name:<30} → Port {assigned_port}")

        # Look for app.py and config.py files
        app_files = []

        # Check main app.py
        if (project / "app.py").exists():
            app_files.append(project / "app.py")

        # Check app/app.py (for nested structures)
        if (project / "app" / "app.py").exists():
            app_files.append(project / "app" / "app.py")

        # Check config.py
        if (project / "config.py").exists():
            app_files.append(project / "config.py")

        # Check app/config.py
        if (project / "app" / "config.py").exists():
            app_files.append(project / "app" / "config.py")

        for file_path in app_files:
            if not dry_run:
                update_port_in_file(file_path, assigned_port)
                print(f"   ✓ Updated {file_path.relative_to(PORTFOLIO_ROOT)}")
            else:
                print(f"   • Would update {file_path.relative_to(PORTFOLIO_ROOT)}")

    print("\n" + "=" * 70)
    return port_assignments


def update_port_in_file(file_path: Path, port: int):
    """Update port configuration in a Python file"""
    content = file_path.read_text(encoding='utf-8')
    original_content = content

    # Pattern 1: app.run(..., port=XXXX, ...)
    content = re.sub(
        r'(app\.run\([^)]*port\s*=\s*)\d+',
        rf'\g<1>{port}',
        content
    )

    # Pattern 2: socketio.run(app, ..., port=XXXX, ...)
    content = re.sub(
        r'(socketio\.run\([^)]*port\s*=\s*)\d+',
        rf'\g<1>{port}',
        content
    )

    # Pattern 3: port = int(os.environ.get("PORT", "XXXX")) or port = int(os.environ.get("PORT", XXXX))
    content = re.sub(
        r'(port\s*=\s*int\(os\.environ\.get\(["\']PORT["\']\s*,\s*["\']?)\d+(["\']?\))',
        rf'\g<1>{port}\g<2>',
        content
    )

    # Pattern 4: PORT = XXXX (in config files)
    content = re.sub(
        r'^(\s*PORT\s*=\s*)\d+',
        rf'\g<1>{port}',
        content,
        flags=re.MULTILINE
    )

    # Pattern 5: "PORT": XXXX (in config dictionaries)
    content = re.sub(
        r'(["\']PORT["\']\s*:\s*)\d+',
        rf'\g<1>{port}',
        content
    )

    # Only write if changes were made
    if content != original_content:
        file_path.write_text(content, encoding='utf-8')


def update_gitignore_files(dry_run=False):
    """Update all .gitignore files with standard patterns"""
    projects = get_all_projects()

    print("\n" + "=" * 70)
    print("GITIGNORE UPDATE")
    print("=" * 70)

    for project in projects:
        gitignore_path = project / ".gitignore"

        if not dry_run:
            gitignore_path.write_text(GITIGNORE_PATTERNS.strip() + "\n", encoding='utf-8')
            print(f"✓ Updated {gitignore_path.relative_to(PORTFOLIO_ROOT)}")
        else:
            print(f"• Would update {gitignore_path.relative_to(PORTFOLIO_ROOT)}")

    # Also update root .gitignore
    root_gitignore = PORTFOLIO_ROOT / ".gitignore"
    if not dry_run:
        current_content = root_gitignore.read_text(encoding='utf-8') if root_gitignore.exists() else ""

        # Add AI agent patterns if not present
        ai_patterns = ["AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules", ".cursor/", ".aider*"]
        lines = current_content.splitlines()

        needs_update = False
        for pattern in ai_patterns:
            if pattern not in current_content:
                needs_update = True
                break

        if needs_update:
            # Add a comment and the patterns
            if "# AI agent files" not in current_content:
                lines.insert(0, "# AI agent files")
                for pattern in ai_patterns:
                    if pattern not in current_content:
                        lines.insert(1, pattern)

                root_gitignore.write_text("\n".join(lines) + "\n", encoding='utf-8')
                print(f"✓ Updated {root_gitignore.relative_to(PORTFOLIO_ROOT)}")
    else:
        print(f"• Would update {root_gitignore.relative_to(PORTFOLIO_ROOT)}")

    print("=" * 70)


def update_requirements(dry_run=False):
    """Update all requirements.txt files with consistent versions"""
    projects = get_all_projects()

    print("\n" + "=" * 70)
    print("REQUIREMENTS UPDATE")
    print("=" * 70)

    # Common dependencies with versions
    common_deps = {
        "Flask": "3.0.3",
        "Werkzeug": "3.0.4",
        "Jinja2": "3.1.4",
        "gunicorn": "22.0.0",
        "python-dotenv": "1.0.1",
    }

    for project in projects:
        req_file = project / "requirements.txt"

        if req_file.exists():
            content = req_file.read_text(encoding='utf-8')
            lines = content.splitlines()
            updated_lines = []
            seen_packages = set()

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    updated_lines.append(line)
                    continue

                # Extract package name
                pkg_name = re.split(r'[=<>!]', line)[0].strip()

                # Update if in common deps
                if pkg_name in common_deps:
                    updated_lines.append(f"{pkg_name}=={common_deps[pkg_name]}")
                    seen_packages.add(pkg_name)
                else:
                    updated_lines.append(line)

            # Add missing common deps
            for pkg, version in common_deps.items():
                if pkg not in seen_packages:
                    # Check if package is likely needed
                    if pkg in ["Flask", "Werkzeug", "Jinja2"]:
                        # These are core Flask deps, add them
                        updated_lines.insert(0, f"{pkg}=={version}")

            if not dry_run:
                req_file.write_text("\n".join(updated_lines) + "\n", encoding='utf-8')
                print(f"✓ Updated {req_file.relative_to(PORTFOLIO_ROOT)}")
            else:
                print(f"• Would update {req_file.relative_to(PORTFOLIO_ROOT)}")

    print("=" * 70)


def clear_caches(dry_run=False):
    """Clear all cache files across projects"""
    print("\n" + "=" * 70)
    print("CACHE CLEARING")
    print("=" * 70)

    cache_patterns = [
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo",
        "**/*.log",
        "**/.pytest_cache",
        "**/htmlcov",
        "**/.coverage",
    ]

    cleared_count = 0

    for project in get_all_projects():
        for pattern in cache_patterns:
            for path in project.glob(pattern):
                if path.is_file():
                    if not dry_run:
                        path.unlink()
                        cleared_count += 1
                        print(f"✓ Removed {path.relative_to(PORTFOLIO_ROOT)}")
                    else:
                        cleared_count += 1
                        print(f"• Would remove {path.relative_to(PORTFOLIO_ROOT)}")
                elif path.is_dir():
                    if not dry_run:
                        import shutil
                        shutil.rmtree(path)
                        cleared_count += 1
                        print(f"✓ Removed {path.relative_to(PORTFOLIO_ROOT)}/")
                    else:
                        cleared_count += 1
                        print(f"• Would remove {path.relative_to(PORTFOLIO_ROOT)}/")

    print(f"\n{'Would clear' if dry_run else 'Cleared'} {cleared_count} cache files/directories")
    print("=" * 70)


def show_status():
    """Show current status of all projects"""
    projects = get_all_projects()
    port_assignments = assign_ports()

    print("\n" + "=" * 70)
    print("PORTFOLIO STATUS")
    print("=" * 70)

    print(f"\nTotal projects: {len(projects)}\n")

    for project in projects:
        proj_name = project.name
        assigned_port = port_assignments.get(proj_name, "N/A")

        # Check what files exist
        has_app = (project / "app.py").exists() or (project / "app" / "app.py").exists()
        has_config = (project / "config.py").exists() or (project / "app" / "config.py").exists()
        has_requirements = (project / "requirements.txt").exists()
        has_gitignore = (project / ".gitignore").exists()
        has_readme = (project / "README.md").exists()

        print(f"📁 {proj_name}")
        print(f"   Port: {assigned_port}")
        print(f"   Files: ", end="")
        files = []
        if has_app:
            files.append("app.py")
        if has_config:
            files.append("config.py")
        if has_requirements:
            files.append("requirements.txt")
        if has_gitignore:
            files.append(".gitignore")
        if has_readme:
            files.append("README.md")
        print(", ".join(files) if files else "None")
        print()

    print("=" * 70)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Portfolio Maintenance Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status              # Show current status
  %(prog)s ports               # Update all ports
  %(prog)s gitignore           # Update all .gitignore files
  %(prog)s requirements        # Update all requirements.txt
  %(prog)s clear-cache         # Clear all caches
  %(prog)s all                 # Run all maintenance tasks
  %(prog)s all --dry-run       # Preview all changes
        """
    )

    parser.add_argument(
        "command",
        choices=["status", "ports", "gitignore", "requirements", "clear-cache", "all"],
        help="Command to execute"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )

    args = parser.parse_args()

    print(f"\n{'=' * 70}")
    print(f"PORTFOLIO MAINTENANCE TOOL")
    print(f"{'=' * 70}")

    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be made\n")

    try:
        if args.command == "status":
            show_status()

        elif args.command == "ports":
            update_app_ports(dry_run=args.dry_run)

        elif args.command == "gitignore":
            update_gitignore_files(dry_run=args.dry_run)

        elif args.command == "requirements":
            update_requirements(dry_run=args.dry_run)

        elif args.command == "clear-cache":
            clear_caches(dry_run=args.dry_run)

        elif args.command == "all":
            update_app_ports(dry_run=args.dry_run)
            update_gitignore_files(dry_run=args.dry_run)
            update_requirements(dry_run=args.dry_run)
            clear_caches(dry_run=args.dry_run)

            if not args.dry_run:
                print("\n✅ All maintenance tasks completed successfully!")
            else:
                print("\n✅ Dry run completed. Use without --dry-run to apply changes.")

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
