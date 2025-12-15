#!/usr/bin/env python3
"""
Unified VPS Deployment Script for Flask Portfolio
===================================================
Automatically deploys, updates, and maintains all Flask projects on Arch Linux VPS.

Features:
- Automatic project discovery from /home/gabo/portfolio/projects/
- Sequential port assignment (pasanotas always gets 5002)
- Virtualenv setup and dependency installation
- Systemd service creation and management
- Nginx configuration with VPS IP (not localhost)
- Removes default Nginx server blocks
- Idempotent and re-runnable
- Validates all configs before applying

Usage:
    sudo python3 /home/gabo/portfolio/scripts/deploy_vps.py
"""

import os
import sys
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Tuple
import argparse

# =============================================================================
# CONFIGURATION
# =============================================================================

# VPS Configuration
VPS_IP = "31.97.8.56"  # Your VPS public IP
PORTFOLIO_ROOT = Path("/home/gabo/portfolio")
PROJECTS_DIR = PORTFOLIO_ROOT / "projects"

# Port Configuration
PORT_MAIN_PORTFOLIO = 5000
PORT_START = 5001
FIXED_PORTS = {
    "pasanotas": 5002,  # Fixed requirement
}

# Domain Mappings
DOMAIN_MAP = {
    "auditel.omar-xyz.shop": "auditel",
    "cleandoc.omar-xyz.shop": "cleandoc",
    "lexnum.omar-xyz.shop": "lexnum",
    "obsidian-vps.omar-xyz.shop": "obsidian-vps",
    "pasanotas.omar-xyz.shop": "pasanotas",
    "sasp.omar-xyz.shop": "sasp",
    "actas.omar-xyz.shop": "scan-actas-nacimiento",
    "sifet-estatales.omar-xyz.shop": "sifet-estatales",
    "siif.omar-xyz.shop": "siif",
}

# Projects to skip
SKIP_PROJECTS = {"sasp-php"}

# System directories
SYSTEMD_DIR = Path("/etc/systemd/system")
NGINX_AVAILABLE = Path("/etc/nginx/sites-available")
NGINX_ENABLED = Path("/etc/nginx/sites-enabled")
NGINX_CONF = Path("/etc/nginx/nginx.conf")


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def log_section(title: str):
    """Print a section header."""
    print(f"\n{'='*70}")
    print(f"{title}")
    print(f"{'='*70}")


def log_info(msg: str, indent: int = 0):
    """Print an info message."""
    prefix = "   " * indent
    print(f"{prefix}• {msg}")


def log_success(msg: str, indent: int = 0):
    """Print a success message."""
    prefix = "   " * indent
    print(f"{prefix}✓ {msg}")


def log_warning(msg: str, indent: int = 0):
    """Print a warning message."""
    prefix = "   " * indent
    print(f"{prefix}⚠️  {msg}")


def log_error(msg: str, indent: int = 0):
    """Print an error message."""
    prefix = "   " * indent
    print(f"{prefix}❌ {msg}")


def log_skip(msg: str, indent: int = 0):
    """Print a skip message."""
    prefix = "   " * indent
    print(f"{prefix}⏭️  {msg}")


def check_root():
    """Ensure script is run as root."""
    if os.geteuid() != 0:
        log_error("This script must be run as root")
        print("   Run with: sudo python3 scripts/deploy_vps.py")
        sys.exit(1)


def get_system_user() -> str:
    """Get the user who invoked sudo (or current user)."""
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user:
        return sudo_user

    # Fallback to checking ownership of portfolio directory
    try:
        import pwd
        stat_info = os.stat(PORTFOLIO_ROOT)
        return pwd.getpwuid(stat_info.st_uid).pw_name
    except:
        return "gabo"  # Fallback to your username


def run_command(cmd: List[str], check: bool = True, capture: bool = True,
                timeout: int = 30, cwd: str = None) -> subprocess.CompletedProcess:
    """Run a shell command with error handling."""
    try:
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture,
            text=True,
            timeout=timeout,
            cwd=cwd
        )
        return result
    except subprocess.CalledProcessError as e:
        if not check:
            return e
        raise
    except subprocess.TimeoutExpired as e:
        log_error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        raise


