#!/usr/bin/env python3
"""Générateur automatique de fichiers docker-compose pour le cluster ES vpdf-cluster.

Deux modes :
  - MAÎTRE     : ip_maitre vide  -> docker-compose-prim.yml (3 nœuds + Kibana)
  - AUXILIAIRE : ip_maitre rempli -> docker-compose-aux.yml (1 nœud)
"""

import argparse
import ipaddress
import json
import os
import socket
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import yaml

ES_IMAGE = "elasticsearch:8.13.0"
KIBANA_IMAGE = "kibana:8.13.0"
NOEUDS_PRINCIPAUX = 3
MIN_NOEUDS = 7


# ─────────────────────────── Module 1 : config ───────────────────────────

def charger_config(chemin):
    with open(chemin, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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
            erreurs.append(f"cluster.nombre_noeuds doit être >= {MIN_NOEUDS} (reçu {n})")

    if "ip_maitre" not in config:
        erreurs.append("Clé 'ip_maitre' manquante (peut être vide)")
    return erreurs


# ───────────────────── Module 2 : détection IP locale ─────────────────────

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
        import re
        for m in re.finditer(r"inet\s+(\d+\.\d+\.\d+\.\d+)/", out):
            ip = m.group(1)
            if not ip.startswith("127."):
                return ip
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    raise RuntimeError("Impossible de détecter l'IP locale")


# ──────────────────────── Module 3 : scan réseau /24 ────────────────────────

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


# ───────────────── Module 4 : interrogation du maître ES ─────────────────

def interroger_maitre(ip_maitre):
    url = f"http://{ip_maitre}:9201/_cat/nodes?format=json&h=name,ip"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {"noeuds": data}
    except (urllib.error.URLError, socket.timeout, json.JSONDecodeError, OSError):
        return None


# ───────────────────── Module 5 : topologie ─────────────────────

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


# ─────────────── Module 6 : génération docker-compose ───────────────

def _service_es(numero, topologie, nom_cluster, nombre_noeuds):
    info = topologie[numero]
    return {
        "image": ES_IMAGE,
        "container_name": f"vpdf-node{numero}",
        "environment": [
            f"node.name=node-{numero}",
            f"cluster.name={nom_cluster}",
            "network.host=0.0.0.0",
            f"network.publish_host={info['ip']}",
            f"discovery.seed_hosts={construire_seed_hosts(topologie, numero)}",
            f"cluster.initial_master_nodes={construire_master_nodes(nombre_noeuds)}",
            f"transport.publish_port={info['transport']}",
            "xpack.security.enabled=false",
            "xpack.license.self_generated.type=basic",
            "ES_JAVA_OPTS=-Xms512m -Xmx512m",
            "bootstrap.memory_lock=true",
        ],
        "ulimits": {
            "memlock": {"soft": -1, "hard": -1},
            "nofile": {"soft": 65536, "hard": 65536},
        },
        "ports": [
            f"{info['http']}:9200",
            f"{info['transport']}:9300",
        ],
        "volumes": [f"es-data{numero}:/usr/share/elasticsearch/data"],
        "networks": ["vpdf-net"],
    }


def generer_compose_principal(topologie, config):
    nom_cluster = config["cluster"]["nom"]
    nombre_noeuds = config["cluster"]["nombre_noeuds"]

    services = {}
    volumes = {}
    for n in range(1, NOEUDS_PRINCIPAUX + 1):
        services[f"es-node{n}"] = _service_es(n, topologie, nom_cluster, nombre_noeuds)
        volumes[f"es-data{n}"] = {"name": f"vpdf-es-data{n}"}

    services["kibana"] = {
        "image": KIBANA_IMAGE,
        "container_name": "vpdf-kibana",
        "environment": [
            "ELASTICSEARCH_HOSTS=http://vpdf-node1:9200",
            "xpack.security.enabled=false",
        ],
        "ports": ["5601:5601"],
        "networks": ["vpdf-net"],
        "depends_on": ["es-node1"],
    }

    doc = {
        "version": "3.8",
        "services": services,
        "volumes": volumes,
        "networks": {
            "vpdf-net": {"name": "vpdf-network", "driver": "bridge"}
        },
    }
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)


