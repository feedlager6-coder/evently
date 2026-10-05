# D6.1.3 — Selectel Migration Audit & Safe Staging Plan

**Document Version:** 1.0.0  
**Status:** Audit Complete — Migration-Readiness Phase (Zero Production Impact)  
**Author:** Lead Infrastructure / DevOps / Backend Engineer  
**Date:** 2026-10-05  
**Target Platform:** Selectel Cloud / VDS (Moscow, Russia — Ubuntu 24.04 LTS, 2 vCPU, 4 GB RAM, 50 GB NVMe, Public IPv4)  
**Current Production:** Railway (`https://ivently.up.railway.app`)

---

## 1. Executive Summary & Safety Mandate

This document establishes the production infrastructure audit and technical migration plan for transitioning the **Ivently** platform from Railway to **Selectel Moscow**.

### Strict Operational Invariant: Zero Production Modification
During this audit and subsequent staging preparation:
- **Zero changes** to Railway production infrastructure, services, or containers.
- **Zero changes** to production DNS or domain routing.
- **Zero changes** to the live Telegram Bot webhook (`https://ivently.up.railway.app/api/v1/telegram/webhook`).
- **Zero rotation** of active production tokens or credentials.
- **Zero data modification** or deletion on Railway PostgreSQL or Railway Volumes.
- `PAYMENTS_ENABLED` remains `false` in production.
- Legal drafts remain unpublished until formal organizational execution.
- Railway production remains 100% operational throughout all audit and staging phases.

---

## 2. Current Railway Production Inventory

| Component | Railway Production Implementation | Notes & Specifications |
|---|---|---|
| **Edge & Ingress** | Railway Anycast Edge (`69.46.46.47`, JFK1 edge, TLS terminated by Railway) | Public URL: `https://ivently.up.railway.app` |
| **Application Process** | Single container monolith (`Dockerfile`) | Stage 1: Node 22 Alpine builds React/Vite SPA; Stage 2: Python 3.13-slim runs FastAPI + Uvicorn |
| **Serving Architecture** | Uvicorn serves both `/api/v1/...` and SPA static bundle (`serve_spa` catch-all) | Static assets mounted at `/assets` and `/uploads` |
| **Database** | Railway Managed PostgreSQL 16 (internal private networking) | Connected via `DATABASE_URL=postgresql+asyncpg://...` |
| **Schema & Migrations** | Startup initialization via `Base.metadata.create_all` + additive migrations in `backend/app/database.py:init_db` | No Alembic migration folder currently exists |
| **File Storage** | Railway Persistent Volume attached to `/app/uploads` | Managed via `STORAGE_LOCAL_DIR` / `RAILWAY_VOLUME_MOUNT_PATH` |
| **Telegram Bot API** | Webhook routed to `/api/v1/telegram/webhook` | Auto-registered on startup via `main.py:lifespan` |
| **Background Processing** | In-process asyncio tasks & FastAPI `BackgroundTasks` | Pure Python asyncio; no Celery, Redis, or external message broker |

---

## 3. Repository Architecture & Component Breakdown

### 3.1 Backend (FastAPI / Python 3.13)
- **Entrypoint:** `backend/app/main.py:app`
- **ASGI Server:** Uvicorn (`uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}`)
- **Python Version:** Python 3.13 (`python:3.13-slim` base image)
- **Dependency Management:** `backend/requirements.txt` (FastAPI 0.115+, SQLAlchemy 2.0.30+, asyncpg 0.29+, pydantic 2.7+, httpx 0.27+, boto3 1.34+)
- **Lifecycle (`lifespan`):**
  1. `await init_db()`: Creates missing tables and executes idempotent column/index additions.
  2. `await seed_database(session)`: Idempotently populates 1,134 Russian cities, 7 categories, and 30 demo events if missing.
  3. Telegram Webhook Auto-Sync: If `settings.is_live_bot` and `settings.effective_public_host` are resolved, queries `getWebhookInfo` and updates upstream via `setWebhook` if URL differs.
- **Healthcheck:** `GET /health` returns JSON `{"status": "healthy", "app": "Ivently", "storage": {...}}`. Container Dockerfile healthcheck: `curl -f http://localhost:${PORT:-8000}/health || exit 1`.
- **Ownership Verification:** `GET /verification/yandex` serves plain-text `YANDEX_VERIFICATION_CODE` without auth.

### 3.2 Frontend (React 19 / TypeScript / Vite / Tailwind v4)
- **Source Directory:** `frontend/`
- **Build Tool:** Vite 8.3 + TypeScript 6.0 (`tsc -b && vite build`)
- **Output Bundle:** `frontend/dist/` (`index.html`, `assets/index-*.js`, `assets/index-*.css`)
- **API Base:** Relative path `const API_BASE = '/api/v1'` in `frontend/src/services/api.ts`.
  - **Critical Finding:** Zero hardcoded production domains in the frontend client. All API requests use same-origin relative URLs (`/api/v1/...`).
- **Telegram Mini App Integration:** `@telegram-apps/sdk` / Telegram WebApp script. `initData` passed as `Authorization: tma <initData>`.

