"""Module 1 — Chargement et validation de la configuration."""

from . import yaml_io
from .constants import MIN_NOEUDS


def charger_config(chemin):
    with open(chemin, "r", encoding="utf-8") as f:
        return yaml_io.safe_load(f.read())


def valider_config(config):
    erreurs = []
    if not isinstance(config, dict):
        return ["config.yml invalide (pas un mapping YAML)"]

    cluster = config.get("cluster")
    if not isinstance(cluster, dict):
        erreurs.append("Section 'cluster' manquante")
    else:
        if not cluster.get("nom"):
            erreurs.append("cluster.nom manquant")
        n = cluster.get("nombre_noeuds")
        if not isinstance(n, int):
            erreurs.append("cluster.nombre_noeuds doit être un entier")
        elif n < MIN_NOEUDS:
            erreurs.append(
                f"cluster.nombre_noeuds doit être >= {MIN_NOEUDS} (reçu {n})"
            )

    if "ip_maitre" not in config:
        erreurs.append("Clé 'ip_maitre' manquante (peut être vide)")
    return erreurs
