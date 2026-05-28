"""Mini parseur/émetteur YAML — sous-ensemble suffisant pour ce projet.

Ne dépend que de la stdlib. Couvre :
  - lecture de config.yml : mapping plat / 1 niveau d'indentation,
    valeurs scalaires (string, int, vide), chaînes entre guillemets ;
  - écriture des fichiers docker-compose : mappings imbriqués, listes
    de scalaires, valeurs str/int/bool/None.
"""

import re


# ────────────────────────── PARSING ──────────────────────────

def _convertir(valeur):
    v = valeur.strip()
    if v == "" or v.lower() in ("null", "~"):
        return ""
    if (v.startswith('"') and v.endswith('"')) or (
        v.startswith("'") and v.endswith("'")
    ):
        return v[1:-1]
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def safe_load(texte):
    """Parseur YAML minimaliste : mapping plat ou avec 1 niveau de nesting.

    Adapté au format de config.yml du projet uniquement.
    """
    racine = {}
    contexte = None  # nom de la clé parente courante

    for brut in texte.splitlines():
        # Supprimer commentaires
        ligne = re.sub(r"\s+#.*$", "", brut)
        if ligne.lstrip().startswith("#"):
            continue
        if not ligne.strip():
            continue

        indent = len(ligne) - len(ligne.lstrip(" "))
        contenu = ligne.strip()

        if ":" not in contenu:
            continue

        cle, _, val = contenu.partition(":")
        cle = cle.strip()
        val = val.strip()

        if indent == 0:
            if val == "":
                racine[cle] = {}
                contexte = cle
            else:
                racine[cle] = _convertir(val)
                contexte = None
        else:
            if contexte is None or not isinstance(racine.get(contexte), dict):
                continue
            racine[contexte][cle] = _convertir(val)

    return racine


# ────────────────────────── EMITTING ──────────────────────────

_BESOIN_QUOTES = re.compile(r'^[\s\-\?:,\[\]{}#&*!|>\'"%@`]')


def _scalaire(v):
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "null"
    if isinstance(v, int) and not isinstance(v, bool):
        return str(v)
    s = str(v)
    # Quotes : versions docker-compose, ou caractères spéciaux
    if s == "" or _BESOIN_QUOTES.match(s) or ":" in s and " " in s:
        return f"'{s}'"
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return f"'{s}'"
    return s


def _dump(obj, indent):
    pad = "  " * indent
    lignes = []
    if isinstance(obj, dict):
        if not obj:
            lignes.append(f"{pad}{{}}")
            return lignes
        for cle, val in obj.items():
            if isinstance(val, dict):
                if not val:
                    lignes.append(f"{pad}{cle}: {{}}")
                else:
                    lignes.append(f"{pad}{cle}:")
                    lignes.extend(_dump(val, indent + 1))
            elif isinstance(val, list):
                if not val:
                    lignes.append(f"{pad}{cle}: []")
                else:
                    lignes.append(f"{pad}{cle}:")
                    lignes.extend(_dump(val, indent + 1))
            else:
                lignes.append(f"{pad}{cle}: {_scalaire(val)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                sub = _dump(item, indent + 1)
                # premier item préfixé par "-"
                if sub:
                    premier = sub[0].lstrip()
                    lignes.append(f"{pad}- {premier}")
                    lignes.extend(sub[1:])
            else:
                lignes.append(f"{pad}- {_scalaire(item)}")
    else:
        lignes.append(f"{pad}{_scalaire(obj)}")
    return lignes


def safe_dump(obj):
    return "\n".join(_dump(obj, 0)) + "\n"