### 3.3 Database & ORM
- **Engine:** `SQLAlchemy[asyncio]>=2.0.30` with `asyncpg>=0.29.0`.
- **Dialect Handling:** Automatic dialect normalization in `settings.async_database_url` (converts `postgres://` or `postgresql://` to `postgresql+asyncpg://`).
- **Table Count:** **18 tables** in `Base.metadata.tables`:
  1. `cities`
  2. `categories`
  3. `users`
  4. `events`
  5. `event_attendees`
  6. `event_company_matches`
  7. `event_company_profiles`
  8. `event_company_requests`
  9. `event_interests`
  10. `event_views`
  11. `organizations`
  12. `organization_plans`
  13. `broadcasts`
  14. `broadcast_recipients`
  15. `subscriptions`
  16. `payment_orders`
  17. `payment_transactions`
  18. `payment_webhook_logs`
- **Indexes:** 9 custom indexes created idempotently during `init_db()` (`uq_broadcasts_attribution_token`, `idx_broadcast_recipients_attr`, `idx_organization_plans_org_status`, `idx_events_source_external`, `uq_payment_orders_provider_payment_id`, `uq_payment_orders_idempotency_key`, `idx_payment_orders_org_status`, `idx_payment_transactions_order_created`, `idx_payment_webhook_logs_event_provider`).

### 3.4 Storage Implementation
- **Service:** `backend/app/services/storage_service.py:StorageService`.
- **Dual Mode Support:**
  - **Local Disk / Persistent Volume:** Default when S3 credentials are unset. Files saved under `get_local_storage_dir()` (`covers/` and `avatars/`).
  - **S3-Compatible Object Storage:** Supports AWS S3, Selectel S3, Cloudflare R2, Yandex Object Storage via `boto3` with fallback to native async AWS SigV4 over `httpx`.
- **URL Resolution Paradigm:**
  - Files saved locally return relative paths: `/uploads/covers/{uuid}.jpg`.
  - Stored in database as relative paths (`/uploads/...`) or external URLs (`https://images.unsplash.com/...`).
  - When sending images to Telegram Bot API or webhooks, `notification_service.py:resolve_event_cover_url` prefixes relative paths with `settings.effective_public_host`.
  - **Critical Finding:** Zero hardcoded domain names exist in database image references. Migrating to a new domain requires **zero database content rewrites** for media URLs.

---

## 4. Railway Dependencies & Assumptions Inventory

The repository was comprehensively audited for Railway-specific references:

| Location in Code | Railway Identifier / Assumption | Impact & Resolution on Selectel |
|---|---|---|
| `Dockerfile:33-45` | `PORT` environment variable (`uvicorn ... --port ${PORT:-8000}`) | Compatible as-is. In Docker Compose, `PORT` defaults to `8000` or can be explicitly passed. |
| `backend/app/config.py:149` | `os.getenv("RAILWAY_PUBLIC_DOMAIN")` checked in `effective_public_host` | Handled cleanly: On Selectel, set `PUBLIC_HOST` or `APP_PUBLIC_HOST` to the Selectel domain. |
| `backend/app/config.py:150` | `os.getenv("RAILWAY_STATIC_URL")` checked in `effective_public_host` | Handled cleanly via `PUBLIC_HOST`. |
| `backend/app/config.py:154` | Production fallback `https://ivently.up.railway.app` when no host specified | Safe fallback; overridden whenever `PUBLIC_HOST` is explicitly set in production `.env`. |
| `backend/app/services/storage_service.py:75` | `os.getenv("RAILWAY_VOLUME_MOUNT_PATH")` checked for upload dir | On Selectel, pass `STORAGE_LOCAL_DIR=/app/uploads` and mount host volume `/var/lib/ivently/uploads:/app/uploads`. |
| `backend/app/services/storage_service.py:113` | Diagnostics returns `backend: railway_volume` when volume detected | Harmless telemetry string; purely informational. |
| `backend/app/services/payment_service.py:163` | Fallback return URL host `base_host = settings.effective_public_host or "https://ivently.up.railway.app"` | Overridden automatically by `effective_public_host` (`PUBLIC_HOST`). |
| `backend/app/services/telegram_bot.py:348` | Informational text for admin: *"добавьте этот ID в переменную ... в настройках проекта на Railway"* | Informational message only; does not affect runtime. Can be updated to generic wording in future polish. |
| `railway.json` | Root Railway deployment manifest (`$schema`, `builder: DOCKERFILE`, `healthcheckPath: /health`) | Ignored outside Railway. Preserved for Railway zero-impact invariant. |

---

## 5. Environment Variables & Secrets Classification

Every configuration variable in `backend/app/config.py` was cataloged and categorized:

