#!/usr/bin/env python3
"""
autodeploy_all.py - Automated deployment for Flask and PHP projects

Handles complete deployment pipeline:
- Creates/updates systemd services for Flask apps
- Generates NGINX configurations with SSL
- Sets up virtual environments and dependencies
- Manages permissions and service restarts

Requires: sudo privileges
Idempotent: Safe to run multiple times
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime


# === CONFIGURATION ===
ROOT = Path("/home/gabo/portfolio")
PROJECTS_DIR = ROOT / "projects"
SYSTEMD_DIR = Path("/etc/systemd/system")
NGINX_AVAILABLE = Path("/etc/nginx/sites-available")
NGINX_ENABLED = Path("/etc/nginx/sites-enabled")
SSL_CERT_PATH = Path("/etc/letsencrypt/live/omar-xyz.shop")
PHP_FPM_SOCKET = Path("/run/php-fpm/php-fpm.sock")

# Project definitions: (service_name, folder_name, port, domain)
PROJECTS = [
    ("portfolio", "main", 5000, "omar-xyz.shop"),
    ("cleanddoc", "01-cleandoc", 5001, "cleandoc.omar-xyz.shop"),
    ("pasanotas", "02-pasanotas", 5002, "pasanotas.omar-xyz.shop"),
    ("auditel", "03-auditel", 5003, "auditel.omar-xyz.shop"),
    ("lexnum", "04-lexnum", 5004, "lexnum.omar-xyz.shop"),
    ("obsidian-vps", "05-obsidian-vps", 5005, "obsidian-vps.omar-xyz.shop"),
    ("sasp", "06-sasp", 5006, "sasp.omar-xyz.shop"),
    ("sasp-php", "07-sasp-php", None, "sasp-php.omar-xyz.shop"),
    ("sifet-estatales", "09-sifet-estatales", 5008, "sifet-estatales.omar-xyz.shop"),
    ("siif", "10-siif", 5009, "siif.omar-xyz.shop"),
    ("xml-php", "11-xml-php", None, "xml-php.omar-xyz.shop"),
]


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


def detect_web_user():
    """
    Detect the system web server user (nginx, http, www-data).

    Returns:
        str: Username of the web server
    """
    for candidate in ["nginx", "http", "www-data"]:
        try:
            result = subprocess.run(
                ["id", candidate],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if result.returncode == 0:
                return candidate
        except Exception:
            continue
    return "http"


# === FLASK ENVIRONMENT ===
def setup_flask_environment(project_path, verbose=False):
    """
    Create fresh virtual environment and install Flask dependencies.

    Args:
        project_path: Path to Flask project
        verbose: Show detailed output

    Returns:
        bool: True if successful
    """
    colors = setup_colors()
    venv_path = project_path / "venv"
    pip_path = venv_path / "bin" / "pip"

    # Remove old venv
    if venv_path.exists():
        if verbose:
            log(f"  Removing old venv: {venv_path}", "Y", colors)
        shutil.rmtree(venv_path)

    # Create new venv
    if verbose:
        log(f"  Creating venv: {venv_path}", "B", colors)

    result = run_command(
        ["python3", "-m", "venv", str(venv_path)],
        cwd=str(project_path)
    )

    if result.returncode != 0:
        log(f"  ✗ Failed to create venv", "R", colors)
        return False

    # Upgrade pip
    run_command([str(pip_path), "install", "-q", "--upgrade", "pip"])

    # Install base dependencies
    run_command([str(pip_path), "install", "-q", "flask", "gunicorn"])

    # Install project requirements
    requirements = project_path / "requirements.txt"
    if requirements.exists():
        if verbose:
            log(f"  Installing requirements.txt", "B", colors)
        run_command([str(pip_path), "install", "-q", "-r", str(requirements)])

    # Verify installation
    verify = run_command([
        venv_path / "bin" / "python",
        "-c",
        "import flask, gunicorn"
    ])

    if verify.returncode == 0:
        log(f"  ✓ Flask environment ready", "G", colors)
        return True
    else:
        log(f"  ✗ Flask environment verification failed", "R", colors)
        return False


# === SYSTEMD SERVICE ===
def generate_systemd_service(name, project_path, port):
    """
    Create systemd service file for Flask app.

    Args:
        name: Service name
        project_path: Path to project
        port: Port number for gunicorn

    Returns:
        Path: Path to service file
    """
    service_file = SYSTEMD_DIR / f"portfolio-{name}.service"
    venv_path = project_path / "venv"
    user = os.environ.get('SUDO_USER', 'gabo')

    service_content = f"""[Unit]
Description={name} Flask Application
After=network.target

[Service]
User={user}
WorkingDirectory={project_path}
Environment="PATH={venv_path}/bin"
ExecStart={venv_path}/bin/gunicorn --bind 127.0.0.1:{port} app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    service_file.write_text(service_content)
    return service_file


