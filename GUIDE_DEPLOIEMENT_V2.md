# Guide de déploiement — Cluster VentesPleinDeFoin
## Pour tout utilisateur souhaitant rejoindre le cluster

---

## Comprendre l'architecture avant de commencer

### Le cluster et ses nœuds

Un cluster Elasticsearch est un ensemble de nœuds qui se connaissent et se partagent
les données. Chaque machine qui rejoint le cluster apporte un nœud supplémentaire.

```
Machine principale                    Machines auxiliaires
┌──────────────────┐                  ┌──────────────────┐
│ node-1           │                  │ node-5           │
│ node-2           │◄────────────────►│                  │
│ node-3           │                  └──────────────────┘
│ node-4           │
│ kibana           │                  ┌──────────────────┐
└──────────────────┘                  │ node-6           │
                                      │                  │
                                      └──────────────────┘
```

### La règle des ports

Chaque nœud occupe deux ports sur la machine hôte :

- **Port HTTP** (interroger ES) : `9200 + numéro du nœud`
- **Port transport** (communication entre nœuds) : `9300 + numéro du nœud`

```
node-1  →  HTTP: 9201  |  Transport: 9301
node-2  →  HTTP: 9202  |  Transport: 9302
node-3  →  HTTP: 9203  |  Transport: 9303
node-4  →  HTTP: 9204  |  Transport: 9304
node-5  →  HTTP: 9205  |  Transport: 9305
node-6  →  HTTP: 9206  |  Transport: 9306
node-N  →  HTTP: 920N  |  Transport: 930N
```

Cette règle s'applique quel que soit le réseau ou la machine.

### Les IPs dépendent du réseau de la machine hôte

Les adresses IP dans les fichiers de configuration dépendent
entièrement du réseau local de la machine hôte. Elles changent d'un environnement à l'autre.

Avant toute configuration, les informations suivantes sont nécessaires :
- L'IP de la **machine principale** (fournie par l'administrateur du cluster)
- L'IP de **la machine participante** (à récupérer avec `ip a`)

```
Réseau exemple A (192.168.1.x)       Réseau exemple B (10.0.0.x)
Machine principale : 192.168.1.10    Machine principale : 10.0.0.5
Machine auxiliaire : 192.168.1.25    Machine auxiliaire : 10.0.0.12
```

Le fichier de configuration est identique dans les deux cas,
seules les IPs changent.

---

## PARTIE 1 — Prérequis sur toute machine participante

### Étape 1 — Installer Docker

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

Vérifier :
```bash
docker --version
docker compose version
```

### Étape 2 — Paramètre kernel obligatoire pour Elasticsearch

```bash
sudo /sbin/sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### Étape 3 — Connaître son IP sur le réseau local

```bash
ip a | grep "inet " | grep -v 127
```

Noter l'IP affichée. C'est cette IP que les autres nœuds utiliseront pour joindre ce nœud.

### Étape 4 — Ouvrir les ports (si pare-feu actif)

```bash
# Vérifier si le pare-feu est actif
sudo ufw status
```

Si le résultat est `active`, ouvrir les ports du nœud :
```bash
sudo ufw allow 920N   # remplacer N par le numéro attribué par l'administrateur
sudo ufw allow 930N   # remplacer N par le numéro attribué par l'administrateur
```

Exemple pour node-5 :
```bash
sudo ufw allow 9205
sudo ufw allow 9305
```

---

## PARTIE 2 — Les fichiers docker-compose

### Fichier principal (machine principale)

Ce fichier est géré par l'administrateur du cluster.
Il héberge node-1 à node-4 et Kibana.

#### Version abstraite (modèle)

```yaml
version: '3.8'