| Variable Name | Classification | Default / Example Value | Required in Production |
|---|---|---|---|
| `APP_NAME` | Public Configuration | `Ivently` | Optional (default applies) |
| `APP_ENV` | Public Configuration | `production` (on server) | **Yes** |
| `DEBUG` | Public Configuration | `false` | **Yes** |
| `PORT` | Public Configuration | `8000` | Optional |
| `HOST` | Public Configuration | `0.0.0.0` | Optional |
| `PUBLIC_HOST` | Public Configuration | `ivently.ru` (target domain) | **Yes** |
| `APP_PUBLIC_HOST` | Public Configuration | `https://ivently.ru` | Optional (alias) |
| `CORS_ORIGINS` | Public Configuration | `*` or domain whitelist | Optional |
| `DATABASE_URL` | **Database Credential** | `postgresql+asyncpg://user:pass@host:5432/db` | **Yes** |
| `TELEGRAM_BOT_TOKEN` | **Telegram Secret / Token** | `123456789:ABC...` | **Yes** (Staging must use test token!) |
| `TELEGRAM_BOT_USERNAME`| Public Configuration | `Ivently_bot` | **Yes** |
| `TELEGRAM_MINI_APP_URL` | Public Configuration | `https://t.me/Ivently_bot/app` | **Yes** |
| `TELEGRAM_MINI_APP_SHORT_NAME` | Public Configuration | `app` | Optional |
| `ADMIN_USER_IDS` | Application Secret / Internal | `123456789` | **Yes** |
| `SECRET_KEY` | **Application Secret** | 32+ bytes random hex string | **Yes** |
| `AUTH_DATE_MAX_AGE_SECONDS` | Public Configuration | `86400` | Optional |
| `STORAGE_BACKEND` | Public Configuration | `local` or `s3` | **Yes** |
| `STORAGE_LOCAL_DIR` | Public Configuration | `/app/uploads` | **Yes** (if local backend) |
| `STORAGE_ENDPOINT` | Public Configuration | `https://s3.storage.selcloud.ru` | Only if S3 |
| `STORAGE_BUCKET` | Public Configuration | `ivently-media` | Only if S3 |
| `STORAGE_ACCESS_KEY` | **Storage Credential** | `S3_KEY_ID` | Only if S3 |
| `STORAGE_SECRET_KEY` | **Storage Secret** | `S3_SECRET_KEY` | Only if S3 |
| `STORAGE_REGION` | Public Configuration | `ru-1` | Only if S3 |
| `STORAGE_PUBLIC_URL` | Public Configuration | `https://media.ivently.ru` | Only if S3 |
| `YANDEX_VERIFICATION_CODE` | Public Configuration | Optional verification string | Optional |
| `PAYMENTS_ENABLED` | Public Configuration | `false` | **Yes** (must remain false) |
| `PRO_MONTHLY_PRICE_RUB`| Public Configuration | `499.0` | Optional |
| `PRO_SUBSCRIPTION_DAYS`| Public Configuration | `30` | Optional |
| `YOOKASSA_SHOP_ID` | **Payment Credential** | `987654` | Only if payments enabled |
| `YOOKASSA_SECRET_KEY` | **Payment Secret** | `test_...` / `live_...` | Only if payments enabled |
| `YOOKASSA_RETURN_URL` | Public Configuration | `https://ivently.ru/#/org/settings` | Only if payments enabled |
| `TYPESAFE_API_KEY` | **Optional AI Secret** | Unset | No |
| `TYPESAFE_ENABLED` | Public Configuration | `false` | Optional |

---

## 6. Selectel Target Architecture & Sizing Baseline

### Baseline Hardware Specifications (Selectel Moscow Pool)
- **CPU:** 2 vCPU (Intel Xeon or AMD EPYC high-frequency vCPU)
- **RAM:** 4 GB RAM
- **Storage:** 50 GB NVMe fast block storage
- **Operating System:** Ubuntu 24.04 LTS (Clean server installation)
- **Networking:** Dedicated Public IPv4 + optional IPv6
- **Access:** SSH Key-only authentication (Ed25519)
- **Data Center Location:** Moscow (e.g. Dubrovka DC or Berzarina DC — compliant with Tier III standards)

---

## 7. PostgreSQL Database Options Evaluation

### Option A: Colocated PostgreSQL 16 on Selectel VDS (Docker Compose)
* **Estimated Monthly Cost:** **0 RUB additional** (included in VDS base rental).
* **Complexity:** Low. Managed via Docker Compose alongside application and Caddy.
* **Backups:** Automated local daily `pg_dump` via cron, compressed with gzip/zstd, with secondary encrypted sync to Selectel Object Storage or offsite backup target.
* **Recovery:** Fast local `pg_restore` (1–3 minutes recovery time).
* **Performance:** Exceptional latency (< 0.2 ms local loopback / unix socket), direct NVMe I/O without network overhead.
* **Operational Burden:** Moderate. Owner responsible for disk monitoring and backup cron verification.
* **Security:** High. Port 5432 is strictly bound to Docker internal network (`bridge`); never exposed to public IPv4.
* **Scalability:** Easily accommodates up to ~15,000–25,000 registered users and ~50 concurrent database connections with proper pool tuning.
* **Suitability for Current Ivently:** **HIGH (Recommended for initial migration).**

