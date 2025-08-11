from __future__ import annotations

import subprocess
from typing import Optional


def block_ip(ip: str) -> bool:
    # nftables preferred; fall back to iptables
    try:
        subprocess.run(["sudo", "/bin/bash", "/opt/routergeist/scripts/privileged/assign_roles.sh", "block_ip", ip], check=False)
        return True
    except Exception:
        try:
            subprocess.run(["sudo", "nft", "add", "rule", "inet", "filter", "input", "ip", "saddr", ip, "drop"], check=False)
            subprocess.run(["sudo", "nft", "add", "rule", "inet", "filter", "forward", "ip", "saddr", ip, "drop"], check=False)
            return True
        except Exception:
            try:
                subprocess.run(["sudo", "iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"], check=False)
                subprocess.run(["sudo", "iptables", "-I", "FORWARD", "-s", ip, "-j", "DROP"], check=False)
                return True
            except Exception:
                return False



