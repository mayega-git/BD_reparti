"""Module 5 — Construction de la topologie du cluster."""

from .constants import NOEUDS_PRINCIPAUX


def construire_topologie(ip_principale, ips_auxiliaires, nombre_noeuds):
    topo = {}
    for i in range(1, NOEUDS_PRINCIPAUX + 1):
        topo[i] = {"ip": ip_principale, "http": 9200 + i, "transport": 9300 + i}
    for j, ip in enumerate(ips_auxiliaires, start=NOEUDS_PRINCIPAUX + 1):
        if j > nombre_noeuds:
            break
        topo[j] = {"ip": ip, "http": 9200 + j, "transport": 9300 + j}
    return topo


def construire_seed_hosts(topologie, exclure_noeud):
    parts = [
        f"{info['ip']}:{info['transport']}"
        for n, info in sorted(topologie.items())
        if n != exclure_noeud
    ]
    return ",".join(parts)


def construire_master_nodes(nombre_noeuds):
    return ",".join(f"node-{i}" for i in range(1, nombre_noeuds + 1))
