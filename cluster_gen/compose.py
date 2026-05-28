"""Module 6 — Génération des fichiers docker-compose."""

import yaml

from .constants import ES_IMAGE, KIBANA_IMAGE, NOEUDS_PRINCIPAUX
from .topologie import construire_seed_hosts, construire_master_nodes


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