# === NGINX CONFIGURATION ===
def generate_nginx_flask(domain, port, is_main=False):
    """Generate NGINX config for Flask reverse proxy."""
    listen_directive = "listen 80 default_server;" if is_main else "listen 80;"

    return f"""server {{
    {listen_directive}
    server_name {domain};
    return 301 https://$server_name$request_uri;
}}

server {{
    listen 443 ssl;
    http2 on;
    server_name {domain};

    ssl_certificate {SSL_CERT_PATH}/fullchain.pem;
    ssl_certificate_key {SSL_CERT_PATH}/privkey.pem;

    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""


def generate_nginx_php(domain, document_root):
    """Generate NGINX config for PHP-FPM."""
    return f"""server {{
    listen 80;
    server_name {domain};
    return 301 https://$server_name$request_uri;
}}

server {{
    listen 443 ssl;
    http2 on;
    server_name {domain};

    root {document_root};
    index index.php index.html;

    ssl_certificate {SSL_CERT_PATH}/fullchain.pem;
    ssl_certificate_key {SSL_CERT_PATH}/privkey.pem;

    # Deny access to hidden files
    location ~ /\\. {{
        deny all;
    }}

    # PHP processing
    location ~ \\.php$ {{
        include fastcgi_params;
        fastcgi_pass unix:{PHP_FPM_SOCKET};
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME {document_root}$fastcgi_script_name;
        fastcgi_param DOCUMENT_ROOT {document_root};
        fastcgi_param PATH_INFO $fastcgi_path_info;
    }}

    # Try files fallback
    location / {{
        try_files $uri $uri/ /index.php?$args;
    }}
}}
"""


# === SERVICE MANAGEMENT ===
def restart_systemd_service(name, verbose=False):
    """
    Restart systemd service and verify status.

    Args:
        name: Service name (without portfolio- prefix)
        verbose: Show detailed output

    Returns:
        bool: True if successful
    """
    colors = setup_colors()
    service_name = f"portfolio-{name}"

    # Reload systemd
    run_command(["systemctl", "daemon-reload"])

    # Enable service
    run_command(["systemctl", "enable", service_name])

    # Restart service
    result = run_command(["systemctl", "restart", service_name])

    if result.returncode == 0:
        log(f"  ✓ Service {name} started", "G", colors)
        return True
    else:
        log(f"  ✗ Service {name} failed to start", "R", colors)
        if verbose:
            # Show last few journal entries
            journal = run_command([
                "journalctl",
                "-u", service_name,
                "-n", "5",
                "--no-pager"
            ])
            log(f"  Journal output:\n{journal.stdout}", "R", colors)
        return False


def setup_nginx_site(name, config_content, verbose=False):
    """
    Create NGINX site configuration and enable it.

    Args:
        name: Site name
        config_content: NGINX configuration text
        verbose: Show detailed output

    Returns:
        bool: True if successful
    """
    colors = setup_colors()

    # Write config
    config_file = NGINX_AVAILABLE / name
    config_file.write_text(config_content)

    if verbose:
        log(f"  Created NGINX config: {config_file}", "B", colors)

    # Enable site (create symlink)
    enabled_link = NGINX_ENABLED / name

    if enabled_link.exists() or enabled_link.is_symlink():
        enabled_link.unlink()

    enabled_link.symlink_to(config_file)

    if verbose:
        log(f"  Enabled NGINX site: {name}", "B", colors)

    return True


def fix_permissions(path, web_user):
    """
    Set correct ownership and permissions for project directory.

    Args:
        path: Project path
        web_user: Web server username
    """
    colors = setup_colors()
    system_user = os.environ.get('SUDO_USER', 'gabo')

    run_command(["chown", "-R", f"{system_user}:{web_user}", str(path)])
    run_command(["chmod", "-R", "755", str(path)])

    log(f"  ✓ Permissions set ({system_user}:{web_user})", "Y", colors)


# === MAIN DEPLOYMENT ===
def deploy_project(name, folder, port, domain, web_user, verbose=False, dry_run=False):
    """
    Deploy a single project (Flask or PHP).

    Args:
        name: Project name
        folder: Folder name (or "main" for root)
        port: Port number (None for PHP projects)
        domain: Domain name
        web_user: Web server username
        verbose: Show detailed output
        dry_run: Don't make actual changes

    Returns:
        tuple: (name, status_message)
    """
    colors = setup_colors()

    # Determine project path
    if name == "portfolio":
        project_path = ROOT
    else:
        project_path = PROJECTS_DIR / folder

    # Check if project exists
    if not project_path.exists():
        log(f"⚠ {name}: Directory not found", "Y", colors)
        return (name, "directory not found")

    # Check project type
    has_flask = (project_path / "app.py").exists()
    has_php_root = (project_path / "index.php").exists()
    has_php_public = (project_path / "public" / "index.php").exists()

    if dry_run:
        log(f"[DRY RUN] {name} ({domain})", "Y", colors)
        if has_flask and port:
            return (name, "Flask [would deploy]")
        elif has_php_root or has_php_public:
            return (name, "PHP [would deploy]")
        else:
            return (name, "skipped [no app]")

    try:
        # Set permissions first
        fix_permissions(project_path, web_user)

        # FLASK DEPLOYMENT
        if has_flask and port:
            log(f"🔧 Deploying Flask: {name} ({domain})", "B", colors)

            # Setup environment
            if not setup_flask_environment(project_path, verbose):
                return (name, "Flask env failed")

            # Generate systemd service
            generate_systemd_service(name, project_path, port)

            # Generate NGINX config
            nginx_config = generate_nginx_flask(domain, port, name == "portfolio")
            setup_nginx_site(name, nginx_config, verbose)

            # Restart service
            if restart_systemd_service(name, verbose):
                return (name, "Flask OK")
            else:
                return (name, "Flask service failed")

        # PHP DEPLOYMENT
        elif has_php_root or has_php_public:
            log(f"⚙ Deploying PHP: {name} ({domain})", "B", colors)

            # Determine document root
            if has_php_public:
                document_root = project_path / "public"
            else:
                document_root = project_path

            if verbose:
                log(f"  Document root: {document_root}", "B", colors)

            # Generate NGINX config
            nginx_config = generate_nginx_php(domain, document_root)
            setup_nginx_site(name, nginx_config, verbose)

            log(f"  ✓ PHP site configured", "G", colors)
            return (name, "PHP OK")

        else:
            log(f"… Skipping {name} (no app.py or index.php)", "Y", colors)
            return (name, "skipped")

    except Exception as e:
        log(f"✗ Error deploying {name}: {e}", "R", colors)
        return (name, f"error: {str(e)[:30]}")


def reload_nginx(verbose=False):
    """Test and reload NGINX configuration."""
    colors = setup_colors()

    # Test config
    test_result = run_command(["nginx", "-t"])

    if test_result.returncode != 0:
        log("✗ NGINX config test failed", "R", colors)
        if verbose:
            log(test_result.stderr, "R", colors)
        return False

    # Reload
    reload_result = run_command(["systemctl", "reload", "nginx"])

    if reload_result.returncode == 0:
        log("🔁 NGINX reloaded successfully", "G", colors)
        return True
    else:
        log("✗ NGINX reload failed", "R", colors)
        return False


def main():
    """Main entry point for autodeploy script."""
    parser = argparse.ArgumentParser(
        description="Deploy all portfolio projects with systemd and NGINX",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo %(prog)s                     # Deploy all projects
  sudo %(prog)s --verbose           # Show detailed output
  sudo %(prog)s --dry-run           # Preview without changes
  sudo %(prog)s --project portfolio # Deploy specific project
        """
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )

    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Preview changes without deploying"
    )

    parser.add_argument(
        "--project", "-p",
        type=str,
        help="Deploy only specific project by name"
    )

    args = parser.parse_args()
    colors = setup_colors()

    # Check root privileges
    if os.geteuid() != 0:
        log("✗ This script requires sudo privileges", "R", colors)
        log("  Run: sudo python3 scripts/autodeploy_all.py", "Y", colors)
        sys.exit(1)

    # Detect web user
    web_user = detect_web_user()
    log(f"🌐 Web server user: {web_user}", "Y", colors)

    # Start deployment
    log(f"\n🚀 AUTODEPLOY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "B", colors)
    log("=" * 60, "B", colors)

    if args.dry_run:
        log("💡 DRY RUN MODE - No changes will be made\n", "Y", colors)

    # Filter projects if specific project requested
    projects_to_deploy = PROJECTS
    if args.project:
        projects_to_deploy = [p for p in PROJECTS if p[0] == args.project]
        if not projects_to_deploy:
            log(f"✗ Project '{args.project}' not found", "R", colors)
            sys.exit(1)

    # Deploy each project
    report = []
    for name, folder, port, domain in projects_to_deploy:
        result = deploy_project(
            name, folder, port, domain, web_user,
            verbose=args.verbose,
            dry_run=args.dry_run
        )
        report.append(result)

    # Reload NGINX
    if not args.dry_run:
        log(f"\n{'=' * 60}", "B", colors)
        reload_nginx(args.verbose)

    # Print report
    log(f"\n{'=' * 60}", "B", colors)
    log("📋 DEPLOYMENT REPORT", "B", colors)
    log("=" * 60, "B", colors)

    for name, status in report:
        if "OK" in status:
            color = "G"
        elif "skip" in status.lower() or "would" in status.lower():
            color = "Y"
        else:
            color = "R"

        print(f"{colors[color]}{name:<25} {status}{colors['N']}")

    log("=" * 60, "B", colors)

    if args.dry_run:
        log("\n💡 Dry run complete. Use without --dry-run to deploy.", "Y", colors)
    else:
        log("\n✅ Deployment complete!", "G", colors)

    return 0


if __name__ == "__main__":
    sys.exit(main())