# =============================================================================
# PROJECT DISCOVERY
# =============================================================================

def discover_projects() -> List[str]:
    """Discover all Flask projects in projects/ directory."""
    log_section("🔍 DISCOVERING PROJECTS")

    if not PROJECTS_DIR.exists():
        log_error(f"Projects directory not found: {PROJECTS_DIR}")
        sys.exit(1)

    projects = []
    for item in sorted(PROJECTS_DIR.iterdir()):
        if not item.is_dir():
            continue

        project_name = item.name

        # Skip excluded projects
        if project_name in SKIP_PROJECTS:
            log_skip(f"Skipping {project_name} (in SKIP_PROJECTS)")
            continue

        # Skip hidden directories
        if project_name.startswith('.'):
            continue

        # Verify it's a Flask project (has app.py)
        app_py = item / "app.py"
        if not app_py.exists():
            log_warning(f"Skipping {project_name}: no app.py found")
            continue

        # Warn if venv is missing (we'll create it)
        venv_dir = item / "venv"
        if not venv_dir.exists():
            log_info(f"Found {project_name} (venv will be created)")
        else:
            log_success(f"Found {project_name}")

        projects.append(project_name)

    log_info(f"Total projects discovered: {len(projects)}")
    return projects


def assign_ports(projects: List[str]) -> Dict[str, int]:
    """Assign stable sequential ports to projects."""
    port_map = {}
    current_port = PORT_START

    # Sort projects for deterministic assignment
    sorted_projects = sorted(projects)

    for project in sorted_projects:
        # Check if project has a fixed port
        if project in FIXED_PORTS:
            port_map[project] = FIXED_PORTS[project]
        else:
            # Skip ports that are already assigned
            while current_port in FIXED_PORTS.values() or current_port in port_map.values():
                current_port += 1
            port_map[project] = current_port
            current_port += 1

    return port_map


def get_domain_for_project(project: str) -> str:
    """Get domain name for a project."""
    for domain, proj in DOMAIN_MAP.items():
        if proj == project:
            return domain
    # Fallback if not in map
    return f"{project}.omar-xyz.shop"


# =============================================================================
# VIRTUALENV SETUP
# =============================================================================

def setup_virtualenv(project: str, project_path: Path, user: str) -> bool:
    """
    Setup project's virtualenv: create if needed, upgrade pip, install deps, ensure gunicorn.
    Returns True if setup succeeded, False otherwise.
    """
    log_info(f"Setting up virtualenv for {project}...", indent=1)

    venv_path = project_path / "venv"
    python_bin = venv_path / "bin" / "python"
    pip_bin = venv_path / "bin" / "pip"
    gunicorn_bin = venv_path / "bin" / "gunicorn"
    requirements_file = project_path / "requirements.txt"

    # Step 1: Create venv if it doesn't exist
    if not venv_path.exists():
        log_info("Creating virtualenv...", indent=2)
        try:
            run_command(
                ["sudo", "-u", user, "python3", "-m", "venv", str(venv_path)],
                cwd=str(project_path)
            )
            log_success("Created virtualenv", indent=2)
        except subprocess.CalledProcessError as e:
            log_error(f"Failed to create virtualenv: {e.stderr}", indent=2)
            return False
    else:
        log_success("Virtualenv already exists", indent=2)

    # Verify python exists
    if not python_bin.exists():
        log_error(f"Python not found in virtualenv: {python_bin}", indent=2)
        return False

    # Step 2: Upgrade pip, setuptools, wheel
    log_info("Upgrading pip, setuptools, wheel...", indent=2)
    try:
        run_command(
            ["sudo", "-u", user, str(pip_bin), "install", "--upgrade",
             "pip", "setuptools", "wheel"],
            cwd=str(project_path),
            timeout=120
        )
        log_success("Upgraded pip tools", indent=2)
    except subprocess.CalledProcessError as e:
        log_warning(f"Failed to upgrade pip tools (continuing anyway)", indent=2)

    # Step 3: Install requirements.txt if present
    if requirements_file.exists():
        log_info("Installing dependencies from requirements.txt...", indent=2)
        try:
            run_command(
                ["sudo", "-u", user, str(pip_bin), "install", "-r", str(requirements_file)],
                cwd=str(project_path),
                timeout=300
            )
            log_success("Installed dependencies", indent=2)
        except subprocess.CalledProcessError as e:
            log_warning(f"Some dependencies may have failed to install", indent=2)
            # Continue anyway - gunicorn might still install
    else:
        log_info("No requirements.txt found, skipping", indent=2)

    # Step 4: Ensure gunicorn is installed
    if not gunicorn_bin.exists():
        log_info("Installing gunicorn...", indent=2)
        try:
            run_command(
                ["sudo", "-u", user, str(pip_bin), "install", "gunicorn"],
                cwd=str(project_path),
                timeout=60
            )
            log_success("Installed gunicorn", indent=2)
        except subprocess.CalledProcessError as e:
            log_error(f"Failed to install gunicorn: {e.stderr}", indent=2)
            return False
    else:
        log_success("Gunicorn already installed", indent=2)

    # Step 5: Verify gunicorn is executable
    if not os.access(gunicorn_bin, os.X_OK):
        log_error(f"Gunicorn exists but is not executable: {gunicorn_bin}", indent=2)
        return False

    # Test gunicorn
    try:
        result = run_command(
            ["sudo", "-u", user, str(gunicorn_bin), "--version"],
            timeout=5
        )
        version = result.stdout.strip()
        log_success(f"Gunicorn is executable: {version}", indent=2)
    except Exception as e:
        log_error(f"Gunicorn test failed: {e}", indent=2)
        return False

    return True


