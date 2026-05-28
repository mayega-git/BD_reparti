#!/usr/bin/env python3
"""Point d'entrée du générateur docker-compose pour le cluster ES vpdf-cluster.

La logique est répartie dans le package `cluster_gen/`.
"""

import argparse
import os
import sys

from cluster_gen.cli import mode_auxiliaire, mode_maitre, print_header
from cluster_gen.config import charger_config, valider_config
from cluster_gen.reseau import detecter_ip_locale


def main():
    parser = argparse.ArgumentParser(
        description="Générateur docker-compose pour cluster ES vpdf-cluster"
    )
    parser.add_argument(
        "--config",
        default="config.yml",
        help="Chemin du fichier de configuration (défaut: config.yml)",
    )
    args = parser.parse_args()

    print_header()

    if not os.path.exists(args.config):
        print(f"✗ Fichier de configuration introuvable : {args.config}")
        sys.exit(1)

    config = charger_config(args.config)
    erreurs = valider_config(config)
    if erreurs:
        print("✗ Configuration invalide :")
        for e in erreurs:
            print(f"   - {e}")
        sys.exit(1)

    ip_locale = detecter_ip_locale()
    print(f"ℹ IP locale détectée : {ip_locale}")

    ip_maitre = (config.get("ip_maitre") or "").strip()
    if ip_maitre == "":
        mode_maitre(config, ip_locale)
    else:
        mode_auxiliaire(config, ip_locale)


if __name__ == "__main__":
    main()
