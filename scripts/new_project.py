#!/usr/bin/env python3
"""
new_project.py - Create new projects from templates

Supports: Python (Flask), PHP, Java
Features:
- Sequential naming enforcement (NN-project-name)
- Template-based project structure
- Automatic .gitignore generation
- Port assignment for Flask projects
- Standard directory structure (src/, logs/, README.md)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


# === CONFIGURATION ===
ROOT = Path("/home/gabo/portfolio")
PROJECTS_DIR = ROOT / "projects"
PORT_CONFIG_FILE = ROOT / ".port_assignments.json"

# Port range for Flask projects
PORT_RANGE_START = 5001
PORT_RANGE_END = 5100


# === TEMPLATES ===
GITIGNORE_TEMPLATE = """# Python cache
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

PYTHON_FLASK_APP_TEMPLATE = """#!/usr/bin/env python3
\"\"\"
{project_name} - Flask Application
Created: {date}
\"\"\"

from flask import Flask, render_template, jsonify

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/health')
def health():
    return jsonify({{'status': 'ok', 'service': '{project_name}'}})


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', {port}))
    app.run(host='0.0.0.0', port=port, debug=True)
"""

PYTHON_FLASK_RUN_TEMPLATE = """#!/usr/bin/env python3
\"\"\"
Entry point for {project_name}
\"\"\"

from app import app

if __name__ == '__main__':
    app.run()
"""

PYTHON_REQUIREMENTS_TEMPLATE = """Flask==3.0.0
gunicorn==21.2.0
python-dotenv==1.0.0
"""

PYTHON_README_TEMPLATE = """# {project_name}

{description}

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python3 run.py
```

## Deploy

```bash
sudo python3 scripts/autodeploy_all.py --project {folder_name}
```

## Environment Variables

Create `.env` file:
```
FLASK_ENV=development
PORT={port}
```

🔗 **Live:** [Coming soon](https://example.com)

Created: {date}
"""

PHP_INDEX_TEMPLATE = """<?php
/**
 * {project_name}
 * Created: {date}
 */

// Error reporting
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Simple routing
$request_uri = $_SERVER['REQUEST_URI'];
$script_name = $_SERVER['SCRIPT_NAME'];
$base_path = dirname($script_name);

// Remove base path from request URI
$route = str_replace($base_path, '', $request_uri);
$route = trim($route, '/');

// Basic router
switch ($route) {{
    case '':
    case 'index':
        require_once __DIR__ . '/views/home.php';
        break;

    case 'api/health':
        header('Content-Type: application/json');
        echo json_encode(['status' => 'ok', 'service' => '{project_name}']);
        break;

    default:
        http_response_code(404);
        echo "<h1>404 - Not Found</h1>";
        break;
}}
?>
"""

PHP_HOME_VIEW_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
</head>
<body>
    <h1>{project_name}</h1>
    <p>{description}</p>
    <p><em>Created: {date}</em></p>
</body>
</html>
"""

PHP_README_TEMPLATE = """# {project_name}

{description}

## Requirements

- PHP 7.4+
- PHP-FPM
- NGINX

## Deploy

```bash
sudo python3 scripts/autodeploy_all.py --project {folder_name}
```

