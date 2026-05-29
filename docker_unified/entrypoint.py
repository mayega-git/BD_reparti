#!/usr/bin/env python3
"""Entrypoint d'auto-configuration pour l'image vpdf-cluster-node.

Lit la configuration via variables d'environnement, détecte l'IP locale
sur le sous-réseau cible, calcule la topologie ES, exporte les variables
attendues par l'image Elasticsearch officielle, puis exec l'entrypoint ES.

Variables d'env requises :
  MODE          master | aux
  CLUSTER_NAME  nom du cluster
  SOUS_RESEAU   CIDR du LAN (ex: 192.168.123.0/24)

Mode master :
  NODE_NUMBER   1, 2 ou 3 (fourni par docker-compose)

Mode aux :
  IP_MAITRE     IP du nœud maître (ex: 192.168.123.155)
  NODE_NUMBER   (optionnel) pour forcer le numéro, sinon auto-attribué
"""

import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

NOEUDS_PRINCIPAUX = 3
BOOTSTRAP_FLAG = "/usr/share/elasticsearch/data/.bootstrapped"


def info(msg):
    print(f"[vpdf-entrypoint] {msg}", flush=True)


def fatal(msg):
    print(f"[vpdf-entrypoint] ✗ {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


# ─────────────────────── Détection IP via sous-réseau ───────────────────────

def detecter_ip_hote(sous_reseau):
    cidr = ipaddress.ip_network(sous_reseau, strict=False)
    try:
        out = subprocess.check_output(
            ["ip", "-o", "-4", "addr", "show"], text=True
        )
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        fatal(f"Impossible d'exécuter `ip addr` : {e}")

    candidats = []
    for ligne in out.splitlines():
        m = re.match(
            r"\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", ligne
        )
        if not m:
            continue
        iface, ip = m.group(1), m.group(2)
        if iface == "lo":
            continue
        try:
            if ipaddress.ip_address(ip) in cidr:
                candidats.append((iface, ip))
        except ValueError:
            continue

    if not candidats:
        fatal(
            f"Aucune IP locale dans {sous_reseau}. "
            f"Vérifie SOUS_RESEAU dans .env et `network_mode: host`."
        )
    if len(candidats) > 1:
        info(f"⚠ Plusieurs IPs dans {sous_reseau} : {candidats}. "
             f"Choix : {candidats[0][1]}")
    iface, ip = candidats[0]
    info(f"IP hôte détectée : {ip} (interface {iface}, sous-réseau {sous_reseau})")
    return ip


# ─────────────────────── Interrogation du maître ES ───────────────────────

def interroger_maitre(ip_maitre, port=9201, tentatives=30, delai=2):
    url = f"http://{ip_maitre}:{port}/_cat/nodes?format=json&h=name,ip"
    for i in range(1, tentatives + 1):
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, socket.timeout, OSError):
            info(f"Maître pas encore prêt ({i}/{tentatives}) — retry dans {delai}s")
            time.sleep(delai)
    return None


def prochain_numero_libre(reponse_maitre):
    pris = set()
    for n in reponse_maitre or []:
        nom = n.get("name", "")
        if nom.startswith("node-"):
            try:
                pris.add(int(nom.split("-")[1]))
            except (ValueError, IndexError):
                pass
    cand = NOEUDS_PRINCIPAUX + 1
    while cand in pris:
        cand += 1
    return cand, pris


# ─────────────────────── Construction seed_hosts ───────────────────────

def seed_hosts_master(ip_hote, mon_numero):
    autres = [n for n in range(1, NOEUDS_PRINCIPAUX + 1) if n != mon_numero]
    return ",".join(f"{ip_hote}:{9300 + n}" for n in autres)


def seed_hosts_aux(ip_maitre, reponse_maitre, mon_numero, mon_ip):
    hosts = [f"{ip_maitre}:{9300 + n}" for n in range(1, NOEUDS_PRINCIPAUX + 1)]
    for n in reponse_maitre or []:
        nom, ip = n.get("name", ""), n.get("ip", "")
        if not nom.startswith("node-") or not ip:
            continue
        try:
            num = int(nom.split("-")[1])
        except (ValueError, IndexError):
            continue
        if num <= NOEUDS_PRINCIPAUX or num == mon_numero:
            continue
        hosts.append(f"{ip}:{9300 + num}")
    return ",".join(hosts)


