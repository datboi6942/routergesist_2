# syntax=docker/dockerfile:1.6

ARG PY_VERSION=3.11
FROM --platform=$BUILDPLATFORM python:${PY_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Minimal OS deps; add tools we use for interface scans and AP services
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       iproute2 iputils-ping iw jq curl tini \
       hostapd dnsmasq nftables isc-dhcp-client rfkill procps wireless-regdb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

# Copy app
COPY backend /app/backend
COPY frontend /app/frontend
COPY scripts /app/scripts
COPY docker/entrypoint.sh /app/entrypoint.sh

# Healthcheck endpoint uses FastAPI root redirect -> /static/index.html
ENV HOST=0.0.0.0 \
    PORT=8080 \
    APP_DATA_DIR=/data

# Create data dir (run as root in container to allow privileged ops)
RUN mkdir -p /data /data/run && chmod +x /app/entrypoint.sh

EXPOSE 8080

# Entrypoint runs AP apply then starts backend (no systemd)
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/entrypoint.sh"]


