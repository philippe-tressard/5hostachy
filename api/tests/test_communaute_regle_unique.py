"""Garde-fou : la règle d'accès à la Communauté ne s'écrit qu'à un seul endroit.

POURQUOI (29/08/2026) : elle était écrite **quatre fois** — `routers/idees.py`,
`routers/annonces.py`, `routers/signalements.py`, `routers/sondages/commun.py` —
sous le même nom `_deny_communaute_for_statut`, et elle avait **déjà divergé**.
Un utilisateur suspendu pour un mois lisait, selon l'écran d'où il venait :

  • « Votre accès à la Communauté est suspendu pour une période probatoire d'un
    mois. À la 2ᵉ infraction, vous serez banni définitivement. » (3 copies)
  • « Votre accès à la Communauté est suspendu. » (`signalements.py`)

La seconde ne dit ni la durée, ni qu'il existe une seconde chance. Le même refus,
deux vérités. Rien ne rougissait : chaque copie était valide isolément, et les
tests passaient par la copie la mieux relue.

CE QUE CE TEST VÉRIFIE — le fait, pas le symptôme :
  1. aucun module hors `app/utils/communaute.py` ne relit les champs de ban
     (`communaute_interdit`, `communaute_ban_jusqu_au`) pour en déduire un refus ;
  2. le vocabulaire du refus (les messages) n'est écrit qu'une fois ;
  3. `exiger_acces` et `motif_de_refus` restent d'accord — la forme levante ne
     doit jamais être une seconde formulation de la règle.

Le point 1 attrape la copie qui change de NOM : c'est ainsi qu'une 4ᵉ table en dur
avait survécu à une consolidation précédente (`perimetre_libelle`, 27/08/2026).
"""
import ast
import pathlib
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"
_SOURCE_UNIQUE = _APP / "utils" / "communaute.py"

# Les champs qui portent la sanction. Les lire pour décider d'un refus, c'est
# réécrire la règle — quel que soit le nom qu'on donne à la fonction.
_CHAMPS_DE_BAN = {"communaute_interdit", "communaute_ban_jusqu_au"}

# L'administration ÉCRIT ces champs (poser/lever un ban) : c'est son métier, pas
# une lecture de la règle. Déclaré ici avec son motif — une exception non écrite
# n'est pas une exception, c'est un oubli qui ressemble à une décision.
_EXCEPTIONS = {
    "models/core.py": "définition des colonnes",
    "schemas.py": "exposition des champs à l'administration",
    "routers/admin/utilisateurs.py": "pose et lève les bans — écrit, ne décide pas",
}


def _modules_python() -> list[pathlib.Path]:
    return sorted(p for p in _APP.rglob("*.py") if "__pycache__" not in p.parts)


def _lit_un_champ_de_ban(source: str) -> set[str]:
    """Les champs de ban LUS par ce source (`user.communaute_interdit` en lecture)."""
    arbre = ast.parse(source)
    lus: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Attribute) and noeud.attr in _CHAMPS_DE_BAN:
            if isinstance(noeud.ctx, ast.Load):
                lus.add(noeud.attr)
    return lus


def test_un_seul_module_decide_du_refus():
    """Aucun autre module ne relit les champs de ban pour en déduire un refus."""
    coupables = {}
    for chemin in _modules_python():
        relatif = chemin.relative_to(_APP).as_posix()
        if chemin == _SOURCE_UNIQUE or relatif in _EXCEPTIONS:
            continue
        lus = _lit_un_champ_de_ban(chemin.read_text(encoding="utf-8"))
        if lus:
            coupables[relatif] = sorted(lus)

    assert not coupables, (
        "La règle d'accès à la Communauté est réécrite hors de "
        f"`app/utils/communaute.py` : {coupables}.\n"
        "Appeler `exiger_acces(user)` (endpoint) ou `acces_ouvert(user)` (compteur). "
        "Une copie diverge toujours, et c'est la moins relue qui devient fausse."
    )


def test_les_exceptions_declarees_servent_encore():
    """Une exception qui ne sert plus est un mensonge dans la liste."""
    mortes = []
    for relatif, motif in _EXCEPTIONS.items():
        chemin = _APP / relatif
        if not chemin.exists():
            mortes.append(f"{relatif} (fichier absent — {motif})")
            continue
        texte = chemin.read_text(encoding="utf-8")
        if not any(champ in texte for champ in _CHAMPS_DE_BAN):
            mortes.append(f"{relatif} (ne touche plus aux champs — {motif})")
    assert not mortes, f"Exceptions à retirer de _EXCEPTIONS : {mortes}"


