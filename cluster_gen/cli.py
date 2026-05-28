"""Module 7 — CLI interactif (mode maître et mode auxiliaire)."""

import ipaddress
import sys

from .compose import generer_compose_principal, generer_compose_auxiliaire
from .constants import NOEUDS_PRINCIPAUX
from .maitre_es import interroger_maitre
from .reseau import scanner_reseau
from .topologie import construire_topologie


def print_header():
    print("═══════════════════════════════════════")
    print("  Générateur Docker-Compose ES Cluster")
    print("═══════════════════════════════════════\n")


def _selectionner_auxiliaires(decouverts, nb_requis):
    print(f"✓ {len(decouverts)} machines découvertes :")
    for i, ip in enumerate(decouverts, 1):
        print(f"  [{i}] {ip}")
    while True:
        saisie = input(
            f"\n→ Sélectionnez {nb_requis} machines auxiliaires "
            f"(ex: 1,2,3,4) : "
        ).strip()
        try:
            idx = [int(x) for x in saisie.split(",") if x.strip()]
            if len(idx) != nb_requis:
                print(f"  ✗ Attendu {nb_requis} indices, reçu {len(idx)}")
                continue
            if any(i < 1 or i > len(decouverts) for i in idx):
                print("  ✗ Indice hors plage")
                continue
            return [decouverts[i - 1] for i in idx]
        except ValueError:
            print("  ✗ Saisie invalide")


def mode_maitre(config, ip_locale):
    nombre_noeuds = config["cluster"]["nombre_noeuds"]
    nb_aux = nombre_noeuds - NOEUDS_PRINCIPAUX

    print("ℹ Mode : MAÎTRE (ip_maitre vide dans config)")
    print(f"ℹ Cluster : {config['cluster']['nom']} | {nombre_noeuds} nœuds total\n")
    reseau = ipaddress.ip_network(f"{ip_locale}/24", strict=False)
    print(f"⏳ Scan du réseau {reseau} ...")
    decouverts = scanner_reseau(ip_locale)

    if len(decouverts) < nb_aux:
        print(
            f"✗ Seulement {len(decouverts)} machines découvertes, "
            f"{nb_aux} requises."
        )
        sys.exit(1)

    ips_aux = _selectionner_auxiliaires(decouverts, nb_aux)
    topologie = construire_topologie(ip_locale, ips_aux, nombre_noeuds)

    print("\n✓ Topologie construite :")
    for n in sorted(topologie):
        info = topologie[n]
        role = "principal" if n <= NOEUDS_PRINCIPAUX else "auxiliaire"
        print(
            f"  node-{n} → {info['ip']}:{info['http']}/{info['transport']} ({role})"
        )

    contenu = generer_compose_principal(topologie, config)
    sortie = "docker-compose-prim.yml"
    with open(sortie, "w", encoding="utf-8") as f:
        f.write(contenu)
    print(f"\n✓ Fichier généré : {sortie}")


def mode_auxiliaire(config, ip_locale):
    ip_maitre = config["ip_maitre"]
    nombre_noeuds = config["cluster"]["nombre_noeuds"]

    print(f"ℹ Mode : AUXILIAIRE (maître = {ip_maitre})")
    print("ℹ Interrogation du maître ES...")

    reponse = interroger_maitre(ip_maitre)
    noeuds_existants = []
    if reponse is not None:
        for n in reponse["noeuds"]:
            nom = n.get("name", "")
            if nom.startswith("node-"):
                try:
                    noeuds_existants.append(int(nom.split("-")[1]))
                except (ValueError, IndexError):
                    pass
        print(
            f"✓ Cluster trouvé : {config['cluster']['nom']} "
            f"({len(noeuds_existants)} nœuds actifs)"
        )
    else:
        print("⚠ Maître ES non accessible — fallback interactif")

    numero = None
    if noeuds_existants:
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

    topologie = {}
    for i in range(1, NOEUDS_PRINCIPAUX + 1):
        topologie[i] = {"ip": ip_maitre, "http": 9200 + i, "transport": 9300 + i}
    topologie[numero] = {
        "ip": ip_locale,
        "http": 9200 + numero,
        "transport": 9300 + numero,
    }

    print(
        f"✓ Nœud attribué : node-{numero} "
        f"(ports {9200 + numero}/{9300 + numero})"
    )

    contenu = generer_compose_auxiliaire(numero, topologie, config)
    sortie = "docker-compose-aux.yml"
    with open(sortie, "w", encoding="utf-8") as f:
        f.write(contenu)
    print(f"\n✓ Fichier généré : {sortie}")
