from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

es = Elasticsearch(["http://localhost:9201"])

# ── CLIENTS ──────────────────────────────────────────
clients = [
    {"noClient": 10, "nomClient": "Luc Sansom",       "noTelephone": "(999)999-9999"},
    {"noClient": 20, "nomClient": "Dollard Tremblay",  "noTelephone": "(888)888-8888"},
    {"noClient": 30, "nomClient": "Lin Bô",            "noTelephone": "(777)777-7777"},
    {"noClient": 40, "nomClient": "Jean Leconte",      "noTelephone": "(666)666-6666"},
    {"noClient": 50, "nomClient": "Hafed Alaoui",      "noTelephone": "(555)555-5555"},
    {"noClient": 60, "nomClient": "Marie Leconte",     "noTelephone": "(666)666-6666"},
    {"noClient": 70, "nomClient": "Simon Lecoq",       "noTelephone": "(444)444-4419"},
    {"noClient": 80, "nomClient": "Dollard Tremblay",  "noTelephone": "(333)333-3333"},
]

# ── ARTICLES ─────────────────────────────────────────
articles = [
    {"noArticle": 10, "description": "Cèdre en boule",   "prixUnitaire": 10.99, "quantiteEnStock": 10},
    {"noArticle": 20, "description": "Sapin",             "prixUnitaire": 12.99, "quantiteEnStock": 10},
    {"noArticle": 40, "description": "Épinette bleue",    "prixUnitaire": 25.99, "quantiteEnStock": 10},
    {"noArticle": 50, "description": "Chêne",             "prixUnitaire": 22.99, "quantiteEnStock": 10},
    {"noArticle": 60, "description": "Érable argenté",    "prixUnitaire": 15.99, "quantiteEnStock": 10},
    {"noArticle": 70, "description": "Herbe à puce",      "prixUnitaire": 10.99, "quantiteEnStock": 10},
    {"noArticle": 80, "description": "Poirier",           "prixUnitaire": 26.99, "quantiteEnStock": 10},
    {"noArticle": 81, "description": "Catalpa",           "prixUnitaire": 25.99, "quantiteEnStock": 10},
    {"noArticle": 90, "description": "Pommier",           "prixUnitaire": 25.99, "quantiteEnStock": 10},
    {"noArticle": 95, "description": "Génévrier",         "prixUnitaire": 15.99, "quantiteEnStock": 10},
]

# ── COMMANDES (dénormalisées avec lignes et livraisons) ──
commandes = [
    {
        "noCommande": 1, "dateCommande": "2000-06-01", "noClient": 10,
        "lignes": [
            {"noArticle": 10, "quantite": 10},
            {"noArticle": 70, "quantite": 5},
            {"noArticle": 90, "quantite": 1}
        ],
        "livraisons": [
            {"noLivraison": 100, "dateLivraison": "2000-06-03",
             "details": [{"noArticle": 10, "quantiteLivree": 7},
                         {"noArticle": 70, "quantiteLivree": 5}]},
            {"noLivraison": 101, "dateLivraison": "2000-06-04",
             "details": [{"noArticle": 10, "quantiteLivree": 3}]},
            {"noLivraison": 103, "dateLivraison": "2000-06-05",
             "details": [{"noArticle": 90, "quantiteLivree": 1}]}
        ]
    },
    {
        "noCommande": 2, "dateCommande": "2000-06-02", "noClient": 20,
        "lignes": [
            {"noArticle": 40, "quantite": 2},
            {"noArticle": 95, "quantite": 3}
        ],
        "livraisons": [
            {"noLivraison": 102, "dateLivraison": "2000-06-04",
             "details": [{"noArticle": 40, "quantiteLivree": 2},
                         {"noArticle": 95, "quantiteLivree": 1}]}
        ]
    },
    {
        "noCommande": 3, "dateCommande": "2000-06-02", "noClient": 10,
        "lignes": [
            {"noArticle": 20, "quantite": 1}
        ],
        "livraisons": [
            {"noLivraison": 100, "dateLivraison": "2000-06-03",
             "details": [{"noArticle": 20, "quantiteLivree": 1}]}
        ]
    },
    {
        "noCommande": 4, "dateCommande": "2000-07-05", "noClient": 10,
        "lignes": [
            {"noArticle": 40, "quantite": 1},
            {"noArticle": 50, "quantite": 1}
        ],
        "livraisons": [
            {"noLivraison": 104, "dateLivraison": "2000-07-07",
             "details": [{"noArticle": 40, "quantiteLivree": 1}]}
        ]
    },
    {
        "noCommande": 5, "dateCommande": "2000-07-09", "noClient": 30,
        "lignes": [
            {"noArticle": 70, "quantite": 3},
            {"noArticle": 10, "quantite": 5},
            {"noArticle": 20, "quantite": 5}
        ],
        "livraisons": [
            {"noLivraison": 105, "dateLivraison": "2000-07-08",
             "details": [{"noArticle": 70, "quantiteLivree": 2}]}
        ]
    },
    {
        "noCommande": 6, "dateCommande": "2000-07-09", "noClient": 20,
        "lignes": [
            {"noArticle": 10, "quantite": 5},
            {"noArticle": 40, "quantite": 1}
        ],
        "livraisons": []
    },
    {
        "noCommande": 7, "dateCommande": "2000-07-15", "noClient": 40,
        "lignes": [
            {"noArticle": 50, "quantite": 1}
        ],
        "livraisons": []
    },
    {
        "noCommande": 8, "dateCommande": "2000-07-15", "noClient": 40,
        "lignes": [
            {"noArticle": 20, "quantite": 3}
        ],
        "livraisons": []
    },
]

# ── ENVOI VERS ES ─────────────────────────────────────
def ingest(index, data, id_field):
    actions = [
        {"_index": index, "_id": doc[id_field], "_source": doc}
        for doc in data
    ]
    success, errors = bulk(es, actions)
    print(f"{index:12} → {success} documents ingérés  {'✓' if not errors else '✗ ' + str(errors)}")

print("=== Ingestion VentesPleinDeFoin ===")
ingest("clients",   clients,   "noClient")
ingest("articles",  articles,  "noArticle")
ingest("commandes", commandes, "noCommande")
print("=== Terminé ===")