def test_le_vocabulaire_du_refus_n_est_ecrit_qu_une_fois():
    """Les messages de refus n'existent que dans le module source."""
    from app.utils import communaute

    fragments = ["n'est pas accessible à votre profil", "définitivement suspendu",
                 "période probatoire"]
    ailleurs = {}
    for chemin in _modules_python():
        if chemin == _SOURCE_UNIQUE:
            continue
        texte = chemin.read_text(encoding="utf-8")
        trouves = [f for f in fragments if f in texte]
        if trouves:
            ailleurs[chemin.relative_to(_APP).as_posix()] = trouves
    assert not ailleurs, (
        f"Messages de refus Communauté recopiés hors du module source : {ailleurs}"
    )


class _Faux:
    """Un utilisateur minimal — le test porte sur la règle, pas sur l'ORM."""

    def __init__(self, statut=None, interdit=False, ban=None):
        self.statut = statut
        self.communaute_interdit = interdit
        self.communaute_ban_jusqu_au = ban


@pytest.mark.parametrize(
    "utilisateur, attendu_ouvert",
    [
        (_Faux(), True),
        (_Faux(interdit=True), False),
        (_Faux(ban=datetime.utcnow() + timedelta(days=10)), False),
        (_Faux(ban=datetime.utcnow() - timedelta(days=10)), True),  # ban expiré
    ],
)
def test_les_deux_formes_disent_la_meme_chose(utilisateur, attendu_ouvert):
    """`exiger_acces` ne doit jamais être une seconde formulation de la règle."""
    from app.utils.communaute import acces_ouvert, exiger_acces, motif_de_refus

    assert acces_ouvert(utilisateur) is attendu_ouvert
    if attendu_ouvert:
        exiger_acces(utilisateur)  # ne lève pas
    else:
        with pytest.raises(HTTPException) as excinfo:
            exiger_acces(utilisateur)
        assert excinfo.value.status_code == 403
        # Le message levé EST le motif : pas de reformulation en chemin.
        assert excinfo.value.detail == motif_de_refus(utilisateur)


def test_le_ban_expire_rouvre_l_acces():
    """Le cas zéro de la suspension probatoire : elle a un terme, il doit compter."""
    from app.utils.communaute import acces_ouvert

    hier = datetime.utcnow() - timedelta(seconds=1)
    assert acces_ouvert(_Faux(ban=hier)) is True


# ---------------------------------------------------------------------------
#  Le front non plus ne réécrit pas la règle
# ---------------------------------------------------------------------------
#  `sondages/+page.svelte` en portait une TROISIÈME copie : il relisait
#  `communaute_interdit` et `communaute_ban_jusqu_au` pour reconstruire lui-même
#  les trois messages. La frontière front/API ne se franchit pas en double
#  (cf. la leçon des liens `EMPLACEMENTS`, 28/08/2026) : l'API expose désormais
#  sa CONCLUSION (`communaute_motif_refus`), et l'écran l'affiche.

_FRONT_SRC = pathlib.Path(__file__).resolve().parents[2] / "front" / "src"

_EXCEPTIONS_FRONT = {
    "lib/api/types.ts": "déclaration des champs — ne décide de rien",
    "routes/(app)/admin/+page.svelte": "écran d'administration : pose et lève les bans",
}


@pytest.mark.skipif(not _FRONT_SRC.exists(), reason="sources front absentes")
def test_le_front_affiche_le_motif_et_ne_le_recalcule_pas():
    coupables = {}
    for chemin in sorted(_FRONT_SRC.rglob("*")):
        if chemin.suffix not in {".svelte", ".ts"} or not chemin.is_file():
            continue
        relatif = chemin.relative_to(_FRONT_SRC).as_posix()
        if relatif in _EXCEPTIONS_FRONT:
            continue
        texte = chemin.read_text(encoding="utf-8")
        trouves = sorted(c for c in _CHAMPS_DE_BAN if c in texte)
        if trouves:
            coupables[relatif] = trouves
    assert not coupables, (
        f"Le front recalcule la règle d'accès à la Communauté : {coupables}. "
        "Lire `communaute_motif_refus` (renvoyé par l'API) au lieu de refaire le "
        "raisonnement : une règle écrite des deux côtés d'une frontière diverge, "
        "et l'utilisateur lit alors deux versions de la même décision."
    )


@pytest.mark.skipif(not _FRONT_SRC.exists(), reason="sources front absentes")
def test_les_exceptions_front_declarees_servent_encore():
    mortes = []
    for relatif, motif in _EXCEPTIONS_FRONT.items():
        chemin = _FRONT_SRC / relatif
        if not chemin.exists():
            mortes.append(f"{relatif} (fichier absent — {motif})")
        elif not any(c in chemin.read_text(encoding="utf-8") for c in _CHAMPS_DE_BAN):
            mortes.append(f"{relatif} (ne touche plus aux champs — {motif})")
    assert not mortes, f"Exceptions à retirer de _EXCEPTIONS_FRONT : {mortes}"
