"""Module 2 & 3 — Détection IP locale et scan réseau.

Améliorations apportées :
  - filtrage des interfaces Docker / loopback / VPN lors de la détection IP ;
  - détection automatique du préfixe CIDR réel (au lieu de /24 hardcodé)
    via `ip -o -4 addr show` puis `ip route`.
"""

import ipaddress
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor

INTERFACES_EXCLUES = ("lo", "docker", "br-", "veth", "tun", "tap", "virbr", "wg")


def _interfaces_reelles():
    """Renvoie [(iface, ip, prefixlen)] pour les interfaces non virtuelles."""
    try:
        out = subprocess.check_output(
            ["ip", "-o", "-4", "addr", "show"], text=True
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return []

    resultats = []
    for ligne in out.splitlines():
        # format : "2: eth0    inet 192.168.1.10/24 brd ..."
        m = re.match(
            r"\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", ligne
        )
        if not m:
            continue
        iface, ip, prefix = m.group(1), m.group(2), int(m.group(3))
        if any(iface.startswith(ex) for ex in INTERFACES_EXCLUES):
            continue
        if ip.startswith("127."):
            continue
        resultats.append((iface, ip, prefix))
    return resultats


def detecter_ip_locale():
    """IP de l'interface principale, en excluant Docker/VPN/loopback."""
    interfaces = _interfaces_reelles()
    if interfaces:
        # Préférer une IP privée RFC1918
        for _, ip, _ in interfaces:
            if ipaddress.ip_address(ip).is_private:
                return ip
        return interfaces[0][1]

    # Fallback 1 : socket UDP trick (filtré contre 172.17/16 Docker bridge)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if (
                ip
                and not ip.startswith("127.")
                and not ip.startswith("172.17.")
            ):
                return ip
        finally:
            s.close()
    except OSError:
        pass

    # Fallback 2 : gethostbyname
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass

    raise RuntimeError("Impossible de détecter l'IP locale")


def detecter_reseau(ip_locale):
    """Renvoie le `ip_network` couvrant ip_locale, basé sur le préfixe réel.

    Si `ip -o -4 addr show` ne trouve pas l'IP, on retombe sur /24.
    """
    for _, ip, prefix in _interfaces_reelles():
        if ip == ip_locale:
            return ipaddress.ip_network(f"{ip}/{prefix}", strict=False)
    return ipaddress.ip_network(f"{ip_locale}/24", strict=False)


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


def scanner_reseau(ip_locale, max_hotes=512):
    """Ping sweep parallèle. Limite à `max_hotes` pour éviter de scanner un /16."""
    reseau = detecter_reseau(ip_locale)
    hotes = [str(h) for h in reseau.hosts() if str(h) != ip_locale]
    if len(hotes) > max_hotes:
        # garder uniquement le /24 contenant l'IP locale
        sous = ipaddress.ip_network(f"{ip_locale}/24", strict=False)
        hotes = [str(h) for h in sous.hosts() if str(h) != ip_locale]

    decouverts = []
    with ThreadPoolExecutor(max_workers=50) as ex:
        for res in ex.map(_ping, hotes):
            if res:
                decouverts.append(res)
    return sorted(decouverts, key=lambda x: tuple(int(o) for o in x.split(".")))
