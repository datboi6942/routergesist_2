Router Geist 2 – Secure Router Controller for Raspberry Pi 5

Overview
- Secure Python 3 backend (FastAPI) with a lightweight modern frontend
- Automated threat detection using an LLM (OpenAI-compatible)
- Automatic Wi‑Fi interface detection and role assignment (AP or WAN)
- Guarded "Nuke" operation to securely shred app data and reset state

Status
- AP/WAN bring-up is container-friendly and host-friendly:
  - In container, startup applies router config and launches `hostapd`/`dnsmasq` directly (no systemd), with hot-reload volumes.
  - On host, privileged operations are delegated to scripts.
- Dynamic interface roles:
  - Detects default-route interface for WAN; picks a different wireless NIC for AP automatically.
- Live monitoring (Analytics tab):
  - Dual charts show WAN and LAN/AP RX/TX for the last 60 minutes (1–2 s latency), minute ticks, 5‑min labels, and legends.
  - DNS analytics: visited domains, top domains, top domains by client, new domains (last hour).
  - Connections: top clients/destination ports; per‑device activity classifier (streaming/download/idle) via conntrack + DNS.
- Threat detection integrates with OpenAI-compatible API if `OPENAI_API_KEY` is set.

Hardware/OS
- Raspberry Pi 5 recommended
- OS: Debian/Raspberry Pi OS (bookworm or later)

Security Model
- Backend runs as non-root user (`routergeist` recommended)
- Privileged operations are delegated to narrowly-scoped scripts run via `sudo` with explicit allow rules
- Admin API secured by static admin token (`ADMIN_TOKEN`) and CSRF token for browser actions
- Login via username/password (config/bootstrap), session cookie; privileged actions gated by auth
- Nuke is gated by: strong confirmation input + server-side unlock env + optional physical presence flag

Quick Start (Development)
1) Python backend
   - Prereqs: Python 3.11+, `iproute2`, `iw`, `nmcli` (optional), `hostapd`/`dnsmasq` (optional)
   - Create virtualenv and install deps:
     ```bash
     cd backend
     python3 -m venv .venv
     source .venv/bin/activate
     pip install -r requirements.txt
     ```
   - Set environment variables (copy `backend/.env.example` → `backend/.env` and edit):
     ```bash
     cp backend/.env.example backend/.env
     # Edit ADMIN_TOKEN, OPENAI_API_KEY, etc.
     ```
   - Run backend:
     ```bash
     ./start.sh
     ```

2) Frontend
   - Static assets are served by the backend at `/`.
   - Open `http://localhost:8080/` (or your host) → Analytics for live charts.

Production Setup (RPi or Container)
- Create a dedicated user:
  ```bash
  sudo useradd --system --home /opt/routergeist --shell /usr/sbin/nologin routergeist
  sudo mkdir -p /opt/routergeist
  sudo chown -R routergeist:routergeist /opt/routergeist
  ```
- Install OS packages (as needed):
  ```bash
  sudo apt-get update
  sudo apt-get install -y iproute2 iw network-manager hostapd dnsmasq jq
  ```
- Configure sudoers for narrowly-scoped scripts:
  ```bash
  sudo visudo -f /etc/sudoers.d/routergeist
  ```
  Add (adjust paths if different):
  ```
  Defaults!RESTRICTED_NUKE !requiretty
  routergeist ALL=(root) NOPASSWD:SETENV: /bin/bash /opt/routergeist/scripts/privileged/nuke.sh *, \
                                         /bin/bash /opt/routergeist/scripts/privileged/assign_roles.sh *
  ```
- Install systemd units (see `systemd/`) when running on host:
  ```bash
  sudo cp -r systemd/* /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable routergeist.service
  sudo systemctl start routergeist.service
  ```

Environment Variables (`backend/.env.example` → `backend/.env`)
- ADMIN_TOKEN: Required admin bearer token (high entropy)
- ADMIN_USERNAME / ADMIN_PASSWORD_HASH: Optional bootstrap login; can also place `admin.json` in `APP_DATA_DIR` instead
- SECRET_KEY: Optional base64 urlsafe key for sessions/at-rest encryption
- OPENAI_API_KEY: Optional. Enables LLM threat analysis
- OPENAI_API_BASE: Optional. Custom endpoint (Azure/OpenRouter-compatible)
- APP_DATA_DIR: App data path to protect/wipe (default `/opt/routergeist/data`)
- NUCLEUS_UNLOCK: `false` by default. Set `true` to allow nuke endpoint
- ALLOW_FULL_DEVICE_WIPE: `false` by default. If `true`, enables full-device wipe option in nuke script (dangerous)
- WIFI_WAN_SSIDS: Comma-separated preferred SSIDs for WAN role
- WIFI_WAN_PSKS: Comma-separated PSKs matching SSIDs (same order)

Nuke Behavior
- Default: Securely wipes only app-scoped data directories (`APP_DATA_DIR`, logs, caches). Attempts multiple overwrite passes for regular files and removes directories. On flash media (SD), guarantees are limited; see README notes.
- Full-device wipe is disabled by default and must be explicitly enabled with `ALLOW_FULL_DEVICE_WIPE=true` and server-side policy. Use with extreme caution.

Interface Roles
- The interface manager scans Wi‑Fi NICs periodically.
- If two or more Wi‑Fi NICs are present:
  - Prefer assigning one to WAN (connecting to preferred SSIDs) and one to AP
- If a single Wi‑Fi NIC is present:
  - Prefer WAN if preferred SSIDs are reachable and credentials exist; else run AP

Traffic Charts (UX)
- WAN chart auto-binds to the current WAN NIC (highest recent RX or `role==WAN`).
- LAN/AP chart auto-binds to the AP NIC (highest recent TX or `role==LAN`).
- 60‑minute rolling window with 1‑minute ticks and 5‑minute labels; legend clarifies RX (download) and TX (upload).

Threat Detection
- Streams network/system events (extensible) into an LLM for heuristic analysis.
- The model returns a severity label and explanation stored locally.

Authentication and Bootstrap
- Set initial admin login via either `backend/.env` or file `APP_DATA_DIR/admin.json`:
  ```json
  { "username": "admin", "password_hash": "$2b$12$..." }
  ```
- To generate a password hash:
  ```bash
  python - <<'PY'
import bcrypt; print(bcrypt.hashpw(b"YourStrongPassword", bcrypt.gensalt()).decode())
PY
  ```
- After login at `/static/login.html`, you can change the password in the Settings card.

OpenAI API Key
- Set from Settings card; the key is stored encrypted at rest in `APP_DATA_DIR/settings.json` using a key in `APP_DATA_DIR/secret.key` (file permissions 600).

Known Limitations
- Hostapd/dnsmasq configuration is generated but activation is best-effort and depends on OS network stack state.
- Secure deletion on SD cards is best-effort; truly secure destruction may require physical destruction.

License
- MIT