def validate_flask_app(project_path: Path, user: str) -> bool:
    """
    Validate that the Flask app can be imported (app:app exists).
    Returns True if valid, False otherwise.
    """
    venv_python = project_path / "venv" / "bin" / "python"

    if not venv_python.exists():
        log_warning("Cannot validate Flask app: virtualenv not found", indent=2)
        return True  # Skip validation if venv doesn't exist yet

    # Test import of Flask app
    test_script = f"""
import sys
sys.path.insert(0, '{project_path}')
try:
    from app import app
    if app is None:
        sys.exit(1)
    if not hasattr(app, '__call__'):
        sys.exit(1)
    print('OK')
    sys.exit(0)
except ImportError as e:
    print(f'ImportError: {{e}}')
    sys.exit(1)
except Exception as e:
    print(f'Error: {{e}}')
    sys.exit(1)
"""

    try:
        result = run_command(
            ["sudo", "-u", user, str(venv_python), "-c", test_script],
            cwd=str(project_path),
            timeout=10
        )

        if result.returncode == 0 and "OK" in result.stdout:
            log_success("Flask app validation passed (app:app is importable)", indent=2)
            return True
        else:
            log_error("Flask app validation failed!", indent=2)
            log_error("Cannot import 'app' from app.py or 'app' is not a Flask application", indent=2)
            if result.stderr:
                log_error(f"Error: {result.stderr.strip()[:200]}", indent=2)
            return False

    except subprocess.TimeoutExpired:
        log_warning("Flask app validation timed out", indent=2)
        return False
    except Exception as e:
        log_warning(f"Flask app validation error: {e}", indent=2)
        return False


# =============================================================================
# NGINX CONFIGURATION
# =============================================================================

