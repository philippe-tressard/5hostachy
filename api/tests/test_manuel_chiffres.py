"""Un chiffre cité par le manuel doit être celui que le code applique.

## 🔴 Pourquoi (#651, et deux récidives)

Le manuel **recopie en prose** des valeurs dont le code est la source. Rien ne les
rapproche, et elles se séparent :

| Écart | Ce qu'il valait |
|---|---|
| « 5 photos » quand `MAX_FICHIERS` valait 10 | le manuel promettait **deux fois moins** que l'application n'accepte, pendant deux semaines |
| « max 15 Mo chacun » pour les **photos** | faux : `MAX_SIZE_MB = 5`. Un résident joignant une photo de 8 Mo se faisait refuser ce que le manuel lui promettait |

⚠️ **Le second a été déclaré corrigé le 30/08/2026, et il ne l'était qu'à moitié** :
deux occurrences subsistaient dans la section des tickets. C'est ce qui a décidé
l'écriture de ce contrôle — une correction à la main ne prouve rien sur les autres
occurrences, et personne ne relit un manuel de 3 000 lignes.

## Ce que ce fichier vérifie, et ce qu'il ne peut pas vérifier

Il prend une **table déclarée** de chiffres attendus, et vérifie que le manuel les
cite tous, et n'en cite aucun qui les contredise.

⚠️ Il ne « lit » pas la prose : c'est impossible sans se tromper, et un contrôle qui
crie sur du légitime finit désarmé (leçon de C16, et du motif écarté dans
`check-formulaire-creation`). Il travaille sur des **motifs nommés**, chacun avec
sa source — la table est tenue à la main, et c'est assumé : « ce chiffre-là parle
de cette limite-là » est une notion de sens, pas une forme repérable.

En revanche il **échoue si une source disparaît**, donc la table ne peut pas
pointer dans le vide.

📖 Même famille que `test_plafonds_pieces_jointes.py` (front ⇆ serveur) : ici c'est
documentation ⇆ serveur. Les deux disent la même chose — *une valeur recopiée
diverge, et deux copies d'accord entre elles ne prouvent rien*.

⚠️ La **synchronisation** entre `docs/` et `front/static/` n'est PAS vérifiée ici :
`test_documentation.py::test_manuels_synchronises_docs_et_static` le fait déjà, à
l'octet, pour les quatre manuels. Elle a été écrite ici par réflexe, puis retirée —
un second contrôle du même fait n'ajoute rien et diverge un jour.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[2]
_MANUEL = _RACINE / "docs" / "manuel-utilisateur.html"


def _valeur(module: str, nom: str) -> int:
    import importlib

    return getattr(importlib.import_module(module), nom)


#: (libellé du cas, motif cherché dans le manuel, module, constante).
#:
#: Le motif porte un groupe `(\d+)` : c'est le chiffre que le manuel annonce. Le
#: contrôle exige qu'il soit égal à la constante, **partout où le motif apparaît**
#: — c'est ce qui aurait empêché la correction à moitié du 30/08/2026.
CHIFFRES = [
    pytest.param(
        r"photos JPG/PNG/WebP jusqu'à (\d+) Mo",
        "app.routers.uploads", "MAX_SIZE_MB",
        id="taille-photo",
    ),
    pytest.param(
        r"PDF, Word, Excel, texte jusqu'à (\d+) Mo",
        "app.routers.uploads", "MAX_DOC_SIZE_MB",
        id="taille-document",
    ),
    pytest.param(
        r"ajouter <strong>1 ou (\d+) photos</strong>",
        "app.utils.annonce_hall", "MAX_PHOTOS",
        id="photos-affiche-de-hall",
    ),
]


@pytest.mark.parametrize("motif, module, constante", CHIFFRES)
def test_le_manuel_cite_le_chiffre_que_le_code_applique(motif: str, module: str, constante: str):
    """Toutes les occurrences du motif, pas seulement la première.

    🔴 C'est le cœur du contrôle. Le 30/08/2026, « 15 Mo » a été corrigé à un
    endroit et laissé à deux autres. Vérifier la première occurrence aurait rendu
    ce test vert sur un manuel qui promettait encore le triple de ce que le
    serveur accepte.
    """
    assert _MANUEL.exists(), f"{_MANUEL} est introuvable — ce test ne mesure plus rien."
    attendu = _valeur(module, constante)
    trouves = re.findall(motif, _MANUEL.read_text(encoding="utf-8"))

    assert trouves, (
        f"Le manuel ne cite plus « {motif} » — la phrase a été réécrite, et ce "
        "contrôle ne surveille plus rien (INCONNU, pas OK). Corriger le motif, ou "
        "retirer cette ligne de la table si le manuel ne dit plus ce chiffre."
    )
    faux = [v for v in trouves if int(v) != attendu]
    assert not faux, (
        f"Le manuel annonce {', '.join(faux)} là où {module}.{constante} vaut "
        f"{attendu} — sur {len(trouves)} occurrence(s) du motif.\n"
        "  Un lecteur se fie au manuel : s'il annonce plus, l'utilisateur se fait "
        "refuser ce qu'on lui a promis ; s'il annonce moins, une possibilité réelle "
        "reste ignorée.\n"
        "  ⚠️ Corriger TOUTES les occurrences — c'est une correction à moitié qui a "
        "rendu ce contrôle nécessaire."
    )
