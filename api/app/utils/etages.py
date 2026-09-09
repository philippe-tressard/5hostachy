"""Le libellé d'un étage — « RDC », « 1er », « 2ème », « SS 1 ».

Un module à lui seul, et non une ligne dans `dates_fr` : un étage n'est pas une
date, et ranger une notion là où elle tombe sous la main est ce qui produit les
fichiers de mille lignes que le plafond de modularité refuse ensuite.
"""
from __future__ import annotations

#: Les bornes d'un étage saisi. Au-delà, ce n'est pas une donnée, c'est une faute
#: de frappe : un `4` devenu `44`, un signe en trop.
#:
#: 🔴 Elles étaient écrites **en clair dans `auth.py`** (#835), et le commentaire
#: qui les accompagnait disait déjà pourquoi elles devaient être vérifiées côté
#: serveur — *« un champ borné côté client se poste directement »*. Le jour où un
#: second écran a permis de saisir un étage (celui d'un LOT, 09/09/2026), la
#: règle allait être recopiée : elle vit ici, avec le libellé qu'elle borne.
ETAGE_MIN = -2
ETAGE_MAX = 50

#: Le message rendu à qui sort des bornes — une seule formulation, pour que les
#: deux écrans disent la même chose.
ETAGE_HORS_BORNES = f"Étage attendu entre {ETAGE_MIN} et {ETAGE_MAX}."


def etage_hors_bornes(etage: int) -> bool:
    """L'étage saisi est-il hors de ce qu'un immeuble peut porter ?"""
    return not ETAGE_MIN <= etage <= ETAGE_MAX


def etage_label(etage) -> str:
    """« RDC », « 1er », « 2ème », « SS 1 » — le libellé d'un étage, côté serveur.

    ## Pourquoi ici, et pourquoi une copie (08/09/2026)

    Le pendant de `front/src/lib/utils.ts::etageLabel`. Les contextes de build
    sont `./api` et `./front` : le partage d'un fichier est impossible, seule la
    copie l'est — comme `KANBAN_LABELS` et la correspondance du kanban.
    `api/tests/test_etage_label.py` échoue si les deux dérivent.

    🔴 Ce qu'elle remplace, dans `fiche_arrivant.py` :

        etage_html = f"Étage {m['etage']}" if m.get("etage") else ""

    Deux défauts en une ligne. Le second est le plus grave :

    1. « Étage 0 » pour un rez-de-chaussée, « Étage -1 » pour un sous-sol —
       alors que tout le reste du site écrit « RDC » et « SS 1 » ;
    2. 🔴 **`if m.get("etage")` est un test de VÉRITÉ** : `0` est faux en
       Python. Un conseiller du rez-de-chaussée n'avait donc **aucun étage**
       sur la fiche d'accueil remise aux nouveaux arrivants — pas un étage
       faux, un étage absent. Le seul cas où l'information manque est
       précisément celui où elle est la plus simple à donner.

    ⚠️ Rend une chaîne **vide** pour `None`, jamais « — » : c'est l'appelant qui
    décide de ce qu'il affiche à la place.
    """
    if etage is None or etage == "":
        return ""
    #  🔴 La donnée n'est PAS toujours un entier, et je l'avais supposé : la
    #  fiche arrivant construit ses dictionnaires depuis la base ET depuis un
    #  import, où l'étage peut arriver en chaîne. Neuf tests l'ont dit tout de
    #  suite — `'<' not supported between instances of 'str' and 'int'`.
    #
    #  ⚠️ Une valeur illisible est rendue TELLE QUELLE, jamais effacée : c'est la
    #  même règle que `lotTypeLabel` pour un type inconnu. Perdre l'information
    #  serait pire que l'afficher sans la mettre en forme — et c'est précisément
    #  le défaut que cette fonction corrige.
    try:
        niveau = int(etage)
    except (TypeError, ValueError):
        return str(etage)
    if niveau == 0:
        return "RDC"
    if niveau < 0:
        return f"SS {abs(niveau)}"
    return "1er" if niveau == 1 else f"{niveau}ème"