def fix_nginx_main_config():
    """
    Fix Nginx main configuration to ensure sites-enabled is included.
    """
    log_section("🔧 CONFIGURING NGINX")

    if not NGINX_CONF.exists():
        log_warning(f"Nginx config not found: {NGINX_CONF}")
        return False

    # Read current config
    try:
        with open(NGINX_CONF, 'r') as f:
            config_content = f.read()
    except Exception as e:
        log_error(f"Failed to read nginx.conf: {e}")
        return False

    # Check if settings already exist
    has_types_hash_max_size = re.search(r'^\s*types_hash_max_size\s+\d+;', config_content, re.MULTILINE)
    has_types_hash_bucket_size = re.search(r'^\s*types_hash_bucket_size\s+\d+;', config_content, re.MULTILINE)
    has_sites_enabled_include = re.search(r'^\s*include\s+/etc/nginx/sites-enabled/\*;', config_content, re.MULTILINE)

    if has_types_hash_max_size and has_types_hash_bucket_size and has_sites_enabled_include:
        log_success("Nginx configuration already correct")
        return True

    # Find the http block
    http_block_match = re.search(r'(http\s*\{)', config_content)

    if not http_block_match:
        log_warning("Could not find http block in nginx.conf")
        return False

    # Prepare settings to add
    settings_to_add = []

    if not has_sites_enabled_include:
        settings_to_add.append("    # Include all enabled sites")
        settings_to_add.append("    include /etc/nginx/sites-enabled/*;")
        log_info("Adding sites-enabled include directive")

    if not has_types_hash_max_size:
        settings_to_add.append("    types_hash_max_size 2048;")
    if not has_types_hash_bucket_size:
        settings_to_add.append("    types_hash_bucket_size 128;")

    if not settings_to_add:
        log_success("Nginx configuration already correct")
        return True

    # Insert settings after the http { line
    insert_pos = http_block_match.end()
    settings_text = "\n" + "\n".join(settings_to_add)
    new_config = config_content[:insert_pos] + settings_text + config_content[insert_pos:]

    # Backup original config
    backup_path = NGINX_CONF.with_suffix('.conf.backup')
    try:
        with open(backup_path, 'w') as f:
            f.write(config_content)
        log_success(f"Backed up nginx.conf to {backup_path}")
    except Exception as e:
        log_warning(f"Could not create backup: {e}")

    # Write new config
    try:
        with open(NGINX_CONF, 'w') as f:
            f.write(new_config)
        log_success("Updated nginx.conf with required settings")
    except Exception as e:
        log_error(f"Failed to write nginx.conf: {e}")
        return False

    # Validate config
    log_info("Validating Nginx configuration...")
    result = run_command(["nginx", "-t"], check=False)

    if result.returncode != 0:
        log_error("Nginx configuration validation failed!")
        print(result.stderr)

        # Restore backup
        log_info("Restoring backup...")
        try:
            with open(backup_path, 'r') as f:
                backup_content = f.read()
            with open(NGINX_CONF, 'w') as f:
                f.write(backup_content)
            log_success("Restored original configuration")
        except Exception as e:
            log_error(f"Failed to restore backup: {e}")

        return False

    log_success("Nginx configuration is valid")
    return True


def remove_default_nginx_sites():
    """
    Remove default Nginx server blocks and site configs.
    """
    log_info("Removing default Nginx sites...")

    # Remove default enabled site
    default_enabled = NGINX_ENABLED / "default"
    if default_enabled.exists() or default_enabled.is_symlink():
        try:
            default_enabled.unlink()
            log_success("Disabled default Nginx site", indent=1)
        except Exception as e:
            log_warning(f"Could not remove default site: {e}", indent=1)

    # Remove default server block from nginx.conf
    try:
        with open(NGINX_CONF, 'r') as f:
            lines = f.readlines()

        # Find and comment out the default server block
        in_server_block = False
        in_http_block = False
        brace_count = 0
        modified = False
        new_lines = []

        for line in lines:
            # Track http block
            if re.match(r'^\s*http\s*\{', line):
                in_http_block = True

            # Detect server block start inside http block
            if in_http_block and re.match(r'^\s*server\s*\{', line):
                in_server_block = True
                brace_count = 1
                # Comment out the line
                if not line.strip().startswith('#'):
                    new_lines.append('#' + line)
                    modified = True
                else:
                    new_lines.append(line)
                continue

            # Inside server block - comment out all lines
            if in_server_block:
                # Count braces to find block end
                brace_count += line.count('{')
                brace_count -= line.count('}')

                # Comment out the line
                if not line.strip().startswith('#'):
                    new_lines.append('#' + line)
                    modified = True
                else:
                    new_lines.append(line)

                # Check if block ended
                if brace_count == 0:
                    in_server_block = False
                continue

            # Track end of http block
            if in_http_block and line.strip() == '}':
                in_http_block = False

            new_lines.append(line)

        if modified:
            # Backup and write
            backup_path = NGINX_CONF.with_suffix('.conf.backup-default')
            with open(backup_path, 'w') as f:
                f.writelines(lines)

            with open(NGINX_CONF, 'w') as f:
                f.writelines(new_lines)

            # Validate
            result = run_command(["nginx", "-t"], check=False)
            if result.returncode != 0:
                log_error("Nginx validation failed after removing default server", indent=1)
                # Restore backup
                with open(backup_path, 'r') as f:
                    with open(NGINX_CONF, 'w') as out:
                        out.write(f.read())
                log_success("Restored original nginx.conf", indent=1)
                return False

            log_success("Removed default server block from nginx.conf", indent=1)
        else:
            log_info("No default server block found (already removed)", indent=1)

    except Exception as e:
        log_error(f"Failed to modify nginx.conf: {e}", indent=1)
        return False

    return True


