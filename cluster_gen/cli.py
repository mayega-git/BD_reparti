"""Module 7 — CLI interactif (mode maître et mode auxiliaire).

Architecture :
  - Mode MAÎTRE : génère un compose à 3 nœuds + Kibana, autonome.
    Le maître ne scanne pas le réseau ; tout auxiliaire configuré avec
    l'IP du maître rejoindra automatiquement le cluster.
  - Mode AUXILIAIRE : interroge l'API ES du maître pour récupérer
    l'état courant, calcule le prochain numéro de nœud libre, génère
    un compose avec seed_hosts = maître + auxiliaires déjà connus.
"""

import os
import sys

from .compose import generer_compose_principal, generer_compose_auxiliaire
from .constants import NOEUDS_PRINCIPAUX
from .maitre_es import interroger_maitre
from .topologie import construire_topologie_principale


def print_header():
    print("═══════════════════════════════════════")
    print("  Générateur Docker-Compose ES Cluster")
    print("═══════════════════════════════════════\n")


def _ecrire_fichier(chemin, contenu, force):
    if os.path.exists(chemin) and not force:
        rep = input(
            f"⚠ Le fichier {chemin} existe déjà. Écraser ? [y/N] : "
        ).strip().lower()
        if rep not in ("y", "yes", "o", "oui"):
            print("✗ Abandon.")
            sys.exit(1)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)


def mode_maitre(config, ip_locale, force=False):
    print("ℹ Mode : MAÎTRE (ip_maitre vide dans config)")
    print(f"ℹ Cluster : {config['cluster']['nom']}")
    print(f"ℹ Les auxiliaires rejoindront le cluster en pointant sur {ip_locale}\n")

    topologie = construire_topologie_principale(ip_locale)

    print("✓ Topologie locale :")
    for n in sorted(topologie):
        info = topologie[n]
        print(
            f"  node-{n} → {info['ip']}:{info['http']}/{info['transport']}"
        )

    contenu = generer_compose_principal(topologie, config)
    sortie = "docker-compose-prim.yml"
    _ecrire_fichier(sortie, contenu, force)
    print(f"\n✓ Fichier généré : {sortie}")


def _topologie_depuis_maitre(reponse, ip_maitre):
    """Construit la topologie à partir de la réponse `_cat/nodes` du maître.

    Retourne (topologie, set_des_numeros_existants).
    """
    topologie = {}
    existants = set()
    for n in reponse["noeuds"]:
        nom = n.get("name", "")
        ip = n.get("ip", "")
        if not nom.startswith("node-") or not ip:
            continue
        try:
            num = int(nom.split("-")[1])
        except (ValueError, IndexError):
            continue
        ip_effective = ip_maitre if num <= NOEUDS_PRINCIPAUX else ip
        topologie[num] = {
            "ip": ip_effective,
            "http": 9200 + num,
            "transport": 9300 + num,
        }
        existants.add(num)
    return topologie, existants


def mode_auxiliaire(config, ip_locale, force=False):
    ip_maitre = config["ip_maitre"]
    nombre_noeuds = config["cluster"]["nombre_noeuds"]

    print(f"ℹ Mode : AUXILIAIRE (maître = {ip_maitre})")
    print("ℹ Interrogation du maître ES...")

    reponse = interroger_maitre(ip_maitre)
    topologie = {}
    noeuds_existants = set()

    if reponse is not None:
        topologie, noeuds_existants = _topologie_depuis_maitre(
            reponse, ip_maitre
        )
        print(
            f"✓ Cluster trouvé : {config['cluster']['nom']} "
            f"({len(noeuds_existants)} nœuds actifs)"
        )
    else:
        print("⚠ Maître ES non accessible — fallback dégradé")
        for i in range(1, NOEUDS_PRINCIPAUX + 1):
            topologie[i] = {
                "ip": ip_maitre,
                "http": 9200 + i,
                "transport": 9300 + i,
            }
            noeuds_existants.add(i)

    numero = None
    for cand in range(NOEUDS_PRINCIPAUX + 1, nombre_noeuds + 1):
        if cand not in noeuds_existants:
            numero = cand
            break

    if numero is None:
        while True:
            try:
                saisie = input(
                    f"→ Numéro de ce nœud "
                    f"({NOEUDS_PRINCIPAUX + 1}–{nombre_noeuds}) : "
                ).strip()
                numero = int(saisie)
                if NOEUDS_PRINCIPAUX < numero <= nombre_noeuds:
                    break
                print("  ✗ Hors plage")
            except ValueError:
                print("  ✗ Saisie invalide")

    topologie[numero] = {
        "ip": ip_locale,
        "http": 9200 + numero,
        "transport": 9300 + numero,
    }

    print(
        f"✓ Nœud attribué : node-{numero} "
        f"(ports {9200 + numero}/{9300 + numero})"
    )
    print(f"  seed_hosts inclura {len(topologie) - 1} autres nœuds")

    contenu = generer_compose_auxiliaire(numero, topologie, config)
    sortie = "docker-compose-aux.yml"
    _ecrire_fichier(sortie, contenu, force)
    print(f"\n✓ Fichier généré : {sortie}")
