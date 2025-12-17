#!/usr/bin/env python3
"""
main.py - Portfolio Automation Toolkit Orchestrator

Unified CLI interface for all portfolio automation scripts:
- autodeploy: Deploy Flask/PHP projects with systemd and NGINX
- clean: Remove Python cache files
- new: Create new projects from templates
- sync: Git synchronization and backup

Usage:
    python3 main.py <command> [options]
    python3 main.py --help

Examples:
    python3 main.py clean --dry-run
    python3 main.py new python "My API"
    python3 main.py sync --backup
    sudo python3 main.py autodeploy
"""

import argparse
import os
import sys
from pathlib import Path


# === CONFIGURATION ===
SCRIPTS_DIR = Path(__file__).parent / "scripts"
VERSION = "1.0.0"


# === UTILITIES ===
def setup_colors():
    """Terminal color codes."""
    return {
        "R": "\033[91m",
        "G": "\033[92m",
        "Y": "\033[93m",
        "B": "\033[94m",
        "M": "\033[95m",
        "C": "\033[96m",
        "N": "\033[0m",
        "BOLD": "\033[1m"
    }


def log(msg, color="B", colors=None):
    """Print colored log message."""
    if colors is None:
        colors = setup_colors()
    print(f"{colors[color]}{msg}{colors['N']}")


def print_banner():
    """Print toolkit banner."""
    colors = setup_colors()
    banner = f"""
{colors['C']}╔══════════════════════════════════════════════════════════╗
║                                                          ║
║        Portfolio Automation Toolkit v{VERSION}              ║
║        Professional DevOps Tools for Flask & PHP         ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝{colors['N']}
"""
    print(banner)


def run_script(script_name, args):
    """
    Execute a script from the scripts/ directory.

    Args:
        script_name: Name of the script (without .py)
        args: List of arguments to pass to the script

    Returns:
        int: Exit code from the script
    """
    script_path = SCRIPTS_DIR / f"{script_name}.py"

    if not script_path.exists():
        colors = setup_colors()
        log(f"✗ Script not found: {script_path}", "R", colors)
        return 1

    # Import and run the script
    import importlib.util

    try:
        # Load the module
        spec = importlib.util.spec_from_file_location(script_name, script_path)
        module = importlib.util.module_from_spec(spec)

        # Inject arguments into sys.argv for the script's argparse
        sys.argv = [str(script_path)] + args

        # Execute the script
        spec.loader.exec_module(module)

        # Call main() if it exists
        if hasattr(module, 'main'):
            return module.main()
        else:
            return 0

    except SystemExit as e:
        # Catch sys.exit() from the script
        return e.code if e.code else 0

    except Exception as e:
        colors = setup_colors()
        log(f"✗ Error running {script_name}: {e}", "R", colors)
        return 1


# === COMMAND HANDLERS ===
def handle_autodeploy(args):
    """Handle autodeploy command."""
    colors = setup_colors()

    # Check for sudo
    if os.geteuid() != 0:
        log("\n⚠️  autodeploy requires sudo privileges", "Y", colors)
        log("   Run: sudo python3 main.py autodeploy [options]\n", "Y", colors)
        return 1

    return run_script("autodeploy_all", args)


def handle_clean(args):
    """Handle clean command."""
    return run_script("clean_pycache", args)


def handle_new(args):
    """Handle new project command."""
    return run_script("new_project", args)


def handle_sync(args):
    """Handle git sync command."""
    return run_script("git_sync", args)


def handle_status(args):
    """Show portfolio status."""
    colors = setup_colors()
    import subprocess

    log("\n📊 Portfolio Status", "B", colors)
    log("=" * 60, "B", colors)

    # Check projects directory
    projects_dir = Path("/home/gabo/portfolio/projects")
    if projects_dir.exists():
        projects = [p for p in projects_dir.iterdir() if p.is_dir() and not p.name.startswith('.')]
        log(f"\n📦 Projects: {len(projects)}", "C", colors)

        for project in sorted(projects)[:5]:  # Show first 5
            log(f"   • {project.name}", "N", colors)

        if len(projects) > 5:
            log(f"   ... and {len(projects) - 5} more", "Y", colors)
    else:
        log("\n📦 Projects: 0", "Y", colors)

    # Check systemd services
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "portfolio-*", "--no-legend"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            services = [line for line in result.stdout.strip().split('\n') if line]
            log(f"\n🔧 Active Services: {len(services)}", "C", colors)

            for service in services[:5]:  # Show first 5
                parts = service.split()
                if parts:
                    status_icon = "✓" if "running" in service.lower() else "✗"
                    status_color = "G" if "running" in service.lower() else "R"
                    log(f"   {colors[status_color]}{status_icon}{colors['N']} {parts[0]}", "N", colors)

            if len(services) > 5:
                log(f"   ... and {len(services) - 5} more", "Y", colors)
    except Exception:
        log("\n🔧 Active Services: Unable to check (requires sudo)", "Y", colors)

    # Check NGINX
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "nginx"],
            capture_output=True,
            text=True
        )

        nginx_status = result.stdout.strip()
        nginx_color = "G" if nginx_status == "active" else "R"
        nginx_icon = "✓" if nginx_status == "active" else "✗"

        log(f"\n🌐 NGINX: {colors[nginx_color]}{nginx_icon} {nginx_status}{colors['N']}", "N", colors)
    except Exception:
        log("\n🌐 NGINX: Unable to check", "Y", colors)

    # Check backups
    backup_dir = Path.home() / "portfolio_backups"
    if backup_dir.exists():
        backups = list(backup_dir.iterdir())
        log(f"\n💾 Backups: {len(backups)}", "C", colors)

        if backups:
            latest = max(backups, key=lambda x: x.stat().st_mtime)
            import datetime
            mtime = datetime.datetime.fromtimestamp(latest.stat().st_mtime)
            log(f"   Latest: {latest.name}", "N", colors)
            log(f"   Date: {mtime.strftime('%Y-%m-%d %H:%M:%S')}", "N", colors)
    else:
        log(f"\n💾 Backups: 0", "Y", colors)

    log("\n" + "=" * 60, "B", colors)
    return 0