def create_nginx_config_content(project: str, port: int, domain: str, is_main: bool = False) -> str:
    """
    Create Nginx configuration content.
    CRITICAL: Uses VPS_IP instead of 127.0.0.1 for proxy_pass.
    """
    if is_main:
        # Main portfolio gets default_server
        server_line = f"    listen 80 default_server;"
        server_name = f"{domain} www.{domain}"
    else:
        server_line = f"    listen 80;"
        server_name = domain

    nginx_content = f"""server {{
{server_line}
    server_name {server_name};

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header Referrer-Policy strict-origin-when-cross-origin;

    # Max upload size
    client_max_body_size 10M;

    location / {{
        proxy_pass http://{VPS_IP}:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}

    # Static files
    location /static {{
        proxy_pass http://{VPS_IP}:{port};
    }}
}}
"""
    return nginx_content


def create_systemd_service_content(project: str, port: int, project_path: Path, user: str) -> str:
    """Create systemd service file content."""
    venv_gunicorn = project_path / "venv" / "bin" / "gunicorn"

    service_content = f"""[Unit]
Description={project} Portfolio Flask Application
After=network.target

[Service]
Type=notify
User={user}
Group={user}
WorkingDirectory={project_path}
Environment="PATH={project_path}/venv/bin"
Environment="PORT={port}"
ExecStart={venv_gunicorn} --bind 0.0.0.0:{port} --workers 2 --timeout 120 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    return service_content


def write_file_if_changed(path: Path, content: str) -> bool:
    """
    Write content to file only if it differs from current content.
    Returns True if file was written (changed), False otherwise.
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Check if content is different
    changed = False
    if path.exists():
        with open(path, 'r') as f:
            existing = f.read()
        if existing != content:
            changed = True
    else:
        changed = True

    # Write if changed
    if changed:
        with open(path, 'w') as f:
            f.write(content)

        # Verify file was written
        if not path.exists():
            raise FileNotFoundError(f"Failed to write file: {path}")

    return changed


# =============================================================================
# DEPLOYMENT
# =============================================================================

def deploy_main_portfolio(user: str) -> Tuple[bool, bool]:
    """Deploy the main portfolio application."""
    log_section("📦 DEPLOYING MAIN PORTFOLIO")

    domain = "omar-xyz.shop"
    port = PORT_MAIN_PORTFOLIO

    log_info(f"Domain: {domain}")
    log_info(f"Port: {port}")

    # Setup virtualenv
    if not setup_virtualenv("portfolio", PORTFOLIO_ROOT, user):
        log_error("Failed to setup virtualenv for main portfolio")
        log_warning("Skipping service creation - fix virtualenv issues first")
        return False, False

    # Validate Flask app
    if not validate_flask_app(PORTFOLIO_ROOT, user):
        log_error("Flask app validation failed for main portfolio")
        log_warning("Skipping service creation - fix Flask app:app import issues first")
        return False, False

    # Create systemd service
    service_name = "portfolio-main"
    service_file = SYSTEMD_DIR / f"{service_name}.service"
    service_content = create_systemd_service_content("portfolio", port, PORTFOLIO_ROOT, user)
    service_changed = write_file_if_changed(service_file, service_content)

    if service_changed:
        log_success(f"Created/updated systemd service: {service_name}")
    else:
        log_info(f"Service unchanged: {service_name}")

    # Create Nginx config
    nginx_available = NGINX_AVAILABLE / "portfolio"
    nginx_enabled = NGINX_ENABLED / "portfolio"
    nginx_content = create_nginx_config_content("portfolio", port, domain, is_main=True)

    # Write config file
    nginx_changed = write_file_if_changed(nginx_available, nginx_content)

    if nginx_changed:
        log_success(f"Created/updated Nginx config: portfolio")
    else:
        log_info(f"Nginx config unchanged: portfolio")

    # Verify config file exists
    if not nginx_available.exists():
        raise FileNotFoundError(f"Nginx config file not found: {nginx_available}")

    # Create or update symlink
    if nginx_enabled.exists() or nginx_enabled.is_symlink():
        nginx_enabled.unlink()
    nginx_enabled.symlink_to(nginx_available)
    log_success(f"Enabled Nginx site: portfolio")

    return service_changed, nginx_changed


