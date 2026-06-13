# ============================================
# Stage 1: Build Frontend
# ============================================
FROM ubuntu:22.04 AS frontend-builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ============================================
# Stage 2: Runtime
# ============================================
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN python3 -m venv /app/venv \
    && /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend/

# Copy config
COPY config/ ./config/

# Copy built frontend
COPY --from=frontend-builder /build/dist ./frontend/dist/

# Expose ports
# 8805/UDP - PFCP relay
# 8080/TCP - Web UI and REST API
EXPOSE 8805/udp
EXPOSE 8080/tcp

# Set PATH to use virtualenv
ENV PATH="/app/venv/bin:$PATH"

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/status || exit 1

# Entrypoint
ENTRYPOINT ["python3", "-m", "backend.app.main"]
