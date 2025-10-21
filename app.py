# app.py
from __future__ import annotations
import os
import time
import re
import configparser
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from flask import (
    Flask, render_template, jsonify, send_file, send_from_directory, abort
)
from werkzeug.utils import secure_filename
from markdown import markdown

# ---------------------------------------------------------
# App setup
# ---------------------------------------------------------
app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = BASE_DIR / "projects"

# ---------------------------------------------------------
# Cache for project metadata
# ---------------------------------------------------------
_CACHE_TTL_SEC = 30
_projects_cache: List[Dict[str, Any]] = []
_projects_cache_sig: str | None = None
_projects_cache_time: float = 0.0


def _projects_signature() -> str:
    """Generate a signature to detect file modifications."""
    parts: List[str] = []
    for folder in sorted(p for p in PROJECTS_DIR.iterdir() if p.is_dir()):
        if folder.name in {".git", "venv", "static", "templates", "__pycache__"}:
            continue
        if folder.name.startswith("."):
            continue
        mtimes: List[str] = []
        for rel in ("README.md", ".git/config"):
            p = folder / rel
            if p.exists():
                try:
                    mtimes.append(str(p.stat().st_mtime_ns))
                except Exception:
                    mtimes.append("0")
        parts.append(f"{folder.name}:{'|'.join(mtimes)}")
    return "|".join(parts)


