"""« Init. prestataires » : les visites de l'exercice en UNE fois (#1193).

Le lot pose des affaires Entretien « Chez le prestataire », toutes ou aucune, et
ne diffuse RIEN : un canal glissé dans le corps est refusé (422), jamais ignoré —
l'appelant croirait avoir diffusé.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlmodel import select

from app.models.core import Ticket
from app.models.tickets import CategorieTicket, StatutTicket
from app.routers.tickets.lot import LotDeVisites, creer_visites_en_lot
from tests.aides_badges import _compte, session  # noqa: F401 — `session` est une fixture


def _visite(**extra):
    return {
        "titre": "Otis — Ascenseur (1/2)",
        "debut": datetime(2027, 1, 15, 9, 0),
        "perimetre_cible": ["bat:1"],
        "frequence_type": "fois_par_an",
        "frequence_valeur": 2,
        **extra,
    }


def test_le_lot_pose_des_affaires_entretien_suivies(session):
    cs = _compte(session, "Cs")
    rendu = creer_visites_en_lot(
        LotDeVisites(affaires=[_visite(), _visite(titre="Otis — Ascenseur (2/2)")]),
        session=session,
        user=cs,
    )
    assert rendu == {"crees": 2}
    affaires = session.exec(select(Ticket)).all()
    assert {(a.categorie, a.statut, a.suivi_kanban) for a in affaires} == {
        (CategorieTicket.entretien, StatutTicket.chez_prestataire, True)
    }
    assert affaires[0].frequence_type == "fois_par_an" and affaires[0].description


def test_un_canal_dans_le_corps_est_refuse_pas_ignore():
    with pytest.raises(ValidationError):
        LotDeVisites(affaires=[_visite(partager_whatsapp=True)])


def test_cas_zero_un_lot_vide_est_refuse(session):
    with pytest.raises(HTTPException) as refus:
        creer_visites_en_lot(
            LotDeVisites(affaires=[]), session=session, user=_compte(session, "Cs")
        )
    assert refus.value.status_code == 422


def test_toutes_ou_aucune(session):
    """Une fréquence inconnue à la 2ᵉ visite : la 1ʳᵉ n'est pas créée non plus."""
    cs = _compte(session, "Cs")
    with pytest.raises(HTTPException):
        creer_visites_en_lot(
            LotDeVisites(affaires=[_visite(), _visite(frequence_type="lunes")]),
            session=session,
            user=cs,
        )
    session.rollback()
    assert session.exec(select(Ticket)).first() is None


def test_la_visite_d_un_contrat_part_sous_ce_contrat(session):
    """#1445 : l'affaire dit qu'elle est sous contrat, et le rythme se lit sur lui."""
    from app.models.prestataires import ContratEntretien, Prestataire

    cs = _compte(session, "Cs")
    p = Prestataire(nom="Otis", specialite="ascenseur")
    session.add(p)
    session.commit()
    session.refresh(p)
    c = ContratEntretien(
        copropriete_id=1, prestataire_id=p.id, libelle="Ascenseur", type_equipement="ascenseur"
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    creer_visites_en_lot(
        LotDeVisites(affaires=[_visite(prestataire_id=p.id, contrat_id=c.id)]),
        session=session,
        user=cs,
    )
    t = session.exec(select(Ticket)).one()
    assert (t.contrat_id, t.frequence_type) == (c.id, None)


def test_un_contrat_d_un_autre_prestataire_refuse_le_lot(session):
    from app.models.prestataires import ContratEntretien, Prestataire

    cs = _compte(session, "Cs")
    otis, sicli = (
        Prestataire(nom="Otis", specialite="ascenseur"),
        Prestataire(nom="Sicli", specialite="extincteurs"),
    )
    session.add_all([otis, sicli])
    session.commit()
    c = ContratEntretien(
        copropriete_id=1,
        prestataire_id=sicli.id,
        libelle="Extincteurs",
        type_equipement="extincteurs",
    )
    session.add(c)
    session.commit()
    with pytest.raises(HTTPException) as refus:
        creer_visites_en_lot(
            LotDeVisites(affaires=[_visite(prestataire_id=otis.id, contrat_id=c.id)]),
            session=session,
            user=cs,
        )
    assert refus.value.status_code == 422 and "Visite 1" in refus.value.detail
