# vpdf-cluster — déploiement Docker unifié

Une seule image (`vpdf-cluster-node`) et un seul `docker-compose.yml`
auto-configurent chaque machine en fonction de son rôle (maître ou
auxiliaire), sans génération préalable de fichier YAML.

---

## 1. Pré-requis

- Linux + Docker + Docker Compose v2 (`docker compose`)
- Sur chaque hôte :
  ```bash
  sudo sysctl -w vm.max_map_count=262144
  ```
- Connectivité TCP entre les machines sur les ports `9201-9203` (HTTP)
  et `9301-9303` (transport, + `930N` pour chaque auxiliaire).

## 2. Configuration

```bash
cp .env.example .env
$EDITOR .env
```

Variables :

| Clé | Description |
|---|---|
| `CLUSTER_NAME` | nom du cluster (identique partout) |
| `SOUS_RESEAU`  | CIDR du LAN — sert à détecter l'IP locale sans se tromper |
| `IP_MAITRE`    | vide = maître ; renseigné = auxiliaire (IP du maître) |

## 3. Lancement

### Sur la machine maître
```bash
docker compose --profile master up -d --build
```
Démarre `vpdf-node1`, `vpdf-node2`, `vpdf-node3` et `vpdf-kibana`.

### Sur chaque machine auxiliaire
```bash
docker compose --profile aux up -d --build
```
Démarre `vpdf-node-aux` (numéro de nœud auto-attribué via l'API du
maître) + une Kibana qui pointe sur le maître.

## 4. Vérification

```bash
curl http://<ip_maitre>:9201/_cat/nodes?v
curl http://<ip_maitre>:9201/_cluster/health?pretty
```

Kibana : http://<ip_maitre>:5601

## 5. Comment ça marche

Au démarrage, le container exécute `entrypoint.py` qui :

1. Lit `MODE`, `CLUSTER_NAME`, `SOUS_RESEAU`, etc.
2. Parcourt `ip -o -4 addr show` (interfaces hôte, grâce à
   `network_mode: host`) et retient la première IP du `SOUS_RESEAU` —
   **garantit qu'on ne prend pas l'IP d'une interface Docker ou VPN**.
3. Calcule `discovery.seed_hosts` :
   - **master** → ses 2 voisins locaux
   - **aux**    → 3 maîtres + auxiliaires déjà connus (via `_cat/nodes`)
4. Exporte les variables ES (`node.name`, `discovery.seed_hosts`,
   `network.publish_host`, `http.port`, `transport.port`, …) que
   l'image officielle ES sait consommer.
5. `exec` l'entrypoint Elasticsearch standard.

Un fichier `.bootstrapped` est créé dans le volume `es-data*` ; il
empêche la directive `cluster.initial_master_nodes` d'être réinjectée
lors d'un redémarrage (évite les risques de split-brain).

## 6. Limitations

- `network_mode: host` → Linux uniquement.
- L'image custom doit être présente sur chaque hôte. Soit `--build`
  sur place, soit `docker save | ssh ... docker load` depuis un build
  central.
- Si deux auxiliaires démarrent dans la même seconde, ils peuvent
  obtenir le même numéro (race condition non couverte ; relancer celui
  qui échoue).
- Sécurité ES désactivée (`xpack.security.enabled=false`) — usage en
  LAN de confiance uniquement.

## 7. Comparaison avec l'ancien workflow

| | Ancien (`generate_compose.py`) | Nouveau (Docker unifié) |
|---|---|---|
| Hôte | Python 3 requis | Docker uniquement |
| Étapes | 1. générer 2. up | 1. up |
| Fichiers générés | docker-compose-prim.yml / -aux.yml | aucun |
| Configuration | config.yml | .env |
| Détection IP | heuristique multi-étape | filtrée par CIDR (`SOUS_RESEAU`) |

L'ancien chemin reste disponible sur la branche
`claude/youthful-tesla-CzIt5`.