# ─────────────────────── Préparation env ES ───────────────────────

def exporter_env(numero, ip_hote, cluster_name, seed_hosts, bootstrap):
    env = os.environ
    env["node.name"] = f"node-{numero}"
    env["cluster.name"] = cluster_name
    env["network.host"] = "0.0.0.0"
    env["network.publish_host"] = ip_hote
    env["http.port"] = str(9200 + numero)
    env["transport.port"] = str(9300 + numero)
    env["transport.publish_port"] = str(9300 + numero)
    env["discovery.seed_hosts"] = seed_hosts
    if bootstrap:
        env["cluster.initial_master_nodes"] = ",".join(
            f"node-{i}" for i in range(1, NOEUDS_PRINCIPAUX + 1)
        )
    env.setdefault("xpack.security.enabled", "false")
    env.setdefault("xpack.license.self_generated.type", "basic")
    env.setdefault("ES_JAVA_OPTS", "-Xms512m -Xmx512m")
    env.setdefault("bootstrap.memory_lock", "true")


# ─────────────────────── Main ───────────────────────

def main():
    mode = os.environ.get("MODE", "").strip().lower()
    cluster_name = os.environ.get("CLUSTER_NAME", "").strip()
    sous_reseau = os.environ.get("SOUS_RESEAU", "").strip()

    if mode not in ("master", "aux"):
        fatal("MODE doit valoir 'master' ou 'aux'")
    if not cluster_name:
        fatal("CLUSTER_NAME requis")
    if not sous_reseau:
        fatal("SOUS_RESEAU requis (ex: 192.168.123.0/24)")

    ip_hote = detecter_ip_hote(sous_reseau)

    # Bootstrap flag : ne réinjecter initial_master_nodes qu'au tout premier
    # démarrage (évite split-brain après redémarrage).
    deja_bootstrap = os.path.exists(BOOTSTRAP_FLAG)

    if mode == "master":
        numero_str = os.environ.get("NODE_NUMBER", "")
        if not numero_str.isdigit():
            fatal("NODE_NUMBER requis en mode master (1, 2 ou 3)")
        numero = int(numero_str)
        if not 1 <= numero <= NOEUDS_PRINCIPAUX:
            fatal(f"NODE_NUMBER doit être 1..{NOEUDS_PRINCIPAUX}")
        seeds = seed_hosts_master(ip_hote, numero)
        bootstrap = not deja_bootstrap
        info(
            f"Mode MASTER node-{numero} | seeds={seeds} | "
            f"bootstrap={bootstrap}"
        )

    else:  # aux
        ip_maitre = os.environ.get("IP_MAITRE", "").strip()
        if not ip_maitre:
            fatal("IP_MAITRE requis en mode aux")
        info(f"Interrogation du maître {ip_maitre} ...")
        reponse = interroger_maitre(ip_maitre)
        forced = os.environ.get("NODE_NUMBER", "")
        if forced.isdigit():
            numero = int(forced)
            info(f"NODE_NUMBER forcé : {numero}")
        elif reponse is not None:
            numero, _ = prochain_numero_libre(reponse)
        else:
            fatal(
                "Maître injoignable et NODE_NUMBER non fourni — impossible "
                "d'attribuer un numéro."
            )
        seeds = seed_hosts_aux(ip_maitre, reponse, numero, ip_hote)
        bootstrap = False  # un aux ne participe jamais au bootstrap initial
        info(f"Mode AUX node-{numero} | seeds={seeds}")

    exporter_env(numero, ip_hote, cluster_name, seeds, bootstrap)

    # Marquer ce nœud comme bootstrappé une fois qu'ES démarrera.
    # On crée le flag immédiatement : si le node crash au boot ES, le flag
    # reste — c'est ce qu'on veut, on ne réinjectera plus initial_master_nodes.
    try:
        with open(BOOTSTRAP_FLAG, "w") as f:
            f.write("1\n")
    except OSError:
        pass

    info("Exec → /usr/local/bin/docker-entrypoint.sh elasticsearch")
    os.execvp(
        "/usr/local/bin/docker-entrypoint.sh",
        ["/usr/local/bin/docker-entrypoint.sh", "elasticsearch"],
    )


if __name__ == "__main__":
    main()
