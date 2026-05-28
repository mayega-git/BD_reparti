"""Module 2 & 3 — Détection IP locale et scan réseau /24."""

import ipaddress
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor


def detecter_ip_locale():
    # Méthode 1 : socket UDP trick
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
        finally:
            s.close()
    except OSError:
        pass

    # Méthode 2 : gethostbyname
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass

    # Méthode 3 : parsing `ip -4 addr show`
    try:
        out = subprocess.check_output(["ip", "-4", "addr", "show"], text=True)
        for m in re.finditer(r"inet\s+(\d+\.\d+\.\d+\.\d+)/", out):
            ip = m.group(1)
            if not ip.startswith("127."):
                return ip
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    raise RuntimeError("Impossible de détecter l'IP locale")


def _ping(ip):
    try:
        r = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return ip if r.returncode == 0 else None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def scanner_reseau(ip_locale):
    reseau = ipaddress.ip_network(f"{ip_locale}/24", strict=False)
    hotes = [str(h) for h in reseau.hosts() if str(h) != ip_locale]
    decouverts = []
    with ThreadPoolExecutor(max_workers=50) as ex:
        for res in ex.map(_ping, hotes):
            if res:
                decouverts.append(res)
    return sorted(decouverts, key=lambda x: tuple(int(o) for o in x.split(".")))
