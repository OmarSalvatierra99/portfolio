#!/usr/bin/env python3
"""
Portfolio Deployment Script
Automatically creates systemd services and Nginx configs for all Flask projects.
Must be run as root.
"""

import os
import sys
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Domain to project mappings
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

# Fixed port assignments
FIXED_PORTS = {
    "pasanotas": 5002
}

# Starting port for sequential assignment
START_PORT = 5001


def check_root():
    """Ensure script is run as root."""
    if os.geteuid() != 0:
        print("❌ This script must be run as root")
        print("   Run with: sudo python3 scripts/deploy_all.py")
        sys.exit(1)


def get_portfolio_root() -> Path:
    """Get portfolio root directory."""
    return Path.cwd().resolve()


def discover_projects(portfolio_root: Path) -> List[str]:
    """Discover all Flask projects in projects/ directory."""
    projects_dir = portfolio_root / "projects"

    if not projects_dir.exists():
        print(f"❌ Projects directory not found: {projects_dir}")
        sys.exit(1)

    projects = []
    for item in sorted(projects_dir.iterdir()):
        if not item.is_dir():
            continue

        project_name = item.name

        # Skip excluded projects
        if project_name in SKIP_PROJECTS:
            print(f"⏭️  Skipping {project_name}")
            continue

        # Skip hidden directories
        if project_name.startswith('.'):
            continue

        # Verify it's a Flask project (has app.py and venv)
        app_py = item / "app.py"
        venv_dir = item / "venv"

        if not app_py.exists():
            print(f"⚠️  Skipping {project_name}: no app.py found")
            continue

        if not venv_dir.exists():
            print(f"⚠️  Warning: {project_name} missing venv - service may fail")

        projects.append(project_name)

    return projects


def assign_ports(projects: List[str]) -> Dict[str, int]:
    """Assign stable sequential ports to projects."""
    port_map = {}
    current_port = START_PORT

    # Sort projects for deterministic assignment
    sorted_projects = sorted(projects)

    for project in sorted_projects:
        # Check if project has a fixed port
        if project in FIXED_PORTS:
            port_map[project] = FIXED_PORTS[project]
        else:
            # Assign next available port
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


def get_system_user() -> str:
    """Get the user who invoked sudo (or current user if not sudo)."""
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user:
        return sudo_user

    # Fallback to checking ownership of portfolio directory
    portfolio_root = get_portfolio_root()
    try:
        import pwd
        stat_info = os.stat(portfolio_root)
        return pwd.getpwuid(stat_info.st_uid).pw_name
    except:
        return "www-data"


def validate_flask_app(project_path: Path, user: str) -> bool:
    """
    Validate that the Flask app can be imported (app:app exists).
    Returns True if valid, False otherwise.
    """
    venv_python = project_path / "venv" / "bin" / "python"

    if not venv_python.exists():
        print(f"   ⚠️  Cannot validate Flask app: virtualenv not found")
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
        result = subprocess.run(
            ["sudo", "-u", user, str(venv_python), "-c", test_script],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(project_path)
        )

        if result.returncode == 0 and "OK" in result.stdout:
            print(f"   ✓ Flask app validation passed (app:app is importable)")
            return True
        else:
            print(f"   ❌ Flask app validation failed!")
            print(f"      Cannot import 'app' from app.py or 'app' is not a Flask application")
            if result.stderr:
                print(f"      Error: {result.stderr.strip()[:200]}")
            if result.stdout and "OK" not in result.stdout:
                print(f"      Output: {result.stdout.strip()[:200]}")
            return False

    except subprocess.TimeoutExpired:
        print(f"   ⚠️  Flask app validation timed out")
        return False
    except Exception as e:
        print(f"   ⚠️  Flask app validation error: {e}")
        return False


