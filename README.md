# Portfolio Automation Toolkit

**Version:** 1.0.0
**Platform:** Linux (Arch Linux)
**Python:** 3.8+

A professional automation toolkit for managing a full-stack developer portfolio with multiple Flask and PHP projects.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Commands](#commands)
  - [Status](#status)
  - [Clean](#clean)
  - [New Project](#new-project)
  - [Git Sync](#git-sync)
  - [Autodeploy](#autodeploy)
- [Scripts Documentation](#scripts-documentation)
- [Configuration](#configuration)
- [Workflows](#workflows)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Installation

The toolkit is already installed and ready to use. All scripts are executable.

### Common Commands

```bash
# Show system status
python3 main.py status

# Clean Python cache
python3 main.py clean --dry-run  # preview first
python3 main.py clean             # execute

# Create new project
python3 main.py new python "My API" "REST API service"

# Sync with git and backup
python3 main.py sync --backup --verbose

# Deploy to production (requires sudo)
sudo python3 main.py autodeploy
```

### Getting Help

```bash
python3 main.py --help                  # main help
python3 main.py <command> --help        # command-specific help
```

---

## Architecture

### Project Structure

```
portfolio/
├── main.py                    # CLI orchestrator (entry point)
├── app.py                     # Main Flask portfolio application
├── scripts/                   # All operational scripts
│   ├── autodeploy_all.py     # Deployment automation
│   ├── clean_pycache.py      # Cache cleanup
│   ├── new_project.py        # Project scaffolding
│   └── git_sync.py           # Git operations & backup
├── projects/                  # Individual projects
│   ├── 01-cleandoc/
│   ├── 02-pasanotas/
│   └── ...
├── templates/                 # Jinja2 templates
├── static/                    # CSS, JS, images
├── log/                       # Application logs
├── .port_assignments.json    # Port allocation registry
└── README.md                 # This file
```

### Design Principles

- **Zero Business Logic in main.py** - Pure orchestration, all logic in `scripts/`
- **Idempotent & Safe** - All scripts can run multiple times safely
- **CLI-First** - Consistent argparse interface with clear error messages
- **Production-Ready** - Systemd services, NGINX configs, SSL/TLS support

---

## Commands

### Status

Show portfolio status overview including projects, services, and backups.

```bash
python3 main.py status
```

**Output:**
```
📊 Portfolio Status
============================================================
📦 Projects: 11
   • 01-cleandoc
   • 02-pasanotas
   ...

🔧 Active Services: 11
   ✓ portfolio-portfolio.service
   ✓ portfolio-cleandoc.service
   ...

🌐 NGINX: ✓ active

💾 Backups: 25
   Latest: portfolio_20251217_143025
   Date: 2025-12-17 14:30:25
============================================================
```

---

### Clean

Remove Python cache files recursively across all projects.

```bash
python3 main.py clean [options]
```

**Options:**
- `--dry-run, -d` - Preview without deleting
- `--verbose, -v` - Show each file/directory
- `--path, -p PATH` - Custom root directory

**What It Cleans:**
- `__pycache__/` directories
- `*.pyc`, `*.pyo`, `*$py.class` files

**Examples:**
```bash
# Preview cleanup
python3 main.py clean --dry-run

# Execute cleanup
python3 main.py clean

# Verbose output
python3 main.py clean --verbose
```

---

### New Project

Create new projects from predefined templates with automatic setup.

```bash
python3 main.py new <type> <name> [description]
```

**Supported Types:**
- `python` - Flask web application
- `php` - PHP application with NGINX
- `java` - Java console application

**Options:**
- `--list-ports` - Show current port assignments

**Features:**
- Sequential naming (e.g., `12-my-api`)
- Automatic port assignment for Python projects
- Template generation with boilerplate code

**Examples:**
```bash
# Create Python Flask project
python3 main.py new python "My API" "REST API service"

# Create PHP project
python3 main.py new php "Admin Panel" "Management dashboard"

# List port assignments
python3 main.py new --list-ports
```

**Generated Structure (Python):**
```
NN-project-name/
├── app.py                 # Flask application
├── run.py                 # Entry point
├── requirements.txt       # Dependencies
├── README.md             # Documentation
├── .gitignore            # Git exclusions
├── templates/            # Jinja2 templates
│   └── index.html
├── static/               # Assets
│   ├── css/
│   └── js/
└── logs/                 # Application logs
```

---

### Git Sync

Automate git operations with safe backups and .gitignore management.

```bash
python3 main.py sync [options]
```

**Options:**
- `--dry-run, -d` - Preview without changes
- `--verbose, -v` - Detailed output
- `--backup, -b` - Create backup before sync
- `--message, -m MSG` - Custom commit message
- `--project, -p NAME` - Sync specific project
- `--update-gitignore` - Update .gitignore to latest template
- `--cleanup-backups` - Remove old backups
- `--keep-backups N` - Keep N most recent backups (default: 10)

**Features:**
- Timestamped backups in `~/portfolio_backups/`
- Safe push with `--force-with-lease`
- Multi-project support
- Automatic .gitignore updates

**Examples:**
```bash
# Sync all projects (dry-run first)
python3 main.py sync --dry-run
python3 main.py sync

# Sync with backup
python3 main.py sync --backup --verbose

# Custom commit message
python3 main.py sync --message "Feature: Add user auth"

# Update all .gitignore files
python3 main.py sync --update-gitignore

# Clean old backups
python3 main.py sync --cleanup-backups --keep-backups 5
```

**Workflow:**
1. Check git status
2. Create backup (if `--backup`)
3. Update .gitignore (if `--update-gitignore`)
4. Stage all changes (`git add .`)
5. Commit with timestamp
6. Push with `--force-with-lease`
7. Report status

---

### Autodeploy

Deploy Flask and PHP projects with systemd and NGINX.

**Requires sudo privileges.**

```bash
sudo python3 main.py autodeploy [options]
```

**Options:**
- `--verbose, -v` - Detailed output
- `--dry-run, -d` - Preview without changes
- `--project, -p NAME` - Deploy specific project

**What It Does:**

1. **Environment Setup**
   - Creates fresh Python virtual environments
   - Installs dependencies from requirements.txt
   - Verifies Flask/Gunicorn installation

2. **Systemd Services**
   - Generates service files in `/etc/systemd/system/`
   - Configures user, working directory, environment
   - Enables and starts services

3. **NGINX Configuration**
   - Creates reverse proxy configs for Flask apps
   - Generates PHP-FPM configs for PHP projects
   - Sets up SSL with Let's Encrypt certificates
   - Enables HTTP → HTTPS redirect

4. **Permissions**
   - Auto-detects web server user (nginx/http/www-data)
   - Sets ownership: `gabo:webuser`
   - Applies 755 permissions

**Examples:**
```bash
# Deploy all projects
sudo python3 main.py autodeploy

# Deploy specific project
sudo python3 main.py autodeploy --project portfolio

# Preview deployment
sudo python3 main.py autodeploy --dry-run --verbose
```

**Project Configuration:**

Projects are defined in `scripts/autodeploy_all.py`:

```python
PROJECTS = [
    ("name", "folder", port, "domain.com"),
    ("portfolio", "main", 5000, "omar-xyz.shop"),
    ("cleandoc", "01-cleandoc", 5001, "cleandoc.omar-xyz.shop"),
]
```

---

## Scripts Documentation

### 1. main.py - CLI Orchestrator

**Purpose:** Unified entry point for all toolkit operations.

**Key Features:**
- Pure routing layer (no business logic)
- Argument forwarding to scripts
- Graceful error handling
- Colored output for UX

**Commands:** `autodeploy`, `clean`, `new`, `sync`, `status`

---

### 2. scripts/autodeploy_all.py

**Purpose:** Deploy Flask/PHP projects with systemd and NGINX.

**Detection:**
- **Flask:** Requires `app.py` + port assignment
- **PHP:** Requires `index.php` (root or `public/` directory)

**SSL/TLS:** All sites use Let's Encrypt certificates from `/etc/letsencrypt/live/`.

---

### 3. scripts/clean_pycache.py

**Purpose:** Recursively remove Python cache files.

**Scanning:**
- Main portfolio directory
- All projects in `projects/`
- Respects `.git`, `venv`, hidden directories

**Performance:** ~1-2 seconds for 11 projects

---

### 4. scripts/new_project.py

**Purpose:** Create projects from templates with automatic setup.

**Port Assignment:**
- Scans port range 5001-5100
- Persists to `.port_assignments.json`
- Prevents conflicts

**Templates:** Python (Flask), PHP, Java

**Performance:** ~0.5 seconds

---

### 5. scripts/git_sync.py

**Purpose:** Git operations with backups and .gitignore management.

**Backup Strategy:**
- Timestamped snapshots: `project_20251217_143025`
- Excludes: venv, __pycache__, .git, node_modules, logs
- Stored in `~/portfolio_backups/`
- Automatic cleanup of old backups

**Safety:** Uses `--force-with-lease` (preserves remote commits not in local history)

**Performance:** ~5-10 seconds per project

---

## Configuration

### Port Assignments

**File:** `.port_assignments.json`

**Format:**
```json
{
  "01-cleandoc": 5001,
  "02-pasanotas": 5002,
  "03-auditel": 5003
}
```

**Management:**
- Auto-created by `new_project.py`
- Read by `autodeploy_all.py`
- Prevents port conflicts

---

### .gitignore Template

The sync script enforces a unified .gitignore across all projects:

```
# Python cache
__pycache__/
*.py[cod]

# AI agents
CLAUDE.md, GEMINI.md, .cursorrules, etc.

# Virtual environments
venv/, .venv/, env/

# Environment files
.env, .env.* (except .env.example)

# Flask
instance/, *.db, *.sqlite*, *.log

# OS & IDE
.DS_Store, .vscode/, .idea/

# Build & Test
build/, dist/, .pytest_cache/
```

---

## Workflows

### Development Workflow

```bash
# 1. Create new project
python3 main.py new python "User Service" "User management API"

# 2. Develop locally
cd projects/XX-user-service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 run.py

# 3. Clean and sync
python3 main.py clean
python3 main.py sync --backup --message "Initial implementation"

# 4. Deploy
sudo python3 main.py autodeploy --project user-service
```

---

### Maintenance Workflow

```bash
# 1. Check status
python3 main.py status

# 2. Clean cache
python3 main.py clean

# 3. Backup and sync
python3 main.py sync --backup

# 4. Update gitignore
python3 main.py sync --update-gitignore

# 5. Cleanup old backups
python3 main.py sync --cleanup-backups --keep-backups 5
```

---

### Deployment Workflow

```bash
# 1. Test deployment (dry-run)
sudo python3 main.py autodeploy --dry-run --verbose

# 2. Deploy all
sudo python3 main.py autodeploy

# 3. Verify services
python3 main.py status
sudo systemctl status portfolio-portfolio

# 4. Check NGINX
sudo nginx -t
```

---

## Troubleshooting

### Port Conflicts

```bash
# List current assignments
python3 main.py new --list-ports

# Check if port in use
sudo lsof -i :5001

# Edit .port_assignments.json manually if needed
```

---

### Service Issues

```bash
# Check service status
sudo systemctl status portfolio-NAME

# View logs
sudo journalctl -u portfolio-NAME -n 50

# Restart service
sudo systemctl restart portfolio-NAME
```

---

### NGINX Problems

```bash
# Test configuration
sudo nginx -t

# Check error logs
sudo tail -f /var/log/nginx/error.log

# Reload configuration
sudo systemctl reload nginx
```

---

### Git Sync Issues

```bash
# Check git status manually
cd projects/XX-project
git status
git log --oneline -5

# Force local priority (careful!)
git push --force-with-lease origin HEAD
```

---

## Performance

| Script      | Time (approx) | Notes                    |
|-------------|---------------|--------------------------|
| clean       | 1-2s          | Scans all projects       |
| new         | <1s           | Creates project files    |
| sync        | 5-10s         | Per project              |
| autodeploy  | 30-60s        | Per Flask project        |
| status      | <1s           | Quick overview           |

---

## Security

### Sudo Operations
- Only `autodeploy` requires sudo
- Never run other scripts with sudo
- Uses `$SUDO_USER` to preserve user context

### Secrets Management
- Never commit `.env` files
- Use `.env.example` for templates
- .gitignore excludes sensitive files

### Force Push Safety
- Uses `--force-with-lease` (not `--force`)
- Prevents overwriting remote commits
- Safe for collaboration

### File Permissions
- Services run as user `gabo`
- NGINX runs as detected web user
- 755 permissions for project directories

---

## Tips

1. **Always dry-run first** for destructive operations
2. **Use --verbose** when debugging
3. **Backup before major changes**: `sync --backup`
4. **Check status regularly**: `main.py status`
5. **Keep backups lean**: `sync --cleanup-backups`

---

## Environment Requirements

### System
- **OS:** Linux (tested on Arch Linux)
- **Python:** 3.8+
- **Privileges:** sudo for deployment operations

### Dependencies
**Python Standard Library Only** (no external dependencies)

### System Services
- **systemd** - Service management
- **NGINX** - Web server
- **PHP-FPM** - PHP processing (for PHP projects)
- **Let's Encrypt** - SSL certificates

---

## Support

For issues or questions:
1. Check this documentation
2. Review script help: `python3 main.py <command> --help`
3. Run with `--verbose` for debugging
4. Check system logs: `journalctl`, `/var/log/nginx/`

---

**Last Updated:** 2025-12-17
**Toolkit Version:** 1.0.0
