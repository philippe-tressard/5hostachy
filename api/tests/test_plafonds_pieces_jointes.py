"""Un plafond de pièces jointes annoncé à l'écran doit être celui que le serveur applique.

## 🔴 Le défaut (01/09/2026)

L'onglet « Annonces Hall » passait `maxPhotos={MAX_FICHIERS}` — **dix**. Le serveur
refuse au-delà de **deux** :

    if len(body.images) > MAX_PHOTOS:
        raise HTTPException(422, f"{MAX_PHOTOS} photos au maximum")

Un conseiller qui ajoutait cinq photos remplissait tout son formulaire — titre,
message, périmètre, format —, cliquait « Générer une affiche », et **perdait sa
saisie sur un 422**. Le manuel, lui, disait « 1 ou 2 » : il avait raison, c'est
l'écran qui mentait.

⚠️ Rien ne pouvait le voir. Les deux valeurs sont justes chacune de son côté :
`MAX_FICHIERS = 10` est le bon plafond commun, `MAX_PHOTOS = 2` la bonne
contrainte du feuillet. Le défaut est **entre les deux**, et il ne se manifeste
qu'au clic, chez quelqu'un d'autre.

## Ce que ce fichier vérifie, et ce qu'il ne vérifie pas

Il rapproche les plafonds que le front **annonce** de ceux que le serveur
**applique**, pour les objets dont le serveur borne le nombre de pièces jointes.

⚠️ Il ne dit rien de `MAX_FICHIERS` (10), et c'est délibéré : **aucun** routeur ne
le borne côté serveur. Ce n'est donc pas une limite, c'est un confort d'interface
— un client qui poste cinquante URLs passe. Le suivre ici laisserait croire le
contraire. Ce manque est un sujet à lui seul, suivi séparément.

📖 Même patron que `test_pieces_jointes.py` pour les types acceptés : la liste qui
fait autorité est celle du serveur, le front ne fait que filtrer le sélecteur.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[2]
_LIB_FRONT = _RACINE / "front" / "src" / "lib"


def _constante_ts(fichier: Path, nom: str) -> int:
    """La valeur d'un `export const <nom> = <entier>;` — ou lève.

    Lever plutôt que rendre `None` : une constante renommée doit faire échouer ce
    test, pas le rendre silencieusement vide. C'est le cas zéro de
    `standards/04` §2 — un contrôle qui ne trouve plus sa cible n'est pas vert.
    """
    assert fichier.exists(), f"{fichier} est introuvable — ce test ne mesure plus rien."
    m = re.search(rf"^export const {nom} = (\d+);", fichier.read_text(encoding="utf-8"), re.M)
    assert m, f"`{nom}` introuvable dans {fichier.name} — renommée ? Le test ne mesure plus rien."
    return int(m.group(1))


#: Les plafonds que le SERVEUR applique, et la constante front qui les annonce.
#:
#: ⚠️ Table tenue à la main, et c'est assumé : « ce plafond borne cet écran » est
#: une notion métier, pas une forme repérable. En revanche le test échoue si l'une
#: des deux constantes disparaît, donc elle ne peut pas pointer dans le vide.
PLAFONDS = [
    pytest.param(
        "app.routers.annonces", "MAX_PHOTOS", "annonces.ts", "MAX_PHOTOS_ANNONCE",
        id="petite-annonce",
    ),
    pytest.param(
        "app.utils.annonce_hall", "MAX_PHOTOS", "annonces.ts", "MAX_PHOTOS_AFFICHE",
        id="affiche-de-hall",
    ),
]


@pytest.mark.parametrize("module_api, const_api, fichier_ts, const_ts", PLAFONDS)
def test_le_front_annonce_le_plafond_que_le_serveur_applique(
    module_api: str, const_api: str, fichier_ts: str, const_ts: str
):
    """Les deux valeurs doivent être ÉGALES, dans les deux sens.

    - front **supérieur** au serveur : l'écran promet ce qui sera refusé, et la
      saisie est perdue. C'est le défaut du 01/09/2026 ;
    - front **inférieur** : l'écran interdit ce que le serveur accepterait. Moins
      grave, mais c'est une fonctionnalité qu'on croit livrée et qui ne l'est pas.
    """
    import importlib

    valeur_api = getattr(importlib.import_module(module_api), const_api)
    valeur_ts = _constante_ts(_LIB_FRONT / fichier_ts, const_ts)

    assert valeur_ts == valeur_api, (
        f"L'écran annonce {valeur_ts} pièce(s) jointe(s), le serveur en accepte "
        f"{valeur_api} ({module_api}.{const_api}).\n"
        "  Si le front est plus haut, l'utilisateur perd sa saisie sur un refus "
        "qu'il ne pouvait pas prévoir ; s'il est plus bas, une possibilité réelle "
        "reste inaccessible.\n"
        "  Aligner les deux — et si la valeur doit changer, la changer aux DEUX "
        "endroits dans le même lot."
    )


def test_le_plafond_commun_n_est_borne_par_aucun_routeur():
    """🔴 `MAX_FICHIERS` (10) est un CONFORT d'interface, pas une limite.

    Ce test ne corrige rien : il **constate**, pour que le constat cesse d'être
    invisible. Aucun routeur ne compte les pièces jointes qu'il reçoit — un client
    qui poste cinquante URLs dans `photos_urls` passe.

    ⚠️ S'il échoue un jour, c'est une **bonne** nouvelle : quelqu'un a posé la
    borne serveur. Il faudra alors ajouter la ligne correspondante à `PLAFONDS`
    ci-dessus et supprimer ce test — sans quoi le contrôle qui vient d'être gagné
    ne serait surveillé par personne.
    """
    routeurs = (_RACINE / "api" / "app" / "routers").rglob("*.py")
    motif = re.compile(r"len\((?:body\.)?(?:photos_urls|fichiers_urls)\)\s*[><]")
    bornes = [
        str(c.relative_to(_RACINE))
        for c in routeurs
        if motif.search(c.read_text(encoding="utf-8"))
    ]
    assert not bornes, (
        "Un routeur borne désormais le nombre de pièces jointes : "
        + ", ".join(bornes)
        + "\n  Ajouter la paire (constante serveur, constante front) à `PLAFONDS`, "
        "puis supprimer ce test — la borne est maintenant une vraie limite, et "
        "c'est elle qu'il faut rapprocher du front."
    )