# === MAIN ===
def main():
    """Main entry point for the toolkit."""
    colors = setup_colors()

    # Create main parser
    parser = argparse.ArgumentParser(
        description="Portfolio Automation Toolkit - Professional DevOps Tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  autodeploy    Deploy all projects with systemd and NGINX (requires sudo)
  clean         Remove Python cache files from all projects
  new           Create new project from template
  sync          Git synchronization and backup
  status        Show portfolio status overview

Examples:
  python3 main.py status
  python3 main.py clean --dry-run
  python3 main.py new python "My API" "REST API service"
  python3 main.py sync --backup --verbose
  sudo python3 main.py autodeploy --project portfolio

For command-specific help:
  python3 main.py <command> --help
        """
    )

    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"Portfolio Automation Toolkit v{VERSION}"
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Autodeploy command
    autodeploy_parser = subparsers.add_parser(
        "autodeploy",
        help="Deploy projects with systemd and NGINX (requires sudo)"
    )
    autodeploy_parser.add_argument("--verbose", "-v", action="store_true")
    autodeploy_parser.add_argument("--dry-run", "-d", action="store_true")
    autodeploy_parser.add_argument("--project", "-p", type=str)

    # Clean command
    clean_parser = subparsers.add_parser(
        "clean",
        help="Remove Python cache files"
    )
    clean_parser.add_argument("--dry-run", "-d", action="store_true")
    clean_parser.add_argument("--verbose", "-v", action="store_true")
    clean_parser.add_argument("--path", "-p", type=str)

    # New command
    new_parser = subparsers.add_parser(
        "new",
        help="Create new project from template"
    )
    new_parser.add_argument(
        "type",
        choices=["python", "php", "java"],
        nargs="?",
        help="Project type"
    )
    new_parser.add_argument("name", nargs="?", help="Project name")
    new_parser.add_argument("description", nargs="?", help="Project description")
    new_parser.add_argument("--list-ports", action="store_true")

    # Sync command
    sync_parser = subparsers.add_parser(
        "sync",
        help="Git synchronization and backup"
    )
    sync_parser.add_argument("--dry-run", "-d", action="store_true")
    sync_parser.add_argument("--verbose", "-v", action="store_true")
    sync_parser.add_argument("--backup", "-b", action="store_true")
    sync_parser.add_argument("--message", "-m", type=str)
    sync_parser.add_argument("--project", "-p", type=str)
    sync_parser.add_argument("--update-gitignore", action="store_true")
    sync_parser.add_argument("--cleanup-backups", action="store_true")
    sync_parser.add_argument("--keep-backups", type=int, default=10)

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show portfolio status"
    )

    # Parse arguments
    args = parser.parse_args()

    # Show banner
    if not args.command:
        print_banner()
        parser.print_help()
        return 0

    # Route to command handler
    command_handlers = {
        "autodeploy": handle_autodeploy,
        "clean": handle_clean,
        "new": handle_new,
        "sync": handle_sync,
        "status": handle_status
    }

    if args.command in command_handlers:
        # Extract command-specific args
        command_args = []
        for key, value in vars(args).items():
            if key != "command" and value is not None:
                if isinstance(value, bool):
                    if value:
                        command_args.append(f"--{key.replace('_', '-')}")
                else:
                    command_args.append(f"--{key.replace('_', '-')}")
                    command_args.append(str(value))

        # For positional arguments in 'new' command
        if args.command == "new" and hasattr(args, 'type') and args.type:
            command_args = [args.type]
            if hasattr(args, 'name') and args.name:
                command_args.append(args.name)
            if hasattr(args, 'description') and args.description:
                command_args.append(args.description)
            if hasattr(args, 'list_ports') and args.list_ports:
                command_args.append("--list-ports")

        return command_handlers[args.command](command_args)

    else:
        log(f"✗ Unknown command: {args.command}", "R", colors)
        parser.print_help()
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        colors = setup_colors()
        log("\n\n⚠️  Operation cancelled by user", "Y", colors)
        sys.exit(130)
    except Exception as e:
        colors = setup_colors()
        log(f"\n✗ Unexpected error: {e}", "R", colors)
        sys.exit(1)