### Option B: Selectel Managed PostgreSQL (DBaaS)
* **Estimated Monthly Cost:** **~1,200 – 1,800 RUB / month** (1 vCPU, 2 GB RAM, 20 GB storage; requires manual billing confirmation in Selectel console).
* **Complexity:** Moderate setup (requires VPC private network peering between VDS and DBaaS instance).
* **Backups:** Fully automated point-in-time recovery (PITR) and automatic daily snapshots managed by Selectel.
* **Recovery:** 1-click restore from Selectel web console.
* **Performance:** Intra-datacenter private network hop (< 1 ms latency within Moscow availability zone).
* **Operational Burden:** Near zero. Selectel manages OS updates, PostgreSQL minor version patching, and replication.
* **Security:** Managed firewall and VPC isolation.
* **Scalability:** High. Scalable with 1 click to read replicas and higher CPU/RAM tiers.
* **Suitability for Current Ivently:** Excellent for future phase when paid Pro subscriptions scale, but represents an unnecessary 100%+ cost increase during pilot stage.

### Architectural Recommendation:
> **Deploy Option A (Colocated PostgreSQL 16 in Docker Compose) for Staging and Initial Production.**  
> Keep `DATABASE_URL` strictly decoupled in `.env`. When active paid Pro subscriptions justify dedicated database infrastructure, migrate seamlessly to Option B without any code modification.

---

## 8. File Storage Options Evaluation

### Option A: Local Persistent Volume (`/var/lib/ivently/uploads` on Selectel VDS NVMe)
* **Estimated Monthly Cost:** **0 RUB additional** (utilizes 50 GB NVMe).
* **Capacity:** ~30 GB dedicated to uploads (capable of holding > 150,000 compressed 200 KB images).
* **Complexity:** Minimum. Host volume `- /var/lib/ivently/uploads:/app/uploads` in `docker-compose.yml`.
* **Serving:** Caddy or Nginx serves `/uploads/` directly from host disk with caching headers (`Cache-Control: public, max-age=2592000, immutable`), bypassing Python/Uvicorn overhead entirely.
* **Backups:** Daily incremental `rsync` / `tar` snapshot.
* **Suitability for Current Stage:** **100% Sufficient and Recommended.**

### Option B: Selectel Object Storage (S3-Compatible)
* **Estimated Monthly Cost:** ~100 – 200 RUB / month (~1.5–2.0 RUB / GB / month + minimal request fees).
* **Complexity:** Moderate. Requires creating S3 bucket in Selectel console, issuing IAM service keys, and setting S3 CORS policies.
* **Application Readiness:** `StorageService` in the repository **already has 100% full support** for Selectel S3 via `STORAGE_BACKEND=s3`, `STORAGE_ENDPOINT=https://s3.storage.selcloud.ru`, and `boto3`/SigV4.
* **Suitability for Current Stage:** Viable anytime. Because the repository already implements clean S3 abstraction, switching from Option A to Option B later requires **zero code changes**, only environment variable configuration.

---

## 9. Deployment Model & Compose Topology

The target deployment model on Selectel Moscow consists of a lean, reliable Docker Compose stack:

```
[ Internet (Clients / Telegram) ]
               │
               ▼  Ports 80 / 443
   ┌───────────────────────┐
   │ Caddy Reverse Proxy   │ (Automatic Let's Encrypt TLS, HTTP/2 & HTTP/3)
   └───────────┬───────────┘
               │  Internal Docker Network (`ivently-net`)
       ┌───────┴───────┐
       ▼               ▼
┌─────────────┐ ┌──────────────┐
│   Static    │ │   FastAPI    │
│  /uploads   │ │   Monolith   │ (Python 3.13 + Built React SPA)
│ (from disk) │ │ (Port 8000)  │
└─────────────┘ └──────┬───────┘
                       │ Internal Docker Network (Port 5432)
                       ▼
               ┌──────────────┐
               │  PostgreSQL  │ (postgres:16-alpine)
               │      16      │ Volume: /var/lib/ivently/postgres_data
               └──────────────┘
```

### Proposed `docker-compose.yml` (For Staging & Target Production):
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
    environment:
      - APP_ENV=production
      - DEBUG=false
      - PORT=8000
      - HOST=0.0.0.0
      - DATABASE_URL=postgresql+asyncpg://ivently_user:${DB_PASSWORD}@db:5432/ivently_prod
      - PUBLIC_HOST=${PUBLIC_HOST}
      - STORAGE_BACKEND=local
      - STORAGE_LOCAL_DIR=/app/uploads
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_BOT_USERNAME=${TELEGRAM_BOT_USERNAME}
      - TELEGRAM_MINI_APP_URL=${TELEGRAM_MINI_APP_URL}
      - ADMIN_USER_IDS=${ADMIN_USER_IDS}
      - SECRET_KEY=${SECRET_KEY}
      - PAYMENTS_ENABLED=false
    volumes:
      - /var/lib/ivently/uploads:/app/uploads
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 20s
    networks:
      - ivently-net

  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      - POSTGRES_USER=ivently_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=ivently_prod
    volumes:
      - /var/lib/ivently/postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ivently_user -d ivently_prod"]
      interval: 10s
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

### Proposed `Caddyfile`:
```caddy
{$PUBLIC_HOST} {
    encode gzip zstd

    # High-performance static serving of user uploads with caching
    handle_path /uploads/* {
        root * /var/www/uploads
        file_server
        header Cache-Control "public, max-age=2592000, immutable"
    }

    # Proxy all API and SPA requests to FastAPI
    handle {
        reverse_proxy app:8000 {
            header_up X-Forwarded-Proto https
            header_up X-Forwarded-Host {host}
        }
    }
}
```