def deploy_project(project: str, port: int, user: str) -> Tuple[bool, bool]:
    """
    Deploy a single project.
    Returns (service_changed, nginx_changed).
    """
    log_section(f"📦 DEPLOYING {project.upper()}")

    domain = get_domain_for_project(project)
    project_path = PROJECTS_DIR / project

    log_info(f"Domain: {domain}")
    log_info(f"Port: {port}")

    # Setup virtualenv
    if not setup_virtualenv(project, project_path, user):
        log_error(f"Failed to setup virtualenv for {project}")
        log_warning("Skipping service creation - fix virtualenv issues first")
        return False, False

    # Validate Flask app
    if not validate_flask_app(project_path, user):
        log_error(f"Flask app validation failed for {project}")
        log_warning("Skipping service creation - fix Flask app:app import issues first")
        return False, False

    # Create systemd service
    service_name = f"portfolio-{project}"
    service_file = SYSTEMD_DIR / f"{service_name}.service"
    service_content = create_systemd_service_content(project, port, project_path, user)
    service_changed = write_file_if_changed(service_file, service_content)

    if service_changed:
        log_success(f"Created/updated systemd service: {service_name}")
    else:
        log_info(f"Service unchanged: {service_name}")

    # Create Nginx config
    nginx_available = NGINX_AVAILABLE / project
    nginx_enabled = NGINX_ENABLED / project
    nginx_content = create_nginx_config_content(project, port, domain, is_main=False)

    # Write config file
    nginx_changed = write_file_if_changed(nginx_available, nginx_content)

    if nginx_changed:
        log_success(f"Created/updated Nginx config: {project}")
    else:
        log_info(f"Nginx config unchanged: {project}")

    # Verify config file exists
    if not nginx_available.exists():
        raise FileNotFoundError(f"Nginx config file not found: {nginx_available}")

    # Create or update symlink
    if nginx_enabled.exists() or nginx_enabled.is_symlink():
        nginx_enabled.unlink()
    nginx_enabled.symlink_to(nginx_available)
    log_success(f"Enabled Nginx site: {project}")

    return service_changed, nginx_changed


# =============================================================================
# SERVICE MANAGEMENT
# =============================================================================

def reload_services(service_changed: bool, nginx_changed: bool):
    """Reload systemd and Nginx if needed."""
    log_section("🔄 RELOADING SERVICES")

    if service_changed:
        log_info("Reloading systemd daemon...")
        run_command(["systemctl", "daemon-reload"])
        log_success("Systemd reloaded")

    if nginx_changed:
        log_info("Testing Nginx configuration...")
        result = run_command(["nginx", "-t"], check=False)
        if result.returncode != 0:
            log_error("Nginx configuration test failed:")
            print(result.stderr)
            return False

        log_info("Reloading Nginx...")
        run_command(["systemctl", "reload", "nginx"])
        log_success("Nginx reloaded")

    if not service_changed and not nginx_changed:
        log_info("No changes detected, skipping reload")

    return True


