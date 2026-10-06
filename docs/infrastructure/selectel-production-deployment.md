# Ivently — Selectel Production Deployment Guide

**Document Version:** 1.1.0  
**Target Environment:** Selectel Moscow VDS  
**Server IP:** `135.106.172.157`  
**Domain:** `https://iventlyapp.ru`  
**Operating System:** Ubuntu 24.04 LTS 64-bit  
**Specifications:** 2 vCPU, 4 GB RAM, 50 GB NVMe  
**Status:** Staging / Production Deployment Runbook (HTTPS Active)  
**Security Level:** Production-Hardened (No secrets committed)

---

## 1. System Architecture Overview

The Ivently production stack on Selectel is designed as a minimal, reliable, self-contained architecture using standard Docker Compose:

```
[ Internet / Telegram Clients ]
               │
               ▼  Ports 80 & 443 (Domain: iventlyapp.ru)
   ┌───────────────────────┐
   │ Caddy Reverse Proxy   │ (Automatic Let's Encrypt TLS, HTTP/2 & HTTP/3)
   └───────────┬───────────┘
               │  Internal Docker Network (`ivently-net`)
       ┌───────┴───────┐
       ▼               ▼
┌─────────────┐ ┌──────────────┐
│   Static    │ │   FastAPI    │
│  /uploads   │ │   Monolith   │ (Python 3.13 + React 19 SPA)
│ (from disk) │ │ (Port 8000)  │
└─────────────┘ └──────┬───────┘
                       │ Internal Docker Network (Port 5432)
                       ▼
               ┌──────────────┐
               │  PostgreSQL  │ (postgres:16-alpine)
               │      16      │ Volume: /var/lib/ivently/postgres_data
               └──────────────┘
```

- **Zero Bloat:** Zero Kubernetes, zero Redis, zero Celery, zero microservices.
- **Persistent Data:**
  - Database: `/var/lib/ivently/postgres_data`
  - Uploads: `/var/lib/ivently/uploads`
  - TLS / ACME certificates: Docker volume `caddy_data`

---

## 2. Server Prerequisites & One-Time Preparation

### 2.1 SSH Key Access Setup
Selectel Moscow VDS requires the registered Ed25519 SSH public key in `/root/.ssh/authorized_keys`:
```bash
# Public key to register in Selectel:
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAoFwfcB8BQ4wsfk9UsCJvvu8vBDHTNAYvNG9XIIEMVC ivently-selectel-2026
```

### 2.2 Server Package Installation & Timezone
```bash
# Update repositories and install base packages
apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ufw \
    ca-certificates \
    gnupg \
    tar \
    gzip

# Set Moscow timezone
timedatectl set-timezone Europe/Moscow
```

### 2.3 Docker Engine & Docker Compose Installation
```bash
# Add Docker official GPG key and repository
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable and start Docker service
systemctl enable --now docker
```

### 2.4 Firewall Configuration (UFW)
```bash
# Strict firewall: allow only essential services
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP ACME challenge'
ufw allow 443/tcp comment 'HTTPS Caddy'
ufw --force enable

# PostgreSQL port 5432 is strictly private to Docker and NEVER opened in UFW.
```

---

## 3. Directory Layout & Docker Compose Configuration

### 3.1 Host Directory Structure
```bash
mkdir -p /opt/ivently
mkdir -p /var/lib/ivently/postgres_data
mkdir -p /var/lib/ivently/uploads/covers
mkdir -p /var/lib/ivently/uploads/avatars
mkdir -p /var/backups/ivently/postgres

# Secure permissions
chmod 700 /var/lib/ivently/postgres_data
chmod 755 /var/lib/ivently/uploads
chmod 700 /var/backups/ivently
```

### 3.2 `/opt/ivently/docker-compose.yml`
```yaml
services:
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
      - /var/lib/ivently/uploads:/var/www/uploads:ro
    depends_on:
      app:
        condition: service_healthy
    networks:
      - ivently-net

  app:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - /var/lib/ivently/uploads:/app/uploads
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 25s
    networks:
      - ivently-net

  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ivently_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ivently_prod
    volumes:
      - /var/lib/ivently/postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ivently_user -d ivently_prod"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - ivently-net

volumes:
  caddy_data:
  caddy_config:

networks:
  ivently-net:
    driver: bridge
```

