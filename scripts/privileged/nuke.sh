#!/usr/bin/env bash
set -euo pipefail

FULL=false
if [[ "${1:-}" == "--full" ]]; then
  FULL=true
fi

log(){ echo "[nuke] $*" >&2; }

safe_wipe_dir(){
  local dir="$1"
  [[ -d "$dir" ]] || return 0
  log "Wiping directory: $dir"
  find "$dir" -type f -print0 | xargs -0 -I{} shred -zuf {} || true
  find "$dir" -type d -empty -delete || true
  rmdir "$dir" 2>/dev/null || true
}

# App-scoped paths only
safe_wipe_dir "/opt/routergeist/data"
safe_wipe_dir "/opt/routergeist/run"
safe_wipe_dir "/var/log/routergeist"

if $FULL; then
  # DANGEROUS: Attempt to wipe entire root device
  # Requires explicit server-side enablement and operator intent
  DEV=$(findmnt -n -o SOURCE / | sed 's/\[.*\]//g')
  if [[ -n "$DEV" ]]; then
    log "FULL WIPE of device $DEV initiating in 10 seconds..."
    sleep 10
    # Overwrite beginning of the device; full wipe can be very long
    dd if=/dev/urandom of="$DEV" bs=10M status=progress || true
    sync || true
  fi
fi

log "Nuke completed"