def setup_project_venv(project: str, project_path: Path, user: str) -> bool:
    """
    Setup project's virtualenv: upgrade pip/setuptools/wheel, install dependencies, ensure gunicorn.
    Returns True if setup succeeded, False otherwise.
    """
    print(f"   🔧 Setting up virtualenv for {project}...")

    venv_path = project_path / "venv"
    python_bin = venv_path / "bin" / "python"
    pip_bin = venv_path / "bin" / "pip"
    gunicorn_bin = venv_path / "bin" / "gunicorn"
    requirements_file = project_path / "requirements.txt"

    # Check if venv exists
    if not venv_path.exists():
        print(f"   ⚠️  No virtualenv found at {venv_path}")
        print(f"   ⚠️  Creating virtualenv for {project}...")
        try:
            # Run as the actual user, not root
            subprocess.run(
                ["sudo", "-u", user, "python3", "-m", "venv", str(venv_path)],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"   ✓ Created virtualenv")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to create virtualenv: {e.stderr}")
            return False

    # Verify python exists
    if not python_bin.exists():
        print(f"   ❌ Python not found in virtualenv: {python_bin}")
        return False

    # Step 1: Upgrade pip, setuptools, wheel
    print(f"   • Upgrading pip, setuptools, wheel...")
    try:
        subprocess.run(
            ["sudo", "-u", user, str(pip_bin), "install", "--upgrade", "pip", "setuptools", "wheel"],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(project_path)
        )
        print(f"   ✓ Upgraded pip, setuptools, wheel")
    except subprocess.CalledProcessError as e:
        print(f"   ⚠️  Warning: Failed to upgrade pip tools: {e.stderr.strip()[:100]}")
        # Continue anyway - not critical

    # Step 2: Install requirements.txt if present
    if requirements_file.exists():
        print(f"   • Installing dependencies from requirements.txt...")
        try:
            subprocess.run(
                ["sudo", "-u", user, str(pip_bin), "install", "-r", str(requirements_file)],
                check=True,
                capture_output=True,
                text=True,
                cwd=str(project_path)
            )
            print(f"   ✓ Installed dependencies")
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️  Warning: Some dependencies may have failed to install")
            print(f"      {e.stderr.strip()[:200]}")
            # Continue anyway - gunicorn might still install
    else:
        print(f"   • No requirements.txt found, skipping")

    # Step 3: Ensure gunicorn is installed
    if not gunicorn_bin.exists():
        print(f"   • Gunicorn not found, installing...")
        try:
            subprocess.run(
                ["sudo", "-u", user, str(pip_bin), "install", "gunicorn"],
                check=True,
                capture_output=True,
                text=True,
                cwd=str(project_path)
            )
            print(f"   ✓ Installed gunicorn")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to install gunicorn: {e.stderr}")
            return False
    else:
        print(f"   ✓ Gunicorn already installed")

    # Step 4: Verify gunicorn is executable
    if not os.access(gunicorn_bin, os.X_OK):
        print(f"   ❌ Gunicorn exists but is not executable: {gunicorn_bin}")
        return False

    # Test gunicorn
    try:
        result = subprocess.run(
            ["sudo", "-u", user, str(gunicorn_bin), "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"   ✓ Gunicorn is executable: {result.stdout.strip()}")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"   ❌ Gunicorn test failed: {e}")
        return False

    return True


def setup_main_portfolio_venv(portfolio_root: Path, user: str) -> bool:
    """Setup main portfolio's virtualenv."""
    print(f"   🔧 Setting up main portfolio virtualenv...")

    venv_path = portfolio_root / "venv"
    python_bin = venv_path / "bin" / "python"
    pip_bin = venv_path / "bin" / "pip"
    gunicorn_bin = venv_path / "bin" / "gunicorn"
    requirements_file = portfolio_root / "requirements.txt"

    # Check if venv exists
    if not venv_path.exists():
        print(f"   ⚠️  No virtualenv found at {venv_path}")
        print(f"   ⚠️  Creating virtualenv for main portfolio...")
        try:
            subprocess.run(
                ["sudo", "-u", user, "python3", "-m", "venv", str(venv_path)],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"   ✓ Created virtualenv")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to create virtualenv: {e.stderr}")
            return False

    # Verify python exists
    if not python_bin.exists():
        print(f"   ❌ Python not found in virtualenv: {python_bin}")
        return False

    # Upgrade pip, setuptools, wheel
    print(f"   • Upgrading pip, setuptools, wheel...")
    try:
        subprocess.run(
            ["sudo", "-u", user, str(pip_bin), "install", "--upgrade", "pip", "setuptools", "wheel"],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(portfolio_root)
        )
        print(f"   ✓ Upgraded pip tools")
    except subprocess.CalledProcessError as e:
        print(f"   ⚠️  Warning: Failed to upgrade pip tools")

    # Install requirements.txt
    if requirements_file.exists():
        print(f"   • Installing dependencies from requirements.txt...")
        try:
            subprocess.run(
                ["sudo", "-u", user, str(pip_bin), "install", "-r", str(requirements_file)],
                check=True,
                capture_output=True,
                text=True,
                cwd=str(portfolio_root)
            )
            print(f"   ✓ Installed dependencies")
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️  Warning: Some dependencies may have failed to install")

    # Ensure gunicorn is installed
    if not gunicorn_bin.exists():
        print(f"   • Installing gunicorn...")
        try:
            subprocess.run(
                ["sudo", "-u", user, str(pip_bin), "install", "gunicorn"],
                check=True,
                capture_output=True,
                text=True,
                cwd=str(portfolio_root)
            )
            print(f"   ✓ Installed gunicorn")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to install gunicorn: {e.stderr}")
            return False
    else:
        print(f"   ✓ Gunicorn already installed")

    # Verify gunicorn is executable
    if not os.access(gunicorn_bin, os.X_OK):
        print(f"   ❌ Gunicorn not executable: {gunicorn_bin}")
        return False

    # Test gunicorn
    try:
        result = subprocess.run(
            ["sudo", "-u", user, str(gunicorn_bin), "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"   ✓ Gunicorn is executable: {result.stdout.strip()}")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"   ❌ Gunicorn test failed: {e}")
        return False

    return True


def fix_nginx_config():
    """
    Fix Nginx configuration to ensure sites-enabled is included and settings are correct.
    This function ensures:
    1. include /etc/nginx/sites-enabled/*; is present in http block
    2. types_hash settings are configured
    3. Configuration is validated before applying
    """
    print("\n🔧 Checking Nginx configuration...")

    nginx_conf = Path("/etc/nginx/nginx.conf")

    if not nginx_conf.exists():
        print(f"   ⚠️  Nginx config not found: {nginx_conf}")
        return False

    # Read current config
    try:
        with open(nginx_conf, 'r') as f:
            config_content = f.read()
    except Exception as e:
        print(f"   ❌ Failed to read nginx.conf: {e}")
        return False

    # Check if settings already exist
    has_types_hash_max_size = re.search(r'^\s*types_hash_max_size\s+\d+;', config_content, re.MULTILINE)
    has_types_hash_bucket_size = re.search(r'^\s*types_hash_bucket_size\s+\d+;', config_content, re.MULTILINE)
    has_sites_enabled_include = re.search(r'^\s*include\s+/etc/nginx/sites-enabled/\*;', config_content, re.MULTILINE)

    if has_types_hash_max_size and has_types_hash_bucket_size and has_sites_enabled_include:
        print(f"   ✓ Nginx configuration already correct")
        return True

    # Find the http block
    http_block_match = re.search(r'(http\s*\{)', config_content)

    if not http_block_match:
        print(f"   ⚠️  Could not find http block in nginx.conf")
        return False

    # Prepare settings to add
    settings_to_add = []

    if not has_sites_enabled_include:
        settings_to_add.append("    # Include all enabled sites")
        settings_to_add.append("    include /etc/nginx/sites-enabled/*;")
        print(f"   • Adding sites-enabled include directive")

    if not has_types_hash_max_size:
        settings_to_add.append("    types_hash_max_size 2048;")
    if not has_types_hash_bucket_size:
        settings_to_add.append("    types_hash_bucket_size 128;")

    if not settings_to_add:
        print(f"   ✓ Nginx configuration already correct")
        return True

    # Insert settings after the http { line
    insert_pos = http_block_match.end()
    settings_text = "\n" + "\n".join(settings_to_add)

    new_config = config_content[:insert_pos] + settings_text + config_content[insert_pos:]

    # Backup original config
    backup_path = nginx_conf.with_suffix('.conf.backup')
    try:
        with open(backup_path, 'w') as f:
            f.write(config_content)
        print(f"   ✓ Backed up nginx.conf to {backup_path}")
    except Exception as e:
        print(f"   ⚠️  Warning: Could not create backup: {e}")

    # Write new config
    try:
        with open(nginx_conf, 'w') as f:
            f.write(new_config)
        print(f"   ✓ Updated nginx.conf with required settings")
    except Exception as e:
        print(f"   ❌ Failed to write nginx.conf: {e}")
        return False

    # Validate config
    print(f"   • Validating Nginx configuration...")
    result = subprocess.run(["nginx", "-t"], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"   ❌ Nginx configuration validation failed!")
        print(result.stderr)

        # Restore backup
        print(f"   • Restoring backup...")
        try:
            with open(backup_path, 'r') as f:
                backup_content = f.read()
            with open(nginx_conf, 'w') as f:
                f.write(backup_content)
            print(f"   ✓ Restored original configuration")
        except Exception as e:
            print(f"   ❌ Failed to restore backup: {e}")

        return False

    print(f"   ✓ Nginx configuration is valid")
    return True


def disable_default_nginx_site():
    """
    Disable the default Nginx site that shows 'Welcome to nginx'.
    This ensures custom sites are served instead of the default page.
    """
    print("\n🔧 Checking default Nginx site...")

    default_enabled = Path("/etc/nginx/sites-enabled/default")

    if default_enabled.exists() or default_enabled.is_symlink():
        try:
            default_enabled.unlink()
            print(f"   ✓ Disabled default Nginx site")
            return True
        except Exception as e:
            print(f"   ⚠️  Warning: Could not remove default site: {e}")
            return False
    else:
        print(f"   • Default site already disabled")
        return False


def remove_default_nginx_server():
    """
    Remove the default server block from nginx.conf that shows 'Welcome to nginx'.
    This block conflicts with custom vhosts and must be removed.
    """
    print("\n🔧 Removing default server block from nginx.conf...")

    nginx_conf = Path("/etc/nginx/nginx.conf")

    if not nginx_conf.exists():
        print(f"   ⚠️  nginx.conf not found")
        return False

    try:
        with open(nginx_conf, 'r') as f:
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
                # Check if this closes the http block (simplified detection)
                in_http_block = False

            new_lines.append(line)

        if modified:
            # Backup original
            backup_path = nginx_conf.with_suffix('.conf.backup-default')
            with open(backup_path, 'w') as f:
                f.writelines(lines)
            print(f"   ✓ Backed up nginx.conf to {backup_path}")

            # Write modified config
            with open(nginx_conf, 'w') as f:
                f.writelines(new_lines)

            # Validate
            result = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"   ❌ Nginx validation failed after removing default server")
                print(result.stderr)
                # Restore backup
                with open(backup_path, 'r') as f:
                    with open(nginx_conf, 'w') as out:
                        out.write(f.read())
                print(f"   ✓ Restored original nginx.conf")
                return False

            print(f"   ✓ Removed default server block from nginx.conf")
            return True
        else:
            print(f"   • No default server block found (already removed)")
            return False

    except Exception as e:
        print(f"   ❌ Failed to modify nginx.conf: {e}")
        return False


def verify_nginx_symlinks(projects: List[str], include_main: bool = True):
    """
    Verify all Nginx site symlinks are valid and point to existing config files.
    Returns True if all symlinks are valid, False otherwise.
    """
    print("\n🔍 Verifying Nginx symlinks...")

    all_valid = True
    sites_to_check = []

    # Add main portfolio
    if include_main:
        sites_to_check.append("portfolio")

    # Add all projects
    sites_to_check.extend(projects)

    for site in sites_to_check:
        available = Path(f"/etc/nginx/sites-available/{site}")
        enabled = Path(f"/etc/nginx/sites-enabled/{site}")

        # Check if config file exists in sites-available
        if not available.exists():
            print(f"   ❌ Missing config: {site} (sites-available)")
            all_valid = False
            continue

        # Check if symlink exists in sites-enabled
        if not enabled.exists() and not enabled.is_symlink():
            print(f"   ❌ Missing symlink: {site} (sites-enabled)")
            all_valid = False
            continue

        # Check if symlink points to the correct file
        if enabled.is_symlink():
            target = enabled.resolve()
            if target != available.resolve():
                print(f"   ⚠️  Incorrect symlink target: {site}")
                print(f"      Expected: {available}")
                print(f"      Got: {target}")
                all_valid = False
                continue

        print(f"   ✓ Valid: {site}")

    if all_valid:
        print(f"   ✓ All symlinks are valid")
    else:
        print(f"   ⚠️  Some symlinks have issues - re-running deployment may fix this")

    return all_valid


def create_systemd_service(project: str, port: int, portfolio_root: Path, user: str) -> str:
    """Create systemd service file content."""
    project_path = portfolio_root / "projects" / project
    venv_python = project_path / "venv" / "bin" / "python"
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


def create_nginx_config(project: str, port: int, domain: str) -> str:
    """Create Nginx configuration content."""
    nginx_content = f"""server {{
    listen 80;
    server_name {domain};

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header Referrer-Policy strict-origin-when-cross-origin;

    # Max upload size
    client_max_body_size 10M;

    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}

    # Static files (if needed)
    location /static {{
        proxy_pass http://127.0.0.1:{port};
    }}
}}
"""
    return nginx_content


def write_file(path: Path, content: str) -> bool:
    """Write content to file, return True if changed. Ensures parent directories exist."""
    changed = False

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        with open(path, 'r') as f:
            existing = f.read()
        if existing != content:
            changed = True
    else:
        changed = True

    if changed:
        with open(path, 'w') as f:
            f.write(content)

        # Verify file was written
        if not path.exists():
            raise FileNotFoundError(f"Failed to write file: {path}")

    return changed


def deploy_portfolio_main(portfolio_root: Path, user: str) -> Tuple[bool, bool]:
    """Deploy the main portfolio application on omar-xyz.shop:5000."""
    domain = "omar-xyz.shop"
    port = 5000
    service_name = "portfolio-main"

    print(f"\n📦 Deploying Main Portfolio")
    print(f"   Domain: {domain}")
    print(f"   Port: {port}")

    # Setup virtualenv first
    if not setup_main_portfolio_venv(portfolio_root, user):
        print(f"   ❌ Failed to setup virtualenv for main portfolio")
        print(f"   ⚠️  Skipping service creation - fix virtualenv issues first")
        return False, False

    # Validate Flask app can be imported
    if not validate_flask_app(portfolio_root, user):
        print(f"   ❌ Flask app validation failed for main portfolio")
        print(f"   ⚠️  Skipping service creation - fix Flask app:app import issues first")
        return False, False

    # Create systemd service for main portfolio
    service_file = Path(f"/etc/systemd/system/{service_name}.service")
    venv_python = portfolio_root / "venv" / "bin" / "python"
    venv_gunicorn = portfolio_root / "venv" / "bin" / "gunicorn"

    service_content = f"""[Unit]
Description=Main Portfolio Flask Application
After=network.target

[Service]
Type=notify
User={user}
Group={user}
WorkingDirectory={portfolio_root}
Environment="PATH={portfolio_root}/venv/bin"
Environment="PORT={port}"
ExecStart={venv_gunicorn} --bind 0.0.0.0:{port} --workers 4 --timeout 120 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    service_changed = write_file(service_file, service_content)

    if service_changed:
        print(f"   ✓ Created/updated systemd service: {service_name}")
    else:
        print(f"   • Service unchanged: {service_name}")

    # Create Nginx config for main portfolio
    nginx_available = Path(f"/etc/nginx/sites-available/portfolio")
    nginx_enabled = Path(f"/etc/nginx/sites-enabled/portfolio")

    nginx_content = f"""server {{
    listen 80 default_server;
    server_name {domain} www.{domain};

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header Referrer-Policy strict-origin-when-cross-origin;

    # Max upload size
    client_max_body_size 10M;

    location / {{
        proxy_pass http://127.0.0.1:{port};
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
        alias {portfolio_root}/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }}
}}
"""

    # Ensure sites-enabled directory exists
    nginx_enabled.parent.mkdir(parents=True, exist_ok=True)

    # Write config file first
    nginx_changed = write_file(nginx_available, nginx_content)

    if nginx_changed:
        print(f"   ✓ Created/updated Nginx config: portfolio")
    else:
        print(f"   • Nginx config unchanged: portfolio")

    # Verify config file exists before creating symlink
    if not nginx_available.exists():
        raise FileNotFoundError(f"Nginx config file not found: {nginx_available}")

    # Create or update symlink
    if nginx_enabled.exists() or nginx_enabled.is_symlink():
        nginx_enabled.unlink()
        print(f"   • Removed old symlink: portfolio")

    nginx_enabled.symlink_to(nginx_available)
    print(f"   ✓ Enabled Nginx site: portfolio")

    return service_changed, nginx_changed


def deploy_project(project: str, port: int, portfolio_root: Path, user: str) -> Tuple[bool, bool]:
    """Deploy a single project. Returns (service_changed, nginx_changed)."""
    domain = get_domain_for_project(project)
    project_path = portfolio_root / "projects" / project

    print(f"\n📦 Deploying {project}")
    print(f"   Domain: {domain}")
    print(f"   Port: {port}")

    # Setup virtualenv first
    if not setup_project_venv(project, project_path, user):
        print(f"   ❌ Failed to setup virtualenv for {project}")
        print(f"   ⚠️  Skipping service creation - fix virtualenv issues first")
        return False, False

    # Validate Flask app can be imported
    if not validate_flask_app(project_path, user):
        print(f"   ❌ Flask app validation failed for {project}")
        print(f"   ⚠️  Skipping service creation - fix Flask app:app import issues first")
        return False, False

    # Create systemd service
    service_name = f"portfolio-{project}"
    service_file = Path(f"/etc/systemd/system/{service_name}.service")
    service_content = create_systemd_service(project, port, portfolio_root, user)
    service_changed = write_file(service_file, service_content)

    if service_changed:
        print(f"   ✓ Created/updated systemd service: {service_name}")
    else:
        print(f"   • Service unchanged: {service_name}")

    # Create Nginx config (CRITICAL: Write file BEFORE creating symlink)
    nginx_available = Path(f"/etc/nginx/sites-available/{project}")
    nginx_enabled = Path(f"/etc/nginx/sites-enabled/{project}")
    nginx_content = create_nginx_config(project, port, domain)

    # Ensure sites-enabled directory exists
    nginx_enabled.parent.mkdir(parents=True, exist_ok=True)

    # Write config file first
    nginx_changed = write_file(nginx_available, nginx_content)

    if nginx_changed:
        print(f"   ✓ Created/updated Nginx config: {project}")
    else:
        print(f"   • Nginx config unchanged: {project}")

    # Verify config file exists before creating symlink
    if not nginx_available.exists():
        raise FileNotFoundError(f"Nginx config file not found: {nginx_available}")

    # Create or update symlink (remove old symlink first if it exists)
    if nginx_enabled.exists() or nginx_enabled.is_symlink():
        nginx_enabled.unlink()
        print(f"   • Removed old symlink: {project}")

    nginx_enabled.symlink_to(nginx_available)
    print(f"   ✓ Enabled Nginx site: {project}")

    return service_changed, nginx_changed


def reload_services(service_changed: bool, nginx_changed: bool):
    """Reload systemd and Nginx if needed."""
    print("\n🔄 Reloading services...")

    if service_changed:
        print("   • Reloading systemd daemon...")
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        print("   ✓ Systemd reloaded")

    if nginx_changed:
        print("   • Testing Nginx configuration...")
        result = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
        if result.returncode != 0:
            print("   ❌ Nginx configuration test failed:")
            print(result.stderr)
            return False

        print("   • Reloading Nginx...")
        subprocess.run(["systemctl", "reload", "nginx"], check=True)
        print("   ✓ Nginx reloaded")

    return True


def start_services(projects: List[str], include_main: bool = True):
    """Enable and start all project services."""
    print("\n🚀 Starting services...")

    # Start main portfolio first
    if include_main:
        service_name = "portfolio-main"
        subprocess.run(["systemctl", "enable", service_name],
                      capture_output=True, check=False)
        result = subprocess.run(["systemctl", "restart", service_name],
                               capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✓ Started {service_name}")
        else:
            print(f"   ⚠️  Failed to start {service_name}")
            print(f"      {result.stderr.strip()}")

    # Start individual projects
    for project in projects:
        service_name = f"portfolio-{project}"

        # Enable service
        subprocess.run(["systemctl", "enable", service_name],
                      capture_output=True, check=False)

        # Restart service
        result = subprocess.run(["systemctl", "restart", service_name],
                               capture_output=True, text=True)

        if result.returncode == 0:
            print(f"   ✓ Started {service_name}")
        else:
            print(f"   ⚠️  Failed to start {service_name}")
            print(f"      {result.stderr.strip()}")


def show_status(projects: List[str], port_map: Dict[str, int], include_main: bool = True):
    """Show deployment status."""
    print("\n" + "="*70)
    print("📊 DEPLOYMENT SUMMARY")
    print("="*70)
    print(f"{'Project':<25} {'Domain':<30} {'Port':<6} {'Status'}")
    print("-"*70)

    # Show main portfolio first
    if include_main:
        service_name = "portfolio-main"
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True
        )
        status = "🟢" if result.stdout.strip() == "active" else "🔴"
        print(f"{'portfolio (main)':<25} {'omar-xyz.shop':<30} {'5000':<6} {status}")

    # Show individual projects
    for project in sorted(projects):
        domain = get_domain_for_project(project)
        port = port_map[project]
        service_name = f"portfolio-{project}"

        # Check service status
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True
        )
        status = "🟢" if result.stdout.strip() == "active" else "🔴"

        print(f"{project:<25} {domain:<30} {port:<6} {status}")

    print("="*70)


def main():
    """Main deployment flow."""
    print("🚀 Portfolio Deployment Script")
    print("="*70)

    # Check root privileges
    check_root()

    # Get portfolio root
    portfolio_root = get_portfolio_root()
    print(f"📁 Portfolio root: {portfolio_root}")

    # Get system user
    user = get_system_user()
    print(f"👤 Running services as: {user}")

    # Discover projects
    projects = discover_projects(portfolio_root)
    print(f"\n✓ Found {len(projects)} Flask projects")

    if not projects:
        print("❌ No projects found to deploy")
        sys.exit(1)

    # Assign ports
    port_map = assign_ports(projects)
    print("\n📍 Port assignments:")
    print(f"   portfolio (main): 5000")
    for project in sorted(projects):
        print(f"   {project}: {port_map[project]}")

    # Fix Nginx configuration first
    fix_nginx_config()

    # Remove default server block from nginx.conf
    remove_default_nginx_server()

    # Disable default Nginx site
    disable_default_nginx_site()

    # Deploy main portfolio
    service_changed, nginx_changed = deploy_portfolio_main(portfolio_root, user)
    any_service_changed = service_changed
    any_nginx_changed = nginx_changed

    # Deploy each project
    for project in projects:
        port = port_map[project]
        service_changed, nginx_changed = deploy_project(
            project, port, portfolio_root, user
        )
        any_service_changed = any_service_changed or service_changed
        any_nginx_changed = any_nginx_changed or nginx_changed

    # Verify all Nginx symlinks are valid
    verify_nginx_symlinks(projects, include_main=True)

    # Reload services if needed
    if any_service_changed or any_nginx_changed:
        if not reload_services(any_service_changed, any_nginx_changed):
            print("\n❌ Service reload failed")
            sys.exit(1)
    else:
        print("\n• No changes detected, skipping reload")

    # Start/restart services
    start_services(projects, include_main=True)

    # Show final status
    show_status(projects, port_map, include_main=True)

    print("\n✅ Deployment complete!")
    print("\n💡 Useful commands:")
    print(f"   • Check logs: journalctl -u portfolio-<project> -f")
    print(f"   • Restart service: systemctl restart portfolio-<project>")
    print(f"   • Check Nginx: nginx -t")


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