### 3.3 `/opt/ivently/Caddyfile`
```caddy
iventlyapp.ru {
    encode gzip zstd

    # Direct static file serving for uploads with immutable caching
    handle_path /uploads/* {
        root * /var/www/uploads
        file_server
        header Cache-Control "public, max-age=2592000, immutable"
    }

    # Proxy all API requests and SPA assets to FastAPI
    handle {
        reverse_proxy app:8000 {
            header_up X-Forwarded-Proto https
        }
    }
}
```

---

## 4. Environment Variables Configuration (`/opt/ivently/.env`)

Create the file `/opt/ivently/.env` with permissions `600`:

```ini
# ==================================================
# Application & Network
# ==================================================
APP_NAME=Ivently
APP_ENV=production
DEBUG=false
PORT=8000
HOST=0.0.0.0
PUBLIC_HOST=iventlyapp.ru
CORS_ORIGINS=*

# ==================================================
# Database (Internal Docker Network)
# ==================================================
DB_PASSWORD=<GENERATE_STRONG_RANDOM_PASSWORD_HERE>
DATABASE_URL=postgresql+asyncpg://ivently_user:${DB_PASSWORD}@db:5432/ivently_prod

# ==================================================
# Persistent Storage
# ==================================================
STORAGE_BACKEND=local
STORAGE_LOCAL_DIR=/app/uploads

# ==================================================
# Security
# ==================================================
SECRET_KEY=<GENERATE_32_BYTES_RANDOM_HEX_KEY_HERE>
AUTH_DATE_MAX_AGE_SECONDS=86400

# ==================================================
# Telegram Bot API
# ==================================================
TELEGRAM_BOT_TOKEN=<YOUR_BOT_TOKEN_FROM_BOTFATHER>
TELEGRAM_BOT_USERNAME=Ivently_bot
TELEGRAM_MINI_APP_URL=https://t.me/Ivently_bot/app
TELEGRAM_MINI_APP_SHORT_NAME=app
ADMIN_USER_IDS=123456789

# ==================================================
# Monetization / Payments (Must remain false)
# ==================================================
PAYMENTS_ENABLED=false
PRO_MONTHLY_PRICE_RUB=499.0
PRO_SUBSCRIPTION_DAYS=30
```

---

## 5. Railway Database & Uploads Migration Runbook

### 5.1 Exporting Railway Database (Zero Downtime)
```bash
# On local workstation or server:
pg_dump "${RAILWAY_DATABASE_URL}" \
    --format=custom \
    --no-owner \
    --no-acl \
    --verbose \
    --file=ivently_railway_prod.dump
```

### 5.2 Restoring to Selectel PostgreSQL
```bash
# Restore custom dump into the colocated database container:
docker compose -f /opt/ivently/docker-compose.yml exec -T db pg_restore \
    -U ivently_user \
    -d ivently_prod \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    --verbose < ivently_railway_prod.dump
```

### 5.3 Transferring Uploaded Media
```bash
# Sync covers and avatars to Selectel host:
rsync -avzP ./uploads/ root@135.106.172.157:/var/lib/ivently/uploads/
chown -R 1000:1000 /var/lib/ivently/uploads
```

---

## 6. Telegram Webhook Switch & Rollback Procedures

### 6.1 Switching Webhook to Selectel
Once the Selectel deployment is healthy and HTTPS is verified:
```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d '{
        "url": "https://<YOUR_DOMAIN>/api/v1/telegram/webhook",
        "allowed_updates": ["inline_query", "message"]
    }'
```

### 6.2 Emergency Rollback to Railway (< 2 Minutes)
If any critical defect is identified on Selectel, revert immediately without data loss:
```bash
# Restore live traffic to Railway:
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d '{
        "url": "https://ivently.up.railway.app/api/v1/telegram/webhook",
        "allowed_updates": ["inline_query", "message"]
    }'
```

---

## 7. Automated Backups & Disaster Recovery