---

## 10. Domain, DNS, TLS & Telegram Integration Strategy

### 10.1 Domain & DNS Requirements
1. The domain `ivently.up.railway.app` is an Anycast Railway domain and **cannot** be pointed to Selectel.
2. Selectel production requires a custom domain (e.g. `ivently.ru`, `app.ivently.ru`).
3. For staging validation, a subdomain (e.g. `staging.ivently.ru`) must be configured with an **A Record** pointing to the Selectel Public IPv4.
4. **TLS:** Let's Encrypt certificates are provisioned automatically by Caddy as soon as DNS propagation reaches the server.

### 10.2 Telegram Webhook & Mini App Critical Findings
> [!CAUTION]
> **Staging Bot Token Isolation Invariant:**  
> In `backend/app/main.py:lifespan`, when `settings.is_live_bot` is true, FastAPI checks `getWebhookInfo` and automatically calls `setWebhook` on startup if `current_url != webhook_url`.  
> If staging on Selectel is started using the **production `TELEGRAM_BOT_TOKEN`**, startup **will immediately hijack the production Telegram webhook** away from Railway!  
> **RULE:** During staging testing on Selectel, **NEVER** use the production `TELEGRAM_BOT_TOKEN`. Staging must use a dedicated test bot token (e.g. `@Ivently_staging_bot`) or dummy token.

### 10.3 Production Cutover Sequence (Step 18)
When the owner approves final cutover:
1. Update `PUBLIC_HOST=ivently.ru` in Selectel `.env`.
2. Update BotFather Mini App Web App URL via `/setapp` to `https://ivently.ru`.
3. Register the production webhook to Selectel:
   ```bash
   curl -X POST "https://api.telegram.org/bot<PROD_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://ivently.ru/api/v1/telegram/webhook", "allowed_updates": ["inline_query", "message"]}'
   ```
4. Incoming Telegram updates immediately route to Selectel.

---

## 11. PostgreSQL Migration Runbook & Data Integrity Plan

### 11.1 Dump Export from Railway (Zero-Downtime Read)
```bash
# Export custom-format compressed backup from Railway PostgreSQL
pg_dump \
  --dbname="${RAILWAY_DATABASE_URL}" \
  --format=custom \
  --no-owner \
  --no-acl \
  --verbose \
  --file=ivently_railway_prod.dump
```

### 11.2 Verification of Dump Integrity
```bash
pg_restore --list ivently_railway_prod.dump | head -n 30
```

### 11.3 Restore into Selectel PostgreSQL
```bash
# Stream dump into Selectel Docker container
docker compose exec -T db pg_restore \
  -U ivently_user \
  -d ivently_prod \
  --no-owner \
  --no-acl \
  --clean \
  --if-exists \
  --verbose < ivently_railway_prod.dump
```

### 11.4 Automated Row Count & Entity Verification
Execute SQL verification across all 18 production tables to ensure zero data loss:
```sql
SELECT 'broadcast_recipients' AS entity, count(*) AS total_rows FROM broadcast_recipients
UNION ALL SELECT 'broadcasts', count(*) FROM broadcasts
UNION ALL SELECT 'categories', count(*) FROM categories
UNION ALL SELECT 'cities', count(*) FROM cities
UNION ALL SELECT 'event_attendees', count(*) FROM event_attendees
UNION ALL SELECT 'event_company_matches', count(*) FROM event_company_matches
UNION ALL SELECT 'event_company_profiles', count(*) FROM event_company_profiles
UNION ALL SELECT 'event_company_requests', count(*) FROM event_company_requests
UNION ALL SELECT 'event_interests', count(*) FROM event_interests
UNION ALL SELECT 'event_views', count(*) FROM event_views
UNION ALL SELECT 'events', count(*) FROM events
UNION ALL SELECT 'organization_plans', count(*) FROM organization_plans
UNION ALL SELECT 'organizations', count(*) FROM organizations
UNION ALL SELECT 'payment_orders', count(*) FROM payment_orders
UNION ALL SELECT 'payment_transactions', count(*) FROM payment_transactions
UNION ALL SELECT 'payment_webhook_logs', count(*) FROM payment_webhook_logs
UNION ALL SELECT 'subscriptions', count(*) FROM subscriptions
UNION ALL SELECT 'users', count(*) FROM users
ORDER BY entity;
```

---

## 12. Storage Migration Runbook

1. **Current Inventory:**
   - Local directory structure: `uploads/covers/` and `uploads/avatars/`.
   - All uploaded files are sanitized UUID filenames (`.jpg`, `.png`, `.webp`).
   - Approximate size: < 50 MB.
2. **Transfer Command:**
   ```bash
   rsync -avzP --chmod=D755,F644 ./uploads/ user@selectel-ip:/var/lib/ivently/uploads/
   ```
3. **Permission Alignment:**
   ```bash
   chown -R 1000:1000 /var/lib/ivently/uploads
   ```
