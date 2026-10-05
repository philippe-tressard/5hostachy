"""Les contrats de la synthèse d'un prestataire se lisent comme ceux de la liste (#1687).

## Le défaut

`GET /prestataires/synthese/{id}` relisait ses contrats par
`ContratRead.model_validate(c)` seul, sans le calcul que la liste des contrats
leur applique (`lister_contrats` : `poser_echeance`, `archivee`,
`synthese_disponible`). `date_fin`, `reconduit` et `echu` y gardaient donc leur
valeur par défaut : un contrat reconduit d'année en année n'avait, dans la
synthèse, aucune échéance. C'est la classe d'erreur de #1563 — une lecture qui
ne passe pas par la fonction commune.

## Ce que ce fichier vérifie

Un contrat reconduit (terme initial passé) porte son échéance déduite dans la
synthèse, et chaque contrat de la synthèse est IDENTIQUE à sa ligne dans la
liste des contrats.
"""

from __future__ import annotations

from datetime import date

from app.models.core import ContratEntretien, Prestataire
from app.routers.prestataires import get_prestataire_synthese, lister_contrats
from app.utils.echeance_contrat import echeance_du_contrat


def _decor(session) -> tuple[int, ContratEntretien]:
    p = Prestataire(nom="Ascenseurs Témoin", specialite="ascenseur")
    session.add(p)
    session.commit()
    session.refresh(p)
    #  Un an à compter de 2020 : le terme initial est passé depuis longtemps, le
    #  contrat est donc RECONDUIT et son échéance se reporte d'année en année.
    c = ContratEntretien(
        copropriete_id=1,
        prestataire_id=p.id,
        libelle="Maintenance de l'ascenseur",
        date_debut=date(2020, 1, 1),
        duree_initiale_valeur=1,
        duree_initiale_unite="ans",
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return p.id, c


def test_la_synthese_porte_l_echeance_deduite(session):
    p_id, c = _decor(session)
    attendue = echeance_du_contrat(c)
    assert attendue is not None and attendue.reconduit  # le décor dit bien ce qu'il annonce

    (lu,) = get_prestataire_synthese(p_id, session, None)["contrats"]
    assert lu["date_fin"] == attendue.date
    assert lu["reconduit"] is True
    assert lu["echu"] is False


def test_un_contrat_de_la_synthese_egale_sa_ligne_de_la_liste(session):
    p_id, _ = _decor(session)

    synthese = get_prestataire_synthese(p_id, session, None)["contrats"]
    liste = [lu.model_dump() for lu in lister_contrats(session, archivees=False)]
    assert synthese == [ligne for ligne in liste if ligne["prestataire_id"] == p_id]
