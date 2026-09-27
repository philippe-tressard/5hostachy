"""Le battement des contrôles de fiabilité prolonge une ligne, il n'en crée pas (#1396).

Le 27/09/2026, l'écran affichait « rapport de 17:06 » à 17:29, et on a cru que
`check-reliability.sh` ne tournait plus : il ne rend un rapport que quand ses
constats CHANGENT. Le passage qui n'a rien de neuf avance désormais
`terminee_le` — « dernier contrôle » —, et laisse `cree_le` — « constats
depuis ». La table n'en garde que vingt par tâche : une ligne par passage en
chasserait tout le reste en cinq heures.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.core import HistoriqueMaintenance
from app.routers.admin import rapports_scripts
from app.routers.admin.rapports_scripts import BattementTache, maintenance_battement

DEPUIS = datetime(2026, 9, 27, 15, 6, 0)


@pytest.fixture
def session(monkeypatch):
    #  La porte par clé est éprouvée par `test_autorisation.py` ; ici, le geste.
    monkeypatch.setattr(rapports_scripts, "exiger_cle_maintenance", lambda cle: None)
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        yield s


def _ligne(noeud: str, cree_le: datetime) -> HistoriqueMaintenance:
    return HistoriqueMaintenance(
        tache="reliability",
        noeud=noeud,
        statut="avertissement",
        cree_le=cree_le,
        terminee_le=cree_le,
    )


def test_le_battement_avance_le_DERNIER_controle_sans_creer_de_ligne(session):
    session.add(_ligne("rpi1", DEPUIS))
    session.commit()
    maintenance_battement(BattementTache(tache="reliability", noeud="rpi1"), None, session)
    lignes = session.exec(select(HistoriqueMaintenance)).all()
    assert len(lignes) == 1, "un battement a créé une ligne : la table serait pleine en cinq heures"
    assert lignes[0].cree_le == DEPUIS, "« constats depuis » ne doit pas bouger"
    assert lignes[0].terminee_le > DEPUIS, "« dernier contrôle » n'a pas avancé"


def test_il_prolonge_la_plus_RECENTE_du_bon_noeud(session):
    ancienne = _ligne("rpi1", datetime(2026, 9, 26, 10, 0))
    recente = _ligne("rpi1", DEPUIS)
    autre = _ligne("rpi2", DEPUIS)
    session.add_all([ancienne, recente, autre])
    session.commit()
    maintenance_battement(BattementTache(tache="reliability", noeud="rpi1"), None, session)
    session.refresh(ancienne), session.refresh(recente), session.refresh(autre)
    assert recente.terminee_le > DEPUIS
    assert ancienne.terminee_le == datetime(2026, 9, 26, 10, 0), (
        "une ancienne ligne a été prolongée"
    )
    assert autre.terminee_le == DEPUIS, "le battement de rpi1 a prolongé la ligne de rpi2"


def test_rien_a_prolonger_rend_404(session):
    """Le script efface alors sa mémoire, et renvoie un rapport complet au passage suivant."""
    with pytest.raises(HTTPException) as err:
        maintenance_battement(BattementTache(tache="reliability", noeud="rpi1"), None, session)
    assert err.value.status_code == 404