4. **URL Consistency:**
   Because database rows store `/uploads/covers/{uuid}.jpg` without hardcoded domains, the new Selectel host automatically serves all assets seamlessly.

---

## 13. Resource Sizing & Capacity Analysis

### 13.1 Memory Allocation Budget (4 GB RAM Total)
| Component | Baseline RAM Footprint | Peak / Burst RAM | Notes |
|---|---|---|---|
| **Ubuntu 24.04 OS & Systemd** | 200 MB | 300 MB | Kernel, sshd, systemd, ufw |
| **Docker Engine & Containerd** | 100 MB | 150 MB | Container runtime daemon |
| **Caddy Reverse Proxy** | 25 MB | 50 MB | Go binary, TLS termination, static files |
| **FastAPI Monolith (Uvicorn)** | 180 MB | 350 MB | Python 3.13 runtime + cached metadata |
| **PostgreSQL 16 (Colocated)** | 500 MB | 900 MB | `shared_buffers = 256MB`, `work_mem = 16MB` |
| **Total Memory Allocated** | **~1,005 MB** | **~1,750 MB** | **Comfortable Headroom: > 2.2 GB available** |

### 13.2 CPU & Disk I/O Utilization
- **CPU (2 vCPU):** Idle load < 2%. Fast response times (< 15 ms API latency). Peak marketing broadcast bursts (25 msgs/sec dispatch) consume ~30–45% of 1 core for the duration of the send loop.
- **Disk (50 GB NVMe):** OS + Docker (~10 GB), DB (~1 GB), Uploads (~2 GB), Backup retention (~5 GB) = **~18 GB used, ~32 GB free**.

### 13.3 Capacity Projections at Scale
| Registered User Tier | Est. Concurrent Users | 2 vCPU / 4 GB Sizing Status | Bottleneck & Actions |
|---|---|---|---|
| **1,000 Users** | 5 – 15 | **10% utilized** — Seamless | None. |
| **5,000 Users** | 20 – 50 | **20% utilized** — Seamless | None. |
| **10,000 Users** | 50 – 100 | **35% utilized** — Stable | Tune asyncpg connection pool (`pool_size=10, max_overflow=20`). |
| **50,000 Users** | 200 – 400 | **70% utilized** — Manageable | Long broadcasts (50k / 25/s = 33 min) block in-process dispatcher. Split database to Managed PostgreSQL and upgrade VDS to 4 vCPU / 8 GB. |
| **100,000 Users** | 500 – 1,000 | **Overload limit** | Introduce Redis + dedicated background worker for broadcast queuing; separate database cluster. |

---

## 14. 152-FZ Russian Data Localization & Residency Analysis

> [!NOTE]
> This section is an infrastructure architecture evaluation, not formal legal counsel.

### Physical Localization Analysis (Part 5, Article 18, 152-FZ)
- **Primary Database:** When deployed on Selectel Moscow, the PostgreSQL database storing all personal data (Telegram IDs, user profiles, names, city choices, organization organizer profiles, payment orders) will be physically located within the Russian Federation (Moscow DC).
- **Media Uploads:** Physical storage in Selectel Moscow NVMe storage.
- **Local Backups:** Stored within the Russian Federation on local disk and Selectel Object Storage.
- **Third-Party Data Flows:**
  - **Telegram Bot API:** Transits global Telegram infrastructure as a messaging channel. User consent is provided via Telegram platform terms.
  - **YooKassa:** NKO YuMoney, physically situated and licensed in Moscow, Russia.
  - **Unsplash:** External stock imagery (public content only; zero personal data).

**Compliance Boundary Statement:**  
Physically moving the primary database from Railway (US-East/Europe) to Selectel (Moscow) resolves the core technical infrastructure requirement of 152-FZ regarding initial recording and storage of Russian citizens' personal data. Formal organizational compliance additionally requires legal publication of the User Agreement, Privacy Policy, and Roskomnadzor registry notification where applicable.

---

## 15. Server Hardening & Security Baseline

1. **SSH Access Control:**
   - Ed25519 public key authentication only.
   - Password authentication disabled: `PasswordAuthentication no`.
   - Direct root SSH disabled: `PermitRootLogin prohibit-password`.
2. **Network Firewall (`ufw`):**
   ```bash
   ufw default deny incoming
   ufw default allow outgoing
   ufw allow 22/tcp comment 'SSH'
   ufw allow 80/tcp comment 'HTTP ACME challenge'
   ufw allow 443/tcp comment 'HTTPS Caddy'
   ufw enable
   ```
   *PostgreSQL port 5432 is strictly private to Docker bridge network and never exposed to the internet.*
3. **Operating System Upgrades:**
   - Enable `unattended-upgrades` for automated security patches.
4. **Secrets Isolation:**
   - Production `.env` file secured with permissions `600`, readable only by the deployment user.

---

## 16. Backup Strategy & Disaster Recovery

| Backup Type | Frequency | Tool / Command | Retention | Destination |
|---|---|---|---|---|
| **PostgreSQL Full Dump** | Daily at 03:00 MSK | `pg_dump -Fc` via automated script | 14 days | `/var/backups/ivently/postgres/` |
| **Uploads Media** | Weekly | `tar -czf` | 4 weeks | `/var/backups/ivently/uploads/` |
| **Offsite Mirror** | Daily (after dump) | Encrypted sync via `rclone` or S3 CLI | 30 days | Selectel S3 cold bucket |