### 7.1 Automated Daily Database Backup Script
Save script to `/usr/local/bin/backup-ivently.sh` (`chmod +x`):
```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/var/backups/ivently/postgres"
DATE=$(date +"%Y%m%d_%H%M%S")
FILENAME="${BACKUP_DIR}/ivently_backup_${DATE}.dump"

mkdir -p "${BACKUP_DIR}"

# Execute pg_dump from container
docker compose -f /opt/ivently/docker-compose.yml exec -T db pg_dump \
    -U ivently_user \
    -d ivently_prod \
    --format=custom \
    --no-owner \
    --no-acl > "${FILENAME}"

# Retain backups for 14 days
find "${BACKUP_DIR}" -type f -name "*.dump" -mtime +14 -delete
```

### 7.2 Crontab Schedule
```bash
# Recommended via /etc/cron.d/ivently-backup (Daily at 03:00 Moscow Time):
echo "0 3 * * * root /usr/local/bin/backup-ivently.sh >> /var/log/ivently_backup.log 2>&1" > /etc/cron.d/ivently-backup
chmod 644 /etc/cron.d/ivently-backup
```

---

## 8. Monthly Cost Model Summary

| Item | Specification | Estimated Monthly Cost (RUB) |
|---|---|---|
| Selectel VDS | 2 vCPU, 4 GB RAM, 50 GB NVMe | ~800 – 1,150 ₽ |
| Public Dedicated IPv4 | 1x Static IPv4 | ~150 – 200 ₽ |
| Database | Colocated PostgreSQL 16 in Docker | 0 ₽ (included) |
| Storage | Local NVMe `/var/lib/ivently/uploads` | 0 ₽ (included) |
| **Total Monthly Cost** | | **~950 – 1,350 ₽ / month** |

---

## 9. Current Deployment Status & Verification Matrix

- **Server IP**: `135.106.172.157` (Selectel Moscow)
- **Domain**: `https://iventlyapp.ru` (delegation active, DNS resolves globally to `135.106.172.157`)
- **Public TLS / SSL**: Valid Let's Encrypt production certificate issued automatically by Caddy (HTTP/2 & HTTP/3 ALPN, 90-day automatic renewal cycle).
- **HTTP -> HTTPS Redirect**: Fully functional (HTTP 308 Permanent Redirect on port 80).
- **Base OS & Security**: Ubuntu 24.04 LTS, UFW active (22, 80, 443 allowed; 5432 strictly internal).
- **Containers**:
  - `ivently-caddy-1` (`caddy:2-alpine`): Running on ports 80 & 443.
  - `ivently-app-1` (`ivently-app:latest`): Running on internal port 8000, `HEALTHY`.
  - `ivently-db-1` (`postgres:16-alpine`): Running on internal port 5432, `HEALTHY`.
- **Endpoints Verified via HTTPS**:
  - `https://iventlyapp.ru/health` -> HTTP 200 `{"status":"healthy",...}`
  - `https://iventlyapp.ru/` -> HTTP 200 (React 19 SPA)
  - `https://iventlyapp.ru/api/v1/categories` -> HTTP 200 (7 categories)
  - `https://iventlyapp.ru/api/v1/events?limit=2` -> HTTP 200 (Events catalog)
  - `https://iventlyapp.ru/uploads/covers/...` -> HTTP 200 (`Cache-Control: public, max-age=2592000, immutable`)
  - `https://iventlyapp.ru/uploads/avatars/...` -> HTTP 200 (Avatars served)
- **Database Initialized**: All 18 tables created and seeded (1134 cities, 30 events, 7 categories).
- **Media Transferred**: 136 covers, 58 avatars (`/var/lib/ivently/uploads/`, permissions `1000:1000`).
- **Persistence & Reboot**: Tested via `docker compose restart` and `systemctl restart docker`. All services recover to healthy within 15 seconds; database data and TLS certificates preserved in volumes.
- **Automated Backup**: Tested via `/usr/local/bin/backup-ivently.sh`. Valid custom pg_dump archive generated and verified with `pg_restore -l`. Daily cron configured at 03:00 MSK with 14-day rotation.
- **Monetization Safety**: `PAYMENTS_ENABLED=false` strictly enforced in `.env`.
- **Telegram Production Isolation**: Railway (`https://ivently.up.railway.app`) remains 100% untouched and active as the production environment until domain and Telegram webhook cutover is approved by the owner.


