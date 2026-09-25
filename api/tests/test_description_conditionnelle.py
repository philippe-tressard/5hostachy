"""La description est obligatoire — sauf si l'objet porte une date d'événement.

## Le constat (#1092, chantier v2.0.0)

L'astérisque de « Description * » **ne vivait qu'à l'écran** : `PublicationCreate.contenu`
et `TicketCreate.description` sont typés `str`, ce qui accepte `""`. Mesuré le
20/09/2026 — aucun des deux routeurs ne vérifiait que la chaîne n'était pas vide.
Un appel direct créait donc une actualité sans contenu, et le champ requis mentait.

En face, le **calendrier** n'exigeait pas de description du tout, ce qui a fait
déclarer une dérogation (#1089). Les deux défauts sont le même : personne n'avait
écrit *où* cette règle vit.

## La règle, et pourquoi elle est conditionnelle

> **La description est obligatoire, sauf si une date d'événement est renseignée.**

« Coupure d'eau — jeudi 9h-12h » se suffit : le titre et la date disent tout. Ce
n'est donc pas une **dérogation d'objet** — « le calendrier, lui, n'en a pas
besoin » — mais une **condition de contenu**, vraie pour les deux objets, et
vérifiable. C'est ce qui permet de refermer #1089 sans exception déclarée.

## Ce que ce fichier vérifie

1. la règle vit dans `app/utils/quand.py`, **et nulle part ailleurs** ;
2. les deux routeurs de création l'appellent — une règle qui existe sans
   s'exécuter ne sert à rien (`standards/04` §7) ;
3. **le cas zéro** : la règle refuse vraiment ce qu'elle doit refuser. Sans ce
   test, une fonction qui ne lève jamais rendrait les deux premiers verts.
"""

import ast
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(RACINE.parent))

#: Le seul endroit où « faut-il une description ? » se décide.
SOURCE = "utils/quand.py"

#: Les fichiers qui doivent appeler la règle — les deux créations.
APPELANTS = ("routers/tickets/crud.py",)

#: 🔴 Les endroits où « le contenu est vide » répond à une **autre** question,
#: avec la raison. Le test échoue si l'une cesse de servir : une exception qui ne
#: couvre plus rien est un oubli qui ressemble à une décision.
#:
#: Trouvée à l'écriture du contrôle, le 20/09/2026 — et c'est le motif à ne pas
#: manquer : « pas de description » et « pas de commentaire » se ressemblent dans
#: le code et ne se ressemblent pas du tout dans le produit. **Aucune date ne
#: dispense d'écrire un commentaire** ; la règle conditionnelle n'a donc rien à
#: y faire, et élargir son motif pour l'y inclure l'aurait rendue fausse.
AUTRES_NOTIONS = {
    "routers/sondages/participation.py": (
        "le commentaire d'un sondage, pas la description d'un objet : il ne porte "
        "aucune date qui puisse le dispenser d'être écrit"
    ),
}


def test_la_regle_a_un_lieu():
    module = RACINE / SOURCE
    assert module.exists(), (
        f"app/{SOURCE} a disparu : la règle « description obligatoire sauf si date » "
        f"n'a plus de lieu, et elle se réécrira chez chaque routeur — c'est ainsi "
        f"qu'elle a fini par ne vivre QUE dans l'écran (#1092)."
    )
    arbre = ast.parse(module.read_text(encoding="utf-8"))
    noms = {n.name for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef)}
    assert "exiger_description" in noms, (
        f"`exiger_description` n'est plus dans app/{SOURCE} : {sorted(noms)}"
    )


@pytest.mark.parametrize("chemin", APPELANTS)
def test_chaque_creation_appelle_la_regle(chemin):
    """Une règle qui existe et ne s'exécute pas ne sert à rien.

    C'est la famille de #409, #410 et #411 — des contrôles écrits et jamais
    branchés. Ici le branchement, c'est l'appel.
    """
    source = (RACINE / chemin).read_text(encoding="utf-8")
    assert "exiger_description(" in source, (
        f"app/{chemin} ne passe pas par `exiger_description` : la description y "
        f"redevient facultative côté serveur, quoi qu'affiche l'écran."
    )


def test_aucune_autre_ecriture_de_la_regle():
    """Une deuxième écriture divergerait sur le cas limite — c'est le motif du dépôt.

    On cherche une condition qui teste à la fois le vide d'un contenu et une
    levée HTTP, hors du module central.
    """
    fautes = []
    exceptions_servies = set()
    for fichier in sorted(RACINE.rglob("*.py")):
        rel = fichier.relative_to(RACINE).as_posix()
        if rel == SOURCE:
            continue
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.If):
                continue
            condition = ast.unparse(noeud.test)
            vise_le_vide = any(m in condition for m in ("not body.contenu", "not body.description"))
            if not vise_le_vide:
                continue
            leve = any(
                isinstance(n, ast.Raise) and "HTTPException" in (ast.unparse(n) or "")
                for n in ast.walk(noeud)
            )
            if not leve:
                continue
            if rel in AUTRES_NOTIONS:
                exceptions_servies.add(rel)
                continue
            fautes.append(f"app/{rel}:{noeud.lineno}")
    assert not fautes, (
        "La règle est réécrite hors de son module :\n"
        + "\n".join(f"  {f}" for f in fautes)
        + f"\n\nElle vit dans `app/{SOURCE}` : deux écritures divergent au premier "
        f"cas limite — ici, « et si l'objet porte une date ? ».\n"
        f"Si c'est une AUTRE notion, l'inscrire dans `AUTRES_NOTIONS` avec sa raison."
    )
    mortes = sorted(set(AUTRES_NOTIONS) - exceptions_servies)
    assert not mortes, (
        f"Exception(s) déclarée(s) qui ne couvrent plus rien : {mortes}\n"
        f"Les retirer — une exception qui ne sert plus fait croire que la règle "
        f"souffre d'un cas particulier qui n'existe pas."
    )


#  ── Le cas zéro : la règle refuse-t-elle vraiment ? ─────────────────────────
#
#  Les trois tests ci-dessus sont satisfaits par une fonction vide. Ceux-ci
#  l'appellent (`standards/04` §2 — vérifier le comportement, pas l'artefact).


def _regle():
    from app.utils.quand import exiger_description

    return exiger_description


def test_une_description_vide_sans_date_est_refusee():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as e:
        _regle()("   ", debut=None)
    assert e.value.status_code == 422


def test_une_description_vide_AVEC_date_est_REFUSEE():
    """🔴 Le renversement du 22/09/2026, arbitré à l'écran.

    Une date dispensait de description pendant deux jours — « Coupure d'eau —
    jeudi 9h-12h » se suffisait. La règle n'a plus de condition :

    > « Un évènement avec une date doit aussi remplir une description
    >   (obligatoire sans exception). »

    Ce test est ce qui empêche la dispense de revenir : elle était défendable,
    et c'est précisément pour cela qu'on la réécrirait sans y penser.
    """
    from datetime import datetime

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        _regle()("", debut=datetime(2026, 9, 24, 9, 0))


def test_une_description_remplie_passe_toujours():
    _regle()("Le local à vélos a été repeint.", debut=None)
