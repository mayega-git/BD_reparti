"""Module 6 — Génération des fichiers docker-compose.

Notes :
  - `cluster.initial_master_nodes` n'est inclus QUE dans le fichier maître
    (bootstrap initial). Les nœuds auxiliaires qui rejoignent un cluster
    déjà formé ne doivent pas porter cette directive (risque de split-brain).
  - La liste `initial_master_nodes` ne contient que les nœuds maîtres
    éligibles du bootstrap, soit `node-1,node-2,node-3`.
"""

import yaml

from .constants import ES_IMAGE, KIBANA_IMAGE, NOEUDS_PRINCIPAUX
from .topologie import construire_seed_hosts, construire_master_nodes


def _service_es(numero, topologie, nom_cluster, inclure_initial_masters):
    info = topologie[numero]
    env = [
        f"node.name=node-{numero}",
        f"cluster.name={nom_cluster}",
        "network.host=0.0.0.0",
        f"network.publish_host={info['ip']}",
        f"discovery.seed_hosts={construire_seed_hosts(topologie, numero)}",
    ]
    if inclure_initial_masters:
        env.append(
            f"cluster.initial_master_nodes={construire_master_nodes(NOEUDS_PRINCIPAUX)}"
        )
    env += [
        f"transport.publish_port={info['transport']}",
        "xpack.security.enabled=false",
        "xpack.license.self_generated.type=basic",
        "ES_JAVA_OPTS=-Xms512m -Xmx512m",
        "bootstrap.memory_lock=true",
    ]
    return {
        "image": ES_IMAGE,
        "container_name": f"vpdf-node{numero}",
        "environment": env,
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

    services = {}
    volumes = {}
    for n in range(1, NOEUDS_PRINCIPAUX + 1):
        services[f"es-node{n}"] = _service_es(
            n, topologie, nom_cluster, inclure_initial_masters=True
        )
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

    services = {
        f"es-node{numero_noeud}": _service_es(
            numero_noeud, topologie, nom_cluster, inclure_initial_masters=False
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
