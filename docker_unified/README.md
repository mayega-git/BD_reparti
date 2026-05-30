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
| `IP_LOCALE`    | IP de cette machine. Renseignée → utilisée directement. Vide → auto-détection via `SOUS_RESEAU` |
| `SOUS_RESEAU`  | CIDR du LAN, utilisé uniquement si `IP_LOCALE` est vide |
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

## 3 bis. Arrêt des containers

Depuis le dossier `docker_unified/` :

```bash
# Maître — arrête et supprime les 3 nœuds ES + Kibana
docker compose --profile master down

# Auxiliaire — arrête et supprime le nœud aux + Kibana aux
docker compose --profile aux down
```

`down` préserve les volumes (données ES conservées). Variantes utiles :

| Commande | Effet |
|---|---|
| `docker compose --profile master stop` | arrête sans supprimer les containers |
| `docker compose --profile master start` | redémarre des containers déjà créés |
| `docker compose --profile master restart` | stop + start |
| `docker compose --profile master down -v` | ⚠ supprime aussi les volumes (**perte des données ES**) |

Arrêter un container particulier :

```bash
docker stop vpdf-node1
docker stop vpdf-node-aux
```

Voir l'état :

```bash
docker compose ps
docker ps -a | grep vpdf
```

## 3 ter. Dépannage

### `Conflict. The container name "/vpdf-node1" is already in use`

Un ancien container du même nom existe encore (par exemple créé par
l'ancien `docker-compose.principal.yml`). Le supprimer :

```bash
# Tous les containers vpdf-* en une commande
docker rm -f $(docker ps -aq --filter "name=vpdf-")

# Puis relancer
docker compose --profile master up -d --build
```

Si tu sais d'où venait l'ancien compose, l'idéal est de le couper proprement
avant :

```bash
# depuis le dossier de l'ancien compose
docker compose -f docker-compose.principal.yml down
```

### `bootstrap checks failed: max virtual memory areas vm.max_map_count is too low`

```bash
sudo sysctl -w vm.max_map_count=262144
# Pour le rendre permanent :
echo "vm.max_map_count=262144" | sudo tee /etc/sysctl.d/99-elasticsearch.conf
```

### `Aucune IP locale dans 192.168.123.0/24`

L'entrypoint n'a trouvé aucune interface dans le `SOUS_RESEAU` indiqué.
Vérifier :

```bash
ip -4 addr show | grep inet
```

et corriger `SOUS_RESEAU` dans `.env`.

## 4. Vérification

```bash
curl http://<ip_maitre>:9201/_cat/nodes?v
curl http://<ip_maitre>:9201/_cluster/health?pretty
```

Kibana : http://<ip_maitre>:5601

## 4 bis. Pare-feu

Avec `network_mode: host`, les ports des containers sont **directement
ceux de l'hôte** : il faut donc autoriser le trafic au niveau du
firewall de chaque machine. Adapter `192.168.123.0/24` au CIDR réel.

### Ouvrir (avant le `up -d`)

**Sur la machine maître** (`ufw`, Debian/Ubuntu) :

```bash
sudo ufw allow from 192.168.123.0/24 to any port 9201:9203 proto tcp comment 'vpdf-es-http'
sudo ufw allow from 192.168.123.0/24 to any port 9301:9303 proto tcp comment 'vpdf-es-transport'
sudo ufw allow from 192.168.123.0/24 to any port 5601    proto tcp comment 'vpdf-kibana'
```

**Sur chaque machine auxiliaire** — remplacer `N` par le numéro du nœud
(ex. `4` pour `node-4`) :

```bash
sudo ufw allow from 192.168.123.0/24 to any port 920N proto tcp comment 'vpdf-es-http'
sudo ufw allow from 192.168.123.0/24 to any port 930N proto tcp comment 'vpdf-es-transport'
sudo ufw allow from 192.168.123.0/24 to any port 5601 proto tcp comment 'vpdf-kibana'
```

> Le port **transport `930N`** est obligatoire : le maître y ouvre des
> connexions retour pour propager le cluster state et répliquer les shards.

Variante `firewalld` (Fedora/RHEL) :
```bash
sudo firewall-cmd --permanent --add-rich-rule='rule family=ipv4 source address=192.168.123.0/24 port port=9201-9203 protocol=tcp accept'
sudo firewall-cmd --permanent --add-rich-rule='rule family=ipv4 source address=192.168.123.0/24 port port=9301-9303 protocol=tcp accept'
sudo firewall-cmd --permanent --add-rich-rule='rule family=ipv4 source address=192.168.123.0/24 port port=5601 protocol=tcp accept'
sudo firewall-cmd --reload
```

### Fermer (après usage)

**Sur la machine maître** :

```bash
sudo ufw delete allow from 192.168.123.0/24 to any port 9201:9203 proto tcp
sudo ufw delete allow from 192.168.123.0/24 to any port 9301:9303 proto tcp
sudo ufw delete allow from 192.168.123.0/24 to any port 5601    proto tcp
```

**Sur chaque machine auxiliaire** :

```bash
sudo ufw delete allow from 192.168.123.0/24 to any port 920N proto tcp
sudo ufw delete allow from 192.168.123.0/24 to any port 930N proto tcp
sudo ufw delete allow from 192.168.123.0/24 to any port 5601 proto tcp
```

Vérifier l'état :
```bash
sudo ufw status numbered
```

Variante `firewalld` (utiliser `--remove-rich-rule` avec la même règle qu'à
l'ouverture) :
```bash
sudo firewall-cmd --permanent --remove-rich-rule='rule family=ipv4 source address=192.168.123.0/24 port port=9201-9203 protocol=tcp accept'
sudo firewall-cmd --permanent --remove-rich-rule='rule family=ipv4 source address=192.168.123.0/24 port port=9301-9303 protocol=tcp accept'
sudo firewall-cmd --permanent --remove-rich-rule='rule family=ipv4 source address=192.168.123.0/24 port port=5601 protocol=tcp accept'
sudo firewall-cmd --reload
```

> Si le pare-feu est désactivé sur ta machine (`sudo ufw status` →
> `inactive`), aucune action n'est nécessaire — mais ES est alors
> exposé sur **toutes** les interfaces.

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
