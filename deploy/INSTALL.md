# Shift Scheduler — Install on Linux home server

These steps assume Debian/Ubuntu, `uv` installed system-wide at `/usr/local/bin/uv`,
and Cloudflare already terminating HTTPS for the existing port-5055 app (we'll add a second hostname).

## 1. System user and directories

```bash
sudo useradd --system --create-home --home-dir /opt/shift-scheduler --shell /usr/sbin/nologin shifts
sudo mkdir -p /var/lib/shift-scheduler
sudo chown shifts:shifts /var/lib/shift-scheduler
sudo install -d -o shifts -g shifts /opt/shift-scheduler
```

## 2. Deploy code

```bash
sudo -u shifts git clone <repo-url> /opt/shift-scheduler
cd /opt/shift-scheduler
sudo -u shifts uv sync
```

## 3. Generate password hash and session secret

```bash
sudo -u shifts uv run python -m shift_scheduler.cli set-password
# copy the printed ADMIN_PASSWORD_HASH=... line

python3 -c "import secrets; print('SESSION_SECRET=' + secrets.token_urlsafe(48))"
```

## 4. Write `/etc/shift-scheduler.env`

```bash
sudo install -m 600 -o root -g shifts /dev/stdin /etc/shift-scheduler.env <<'EOF'
ADMIN_PASSWORD_HASH=<paste from previous step>
SESSION_SECRET=<paste from previous step>
DATABASE_URL=sqlite:////var/lib/shift-scheduler/data.db
COOKIE_SECURE=true
EOF
```

## 5. Apply schema

```bash
cd /opt/shift-scheduler
sudo -u shifts DATABASE_URL=sqlite:////var/lib/shift-scheduler/data.db \
  uv run alembic upgrade head
```

## 6. Install and enable systemd unit

```bash
sudo cp deploy/shift-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now shift-scheduler
sudo systemctl status shift-scheduler
```

## 7. Cloudflare

Add a DNS record (or tunnel route) for `shifts.<your-domain>` pointing at this host on port 2323.
The app binds to 127.0.0.1, so use a Cloudflare Tunnel (preferred) or a local reverse-proxy
that exposes 2323 to the tunnel. TLS terminates at Cloudflare; the cookie's `Secure` flag
relies on that.

## 8. Backups

Add a nightly cron for `shifts`:

```cron
0 3 * * * sqlite3 /var/lib/shift-scheduler/data.db ".backup '/var/backups/shifts-$(date +\%F).db'" && find /var/backups -name 'shifts-*.db' -mtime +14 -delete
```

## 9. Update procedure

```bash
cd /opt/shift-scheduler
sudo -u shifts git pull
sudo -u shifts uv sync
sudo -u shifts DATABASE_URL=sqlite:////var/lib/shift-scheduler/data.db \
  uv run alembic upgrade head
sudo systemctl restart shift-scheduler
```