services:

  es-node1:
    image: elasticsearch:8.13.0
    container_name: vpdf-node1
    environment:
      - node.name=node-1
      - cluster.name=vpdf-cluster
      - network.host=0.0.0.0
      - network.publish_host=IP_MACHINE_PRINCIPALE
      - discovery.seed_hosts=IP_MACHINE_PRINCIPALE:9302,IP_MACHINE_PRINCIPALE:9303,IP_MACHINE_PRINCIPALE:9304,IP_MACHINE_AUXILIAIRE_1:9305
      - cluster.initial_master_nodes=node-1,node-2,node-3,node-4,node-5
      - transport.publish_port=9301
      - xpack.security.enabled=false
      - xpack.license.self_generated.type=basic
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - bootstrap.memory_lock=true
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    ports:
      - "9201:9200"
      - "9301:9300"
    volumes:
      - es-data1:/usr/share/elasticsearch/data
    networks:
      - vpdf-net

  es-node2:
    image: elasticsearch:8.13.0
    container_name: vpdf-node2
    environment:
      - node.name=node-2
      - cluster.name=vpdf-cluster
      - network.host=0.0.0.0
      - network.publish_host=IP_MACHINE_PRINCIPALE
      - discovery.seed_hosts=IP_MACHINE_PRINCIPALE:9301,IP_MACHINE_PRINCIPALE:9303,IP_MACHINE_PRINCIPALE:9304,IP_MACHINE_AUXILIAIRE_1:9305
      - cluster.initial_master_nodes=node-1,node-2,node-3,node-4,node-5
      - transport.publish_port=9302
      - xpack.security.enabled=false
      - xpack.license.self_generated.type=basic
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - bootstrap.memory_lock=true
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    ports:
      - "9202:9200"
      - "9302:9300"
    volumes:
      - es-data2:/usr/share/elasticsearch/data
    networks:
      - vpdf-net

  es-node3:
    image: elasticsearch:8.13.0
    container_name: vpdf-node3
    environment:
      - node.name=node-3
      - cluster.name=vpdf-cluster
      - network.host=0.0.0.0
      - network.publish_host=IP_MACHINE_PRINCIPALE
      - discovery.seed_hosts=IP_MACHINE_PRINCIPALE:9301,IP_MACHINE_PRINCIPALE:9302,IP_MACHINE_PRINCIPALE:9304,IP_MACHINE_AUXILIAIRE_1:9305
      - cluster.initial_master_nodes=node-1,node-2,node-3,node-4,node-5
      - transport.publish_port=9303
      - xpack.security.enabled=false
      - xpack.license.self_generated.type=basic
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - bootstrap.memory_lock=true
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    ports:
      - "9203:9200"
      - "9303:9300"
    volumes:
      - es-data3:/usr/share/elasticsearch/data
    networks:
      - vpdf-net

  es-node4:
    image: elasticsearch:8.13.0
    container_name: vpdf-node4
    environment:
      - node.name=node-4
      - cluster.name=vpdf-cluster
      - network.host=0.0.0.0
      - network.publish_host=IP_MACHINE_PRINCIPALE
      - discovery.seed_hosts=IP_MACHINE_PRINCIPALE:9301,IP_MACHINE_PRINCIPALE:9302,IP_MACHINE_PRINCIPALE:9303,IP_MACHINE_AUXILIAIRE_1:9305
      - cluster.initial_master_nodes=node-1,node-2,node-3,node-4,node-5
      - transport.publish_port=9304
      - xpack.security.enabled=false
      - xpack.license.self_generated.type=basic
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - bootstrap.memory_lock=true
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    ports:
      - "9204:9200"
      - "9304:9300"
    volumes:
      - es-data4:/usr/share/elasticsearch/data
    networks:
      - vpdf-net

  kibana:
    image: kibana:8.13.0
    container_name: vpdf-kibana
    environment:
      - ELASTICSEARCH_HOSTS=http://vpdf-node1:9200
      - xpack.security.enabled=false
    ports:
      - "5601:5601"
    networks:
      - vpdf-net
    depends_on:
      - es-node1

volumes:
  es-data1:
    name: vpdf-es-data1
  es-data2:
    name: vpdf-es-data2
  es-data3:
    name: vpdf-es-data3
  es-data4:
    name: vpdf-es-data4

networks:
  vpdf-net:
    name: vpdf-network
    driver: bridge
```

#### Version concrète (avec IPs réelles — exemple de ce projet)

```yaml
# Machine principale IP : 192.168.123.155
# Machine auxiliaire 1  IP : 192.168.123.156 (node-5)

  es-node1:
    environment:
      - network.publish_host=192.168.123.155
      - discovery.seed_hosts=192.168.123.155:9302,192.168.123.155:9303,192.168.123.155:9304,192.168.123.156:9305
      - transport.publish_port=9301

  es-node2:
    environment:
      - network.publish_host=192.168.123.155
      - discovery.seed_hosts=192.168.123.155:9301,192.168.123.155:9303,192.168.123.155:9304,192.168.123.156:9305
      - transport.publish_port=9302

  es-node3:
    environment:
      - network.publish_host=192.168.123.155
      - discovery.seed_hosts=192.168.123.155:9301,192.168.123.155:9302,192.168.123.155:9304,192.168.123.156:9305
      - transport.publish_port=9303

  es-node4:
    environment:
      - network.publish_host=192.168.123.155
      - discovery.seed_hosts=192.168.123.155:9301,192.168.123.155:9302,192.168.123.155:9303,192.168.123.156:9305
      - transport.publish_port=9304
```

---

### Fichier auxiliaire (machine participante)

Ce fichier est celui que chaque nouveau participant configure sur la machine participante.
Il ne contient qu'un seul nœud.

#### Version abstraite (modèle)

```yaml
version: '3.8'

