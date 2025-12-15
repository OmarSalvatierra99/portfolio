#!/usr/bin/env python3
# autodeploy_final.py — despliegue integral Flask/PHP
# Limpia __pycache__, recrea venv, genera servicios systemd y sites NGINX.
# Autodetecta usuario http/nginx y permisos correctos.

import os, sys, shutil, subprocess
from pathlib import Path
from datetime import datetime

# === CONFIGURACIÓN BASE ======================================================
ROOT = Path("/home/gabo/portfolio")
PROJECTS_DIR = ROOT / "projects"
SYSTEMD = Path("/etc/systemd/system")
NG_AVAIL = Path("/etc/nginx/sites-available")
NG_ENABLED = Path("/etc/nginx/sites-enabled")
CERT = Path("/etc/letsencrypt/live/omar-xyz.shop")
PHP_SOCK = Path("/run/php-fpm/php-fpm.sock")

PROJECTS = [
    ("portfolio","main",5000,"omar-xyz.shop"),
    ("cleanddoc","01-cleandoc",5001,"cleandoc.omar-xyz.shop"),
    ("pasanotas","02-pasanotas",5002,"pasanotas.omar-xyz.shop"),
    ("auditel","03-auditel",5003,"auditel.omar-xyz.shop"),
    ("lexnum","04-lexnum",5004,"lexnum.omar-xyz.shop"),
    ("obsidian-vps","05-obsidian-vps",5005,"obsidian-vps.omar-xyz.shop"),
    ("sasp","06-sasp",5006,"sasp.omar-xyz.shop"),
    ("sasp-php","07-sasp-php",None,"sasp-php.omar-xyz.shop"),
    ("sifet-estatales","09-sifet-estatales",5008,"sifet-estatales.omar-xyz.shop"),
    ("siif","10-siif",5009,"siif.omar-xyz.shop"),
    ("xml-php","11-xml-php",None,"xml-php.omar-xyz.shop"),
]

# === UTILIDADES ==============================================================
C = {"R":"\033[91m","G":"\033[92m","Y":"\033[93m","B":"\033[94m","N":"\033[0m"}
def log(msg,c="B"): print(f"{C[c]}{msg}{C['N']}")
def run(cmd,**kw): return subprocess.run(cmd,capture_output=True,text=True,**kw)
def exists(p): return p.exists() and p.is_file()