def start_services(projects: List[str], include_main: bool = True):
    """Enable and start all project services."""
    log_section("🚀 STARTING SERVICES")

    # Start main portfolio first
    if include_main:
        service_name = "portfolio-main"
        run_command(["systemctl", "enable", service_name], check=False)
        result = run_command(["systemctl", "restart", service_name], check=False)
        if result.returncode == 0:
            log_success(f"Started {service_name}")
        else:
            log_warning(f"Failed to start {service_name}")
            if result.stderr:
                print(f"      {result.stderr.strip()}")

    # Start individual projects
    for project in projects:
        service_name = f"portfolio-{project}"

        # Enable service
        run_command(["systemctl", "enable", service_name], check=False)

        # Restart service
        result = run_command(["systemctl", "restart", service_name], check=False)

        if result.returncode == 0:
            log_success(f"Started {service_name}")
        else:
            log_warning(f"Failed to start {service_name}")
            if result.stderr:
                print(f"      {result.stderr.strip()}")


def show_status(projects: List[str], port_map: Dict[str, int], include_main: bool = True):
    """Show deployment status."""
    log_section("📊 DEPLOYMENT SUMMARY")

    print(f"{'Project':<25} {'Domain':<30} {'Port':<6} {'Status'}")
    print("-"*70)

    # Show main portfolio first
    if include_main:
        service_name = "portfolio-main"
        result = run_command(
            ["systemctl", "is-active", service_name],
            check=False
        )
        status = "🟢" if result.stdout.strip() == "active" else "🔴"
        print(f"{'portfolio (main)':<25} {'omar-xyz.shop':<30} {PORT_MAIN_PORTFOLIO:<6} {status}")

    # Show individual projects
    for project in sorted(projects):
        domain = get_domain_for_project(project)
        port = port_map[project]
        service_name = f"portfolio-{project}"

        # Check service status
        result = run_command(
            ["systemctl", "is-active", service_name],
            check=False
        )
        status = "🟢" if result.stdout.strip() == "active" else "🔴"

        print(f"{project:<25} {domain:<30} {port:<6} {status}")

    print("="*70)


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main deployment flow."""
    print("\n🚀 VPS Deployment Script for Flask Portfolio")
    log_section("CONFIGURATION")

    # Check root privileges
    check_root()

    log_info(f"Portfolio root: {PORTFOLIO_ROOT}")
    log_info(f"VPS IP: {VPS_IP}")
    log_info(f"Main portfolio port: {PORT_MAIN_PORTFOLIO}")

    # Get system user
    user = get_system_user()
    log_info(f"Running services as: {user}")

    # Discover projects
    projects = discover_projects()

    if not projects:
        log_error("No projects found to deploy")
        sys.exit(1)

    # Assign ports
    port_map = assign_ports(projects)
    log_section("PORT ASSIGNMENTS")
    log_info(f"portfolio (main): {PORT_MAIN_PORTFOLIO}")
    for project in sorted(projects):
        log_info(f"{project}: {port_map[project]}")

    # Fix Nginx configuration
    fix_nginx_main_config()

    # Remove default Nginx sites
    remove_default_nginx_sites()

    # Deploy main portfolio
    service_changed, nginx_changed = deploy_main_portfolio(user)
    any_service_changed = service_changed
    any_nginx_changed = nginx_changed

    # Deploy each project
    for project in projects:
        port = port_map[project]
        service_changed, nginx_changed = deploy_project(project, port, user)
        any_service_changed = any_service_changed or service_changed
        any_nginx_changed = any_nginx_changed or nginx_changed

    # Reload services if needed
    if any_service_changed or any_nginx_changed:
        if not reload_services(any_service_changed, any_nginx_changed):
            log_error("Service reload failed")
            sys.exit(1)

    # Start/restart services
    start_services(projects, include_main=True)

    # Show final status
    show_status(projects, port_map, include_main=True)

    log_section("✅ DEPLOYMENT COMPLETE")
    print("\n💡 Useful commands:")
    print(f"   • Check logs: journalctl -u portfolio-<project> -f")
    print(f"   • Restart service: systemctl restart portfolio-<project>")
    print(f"   • Check Nginx: nginx -t")
    print(f"   • Reload Nginx: systemctl reload nginx")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