services:

  es-nodeN:                                  # remplacer N par le numéro attribué par l'administrateur
    image: elasticsearch:8.13.0
    container_name: vpdf-nodeN               # remplacer N
    environment:
      - node.name=node-N                     # remplacer N
      - cluster.name=vpdf-cluster            # NE PAS MODIFIER
      - network.host=0.0.0.0                 # NE PAS MODIFIER
      - network.publish_host=IP_MACHINE_PARTICIPANTE          # l'IP de la machine participante sur le réseau local
      - discovery.seed_hosts=IP_PRINCIPALE:9301,IP_PRINCIPALE:9302,IP_PRINCIPALE:9303,IP_PRINCIPALE:9304
                                             # IPs et ports de TOUS les autres nœuds
                                             # Ne jamais se lister le nœud lui-même
      - cluster.initial_master_nodes=node-1,node-2,node-3,node-4,node-N
                                             # liste complète + le nom du nœud
      - transport.publish_port=930N          # remplacer N
      - xpack.security.enabled=false
      - xpack.license.self_generated.type=basic
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - bootstrap.memory_lock=true
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    ports:
      - "920N:9200"                          # remplacer N
      - "930N:9300"                          # remplacer N
    volumes:
      - es-dataN:/usr/share/elasticsearch/data   # remplacer N
    networks:
      - vpdf-net

volumes:
  es-dataN:                                  # remplacer N
    name: vpdf-es-dataN                      # remplacer N

networks:
  vpdf-net:
    name: vpdf-network
    driver: bridge
```

#### Version concrète — node-5 sur 192.168.123.156

```yaml
version: '3.8'

services:

  es-node5:
    image: elasticsearch:8.13.0
    container_name: vpdf-node5
    environment:
      - node.name=node-5
      - cluster.name=vpdf-cluster
      - network.host=0.0.0.0
      - network.publish_host=192.168.123.156
      - discovery.seed_hosts=192.168.123.155:9301,192.168.123.155:9302,192.168.123.155:9303,192.168.123.155:9304
      - cluster.initial_master_nodes=node-1,node-2,node-3,node-4,node-5
      - transport.publish_port=9305
      - xpack.security.enabled=false
      - xpack.license.self_generated.type=basic
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - bootstrap.memory_lock=true
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    ports:
      - "9205:9200"
      - "9305:9300"
    volumes:
      - es-data5:/usr/share/elasticsearch/data
    networks:
      - vpdf-net

volumes:
  es-data5:
    name: vpdf-es-data5

networks:
  vpdf-net:
    name: vpdf-network
    driver: bridge
```

---

## PARTIE 3 — Procédure de démarrage dans le bon ordre

### 1. L'administrateur met à jour le fichier principal

Avant qu'une machine auxiliaire démarre, l'administrateur doit
ajouter le nouveau nœud dans `discovery.seed_hosts` de chaque nœud
existant, puis redémarrer le cluster principal :

```bash
# Sur la machine principale
docker compose down
# Modifier docker-compose.yml (ajouter IP_AUXILIAIRE:930N dans discovery)
docker compose up -d
```

### 2. La machine auxiliaire démarre

```bash
cd ~/cluster_es
docker compose up -d
```

### 3. Vérifier que le nœud a rejoint le cluster

Depuis n'importe quelle machine sur le réseau :
```bash
curl "http://IP_MACHINE_PRINCIPALE:9201/_cat/nodes?v&h=name,ip,master"
```

Le nouveau nœud doit apparaître dans la liste avec son IP.

---

## PARTIE 4 — Tableau récapitulatif des paramètres

| Paramètre | Valeur | Qui la fournit |
|---|---|---|
| `cluster.name` | `vpdf-cluster` | Fixe, ne pas modifier |
| `node.name` | `node-N` | Le prochain numéro disponible est fourni par l'administrateur du cluster |
| `network.publish_host` | IP de la machine participante | `ip a` sur la machine participante |
| `transport.publish_port` | `9300 + N` | Calculé depuis le numéro du nœud |
| `discovery.seed_hosts` | IPs et ports des autres nœuds | Fourni par l'administrateur |
| `cluster.initial_master_nodes` | Liste complète | Fourni par l'administrateur + nom du nœud à ajouter |

---

## PARTIE 5 — Résolution des problèmes fréquents

| Symptôme | Cause | Solution |
|---|---|---|
| `master_not_discovered_exception` | `transport.publish_port` manquant ou incorrect | Vérifier que le port correspond au port externe mappé |
| `Connection refused` | Pare-feu bloque le port 930N | `sudo ufw allow 930N` |
| Nœud invisible dans `_cat/nodes` | `discovery.seed_hosts` incorrect | Vérifier IPs et ports des autres nœuds |
| Kibana `server is not ready` | Cluster pas encore formé | Attendre 60s, vérifier `_cluster/health` |
| `vm.max_map_count` trop bas | Paramètre kernel insuffisant | `sudo /sbin/sysctl -w vm.max_map_count=262144` |
| `[same node ID]` dans les logs | Clone de VM sans suppression du data dir | `rm -rf /var/lib/elasticsearch/*` |
