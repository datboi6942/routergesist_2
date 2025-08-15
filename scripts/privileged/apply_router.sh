#!/usr/bin/env bash
set -euo pipefail

CFG_JSON="${1:-}"
if [[ -z "$CFG_JSON" || ! -f "$CFG_JSON" ]]; then
  echo "config not provided" >&2
  exit 1
fi

LAN_IF=$(jq -r .lan.interface "$CFG_JSON")
LAN_CIDR=$(jq -r .lan.cidr "$CFG_JSON")
LAN_IP=${LAN_CIDR%/*}
DHCP_START=$(jq -r .lan.dhcp_start "$CFG_JSON")
DHCP_END=$(jq -r .lan.dhcp_end "$CFG_JSON")
LAN_DNS=$(jq -r '.lan.dns | join(",")' "$CFG_JSON" 2>/dev/null || echo "")
WAN_IF=$(jq -r .wan.interface "$CFG_JSON")
WAN_MODE=$(jq -r .wan.mode "$CFG_JSON")
WAN_STATIC_ADDR=$(jq -r .wan.static.address "$CFG_JSON")
WAN_STATIC_GW=$(jq -r .wan.static.gateway "$CFG_JSON")
WIFI_IF=$(jq -r .wifi.interface "$CFG_JSON")
SSID=$(jq -r .wifi.ssid "$CFG_JSON")
PSK=$(jq -r .wifi.psk "$CFG_JSON")
CHANNEL=$(jq -r .wifi.channel "$CFG_JSON")
COUNTRY=$(jq -r .wifi.country "$CFG_JSON")

echo "Applying router config..."

# Try to ensure Wi‑Fi is usable for AP
rfkill unblock all || true
nmcli dev disconnect "$WIFI_IF" >/dev/null 2>&1 || true
nmcli dev set "$WIFI_IF" managed no >/dev/null 2>&1 || true
pkill -f "wpa_supplicant.*$WIFI_IF" >/dev/null 2>&1 || true
# Prepare Wi‑Fi interface; let hostapd take it to AP mode itself
ip link set "$WIFI_IF" down || true
iw dev "$WIFI_IF" set type managed >/dev/null 2>&1 || true
ip link set "$WIFI_IF" up || true
# Use base interface for AP; do not create virtual AP
AP_IF="$WIFI_IF"

# 1) IP address on LAN side (serve clients over Wi‑Fi AP). Prefer AP_IF if present.
LAN_EDGE_IF="$AP_IF"
ip addr flush dev "$WIFI_IF" || true
ip addr flush dev "$LAN_EDGE_IF" || true
ip addr add "$LAN_CIDR" dev "$LAN_EDGE_IF" || true
ip link set "$LAN_EDGE_IF" up || true

# 2) Enable IPv4 forwarding (skip if not permitted, e.g., rootless container)
if [ -w /proc/sys/net/ipv4/ip_forward ]; then
  sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
fi

# 3) nftables NAT/forward baseline (scoped tables; no global flush)
nft add table inet routergeist_filter 2>/dev/null || true
nft add chain inet routergeist_filter input '{ type filter hook input priority 0; policy accept; }' 2>/dev/null || true
nft add chain inet routergeist_filter forward '{ type filter hook forward priority 0; policy accept; }' 2>/dev/null || true
nft add chain inet routergeist_filter output '{ type filter hook output priority 0; policy accept; }' 2>/dev/null || true
nft add table ip routergeist_nat 2>/dev/null || true
nft add chain ip routergeist_nat prerouting '{ type nat hook prerouting priority -100; }' 2>/dev/null || true
nft add chain ip routergeist_nat postrouting '{ type nat hook postrouting priority 100; }' 2>/dev/null || true

# 3b) Lock down admin panel to AP network only
# Determine admin port (default 8080)
ADMIN_PORT=$(jq -r '.admin.port' "$CFG_JSON" 2>/dev/null || echo "")
if [[ -z "$ADMIN_PORT" || "$ADMIN_PORT" == "null" ]]; then ADMIN_PORT=8080; fi
# Always allow loopback traffic
nft add rule inet routergeist_filter input iif lo accept || true
# Allow admin access only from the AP/LAN interface
nft add rule inet routergeist_filter input iif "$LAN_EDGE_IF" tcp dport $ADMIN_PORT accept || true
# Drop admin access from any other interface (e.g., WAN)
nft add rule inet routergeist_filter input tcp dport $ADMIN_PORT drop || true

# 4) Masquerade from LAN to WAN
nft add rule ip routergeist_nat postrouting oif "$WAN_IF" masquerade || true

# Allow forwarding from LAN edge to WAN and established traffic
nft add rule inet routergeist_filter forward ct state established,related accept || true
nft add rule inet routergeist_filter forward iif "$LAN_EDGE_IF" oif "$WAN_IF" accept || true

# 5) dnsmasq minimal config for DHCP on LAN
mkdir -p /etc/routergeist
cat >/etc/routergeist/dnsmasq.conf <<EOF
interface=$LAN_EDGE_IF
dhcp-range=$DHCP_START,$DHCP_END,24h
bind-interfaces
log-queries
log-facility=/var/log/dnsmasq.log
# Default gateway and DNS options
dhcp-option=3,$LAN_IP
EOF

# Append DNS servers for clients if configured
if [[ -n "$LAN_DNS" && "$LAN_DNS" != "null" && "$LAN_DNS" != "" ]]; then
  IFS=',' read -r -a DNS_ARR <<< "$LAN_DNS"
  echo -n "dhcp-option=6" >> /etc/routergeist/dnsmasq.conf
  for d in "${DNS_ARR[@]}"; do echo -n ",$d" >> /etc/routergeist/dnsmasq.conf; done
  echo >> /etc/routergeist/dnsmasq.conf
fi

# Append DHCP reservations
if jq -e '.dhcp_reservations | length > 0' "$CFG_JSON" >/dev/null 2>&1; then
  while IFS= read -r item; do
    MAC=$(jq -r .mac <<<"$item")
    IP=$(jq -r .ip <<<"$item")
    HOST=$(jq -r .hostname <<<"$item")
    echo "dhcp-host=$MAC,$IP,$HOST" >> /etc/routergeist/dnsmasq.conf
  done < <(jq -c '.dhcp_reservations[]' "$CFG_JSON")
fi

# Append DNS overrides
if jq -e '.dns_overrides | length > 0' "$CFG_JSON" >/dev/null 2>&1; then
  while IFS= read -r item; do
    H=$(jq -r .host <<<"$item")
    IP=$(jq -r .ip <<<"$item")
    echo "address=/$H/$IP" >> /etc/routergeist/dnsmasq.conf
  done < <(jq -c '.dns_overrides[]' "$CFG_JSON")
fi
# Start dnsmasq (systemd if present; otherwise directly)
if [ -d /run/systemd/system ]; then
  systemctl stop dnsmasq.service || true
  mkdir -p /etc/systemd/system
  cat >/etc/systemd/system/routergeist-dnsmasq.service <<'UNIT'
[Unit]
Description=RouterGeist dnsmasq
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/sbin/dnsmasq --conf-file=/etc/routergeist/dnsmasq.conf --user=nobody --group=nogroup --keep-in-foreground
Restart=always

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable --now routergeist-dnsmasq.service || true
else
  pkill -x dnsmasq >/dev/null 2>&1 || true
  sleep 0.5
  dnsmasq --conf-file=/etc/routergeist/dnsmasq.conf --user=nobody --group=nogroup --keep-in-foreground &
  echo "dnsmasq started (container mode)"
fi

# 6) hostapd config for AP (on Wi‑Fi interface)
mkdir -p /etc/routergeist
mkdir -p /var/run/hostapd || true
# Sanitize PSK and select correct hostapd key directive
PSK_CLEAN=$(printf '%s' "$PSK" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
if echo "$PSK_CLEAN" | grep -Eq '^[0-9A-Fa-f]{64}$'; then
  WPA_LINE="wpa_psk=$PSK_CLEAN"
else
  # hostapd passphrase must be 8..63 ASCII
  WPA_LINE="wpa_passphrase=$PSK_CLEAN"
fi
cat >/etc/routergeist/hostapd.conf <<EOF
country_code=$COUNTRY
interface=$AP_IF
driver=nl80211
ssid=$SSID
hw_mode=g
channel=$CHANNEL
ieee80211d=1
ieee80211n=1
wmm_enabled=1
wmm_ac_bk_cwmin=4
wmm_ac_bk_cwmax=10
wmm_ac_bk_aifs=7
wmm_ac_bk_txop_limit=0
wmm_ac_be_aifs=3
wmm_ac_vi_aifs=2
wmm_ac_vo_aifs=2
wpa=2
$WPA_LINE
# WPA2-PSK (RSN) with AES/CCMP only for modern client compatibility (iOS/Android)
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
auth_algs=1
ieee80211w=0
macaddr_acl=0
ignore_broadcast_ssid=0
ctrl_interface=/var/run/hostapd
ap_isolate=0
disassoc_low_ack=1
beacon_int=100
dtim_period=2
max_num_sta=64
EOF
# Start hostapd (prefer systemd when PID 1 is systemd or container runs with systemd)
if [ -d /run/systemd/system ] && pidof systemd >/dev/null 2>&1; then
  cat >/etc/systemd/system/routergeist-hostapd.service <<'UNIT'
[Unit]
Description=RouterGeist hostapd
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/sbin/hostapd /etc/routergeist/hostapd.conf -d
Restart=always

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable --now routergeist-hostapd.service || true
else
  pkill -x hostapd >/dev/null 2>&1 || true
  # Let hostapd perform the interface type switch to AP
  hostapd -B /etc/routergeist/hostapd.conf
  echo "hostapd started (container mode)"
fi

# 7) WAN
# Do not disrupt an already-connected WAN (e.g., managed by NetworkManager).
if [[ "$WAN_MODE" == "dhcp" ]]; then
  if ! ip -4 addr show dev "$WAN_IF" | grep -q " inet "; then
    dhclient -r "$WAN_IF" || true
    dhclient "$WAN_IF" || true
  fi
elif [[ "$WAN_MODE" == "static" ]]; then
  if [[ -n "$WAN_STATIC_ADDR" ]]; then ip addr add "$WAN_STATIC_ADDR" dev "$WAN_IF" || true; fi
  ip link set "$WAN_IF" up || true
  ip route replace default via "$WAN_STATIC_GW" dev "$WAN_IF" || true
fi

echo "Router config applied"

# 8) Port forwards (DNAT) from WAN to internal hosts
if jq -e '.forwards | length > 0' "$CFG_JSON" >/dev/null 2>&1; then
  while IFS= read -r item; do
    PROTO=$(jq -r .proto <<<"$item")
    INP=$(jq -r .in_port <<<"$item")
    DIP=$(jq -r .dest_ip <<<"$item")
    DPT=$(jq -r .dest_port <<<"$item")
    if [[ "$PROTO" == "tcp" || "$PROTO" == "udp" ]]; then
      nft add rule ip nat prerouting iif "$WAN_IF" $PROTO dport $INP dnat to $DIP:$DPT || true
    fi
  done < <(jq -c '.forwards[]' "$CFG_JSON")
fi

