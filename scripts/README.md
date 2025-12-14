# Portfolio Maintenance Scripts

This directory contains utility scripts for maintaining the portfolio project structure.

## Scripts Overview

1. **`maintain_portfolio.py`** - Manages project configuration (ports, .gitignore, requirements, caches)
2. **`git_sync_all.py`** - Commits and pushes all projects to GitHub

---

## Main Script: `maintain_portfolio.py`

A unified maintenance tool that manages all projects in the portfolio.

### Features

1. **Port Assignment** - Assigns sequential ports to all Flask applications
2. **GitIgnore Management** - Updates all .gitignore files with standard patterns
3. **Requirements Sync** - Keeps requirements.txt files consistent across projects
4. **Cache Clearing** - Removes all __pycache__ and .pyc files

### Usage

```bash
# Show current status of all projects
python3 scripts/maintain_portfolio.py status

# Update all port assignments
python3 scripts/maintain_portfolio.py ports

# Update all .gitignore files
python3 scripts/maintain_portfolio.py gitignore

# Update all requirements.txt files
python3 scripts/maintain_portfolio.py requirements

# Clear all caches
python3 scripts/maintain_portfolio.py clear-cache

# Run all maintenance tasks at once
python3 scripts/maintain_portfolio.py all

# Preview changes without applying them
python3 scripts/maintain_portfolio.py all --dry-run
```

### Port Assignment Rules

- Ports are assigned sequentially starting from **5001**
- **pasanotas** is always assigned port **5002** (fixed requirement)
- Projects are ordered alphabetically (except for fixed ports)

### Current Port Assignments

- auditel: 5001
- **pasanotas: 5002** (fixed)
- cleandoc: 5003
- lexnum: 5004
- obsidian-vps: 5005
- sasp: 5006
- sasp-php: 5007
- scan-actas-nacimiento: 5008
- sifet-estatales: 5009
- siif: 5010

### GitIgnore Patterns

The script ensures all projects ignore:
- AI agent files (AGENTS.md, CLAUDE.md, GEMINI.md, .cursorrules, .cursor/, .aider*)
- Python cache (__pycache__/, *.pyc, *.pyo)
- Virtual environments (venv/, .venv/, env/)
- Flask artifacts (*.db, *.sqlite, instance/, *.log)
- Environment files (*.env, except .env.example)
- OS files (.DS_Store, Thumbs.db)
- IDE files (.vscode/, .idea/)
- Build artifacts (build/, dist/, *.egg-info/)

### Requirements Management

The script ensures consistent versions of core Flask dependencies:
- Flask==3.0.3
- Werkzeug==3.0.4
- Jinja2==3.1.4
- gunicorn==22.0.0
- python-dotenv==1.0.1

Project-specific dependencies are preserved.

## Adding New Projects

When you add a new project to `projects/`:

1. Create the project directory
2. Add a README.md file (for portfolio display)
3. Run `python3 scripts/maintain_portfolio.py all` to configure it

The script will automatically:
- Assign a sequential port
- Create a standard .gitignore
- Update requirements.txt if it exists

## Maintenance Workflow

It's recommended to run the maintenance script periodically:

```bash
# Before committing major changes
python3 scripts/maintain_portfolio.py all --dry-run  # Preview
python3 scripts/maintain_portfolio.py all            # Apply
```

This ensures consistency across all projects in the portfolio.

---

## Git Sync Script: `git_sync_all.py`

Automatically commits and pushes all portfolio projects to GitHub.

### Features

- **Automatic commit & push** - Processes all projects in one command
- **Force push support** - Local state overrides remote (with safety confirmations)
- **Smart force push** - Uses `--force-with-lease` for safety, falls back to `--force` if needed
- **Status display** - Shows uncommitted changes, unpushed commits, and remote tracking
- **Dry run mode** - Preview changes before applying
- **Custom commit messages** - Use your own message or auto-generate timestamp
- **Colored output** - Easy-to-read terminal output with status indicators

### Usage

```bash
# Show git status for all projects
python3 scripts/git_sync_all.py status

# Commit and push all projects (auto-generated message)
python3 scripts/git_sync_all.py sync

# Commit with custom message
python3 scripts/git_sync_all.py sync -m "Update configuration"

# Force push (local overrides remote) - REQUIRES CONFIRMATION
python3 scripts/git_sync_all.py sync --force

# Preview changes without applying
python3 scripts/git_sync_all.py sync --dry-run

# Preview force push
python3 scripts/git_sync_all.py sync --force --dry-run
```

### Force Push Behavior

When using `--force`:

1. **Safety First**: Uses `--force-with-lease` which prevents overwriting if remote has new commits
2. **Fallback**: If `--force-with-lease` fails, tries regular `--force` to override remote
3. **Confirmation**: Requires typing "YES" to confirm (bypassed in dry-run mode)
4. **Local Priority**: Your local state becomes the source of truth

**Warning**: Force push will override remote changes. Only use when you're certain local state is correct.

### Status Indicators

- `✓` Green - Clean (no changes)
- `●` Yellow - Uncommitted changes
- `↑` Cyan - Unpushed commits
- `✗` Red - Error
- `ℹ` Blue - Info

### Example Workflow

```bash
# 1. Check what needs to be committed
python3 scripts/git_sync_all.py status

# 2. Preview the sync
python3 scripts/git_sync_all.py sync --dry-run -m "Homogenize configuration"

# 3. Execute the sync
python3 scripts/git_sync_all.py sync -m "Homogenize configuration"

# 4. If conflicts occur and you want to force (use with caution!)
python3 scripts/git_sync_all.py sync --force -m "Override remote with local state"
```

### Safety Features

1. **Confirmation prompt** - Force push requires typing "YES"
2. **Dry run mode** - Test before executing
3. **Force-with-lease** - Won't override if remote changed unexpectedly
4. **Per-project error handling** - One failure doesn't stop other projects
5. **Detailed summary** - Shows what succeeded and what failed

### Integration with Maintenance

Typical maintenance workflow:

```bash
# 1. Update configuration
python3 scripts/maintain_portfolio.py all

# 2. Review changes
python3 scripts/git_sync_all.py status

# 3. Commit and push
python3 scripts/git_sync_all.py sync -m "Update: homogenize ports and configuration"
```