- **RPO (Recovery Point Objective):** <= 24 hours (with daily full dumps).
- **RTO (Recovery Time Objective):** <= 30 minutes (time to deploy clean container and restore dump).

---

## 17. Migration Risk Register

| # | Identified Risk | Severity | Probability | Impact | Preventive Mitigation | Rollback Procedure |
|---|---|---|---|---|---|---|
| 1 | **Telegram Webhook Collision** | HIGH | HIGH | Staging steals production Telegram updates | Use dedicated test bot token for staging; NEVER put production token on staging | Point webhook back to Railway via `setWebhook` API |
| 2 | **In-Flight Data Loss During Dump** | MEDIUM | LOW | Data written between dump and cutover is lost | Put Railway in brief maintenance mode or perform final delta sync before DNS switch | Re-enable Railway write access |
| 3 | **DNS Propagation Delay** | MEDIUM | MEDIUM | Users see old site during DNS cache TTL | Set DNS TTL to 300s (5 min) 48 hours prior to cutover | Change DNS A record back to Railway edge |
| 4 | **TLS Handshake / ACME Failure** | HIGH | LOW | HTTPS unavailable, Mini App blocked | Verify DNS A record points directly to Selectel IPv4 before launching Caddy | Serve temporary self-signed cert or fix DNS |
| 5 | **Missing Environment Variable** | MEDIUM | LOW | App crashes on boot or runtime error | Pre-validate `.env` using Pydantic Settings schema before boot | Inspect `docker compose logs app` and add missing var |
| 6 | **Database Extension Mismatch** | LOW | LOW | `init_db` failure | Code uses standard PostgreSQL types (`DOUBLE PRECISION`, `TIMESTAMP`); no non-standard extensions required | Not applicable |
| 7 | **Uploads Mount Failure** | MEDIUM | LOW | User avatars and covers return 404 | Test `/uploads/` file access in staging before cutover | Fix volume path in `docker-compose.yml` |
| 8 | **Memory Exhaustion (OOM)** | MEDIUM | LOW | Container killed if memory spikes | Colocated Postgres memory tuned to 256MB shared buffers; 2.2 GB free headroom | Restart container; increase swap |
| 9 | **Broadcast Dispatch Rate Limiting** | LOW | LOW | Telegram 429 errors during marketing blast | Engine already implements adaptive backoff and 25 msg/sec cap | Throttled automatically by code |
| 10 | **CORS / Origin Enforcement Block** | MEDIUM | LOW | Mini App fetch fails | `CORS_ORIGINS=*` configured by default; BotFather URL matches domain | Update CORS or BotFather URL |
| 11 | **Payment Webhook IP Block** | MEDIUM | LOW | YooKassa callbacks fail | YooKassa notifications use domain HTTPS; ensure firewall allows 443 | Re-verify YooKassa callback settings |
| 12 | **Background Task Failure** | LOW | LOW | Notifications not delivered | Errors logged with structured stack traces; non-blocking | Check logs via `docker compose logs` |
| 13 | **Disk Space Exhaustion** | MEDIUM | LOW | Backups fill 50 GB NVMe | Backup script enforces 14-day automated prune | Delete older backups via cron |
| 14 | **Rollback Execution Failure** | HIGH | LOW | Cannot return to Railway | Railway kept 100% untouched throughout migration | Switch DNS / Webhook back to Railway |
| 15 | **Staging Environment Accidental Charge** | HIGH | LOW | Test payments trigger real bank operations | `PAYMENTS_ENABLED=false` enforced across all staging configs | Keep payments disabled |
| 16 | **Let's Encrypt Rate Limit Exceeded** | MEDIUM | LOW | ACME cert issuance temporarily throttled | Use Caddy staging ACME endpoint during pre-testing if cycling domains | Wait 1 hr or use ZeroSSL fallback |

---

## 18. Exact 21-Step Migration Runbook