🔗 **Live:** [Coming soon](https://example.com)

Created: {date}
"""

JAVA_MAIN_TEMPLATE = """package com.{project_slug};

/**
 * {project_name}
 * Created: {date}
 */
public class Main {{
    public static void main(String[] args) {{
        System.out.println("{project_name} - Hello, World!");
    }}
}}
"""

JAVA_README_TEMPLATE = """# {project_name}

{description}

## Build

```bash
javac src/com/{project_slug}/*.java -d bin/
```

## Run

```bash
java -cp bin com.{project_slug}.Main
```

Created: {date}
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


def get_next_project_number():
    """
    Scan projects directory and return next sequential number.

    Returns:
        int: Next available project number
    """
    if not PROJECTS_DIR.exists():
        return 1

    max_num = 0
    for item in PROJECTS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            # Extract number from format "NN-project-name"
            parts = item.name.split('-', 1)
            if parts[0].isdigit():
                max_num = max(max_num, int(parts[0]))

    return max_num + 1


def load_port_assignments():
    """
    Load port assignments from JSON file.

    Returns:
        dict: Project name -> port mapping
    """
    if not PORT_CONFIG_FILE.exists():
        return {}

    try:
        with open(PORT_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def save_port_assignments(assignments):
    """
    Save port assignments to JSON file.

    Args:
        assignments: dict of project -> port mappings
    """
    with open(PORT_CONFIG_FILE, 'w') as f:
        json.dump(assignments, f, indent=2, sort_keys=True)


def get_next_available_port():
    """
    Find next available port number.

    Returns:
        int: Next available port
    """
    assignments = load_port_assignments()
    used_ports = set(assignments.values())

    for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
        if port not in used_ports:
            return port

    raise Exception(f"No available ports in range {PORT_RANGE_START}-{PORT_RANGE_END}")


def assign_port(project_name):
    """
    Assign and persist port for a Flask project.

    Args:
        project_name: Name of the project

    Returns:
        int: Assigned port number
    """
    assignments = load_port_assignments()

    if project_name in assignments:
        return assignments[project_name]

    port = get_next_available_port()
    assignments[project_name] = port
    save_port_assignments(assignments)

    return port


# === PROJECT CREATION ===
def create_python_flask_project(folder_path, project_name, description, port):
    """Create Python Flask project structure."""
    colors = setup_colors()

    # Create directories
    dirs = [
        folder_path / "templates",
        folder_path / "static" / "css",
        folder_path / "static" / "js",
        folder_path / "logs",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        log(f"  Created: {d.relative_to(PROJECTS_DIR)}", "G", colors)

    # Create files
    date = datetime.now().strftime("%Y-%m-%d")

    files = {
        "app.py": PYTHON_FLASK_APP_TEMPLATE.format(
            project_name=project_name,
            date=date,
            port=port
        ),
        "run.py": PYTHON_FLASK_RUN_TEMPLATE.format(
            project_name=project_name
        ),
        "requirements.txt": PYTHON_REQUIREMENTS_TEMPLATE,
        "README.md": PYTHON_README_TEMPLATE.format(
            project_name=project_name,
            description=description,
            folder_name=folder_path.name,
            port=port,
            date=date
        ),
        ".gitignore": GITIGNORE_TEMPLATE,
        "templates/index.html": f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
    <link rel="stylesheet" href="{{{{ url_for('static', filename='css/style.css') }}}}">
</head>
<body>
    <h1>{project_name}</h1>
    <p>{description}</p>
</body>
</html>
""",
        "static/css/style.css": "/* Add your styles here */\n"
    }

    for filepath, content in files.items():
        file_path = folder_path / filepath
        file_path.write_text(content)
        log(f"  Created: {file_path.relative_to(PROJECTS_DIR)}", "G", colors)


def create_php_project(folder_path, project_name, description):
    """Create PHP project structure."""
    colors = setup_colors()

    # Create directories
    dirs = [
        folder_path / "views",
        folder_path / "public" / "css",
        folder_path / "public" / "js",
        folder_path / "logs",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        log(f"  Created: {d.relative_to(PROJECTS_DIR)}", "G", colors)

    # Create files
    date = datetime.now().strftime("%Y-%m-%d")

    files = {
        "index.php": PHP_INDEX_TEMPLATE.format(
            project_name=project_name,
            date=date
        ),
        "views/home.php": PHP_HOME_VIEW_TEMPLATE.format(
            project_name=project_name,
            description=description,
            date=date
        ),
        "README.md": PHP_README_TEMPLATE.format(
            project_name=project_name,
            description=description,
            folder_name=folder_path.name,
            date=date
        ),
        ".gitignore": GITIGNORE_TEMPLATE,
        "public/css/style.css": "/* Add your styles here */\n"
    }

    for filepath, content in files.items():
        file_path = folder_path / filepath
        file_path.write_text(content)
        log(f"  Created: {file_path.relative_to(PROJECTS_DIR)}", "G", colors)


def create_java_project(folder_path, project_name, description):
    """Create Java project structure."""
    colors = setup_colors()

    # Create slug for package name
    project_slug = folder_path.name.split('-', 1)[1].replace('-', '_')

    # Create directories
    dirs = [
        folder_path / "src" / "com" / project_slug,
        folder_path / "bin",
        folder_path / "logs",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        log(f"  Created: {d.relative_to(PROJECTS_DIR)}", "G", colors)

    # Create files
    date = datetime.now().strftime("%Y-%m-%d")

    files = {
        f"src/com/{project_slug}/Main.java": JAVA_MAIN_TEMPLATE.format(
            project_name=project_name,
            project_slug=project_slug,
            date=date
        ),
        "README.md": JAVA_README_TEMPLATE.format(
            project_name=project_name,
            description=description,
            project_slug=project_slug,
            date=date
        ),
        ".gitignore": GITIGNORE_TEMPLATE + "\n# Java\n*.class\nbin/\n"
    }

    for filepath, content in files.items():
        file_path = folder_path / filepath
        file_path.write_text(content)
        log(f"  Created: {file_path.relative_to(PROJECTS_DIR)}", "G", colors)


def create_project(project_type, project_name, description=None):
    """
    Create a new project with sequential naming.

    Args:
        project_type: 'python', 'php', or 'java'
        project_name: Human-readable project name
        description: Optional project description

    Returns:
        tuple: (success, folder_path, port_or_none)
    """
    colors = setup_colors()

    # Validate project type
    valid_types = ['python', 'php', 'java']
    if project_type not in valid_types:
        log(f"✗ Invalid project type: {project_type}", "R", colors)
        log(f"  Valid types: {', '.join(valid_types)}", "Y", colors)
        return False, None, None

    # Create projects directory if it doesn't exist
    PROJECTS_DIR.mkdir(exist_ok=True)

    # Get next sequential number
    project_num = get_next_project_number()

    # Create folder name: NN-project-name
    folder_name = f"{project_num:02d}-{project_name.lower().replace(' ', '-')}"
    folder_path = PROJECTS_DIR / folder_name

    # Check if already exists
    if folder_path.exists():
        log(f"✗ Project already exists: {folder_path}", "R", colors)
        return False, None, None

    # Set default description
    if not description:
        description = f"{project_name} - A new project"

    log(f"\n🚀 Creating new {project_type.upper()} project", "B", colors)
    log(f"  Name: {project_name}", "B", colors)
    log(f"  Folder: {folder_name}", "B", colors)

    # Create project based on type
    try:
        folder_path.mkdir(parents=True, exist_ok=True)

        port = None
        if project_type == 'python':
            port = assign_port(folder_name)
            log(f"  Port: {port}", "B", colors)
            create_python_flask_project(folder_path, project_name, description, port)
        elif project_type == 'php':
            create_php_project(folder_path, project_name, description)
        elif project_type == 'java':
            create_java_project(folder_path, project_name, description)

        log(f"\n✅ Project created successfully!", "G", colors)
        log(f"  Location: {folder_path}", "G", colors)

        return True, folder_path, port

    except Exception as e:
        log(f"\n✗ Error creating project: {e}", "R", colors)
        # Clean up partial creation
        if folder_path.exists():
            import shutil
            shutil.rmtree(folder_path)
        return False, None, None


def main():
    """Main entry point for new_project script."""
    parser = argparse.ArgumentParser(
        description="Create new projects from templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Project Types:
  python    Flask web application with automatic port assignment
  php       PHP application with NGINX configuration
  java      Basic Java application structure

Examples:
  %(prog)s python "My API" "REST API for my app"
  %(prog)s php "Admin Panel" "Management dashboard"
  %(prog)s java "Data Processor" "Batch processing tool"

The project will be created in projects/ with format: NN-project-name
        """
    )

    parser.add_argument(
        "type",
        choices=["python", "php", "java"],
        help="Project type"
    )

    parser.add_argument(
        "name",
        type=str,
        help="Project name (human-readable)"
    )

    parser.add_argument(
        "description",
        type=str,
        nargs="?",
        default=None,
        help="Project description (optional)"
    )

    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="List current port assignments"
    )

    args = parser.parse_args()
    colors = setup_colors()

    # List ports if requested
    if args.list_ports:
        assignments = load_port_assignments()
        if not assignments:
            log("No port assignments yet", "Y", colors)
        else:
            log("\n📋 Current Port Assignments:", "B", colors)
            log("=" * 60, "B", colors)
            for project, port in sorted(assignments.items(), key=lambda x: x[1]):
                print(f"{colors['G']}{port:<6} {project}{colors['N']}")
        return 0

    # Create project
    success, folder_path, port = create_project(
        args.type,
        args.name,
        args.description
    )

    if success:
        log("\n📝 Next Steps:", "B", colors)
        log(f"  1. cd {folder_path}", "Y", colors)

        if args.type == "python":
            log(f"  2. python3 -m venv venv", "Y", colors)
            log(f"  3. source venv/bin/activate", "Y", colors)
            log(f"  4. pip install -r requirements.txt", "Y", colors)
            log(f"  5. python3 run.py", "Y", colors)
            log(f"  6. Deploy: sudo python3 scripts/autodeploy_all.py", "Y", colors)
        elif args.type == "php":
            log(f"  2. Deploy: sudo php scripts/autodeploy_all.py", "Y", colors)
        elif args.type == "java":
            log(f"  2. javac src/**/*.java -d bin/", "Y", colors)
            log(f"  3. java -cp bin com.<package>.Main", "Y", colors)

        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
