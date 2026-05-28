# BD_reparti — Cluster Elasticsearch distribué

Générateur automatique de fichiers `docker-compose` pour déployer un cluster
**Elasticsearch 8.13** (`vpdf-cluster`) réparti sur plusieurs machines, avec
Kibana sur la machine maître.

---

## 1. Architecture

- **1 machine maître** : 3 nœuds Elasticsearch + 1 Kibana
- **N machines auxiliaires** : 1 nœud Elasticsearch chacune
- **Total** : ≥ 7 nœuds (donc ≥ 4 auxiliaires)

Convention de ports (calculée automatiquement) :

| Nœud N | Port HTTP externe | Port Transport externe |
|---|---|---|
| node-N | `9200 + N` | `9300 + N` |

---

## 2. Pré‑requis

Sur chaque machine (maître + auxiliaires) :

- Linux (Ubuntu / Debian recommandé)
- Python ≥ 3.8
- Docker + Docker Compose v2 (`docker compose ...`)
- Connectivité réseau entre toutes les machines (LAN /24)
- Paramètre kernel pour Elasticsearch :

```bash
sudo sysctl -w vm.max_map_count=262144
```

Installer la seule dépendance Python externe :

```bash
pip3 install pyyaml
```

---

## 3. Configuration

Éditer le fichier [`config.yml`](./config.yml) :

```yaml
cluster:
  nom: "vpdf-cluster"     # nom partagé par tous les nœuds
  nombre_noeuds: 7         # total (≥ 7)

# Laisser VIDE  → cette machine est le MAÎTRE
# Renseigner    → cette machine est un AUXILIAIRE (IP du maître)
ip_maitre: ""
```

---

## 4. Déploiement

### 4.1 Sur la machine maître

```bash
# config.yml : ip_maitre = ""
python3 generate_compose.py
```

Le script :
1. détecte l'IP locale,
2. scanne le réseau /24 (ping sweep parallèle, ~5 s),
3. propose les machines découvertes ; on sélectionne les auxiliaires
   (ex : `1,2,3,4`),
4. génère **`docker-compose-prim.yml`** (3 nœuds ES + Kibana).

Démarrage du cluster :

```bash
docker compose -f docker-compose-prim.yml up -d
docker compose -f docker-compose-prim.yml ps
```

Kibana : http://<ip_maitre>:5601

### 4.2 Sur chaque machine auxiliaire

```bash
# config.yml : ip_maitre = "192.168.x.y"   (IP du maître)
python3 generate_compose.py
```

Le script :
1. interroge l'API ES du maître (`_cat/nodes`),
2. attribue automatiquement le prochain numéro de nœud libre,
3. génère **`docker-compose-aux.yml`** (1 nœud).

Démarrage :

```bash
docker compose -f docker-compose-aux.yml up -d
```

Le nœud rejoint le cluster automatiquement.

### 4.3 Vérification du cluster

Depuis n'importe quelle machine du cluster :

```bash
curl http://<ip_maitre>:9201/_cat/nodes?v
curl http://<ip_maitre>:9201/_cluster/health?pretty
```

---

## 5. Structure du projet

```
BD_reparti/
├── config.yml                 # configuration utilisateur
├── generate_compose.py        # point d'entrée
├── cluster_gen/               # package Python (modules)
│   ├── constants.py
│   ├── config.py              # chargement + validation YAML
│   ├── reseau.py              # détection IP + scan /24
│   ├── maitre_es.py           # interrogation API ES
│   ├── topologie.py           # topologie + seed_hosts
│   ├── compose.py             # génération YAML docker-compose
│   └── cli.py                 # modes interactifs
├── docker-compose-prim.yml    # [GÉNÉRÉ] machine maître
├── docker-compose-aux.yml     # [GÉNÉRÉ] machine auxiliaire
├── docker-compose.principal.yml             # exemple manuel (existant)
├── docker-compose-auxilliaire.example.yml   # exemple manuel (existant)
├── ingest-node-master.py      # script d'ingestion
└── GUIDE_DEPLOIEMENT_V2.md    # documentation détaillée
```

---

## 6. Ingestion de données

Une fois le cluster vert :

```bash
pip3 install elasticsearch
python3 ingest-node-master.py
```

---

## 7. Options du script

```bash
python3 generate_compose.py --help
python3 generate_compose.py --config autre_config.yml
```

---

## 8. Limitations connues

- Le scan réseau suppose un sous‑réseau **/24**.
- Le ping sweep nécessite **ICMP autorisé** sur le LAN.
- Sécurité ES désactivée (`xpack.security.enabled=false`) — **usage en
  réseau de confiance uniquement**.
- Si plusieurs auxiliaires s'enregistrent simultanément, relancer le script
  sur celui qui échoue.
- Linux uniquement (option `ping -W`).

Voir [`GUIDE_DEPLOIEMENT_V2.md`](./GUIDE_DEPLOIEMENT_V2.md) pour la
procédure manuelle de référence.
