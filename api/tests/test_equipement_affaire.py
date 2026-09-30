"""L'équipement d'une affaire — posé par le conseil, jamais demandé au résident (#1097).

Le décret n° 2001-477 attend d'un carnet d'entretien qu'il dise quels travaux,
**sur quoi**, par qui. Un résident qui voit une flaque ne sait pas si c'est la
plomberie, la toiture ou la VMC : le lui demander, c'est obtenir une réponse
fausse qu'on retrouvera au carnet dans dix ans. Le conseil le désigne ensuite.

Et c'est lui qui RANGE une affaire résolue au carnet. Sans lui, elle y figure
quand même, sous « Sans équipement rattaché » : la v2.31.0 l'excluait, et le
carnet a perdu toutes les affaires résolues d'avant — arbitré à l'écran le
24/09/2026 : « on a perdu les affaires, c'est dommage ».

Ce que l'équipement partage avec l'intervenant et le contrat — ignoré venant
d'un résident, effacé hors du bâti, effacé par le conseil — se vérifie champ par
champ dans `test_intervenant_affaire.py` (`CHAMPS_DU_CONSEIL`).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException

from app.models.core import RoleUtilisateur, Ticket
from app.models.prestataires import TypeEquipement
from app.models.tickets import StatutTicket
from app.utils.carnet_entretien import construire_carnet
from app.utils.intervenant import EQUIPEMENTS_AFFAIRE
from tests.aides_affaire import _compte, _corriger, _creer, session  # noqa: F401


def _cs(session):
    return _compte(session, role=RoleUtilisateur.conseil_syndical)


def test_le_conseil_designe_l_equipement(session):
    lu = _creer(session, _cs(session), categorie="panne", equipement="toiture")
    assert lu.equipement == "toiture"


def test_le_conseil_le_designe_apres_coup_meme_une_fois_l_affaire_close(session):
    """Le cas de TK-417640 : l'auteur ne peut plus corriger une affaire close, le conseil si."""
    resident, cs = _compte(session), _cs(session)
    t = _creer(session, resident, categorie="panne")
    session.get(Ticket, t.id).statut = StatutTicket.résolu
    session.commit()
    assert _corriger(session, cs, t.id, equipement="plomberie").equipement == "plomberie"


@pytest.mark.parametrize(
    "valeur", ["licorne", TypeEquipement.assurance.value, TypeEquipement.syndic.value]
)
def test_ce_qui_n_est_pas_un_equipement_est_refuse(session, valeur):
    """`assurance` et `syndic` classent des CONTRATS : on n'intervient pas dessus."""
    with pytest.raises(HTTPException) as refus:
        _creer(session, _cs(session), categorie="panne", equipement=valeur)
    assert refus.value.status_code == 422


def test_la_liste_blanche_n_est_pas_vide():
    """🔴 Cas zéro : vide, elle refuserait tout, et les tests de refus passeraient."""
    assert "ascenseur" in EQUIPEMENTS_AFFAIRE and "autre" in EQUIPEMENTS_AFFAIRE


# ── Le carnet d'entretien ───────────────────────────────────────────────────


def _resolue(session, cs, titre, **champs):
    t = _creer(session, cs, categorie="panne", **champs)
    ligne = session.get(Ticket, t.id)
    ligne.titre, ligne.statut, ligne.ferme_le = titre, StatutTicket.résolu, datetime(2026, 9, 17)
    session.commit()
    return t


def test_l_equipement_range_l_affaire_et_son_absence_ne_l_exclut_pas(session):
    cs = _cs(session)
    _resolue(session, cs, "Infiltration hall B — sans équipement")
    _resolue(session, cs, "Infiltration hall B — toiture", equipement="toiture")
    carnet = {e["libelle"]: e for e in construire_carnet(session, lecteur=cs)}
    assert carnet["Infiltration hall B — toiture"]["equipement"] == "toiture"
    assert carnet["Infiltration hall B — sans équipement"]["equipement"] is None, (
        "une affaire résolue sans équipement a disparu du carnet"
    )
