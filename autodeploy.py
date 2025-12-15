#!/usr/bin/env python3
# autodeploy.py — despliegue rápido Flask/PHP con cache cleanup, servicios y nginx honestos.

import os, sys, shutil, subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path("/home/gabo/portfolio")
PROJECTS_DIR = ROOT / "projects"
SYSTEMD = Path("/etc/systemd/system")
NG_AVAIL = Path("/etc/nginx/sites-available")
NG_ENABLED = Path("/etc/nginx/sites-enabled")
CERT_DIR = Path("/etc/letsencrypt/live/omar-xyz.shop")
PHP_SOCK = Path("/run/php-fpm/php-fpm.sock")

PROJECTS = [
    ("portfolio","main",5000,"omar-xyz.shop"),
    ("cleanddoc","01-cleandoc",5001,"cleandoc.omar-xyz.shop"),
    ("pasanotas","02-pasanotas",5002,"pasanotas.omar-xyz.shop"),
    ("auditel","03-auditel",5003,"audite.omar-xyz.shop"),
    ("lexnum","04-lexnum",5004,"lexnum.omar-xyz.shop"),
    ("obsidian-vps","05-obsidian-vps",5005,"obsidian-vps.omar-xyz.shop"),
    ("sasp","06-sasp",5006,"sasp.omar-xyz.shop"),
    ("sasp-php","07-sasp-php",None,"sasp-php.omar-xyz.shop"),
    ("scan-actas-nacimientos","08-scan-actas-nacimiento",5007,"actas.omar-xyz.shop"),
    ("sifet-estatales","09-sifet-estatales",5008,"sifet-estatales.omar-xyz.shop"),
    ("siif","10-siif",5009,"siif.omar-xyz.shop"),
    ("xml-php","11-xml-php",None,"xml-php.omar-xyz.shop"),
]

C = {"R":"\033[91m","G":"\033[92m","Y":"\033[93m","B":"\033[94m","N":"\033[0m"}

def log(t,c="B"): print(f"{C[c]}{t}{C['N']}")
def run(cmd,**kw): return subprocess.run(cmd,capture_output=True,text=True,**kw)

def clean_cache():
    log("🧹 Limpiando __pycache__ y temporales...","B")
    for p in [ROOT,PROJECTS_DIR]:
        if not p.exists(): continue
        for pat in ["**/__pycache__","**/*.pyc","**/*.pyo","**/*.log","**/tmp","**/temp"]:
            for f in p.glob(pat):
                try:
                    if f.is_dir(): shutil.rmtree(f)
                    else: f.unlink()
                except: pass
    log("✓ Limpieza completa","G")

def gen_service(name,path,port):
    svc = SYSTEMD/f"portfolio-{name}.service"
    venv = path/"venv"
    content=f"""[Unit]
Description={name} Flask
After=network.target

[Service]
User={os.environ.get('SUDO_USER','gabo')}
WorkingDirectory={path}
Environment="PATH={venv}/bin"
ExecStart={venv}/bin/gunicorn --bind 127.0.0.1:{port} app:app
Restart=always

[Install]
WantedBy=multi-user.target
"""
    svc.write_text(content)
    return svc

def gen_nginx_flask(domain,port,is_main=False):
    listen = "listen 80 default_server;" if is_main else "listen 80;"
    return f"""server {{
    {listen}
    server_name {domain};
    return 301 https://$server_name$request_uri;
}}
server {{
    listen 443 ssl http2;
    server_name {domain};
    ssl_certificate {CERT_DIR}/fullchain.pem;
    ssl_certificate_key {CERT_DIR}/privkey.pem;
    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }}
}}"""

def gen_nginx_php(domain,root):
    return f"""server {{
    listen 80;
    server_name {domain};
    return 301 https://$server_name$request_uri;
}}
server {{
    listen 443 ssl http2;
    server_name {domain};
    root {root};
    index index.php;
    ssl_certificate {CERT_DIR}/fullchain.pem;
    ssl_certificate_key {CERT_DIR}/privkey.pem;
    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}
    location ~ \\.php$ {{
        include fastcgi_params;
        fastcgi_pass unix:{PHP_SOCK};
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    }}
}}"""

def recreate_flask(path):
    venv = path/"venv"
    if venv.exists(): shutil.rmtree(venv)
    run(["python3","-m","venv",str(venv)],cwd=str(path))
    pip=venv/"bin/pip"; req=path/"requirements.txt"
    if req.exists(): run([str(pip),"install","-q","-r",str(req)],cwd=str(path))

def main():
    if os.geteuid()!=0:
        log("✗ Ejecuta con sudo","R"); sys.exit(1)
    log(f"🚀 AUTODEPLOY {datetime.now().strftime('%H:%M:%S')}","B")
    clean_cache()
    report=[]
    for name,folder,port,url in PROJECTS:
        path = ROOT if name=="portfolio" else PROJECTS_DIR/folder
        if not path.exists(): log(f"⚠ {name}: carpeta no encontrada","Y"); report.append((name,"no existe")); continue
        app=path/"app.py"; php=path/"index.php"; pub=path/"public"/"index.php"
        try:
            if app.exists() and port:
                log(f"⚙ Flask → {name} ({url})","B")
                recreate_flask(path)
                svc=gen_service(name,path,port)
                ng=NG_AVAIL/name; ng.write_text(gen_nginx_flask(url,port,name=="portfolio"))
                dst=NG_ENABLED/ng.name
                if dst.exists() or dst.is_symlink(): dst.unlink()
                dst.symlink_to(ng)
                run(["systemctl","daemon-reload"])
                run(["systemctl","enable",f"portfolio-{name}"],check=False)
                r=run(["systemctl","restart",f"portfolio-{name}"],check=False)
                if r.returncode==0:
                    log(f"✓ {name} servicio activo","G"); report.append((name,"Flask ok"))
                else:
                    log(f"✗ {name} fallo al iniciar","R"); report.append((name,"Flask error"))
            elif php.exists() or pub.exists():
                root=path/"public" if pub.exists() else path
                ng=NG_AVAIL/name; ng.write_text(gen_nginx_php(url,root))
                dst=NG_ENABLED/ng.name
                if dst.exists() or dst.is_symlink(): dst.unlink()
                dst.symlink_to(ng)
                log(f"✓ PHP configurado {url}","G")
                report.append((name,"PHP ok"))
            else:
                log(f"… Omitido {name} (sin app.py ni PHP)","Y"); report.append((name,"omitido"))
        except Exception as e:
            log(f"✗ Error en {name}: {e}","R")
            report.append((name,"error"))

    run(["nginx","-t"],check=False)
    run(["systemctl","reload","nginx"],check=False)
    log("🔁 nginx recargado","G")

    log("\n📋 REPORTE FINAL","B")
    for n,s in report:
        c="G" if "ok" in s else "Y" if "omitido" in s else "R"
        print(f"{C[c]}{n:<25} {s}{C['N']}")
    log("✅ Autodeploy finalizado","G")

if __name__=="__main__":
    main()