# === DETECCIÓN DE USUARIO ====================================================
def detect_web_user():
    """Detecta si el usuario del servicio web es nginx o http."""
    for candidate in ["nginx","http","www-data"]:
        try:
            subprocess.run(["id",candidate],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            return candidate
        except: continue
    return "http"

WEBUSER = detect_web_user()
log(f"🌐 Usuario web detectado: {WEBUSER}","Y")

# === LIMPIEZA ================================================================
def clean_cache():
    log("🧹 Limpiando __pycache__ y temporales...","B")
    for base in [ROOT, PROJECTS_DIR]:
        if not base.exists(): continue
        for pat in ["**/__pycache__","**/*.pyc","**/*.pyo","**/*.log","**/tmp","**/temp"]:
            for f in base.glob(pat):
                try:
                    if f.is_dir(): shutil.rmtree(f)
                    else: f.unlink()
                except: pass
    log("✓ Limpieza completa","G")

# === ENTORNOS FLASK ==========================================================
def ensure_flask_env(path):
    venv = path/"venv"
    pip = venv/"bin/pip"
    if venv.exists(): shutil.rmtree(venv)
    run(["python3","-m","venv",str(venv)],cwd=str(path))
    run([str(pip),"install","-q","--upgrade","pip"],cwd=str(path))
    run([str(pip),"install","-q","flask","gunicorn"],cwd=str(path))
    req = path/"requirements.txt"
    if req.exists():
        run([str(pip),"install","-q","-r",str(req)],cwd=str(path))
    ok = run([venv/"bin/python","-c","import flask,gunicorn"],cwd=str(path))
    log("✓ Entorno Flask listo" if ok.returncode==0 else "✗ Error en entorno Flask",
        "G" if ok.returncode==0 else "R")

# === SYSTEMD ================================================================
def gen_service(name,path,port):
    svc = SYSTEMD/f"portfolio-{name}.service"
    venv = path/"venv"
    svc.write_text(f"""[Unit]
Description={name} Flask App
After=network.target

[Service]
User={os.environ.get('SUDO_USER','gabo')}
WorkingDirectory={path}
Environment="PATH={venv}/bin"
ExecStart={venv}/bin/gunicorn --bind 127.0.0.1:{port} app:app
Restart=always

[Install]
WantedBy=multi-user.target
""")
    return svc

# === NGINX ================================================================
def gen_nginx_flask(domain,port,is_main=False):
    listen = "listen 80 default_server;" if is_main else "listen 80;"
    return f"""server {{
    {listen}
    server_name {domain};
    return 301 https://$server_name$request_uri;
}}

server {{
    listen 443 ssl;
    http2 on;
    server_name {domain};
    ssl_certificate {CERT}/fullchain.pem;
    ssl_certificate_key {CERT}/privkey.pem;
    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }}
}}"""

def gen_nginx_php(domain, root):
    """NGINX robusto con rutas absolutas y compatibilidad PHP-FPM."""
    return f"""server {{
    listen 80;
    server_name {domain};
    return 301 https://$server_name$request_uri;
}}

server {{
    listen 443 ssl;
    http2 on;
    server_name {domain};
    root {root};
    index index.php index.html;
    ssl_certificate {CERT}/fullchain.pem;
    ssl_certificate_key {CERT}/privkey.pem;

    location ~ /\\. {{
        deny all;
    }}

    location ~ \\.php$ {{
        include fastcgi_params;
        fastcgi_pass unix:{PHP_SOCK};
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME {root}$fastcgi_script_name;
        fastcgi_param DOCUMENT_ROOT {root};
        fastcgi_param PATH_INFO $fastcgi_path_info;
    }}

    location / {{
        try_files $uri $uri/ /index.php?$args;
    }}
}}"""

# === REINICIO SERVICIOS =====================================================
def restart_service(name):
    svc = f"portfolio-{name}"
    run(["systemctl","daemon-reload"])
    run(["systemctl","enable",svc],check=False)
    r = run(["systemctl","restart",svc],check=False)
    if r.returncode == 0:
        log(f"✓ {name} iniciado correctamente","G")
        return True
    else:
        err = run(["journalctl","-u",svc,"-n","3","--no-pager"])
        log(f"✗ {name} falló:\n{err.stdout.strip()}","R")
        return False

# === CORRECCIÓN DE PERMISOS =================================================
def fix_permissions(path):
    run(["chown","-R",f"gabo:{WEBUSER}",str(path)],check=False)
    run(["chmod","-R","755",str(path)],check=False)
    log(f"✓ Permisos corregidos para {WEBUSER} en {path.name}","Y")

# === PROCESO PRINCIPAL ======================================================
def main():
    if os.geteuid()!=0:
        log("✗ Ejecuta con sudo python3 autodeploy_final.py","R")
        sys.exit(1)

    log(f"🚀 AUTODEPLOY FINAL {datetime.now().strftime('%H:%M:%S')}","B")
    clean_cache()
    report = []

    for name,folder,port,url in PROJECTS:
        path = ROOT if name=="portfolio" else PROJECTS_DIR/folder
        if not path.exists():
            log(f"⚠ {name}: carpeta no encontrada","Y")
            report.append((name,"no existe"))
            continue

        app = path/"app.py"
        php_root = path/"index.php"
        php_pub = path/"public"/"index.php"

        try:
            fix_permissions(path)

            # Flask
            if app.exists() and port:
                log(f"🔧 Flask → {name} ({url})","B")
                ensure_flask_env(path)
                gen_service(name,path,port)
                ng = NG_AVAIL/name
                ng.write_text(gen_nginx_flask(url,port,name=="portfolio"))
                dst = NG_ENABLED/ng.name
                if dst.exists() or dst.is_symlink(): dst.unlink()
                dst.symlink_to(ng)
                ok = restart_service(name)
                report.append((name,"Flask OK" if ok else "Flask DOWN"))

            # PHP
            elif php_root.exists() or php_pub.exists():
                root = path/"public" if php_pub.exists() else path
                log(f"⚙ PHP → {name} ({url}) raíz {root}","B")
                ng = NG_AVAIL/name
                ng.write_text(gen_nginx_php(url,root))
                dst = NG_ENABLED/ng.name
                if dst.exists() or dst.is_symlink(): dst.unlink()
                dst.symlink_to(ng)
                log(f"✓ Sitio PHP configurado: {url}","G")
                report.append((name,"PHP OK"))

            else:
                log(f"… Omitido {name} (sin app.py ni PHP)","Y")
                report.append((name,"omitido"))

        except Exception as e:
            log(f"✗ Error en {name}: {e}","R")
            report.append((name,"error"))

    run(["nginx","-t"],check=False)
    run(["systemctl","reload","nginx"],check=False)
    log("🔁 nginx recargado","G")

    log("\n📋 REPORTE FINAL","B")
    for n,s in report:
        color = "G" if "OK" in s else "Y" if "omitido" in s else "R"
        print(f"{C[color]}{n:<25} {s}{C['N']}")
    log("✅ Despliegue completado","G")

# === EJECUCIÓN ==============================================================
if __name__=="__main__":
    main()