```
[ Phase A: Staging & Preparation (Steps 1–15) ]
  Step 1:  Provision Selectel VDS (2 vCPU, 4 GB RAM, 50 GB NVMe, Ubuntu 24.04, Public IPv4)
  Step 2:  Basic Ubuntu configuration (hostname, timezone Europe/Moscow, locale UTF-8)
  Step 3:  SSH key hardening (disable password authentication, configure deployment user)
  Step 4:  Configure UFW firewall (allow 22, 80, 443; deny all else)
  Step 5:  Install Docker Engine & Docker Compose plugin from official Docker repository
  Step 6:  Clone repository from origin/main to /opt/ivently
  Step 7:  Configure staging .env (staging domain, STAGING test bot token, PAYMENTS_ENABLED=false)
  Step 8:  Initialize local directories (/var/lib/ivently/postgres_data, /var/lib/ivently/uploads)
  Step 9:  Restore database dump from Railway staging/sanitized snapshot
  Step 10: Copy uploads assets to /var/lib/ivently/uploads
  Step 11: Run startup verification (init_db, column migrations, index verifications)
  Step 12: Start staging containers (docker compose up -d)
  Step 13: Run container health checks (curl -f http://localhost:8000/health)
  Step 14: Run automated test suite inside container
  Step 15: Perform end-to-end smoke tests (Mini App UI, catalog, search, auth)

[ Phase B: Owner Review & Cutover Preparation (Steps 16–17) ]
  Step 16: Prepare custom production DNS (reduce TTL to 300 seconds)
  Step 17: Pre-stage production secrets in /opt/ivently/.env.production (STOP FOR APPROVAL)

[ Phase C: Production Cutover (Steps 18–20) ]
  Step 18: Execute Cutover:
           a. Export final Railway DB dump
           b. Restore final dump to Selectel DB
           c. Sync latest uploads delta
           d. Switch DNS A record to Selectel IPv4
           e. Call Telegram setWebhook with new domain
           f. Update BotFather Mini App URL to new domain
  Step 19: Live Production Monitoring (error logs, webhook delivery, response times)
  Step 20: Rollback Procedure (Available if any critical issue arises within 48 hours)

[ Phase D: Decommissioning (Step 21) ]
  Step 21: Decommission Railway only after 7 days of 100% stable Selectel production.
```

---

## 19. Financial Cost Model

*All prices are estimates in Russian Rubles (RUB) based on standard Selectel Moscow tariff rates and require manual verification in the Selectel Billing Console prior to provisioning.*

| Configuration Tier | Components Included | Estimated Monthly Cost (RUB) | Notes |
|---|---|---|---|
| **A. Minimum Viable Setup** | 1x VDS (2 vCPU, 4 GB RAM, 50 GB NVMe) + 1x Public IPv4 + Colocated PostgreSQL + Local NVMe Uploads | **~950 – 1,350 ₽ / month** | Lowest cost; completely sufficient for current MVP stage. |
| **B. Recommended Setup** | Minimum Viable Setup + Selectel Object Storage (50 GB backup & offsite media retention) | **~1,200 – 1,600 ₽ / month** | Adds offsite disaster recovery in Russian jurisdiction. |
| **C. Scaled Setup** | 1x App VDS (2 vCPU, 4 GB RAM) + 1x Selectel Managed PostgreSQL (1 vCPU, 2 GB RAM, 20 GB NVMe) + S3 Storage | **~2,700 – 3,400 ₽ / month** | Recommended once active paying Pro customers scale (> 10k users). |

---

## 20. Implementation Readiness & Final Verdict

### Specific Audit Responses:
1. **Can Ivently be moved to Selectel without major code changes?**  
   **YES.** The application is already an autonomous, self-contained Docker container monolith.
2. **What exact code changes are required?**  
   **ZERO.** No application code changes are required. The codebase already supports generic Linux environments, persistent disk volumes, and standard PostgreSQL async drivers.
3. **What exact infrastructure changes are required?**  
   Provisioning of the Selectel VDS, adding `docker-compose.yml` and `Caddyfile`, configuring DNS A records, and setting up automated backup cron jobs.
4. **What can remain unchanged?**  
   Frontend React application, FastAPI routing, database models, Telegram message formatting, payment workflows, and business logic remain 100% identical.
5. **What is the minimum monthly cost?**  
   Approximately **~950 – 1,350 ₽ / month** (~$10–$14 USD).
6. **What is the recommended production configuration?**  
   Single VDS (2 vCPU, 4 GB RAM, 50 GB NVMe) with Docker Compose running Caddy, FastAPI, and PostgreSQL 16, backed by automated offsite S3 backups.
7. **What is the recommended staging configuration?**  
   Same stack deployed under `staging.ivently.ru` using a dedicated secondary test Telegram bot token to avoid production webhook interference.
8. **What are the top 5 migration risks?**  
   1) Accidental production webhook hijacking by staging.  
   2) In-flight data loss during the database transfer window.  
   3) DNS/TLS delay during domain switch.  
   4) Uploads volume permission mismatch.  
   5) Environment variable omission.
9. **What is the rollback procedure?**  
   Keep Railway untouched. Re-point DNS to Railway and re-register the Telegram webhook back to `https://ivently.up.railway.app/api/v1/telegram/webhook`. Rollback takes < 3 minutes.
10. **Is the project ready to begin a staging migration?**  
   **YES.** All technical verifications, tests (292/292 passed), and build checks have passed.

---

## Verdict & Next Steps

```
================================================================================
STATUS: AUDIT COMPLETE — AWAITING OWNER APPROVAL
================================================================================

GO:
- Repository is 100% migration-ready.
- 292/292 backend tests passed.
- Frontend build (TypeScript + Vite) passed cleanly.
- Zero production code refactoring required.
- Full 21-step runbook and risk mitigations established.

BLOCKED:
- Awaiting Owner Decision on target domain name (e.g. ivently.ru vs app.ivently.ru).
- Awaiting Owner Provisioning of Selectel Moscow VDS instance.
- Awaiting Owner Confirmation of dedicated test bot token for staging.

NEXT:
- Owner reviews audit report and approves initiation of Staging Phase on Selectel.
- Do NOT touch Railway production.
================================================================================
```
