# Production Deployment Guide

## Quick Deploy

Run the automated deployment script as root from the portfolio directory:

```bash
cd /home/gabo/portfolio
sudo python3 scripts/deploy_all.py
```

## What the Script Does

The `deploy_all.py` script is **idempotent** (safe to run multiple times) and performs:

1. **Project Discovery** — Scans `projects/` for Flask apps with `app.py` and `venv` (skips `sasp-php`)
2. **Port Assignment** — Assigns stable sequential ports (5001+), keeping `pasanotas` on 5002
3. **Dependency Installation** — Installs/upgrades dependencies from requirements.txt, ensures gunicorn is installed
4. **Flask App Validation** — Validates that `app:app` can be imported before deployment (fails fast on invalid entry points)
5. **Systemd Services** — Creates services for main portfolio (`portfolio-main`) and projects (`portfolio-<project>`)
   - **Bind Address**: Services bind to `0.0.0.0:<port>` (accessible via public IP 31.97.8.56)
   - **Absolute Paths**: Uses absolute path to `venv/bin/gunicorn`
6. **Nginx Configs** — Safely creates configs in `/etc/nginx/sites-available/` then symlinks to `sites-enabled/`
   - **Critical Fix**: Always writes config file BEFORE creating symlink to prevent FileNotFoundError
   - Ensures both directories exist before writing
   - Verifies config file exists before symlinking
   - Ensures `include /etc/nginx/sites-enabled/*;` is present in `/etc/nginx/nginx.conf`
   - Disables `/etc/nginx/sites-enabled/default` to prevent conflicts
7. **Domain Binding** — Maps each service to its configured domain
8. **Service Reload** — Tests Nginx config with `nginx -t`, then reloads systemd and Nginx only if configs changed
9. **Service Start** — Enables and restarts all project services

## Port Assignments

Projects are assigned ports deterministically (alphabetically):

| Project | Port | Domain | Service Name |
|---------|------|--------|--------------|
| **portfolio (main)** | **5000** | omar-xyz.shop | portfolio-main |
| auditel | 5001 | auditel.omar-xyz.shop | portfolio-auditel |
| cleandoc | 5003 | cleandoc.omar-xyz.shop | portfolio-cleandoc |
| lexnum | 5004 | lexnum.omar-xyz.shop | portfolio-lexnum |
| obsidian-vps | 5005 | obsidian-vps.omar-xyz.shop | portfolio-obsidian-vps |
| **pasanotas** | **5002** | pasanotas.omar-xyz.shop | portfolio-pasanotas |
| sasp | 5006 | sasp.omar-xyz.shop | portfolio-sasp |
| scan-actas-nacimiento | 5007 | actas.omar-xyz.shop | portfolio-scan-actas-nacimiento |
| sifet-estatales | 5008 | sifet-estatales.omar-xyz.shop | portfolio-sifet-estatales |
| siif | 5009 | siif.omar-xyz.shop | portfolio-siif |

**Notes:**
- Main portfolio runs on port 5000 (service: `portfolio-main`)
- `pasanotas` is always assigned port 5002 (fixed requirement)
- `sasp-php` is automatically skipped (not a Flask app)

## Accessing Services

Each service is accessible in two ways:

### 1. Via Domain (through Nginx)
- Main Portfolio: http://omar-xyz.shop
- Projects: http://<project>.omar-xyz.shop (e.g., http://auditel.omar-xyz.shop)

### 2. Via Public IP (direct to Gunicorn)
- Main Portfolio: http://31.97.8.56:5000
- Projects: http://31.97.8.56:<port> (e.g., http://31.97.8.56:5001)

**Important:** Services bind to `0.0.0.0:<port>` which means they're accessible from any network interface, including the public IP address.

## Service Management

The main portfolio gets `portfolio-main` service, and each project gets `portfolio-<project>`:

```bash
# View main portfolio logs
sudo journalctl -u portfolio-main -f

# View project logs
sudo journalctl -u portfolio-auditel -f

# Restart the main portfolio
sudo systemctl restart portfolio-main

# Restart a project service
sudo systemctl restart portfolio-pasanotas

# Check status
sudo systemctl status portfolio-cleandoc

# Stop a service
sudo systemctl stop portfolio-lexnum

# View all portfolio services
systemctl list-units 'portfolio-*'

# Check if all services are active
systemctl is-active portfolio-*
```

## Nginx Management

Nginx configs are created in `/etc/nginx/sites-available/` and symlinked to `sites-enabled/`:

```bash
# Test Nginx configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# View a project's Nginx config
cat /etc/nginx/sites-available/auditel

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

## Adding a New Project

1. Create project directory in `projects/`:
   ```bash
   mkdir projects/my-new-project
   cd projects/my-new-project
   ```

2. Set up Flask app:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install flask gunicorn
   # Create app.py
   ```

3. Add domain mapping to `scripts/deploy_all.py`:
   ```python
   DOMAIN_MAP = {
       # ... existing mappings ...
       "mynewproject.omar-xyz.shop": "my-new-project",
   }
   ```

