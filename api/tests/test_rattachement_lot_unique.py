"""La règle « un seul lot actif ⇒ on rattache » ne s'écrit qu'à UN endroit.

## 🔴 Pourquoi (03/09/2026)

Elle était écrite **quatre fois** — deux dans `routers/acces.py`, deux dans
`utils/auto_match_service.py` — et les copies avaient déjà commencé à diverger :
deux posaient `changed = True` après le rattachement, deux non. Personne ne
pouvait dire si c'était voulu.

Ce n'est pas une commodité de lecture. Cette règle décide **à quel lot une ligne
d'import se rattache**, donc qui verra ce lot, ses accès, ses badges. Une règle
qui gouverne un accès et qui est écrite quatre fois n'a plus d'auteur, seulement
des copies — c'est le constat qui avait fait naître `test_regles_acces_centralisees`
pour `auteur_id`, et le même schéma se rejouait ici.

## Ce que ce fichier vérifie

1. La règle **décide bien** ce qu'elle prétend : un lot → rattachement ; zéro,
   deux ou plus → rien.
2. Elle est **prudente** : avec plusieurs lots, elle ne devine pas. Une
   heuristique qui choisirait le « plus probable » attribuerait des droits
   d'accès sur une supposition.
3. 🔴 **Aucune cinquième copie** ne réapparaît. C'est le seul des trois qui
   protège dans la durée : les deux premiers passeraient au vert alors qu'un
   nouveau site réécrirait la règle à côté.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import Batiment, Copropriete, Lot, UserLot, Utilisateur
from app.utils.auto_match_service import rattacher_lot_unique

_APP = Path(__file__).resolve().parents[1] / "app"

#: 🔴 CE MOTIF A ÉTÉ RESSERRÉ, et c'est une leçon sur la portée d'un contrôle.
#:
#: La première rédaction cherchait `select(UserLot).where(UserLot.user_id == …)`.
#: Elle a signalé QUATRE fichiers — dont trois parfaitement légitimes : lister
#: les lots d'un utilisateur pour les afficher n'est pas décider à quel lot un
#: import se rattache. Même requête, autre décision.
#:
#: Un contrôle qui crie sur du licite finit désarmé : on ajoute une exception,
#: puis deux, et il ne dit plus rien. Le motif vise donc ce qui appartient à
#: CETTE règle et à elle seule — `user_proprietaire_id`, le champ d'un
#: `LotImport`. Aucun écran d'affichage ne le lit pour chercher des lots.
_COPIE = re.compile(
    r"select\(UserLot\)\.where\([^)]*?user_proprietaire_id",
    re.S,
)

#: Le seul fichier qui a le droit de la porter.
_SOURCE = "utils/auto_match_service.py"


@pytest.fixture()
def scene():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        copro = Copropriete(nom=f"T-{uuid.uuid4().hex[:6]}", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        bat = Batiment(copropriete_id=copro.id, numero="1")
        session.add(bat)
        session.flush()
        lots = [Lot(batiment_id=bat.id, numero=f"L{i}") for i in (1, 2)]
        for lot in lots:
            session.add(lot)
        user = Utilisateur(
            email=f"p-{uuid.uuid4().hex[:8]}@exemple.test", mot_de_passe_hash="x",
            prenom="P", nom="T", roles_json="propriétaire", actif=True,
        )
        session.add(user)
        session.commit()
        for o in (*lots, user, bat, copro):
            session.refresh(o)
        yield session, user, lots
        for liaison in session.exec(
            select(UserLot).where(UserLot.user_id == user.id)
        ).all():
            session.delete(liaison)
        for o in (*lots, user, bat, copro):
            session.delete(o)
        session.commit()


def _import(user_id, lot_id=None):
    """Une ligne d'import, réduite à ce que la règle regarde."""
    return SimpleNamespace(user_proprietaire_id=user_id, lot_id=lot_id)


def test_un_seul_lot_actif_rattache(scene):
    session, user, lots = scene
    session.add(UserLot(user_id=user.id, lot_id=lots[0].id, actif=True))
    session.commit()

    imp = _import(user.id)
    assert rattacher_lot_unique(imp, session) is True
    assert imp.lot_id == lots[0].id


def test_DEUX_lots_ne_rattachent_RIEN(scene):
    """🔴 La prudence de la règle, et c'est le test qui compte.

    Avec deux lots, on ne devine pas : l'import reste non rattaché et quelqu'un
    tranche. Une heuristique qui choisirait le « plus probable » donnerait des
    droits d'accès sur une supposition — et sur un import, la supposition se
    transforme en badge.
    """
    session, user, lots = scene
    for lot in lots:
        session.add(UserLot(user_id=user.id, lot_id=lot.id, actif=True))
    session.commit()

    imp = _import(user.id)
    assert rattacher_lot_unique(imp, session) is False
    assert imp.lot_id is None


def test_un_lot_INACTIF_ne_compte_pas(scene):
    """`actif` est dans la clause des quatre copies : il ne doit pas se perdre.

    Un rattachement révoqué ne doit pas ressusciter par un import.
    """
    session, user, lots = scene
    session.add(UserLot(user_id=user.id, lot_id=lots[0].id, actif=True))
    session.add(UserLot(user_id=user.id, lot_id=lots[1].id, actif=False))
    session.commit()

    imp = _import(user.id)
    assert rattacher_lot_unique(imp, session) is True
    assert imp.lot_id == lots[0].id, "le lot inactif a été retenu"


def test_un_import_deja_rattache_ou_sans_proprietaire_est_laisse_tel_quel(scene):
    session, user, lots = scene
    session.add(UserLot(user_id=user.id, lot_id=lots[0].id, actif=True))
    session.commit()

    deja = _import(user.id, lot_id=lots[1].id)
    assert rattacher_lot_unique(deja, session) is False
    assert deja.lot_id == lots[1].id, "un rattachement existant a été écrasé"

    assert rattacher_lot_unique(_import(None), session) is False


def test_aucune_CINQUIEME_copie_de_la_regle():
    """🔴 Le seul contrôle qui protège dans la durée.

    Les tests ci-dessus resteraient verts si quelqu'un réécrivait la requête à
    côté : ils éprouvent la fonction, pas son unicité.
    """
    fautifs = []
    for f in _APP.rglob("*.py"):
        if "__pycache__" in f.parts:
            continue
        court = f.relative_to(_APP).as_posix()
        if court == _SOURCE:
            continue
        if _COPIE.search(f.read_text(encoding="utf-8", errors="replace")):
            fautifs.append(court)
    assert not fautifs, (
        "la règle des lots d'un utilisateur est réécrite hors de sa source :\n  "
        + "\n  ".join(fautifs)
        + f"\n\nElle vit dans `{_SOURCE}` (`rattacher_lot_unique`). Elle décide "
        "à quel lot un import se rattache — donc qui verra ses accès."
    )


def test_le_controle_regarde_bien_la_source():
    """Cas zéro. Un motif qui ne correspond plus à rien rendrait le test
    ci-dessus vert en ne mesurant plus rien.
    """
    source = (_APP / _SOURCE).read_text(encoding="utf-8")
    assert _COPIE.search(source), (
        "le motif ne trouve plus la règle dans sa propre source : il ne "
        "détecterait aucune copie non plus"
    )
