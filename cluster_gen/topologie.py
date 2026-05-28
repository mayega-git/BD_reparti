"""Module 5 — Construction de la topologie du cluster."""

from .constants import NOEUDS_PRINCIPAUX


def construire_topologie_principale(ip_principale):
    """Topologie restreinte à la machine maître : les 3 nœuds locaux.

    Les auxiliaires rejoindront le cluster d'eux-mêmes en pointant sur
    l'IP du maître — pas besoin de les déclarer ici.
    """
    return {
        i: {"ip": ip_principale, "http": 9200 + i, "transport": 9300 + i}
        for i in range(1, NOEUDS_PRINCIPAUX + 1)
    }


def construire_seed_hosts(topologie, exclure_noeud):
    parts = [
        f"{info['ip']}:{info['transport']}"
        for n, info in sorted(topologie.items())
        if n != exclure_noeud
    ]
    return ",".join(parts)


def construire_master_nodes(nombre_noeuds):
    return ",".join(f"node-{i}" for i in range(1, nombre_noeuds + 1))