4. Run deployment:
   ```bash
   sudo python3 scripts/deploy_all.py
   ```

## Troubleshooting

### Service won't start

```bash
# Check service status and logs
sudo systemctl status portfolio-<project>
sudo journalctl -u portfolio-<project> -n 50

# Common issues:
# - Missing venv: cd projects/<project> && python3 -m venv venv
# - Missing dependencies: cd projects/<project> && source venv/bin/activate && pip install -r requirements.txt
# - Wrong permissions: sudo chown -R $USER:$USER projects/<project>
```

### Nginx errors

```bash
# Test configuration
sudo nginx -t

# Common issues:
# - Port conflict: Check if port is already in use with: sudo lsof -i :<port>
# - Syntax error: Review /etc/nginx/sites-available/<project>
```

### Port conflicts

```bash
# Check what's using a port
sudo lsof -i :5002

# Kill a process using a port
sudo kill $(sudo lsof -t -i :5002)
```

## Manual Service File Location

If you need to manually edit a service:

```bash
# Edit service
sudo nano /etc/systemd/system/portfolio-<project>.service

# Reload systemd
sudo systemctl daemon-reload

# Restart service
sudo systemctl restart portfolio-<project>
```

## Manual Nginx Config Location

```bash
# Edit Nginx config
sudo nano /etc/nginx/sites-available/<project>

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

## SSL/HTTPS Setup (Optional)

To add HTTPS with Let's Encrypt:

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate for a domain
sudo certbot --nginx -d auditel.omar-xyz.shop

# Certbot will automatically update the Nginx config
# Repeat for each domain
```

## Deployment Checklist

Before running the script:

- [ ] All projects have `venv/` directory with dependencies installed
- [ ] All projects have `app.py` with Flask app named `app`
- [ ] DNS A records point to server IP (31.97.8.56)
- [ ] Nginx is installed: `sudo apt install nginx`
- [ ] Script is run as root: `sudo python3 scripts/deploy_all.py`

After deployment:

- [ ] Check all services are active: `systemctl list-units 'portfolio-*'`
- [ ] Test Nginx config: `sudo nginx -t`
- [ ] Verify domains resolve: `curl -I http://auditel.omar-xyz.shop`
- [ ] Check logs for errors: `sudo journalctl -u portfolio-* --since "5 minutes ago"`

## Re-deployment

The script is idempotent. To re-deploy after code changes:

```bash
# 1. Pull latest code
cd /home/gabo/portfolio
git pull

# 2. Update project dependencies if needed
cd projects/<project>
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 3. Re-run deployment (only restarts services)
cd /home/gabo/portfolio
sudo python3 scripts/deploy_all.py
```

## Performance Tuning

To adjust Gunicorn workers in service files:

```bash
# Edit the script to change worker count (default: 2)
# In create_systemd_service() function:
ExecStart={venv_gunicorn} --bind 127.0.0.1:{port} --workers 4 --timeout 120 app:app
```

Recommended workers: `(2 x CPU cores) + 1`

## Security Notes

- All services run as the user who owns the portfolio directory
- **Services bind to `0.0.0.0:<port>`** — Accessible via public IP (31.97.8.56) and domain names
- Nginx acts as reverse proxy with security headers for domain access
- Max upload size: 10MB (configurable in Nginx config)
- Restart policy: Services auto-restart on failure after 10 seconds
- **Firewall**: Ensure firewall allows inbound traffic on ports 5000-5009 for direct IP access
- **SSL/TLS**: Consider adding HTTPS via Let's Encrypt for production (see SSL/HTTPS Setup section)

## Error Handling & Safety

The deployment script includes robust error handling:

### Nginx Symlink Safety
The script prevents the `FileNotFoundError: No such file or directory` error by:

1. **Creating parent directories first** — `/etc/nginx/sites-available/` and `/etc/nginx/sites-enabled/`
2. **Writing config files BEFORE symlinking** — Never creates symlink before the target file exists
3. **Verifying file existence** — Checks config file exists before creating symlink
4. **Removing stale symlinks** — Cleans up old symlinks before creating new ones

### Idempotent Operation
- Safe to run multiple times without side effects
- Only restarts services when configs change
- Preserves existing configs if unchanged
- Automatically detects and skips non-Flask projects

### Configuration Validation
- Tests Nginx config with `nginx -t` before reload
- Verifies all venv directories exist before creating services
- Checks service status after start and reports failures

### Error Recovery
If deployment fails:

```bash
# Check which step failed
sudo python3 scripts/deploy_all.py

# Common fixes:
# 1. Missing Nginx directories
sudo mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled

# 2. Permission issues
sudo chown -R $USER:$USER /home/gabo/portfolio

# 3. Missing venv for a project
cd /home/gabo/portfolio/projects/<project>
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Clean up broken symlinks
sudo find /etc/nginx/sites-enabled -xtype l -delete

# 5. Re-run deployment
cd /home/gabo/portfolio
sudo python3 scripts/deploy_all.py
```
