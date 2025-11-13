# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Flask-based portfolio web application that dynamically displays projects by scanning subdirectories in the `projects/` folder. Each project can have its own Git repository and README.md, which are parsed and displayed on the portfolio site.

## Development Commands

### Running the Application

```bash
# Activate virtual environment
source venv/bin/activate

# Run development server (port 5000 by default)
python app.py

# Run with custom port
PORT=8000 python app.py

# Run with gunicorn (production)
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Dependencies

```bash
# Install dependencies
pip install -r requirements.txt

# Update dependencies
pip freeze > requirements.txt
```

## Architecture

### Project Discovery System

The core feature is **automatic project discovery** from the `projects/` directory:

1. **Scanning**: `load_projects()` (app.py:84) scans all subdirectories in `projects/`
2. **Metadata Extraction**: For each project folder:
   - Parses `README.md` for title, description, and live URL (app.py:55-81)
   - Extracts GitHub repo URL from `.git/config` (app.py:118-129)
   - Converts markdown to HTML using the `markdown` library
3. **Caching**: Uses signature-based caching (app.py:32-49) with 30-second TTL to detect changes in project files without re-parsing every request
4. **Serving**: Project assets are served dynamically via `/projects/<slug>/<path:asset>` (app.py:256-262)

### README.md Parsing Convention

Projects are expected to follow this README format:

```markdown
# Project Title

First paragraph becomes the short description.

🔗 **Live:** [Demo](https://example.com)

Additional content becomes the full description...
```

The parser (`_parse_readme` at app.py:55):
- Extracts the first `#` heading as the project name
- Uses the first substantial paragraph (>3 words) as description
- Detects live URLs using the pattern: `🔗 **Live:** [text](url)`

### Portfolio Data Structure

Static portfolio data (profile, experience, education, skills) is hardcoded in `portfolio_data` dict (app.py:156-216). This data is injected globally into all templates via `inject_globals()` (app.py:221-223).

### Resume Upload System

Supports authenticated PDF resume uploads:

- Upload endpoint: `POST /resume/upload` (app.py:287-311)
- Authentication via `X-RESUME-TOKEN` header or `?token=` query param
- Token must match `RESUME_UPLOAD_TOKEN` environment variable
- Stores as `static/cv/resume.pdf` (overwriting previous version)
- Download endpoint: `GET /resume` (app.py:279-284)

### Security Headers

All responses include security headers via `add_security_headers()` (app.py:226-232):
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

## Project Structure

```
portfolio/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/             # Jinja2 templates (Bootstrap 5)
│   ├── base.html         # Base template with navbar/footer and theme toggle
│   ├── index.html        # Homepage with hero section
│   ├── projects.html     # Projects listing with stats
│   └── project_detail.html  # Individual project page with breadcrumbs
├── static/
│   ├── css/style.css     # Custom styles with CSS variables for theming
│   ├── img/profile.jpg   # Profile photo
│   └── cv/resume.pdf     # Resume (excluded from git)
└── projects/             # Auto-discovered project folders (excluded from git)
    └── <project-name>/
        ├── README.md     # Parsed for metadata
        └── .git/config   # Parsed for GitHub URL
```

## Design System

### Theme System
- **Dark/Light Mode**: Implemented using CSS variables and localStorage persistence
- Default theme is dark mode
- Toggle button in navigation bar switches between themes
- Theme preference persists across page reloads
- CSS variables in `:root` and `[data-theme="dark"]` control all colors

### Color Palette
- **Python Branding**: Uses official Python colors (#3776ab blue, #ffd43b yellow)
- **Gradients**: Purple gradient for primary elements, Python gradient for accents
- **Dark Mode**: Dark gray backgrounds (#1a202c, #2d3748) with light text
- **Light Mode**: White backgrounds with dark text

### Typography
- Font family: Inter (Google Fonts) with system fallbacks
- Bold headings (700-800 weight)
- Consistent spacing and line-height

## Important Notes

- The `projects/` directory is excluded from Git (see .gitignore:67). Each project maintains its own Git repository.
- Virtual environments (`venv/`, `.venv/`) are excluded from Git
- The cache signature system (app.py:32-49) watches for changes to `README.md` and `.git/config` files within project folders to invalidate cache
- Project slugs are derived from folder names and used in URLs: `/projects/<slug>`
- Templates use Bootstrap 5 and Font Awesome 6 via CDN
