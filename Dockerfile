# Multi-stage Dockerfile for Evently Monolith (FastAPI + React Telegram Mini App)

# --- Stage 1: Build Frontend Mini App ---
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci || npm install

COPY frontend/ ./
RUN npm run build

# --- Stage 2: Production Python Backend + Static SPA ---
FROM python:3.13-slim
WORKDIR /app

# Install runtime utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (including asyncpg for PostgreSQL)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend codebase
COPY backend/ ./backend/
RUN mkdir -p uploads/covers

# Copy built frontend SPA assets
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Default environment configuration (Railway overrides PORT dynamically)
ENV HOST=0.0.0.0
ENV PORT=8000
ENV APP_ENV=production

EXPOSE 8000

# Healthcheck for container orchestrators
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Launch uvicorn dynamically bound to $PORT
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