def generer_compose_auxiliaire(numero_noeud, topologie, config):
    nom_cluster = config["cluster"]["nom"]
    nombre_noeuds = config["cluster"]["nombre_noeuds"]

    services = {
        f"es-node{numero_noeud}": _service_es(
            numero_noeud, topologie, nom_cluster, nombre_noeuds
        )
    }
    volumes = {f"es-data{numero_noeud}": {"name": f"vpdf-es-data{numero_noeud}"}}

    doc = {
        "version": "3.8",
        "services": services,
        "volumes": volumes,
        "networks": {
            "vpdf-net": {"name": "vpdf-network", "driver": "bridge"}
        },
    }
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)


# ─────────────────────── Module 7 : CLI interactif ───────────────────────

def _print_header():
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

    print(f"ℹ Mode : MAÎTRE (ip_maitre vide dans config)")
    print(f"ℹ Cluster : {config['cluster']['nom']} | {nombre_noeuds} nœuds total\n")
    reseau = ipaddress.ip_network(f"{ip_locale}/24", strict=False)
    print(f"⏳ Scan du réseau {reseau} ...")
    decouverts = scanner_reseau(ip_locale)

    if len(decouverts) < nb_aux:
        print(f"✗ Seulement {len(decouverts)} machines découvertes, "
              f"{nb_aux} requises.")
        sys.exit(1)

    ips_aux = _selectionner_auxiliaires(decouverts, nb_aux)
    topologie = construire_topologie(ip_locale, ips_aux, nombre_noeuds)

    print("\n✓ Topologie construite :")
    for n in sorted(topologie):
        info = topologie[n]
        role = "principal" if n <= NOEUDS_PRINCIPAUX else "auxiliaire"
        print(f"  node-{n} → {info['ip']}:{info['http']}/{info['transport']} ({role})")

    contenu = generer_compose_principal(topologie, config)
    sortie = "docker-compose-prim.yml"
    with open(sortie, "w", encoding="utf-8") as f:
        f.write(contenu)
    print(f"\n✓ Fichier généré : {sortie}")


def mode_auxiliaire(config, ip_locale):
    ip_maitre = config["ip_maitre"]
    nombre_noeuds = config["cluster"]["nombre_noeuds"]

    print(f"ℹ Mode : AUXILIAIRE (maître = {ip_maitre})")
    print(f"ℹ Interrogation du maître ES...")

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
        print(f"✓ Cluster trouvé : {config['cluster']['nom']} "
              f"({len(noeuds_existants)} nœuds actifs)")
    else:
        print("⚠ Maître ES non accessible — fallback interactif")

    # Attribution du numéro
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

    # Topologie : principale = ip_maitre, ce nœud à ip_locale, autres inconnus
    # On reconstruit du mieux possible (seed_hosts inclura les principaux + ce nœud)
    topologie = {}
    for i in range(1, NOEUDS_PRINCIPAUX + 1):
        topologie[i] = {"ip": ip_maitre, "http": 9200 + i, "transport": 9300 + i}
    topologie[numero] = {"ip": ip_locale, "http": 9200 + numero, "transport": 9300 + numero}

    print(f"✓ Nœud attribué : node-{numero} "
          f"(ports {9200 + numero}/{9300 + numero})")

    contenu = generer_compose_auxiliaire(numero, topologie, config)
    sortie = "docker-compose-aux.yml"
    with open(sortie, "w", encoding="utf-8") as f:
        f.write(contenu)
    print(f"\n✓ Fichier généré : {sortie}")


# ─────────────────────────── main ───────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Générateur docker-compose pour cluster ES vpdf-cluster"
    )
    parser.add_argument("--config", default="config.yml",
                        help="Chemin du fichier de configuration (défaut: config.yml)")
    args = parser.parse_args()

    _print_header()

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
