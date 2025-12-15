#!/usr/bin/env python3
# gitforce.py — actualiza .gitignore y sincroniza todos los proyectos forzando prioridad local

import os, subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path("/home/gabo/portfolio")
PROJECTS = [ROOT] + [p for p in (ROOT / "projects").iterdir() if p.is_dir() and not p.name.startswith(".")]

C = {"R":"\033[91m","G":"\033[92m","Y":"\033[93m","B":"\033[94m","N":"\033[0m"}

GITIGNORE_CONTENT = """# Python cache
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
.env.*
!.env.example

# Flask
instance/
*.db
*.sqlite*
*.log
*.pid

# Environment
.env
.env.* 
!.env.example

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
"""

def log(msg,c="B"): print(f"{C[c]}{msg}{C['N']}")
def run(cmd,cwd=None): return subprocess.run(cmd,cwd=cwd,capture_output=True,text=True)

def ensure_gitignore(path: Path):
    gi = path / ".gitignore"
    if not gi.exists() or "CLAUDE.md" not in gi.read_text():
        gi.write_text(GITIGNORE_CONTENT)
        log(f"✓ .gitignore actualizado en {path.name}","G")
        return True
    else:
        log(f"→ .gitignore ya correcto en {path.name}","B")
        return False

def commit_and_push(path: Path):
    if not (path / ".git").exists():
        log(f"⚠ No es repo git: {path}","Y")
        return "no-git"
    run(["git","add","."],cwd=path)
    msg=f"Auto-update .gitignore {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    commit=run(["git","commit","-m",msg],cwd=path)
    if "nothing to commit" in commit.stdout:
        log(f"→ Sin cambios en {path.name}","Y")
        return "no-change"
    push=run(["git","push","--force-with-lease","origin","HEAD"],cwd=path)
    if push.returncode==0:
        log(f"✓ Push completado (prioridad local): {path.name}","G")
        return "ok"
    else:
        log(f"✗ Error en push {path.name}: {push.stderr.strip()}","R")
        return "error"

def main():
    if os.geteuid()!=0:
        log("✗ Ejecuta con sudo python3 gitforce.py","R")
        return
    log("🚀 Iniciando gitforce (actualización y push forzado)","B")
    report=[]
    for proj in PROJECTS:
        updated = ensure_gitignore(proj)
        state = commit_and_push(proj)
        report.append((proj.name,state))

    log("\n📋 REPORTE FINAL","B")
    for n,s in report:
        c="G" if s=="ok" else "Y" if "no" in s else "R"
        print(f"{C[c]}{n:<25} {s}{C['N']}")
    log("✅ Operación completada","G")

if __name__=="__main__":
    main()