# ---------------------------------------------------------
# Project parsing logic
# ---------------------------------------------------------
def _parse_readme(path: Path) -> Dict[str, str]:
    """Parse README.md for name, description, live URL, and HTML content."""
    text = path.read_text(encoding="utf-8")
    html = markdown(text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    data = {"name": "", "description": "", "live_url": "", "full_description": html}

    # Title from first heading
    for line in lines:
        if line.startswith("#"):
            data["name"] = line.lstrip("#").strip()
            break

    # Description: first normal paragraph
    for line in lines:
        if line.startswith("#") or line.startswith("🔗") or line.startswith("**"):
            continue
        if len(line.split()) > 3:
            # Render this paragraph as HTML to preserve markdown formatting
            data["description"] = markdown(line)
            break

    # Live link pattern: 🔗 **Live:** [text](url)
    m = re.search(r"🔗\s*\*\*Live:\*\*\s*\[[^\]]*\]\(([^\)]+)\)", text)
    if m:
        data["live_url"] = m.group(1).strip()

    return data


def load_projects() -> List[Dict[str, Any]]:
    """Load all projects dynamically from ~/portfolio/projects."""
    global _projects_cache, _projects_cache_sig, _projects_cache_time
    now = time.time()
    sig = _projects_signature()
    if (
        _projects_cache
        and _projects_cache_sig == sig
        and now - _projects_cache_time < _CACHE_TTL_SEC
    ):
        return _projects_cache

    projects: List[Dict[str, Any]] = []
    for folder in sorted(p for p in PROJECTS_DIR.iterdir() if p.is_dir()):
        try:
            if folder.name in {".git", "venv", "static", "templates", "__pycache__"}:
                continue
            if folder.name.startswith("."):
                continue

            readme_path = folder / "README.md"
            git_config = folder / ".git" / "config"

            if not readme_path.exists() and not git_config.exists():
                continue

            meta = _parse_readme(readme_path) if readme_path.exists() else {}
            name = meta.get("name") or folder.name.replace("-", " ").title()
            description = meta.get("description") or markdown("No description available.")
            live_url = meta.get("live_url") or ""
            full_description = meta.get("full_description") or ""

            # Extract GitHub repo URL from .git/config
            repo_url = ""
            if git_config.exists():
                try:
                    cfg = configparser.ConfigParser()
                    cfg.read(git_config, encoding="utf-8")
                    raw = cfg.get('remote "origin"', "url", fallback="")
                    if raw:
                        if raw.startswith("git@github.com:"):
                            repo_url = raw.replace("git@github.com:", "https://github.com/").removesuffix(".git")
                        elif raw.startswith("https://github.com/"):
                            repo_url = raw.removesuffix(".git")
                except Exception:
                    repo_url = ""

            projects.append(
                {
                    "name": name,
                    "slug": folder.name,
                    "description": description,  # already rendered as HTML
                    "full_description": full_description,
                    "repo_url": repo_url,
                    "live_url": live_url,
                    "template_url": "",
                }
            )

        except Exception as e:
            print(f"[WARN] Skipped {folder.name}: {e}")
            continue

    _projects_cache = projects
    _projects_cache_sig = sig
    _projects_cache_time = now
    return projects


# ---------------------------------------------------------
# Portfolio Data (Profile + Resume)
# ---------------------------------------------------------
portfolio_data: Dict[str, Any] = {
    "name": "Omar Gabriel Salvatierra Garcia",
    "title": "Full Stack Developer | Python & React Specialist",
    "headline": "Building scalable, automated, and maintainable systems.",
    "about": (
        "Full Stack Developer with strong expertise in Python, JavaScript, and Excel automation. "
        "Experienced in developing enterprise-level web applications and backend systems "
        "for institutional and private sector environments."
    ),
    "photo_url": "/static/img/profile.jpg",
    "socials": {
        "GitHub": "https://github.com/OmarSalvatierra99",
        "LinkedIn": "https://www.linkedin.com/in/omarsalvatierra",
        "Email": "mailto:omargabrielsalvatierragarcia@gmail.com",
    },
    "technical_skills": [
        "Python",
        "JavaScript",
        "Excel (Advanced)",
    ],
    "experience": [
        {
            "title": "Python Developer — OFS (Audit and Fiscal Oversight)",
            "period": "Sep 2024 – Present",
            "description": (
                "Developed automation pipelines in Python for public account preparation, "
                "reducing error rates and cycle times. Designed scalable XML processing tools "
                "and built AI-assisted models to streamline audit workflows."
            ),
        },
        {
            "title": "Full Stack Developer — Tornillera Central S.A. de C.V.",
            "period": "Apr 2023 – Sep 2024",
            "description": (
                "Developed a complete sales management system with inventory tracking, "
                "QR scanning, and role-based access control using Django and React."
            ),
        },
        {
            "title": "Python Developer — Comerzializador Plugar S.A. de C.V.",
            "period": "Jan 2018 – May 2022",
            "description": (
                "Built custom automation software for enterprise clients integrating "
                "data processing and reporting systems using Python and Excel."
            ),
        },
    ],
    "education": [
        "Master’s in Government Auditing — Iexe School of Public Policy (2024 – Present)",
        "B.Sc. in Business Management — Instituto Tecnológico de Apizaco (2018 – 2023)",
        "Data Science — Instituto Politécnico Nacional (2022 – 2023, Incomplete)",
        "Graphic Design — Cecyteh Metropolitano del Valle de México (2014 – 2017)",
    ],
    "languages": [
        "Spanish — Native",
        "English — Advanced",
        "French — Advanced",
    ],
    "resume": {"url": "/resume"},
}

# ---------------------------------------------------------
# Template context + security headers
# ---------------------------------------------------------
@app.context_processor
def inject_globals():
    return {"year": datetime.utcnow().year, "data": portfolio_data}


@app.after_request
def add_security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return resp


# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", projects=load_projects())


@app.route("/projects")
def projects():
    return render_template("projects.html", projects=load_projects())


@app.route("/projects/<slug>")
def project_detail(slug: str):
    project = next((p for p in load_projects() if p["slug"] == slug), None)
    if not project:
        abort(404)
    return render_template("project_detail.html", project=project)


@app.route("/projects/<slug>/<path:asset>")
def serve_project_asset(slug: str, asset: str):
    folder = PROJECTS_DIR / slug
    path = folder / asset
    if not (folder.is_dir() and path.exists()):
        abort(404)
    return send_from_directory(folder, asset)


# ---------------------------------------------------------
# Resume handling
# ---------------------------------------------------------
CV_DIR = BASE_DIR / "static" / "cv"
CV_DIR.mkdir(parents=True, exist_ok=True)
CV_FILENAME = "resume.pdf"
RESUME_UPLOAD_TOKEN = os.environ.get("RESUME_UPLOAD_TOKEN")
ALLOWED_EXTENSIONS = {"pdf"}


def _cv_path() -> Path:
    return CV_DIR / CV_FILENAME


@app.get("/resume")
def resume_download():
    path = _cv_path()
    if not path.exists():
        return jsonify({"status": "missing", "message": "Resume not uploaded yet."}), 404
    return send_file(path, as_attachment=False, download_name=CV_FILENAME, mimetype="application/pdf")


@app.post("/resume/upload")
def resume_upload():
    from flask import request
    token = request.headers.get("X-RESUME-TOKEN") or request.args.get("token")
    if not RESUME_UPLOAD_TOKEN or token != RESUME_UPLOAD_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401
    if "file" not in request.files:
        return jsonify({"error": "File part missing"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Only PDF is allowed"}), 400
    tmp_name = f"._tmp_{int(datetime.utcnow().timestamp())}.pdf"
    tmp_path = CV_DIR / secure_filename(tmp_name)
    file.save(tmp_path)
    tmp_path.replace(_cv_path())
    dest = _cv_path()
    return jsonify({
        "status": "ok",
        "public_url": "/resume",
        "size_bytes": dest.stat().st_size,
        "updated_at": datetime.utcfromtimestamp(dest.stat().st_mtime).isoformat() + "Z",
    }), 201


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)

