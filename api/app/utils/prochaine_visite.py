"""La prochaine visite d'un contrat, recalculée quand un Entretien récurrent se clôt.

## D'où ça vient (#1092, lot 5, 23/09/2026)

Le calendrier le faisait quand une maintenance récurrente passait « Terminé »
(`routers/calendrier.py`, `_update_contrat_prochaine_visite`). Les événements
sont devenus des affaires Entretien : la règle suit l'affaire, et elle est
écrite ICI, une fois, pour les deux chemins qui résolvent une affaire — la
Suite d'état (`evolutions.py`) et la correction (`mise_a_jour.py`).

## La règle, inchangée

- une affaire **Entretien**, **récurrente** (elle porte une fréquence), avec un
  **intervenant** ;
- le contrat actif de ce prestataire — rapproché par son libellé dans le titre
  (« Otis — Ascenseur »), ou le seul qu'il ait ;
- sa `prochaine_visite` part de la date de l'intervention (`debut`, à défaut
  aujourd'hui), selon la fréquence du CONTRAT.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.models.prestataires import ContratEntretien
from app.models.tickets import CategorieTicket, StatutTicket
from app.utils.valeurs import valeur


def _ajouter_mois(depuis: date, mois: int) -> date:
    m = depuis.month + mois
    return date(depuis.year + (m - 1) // 12, (m - 1) % 12 + 1, min(depuis.day, 28))


def date_prochaine_visite(contrat: ContratEntretien, depuis: date) -> Optional[date]:
    """La visite suivante, d'après la fréquence du contrat — `None` s'il n'en a pas."""
    ft, fv = contrat.frequence_type, contrat.frequence_valeur
    if not ft or not fv:
        return None
    if ft == "semaines":
        return depuis + timedelta(weeks=fv)
    if ft == "mois":
        return _ajouter_mois(depuis, fv)
    if ft == "fois_par_an":
        return _ajouter_mois(depuis, max(1, 12 // fv))
    if ft == "ans":
        return _ajouter_mois(depuis, 12 * fv)
    return None


def apres_cloture(ticket, session: Session) -> None:
    """Avance la prochaine visite du contrat quand un Entretien récurrent est résolu."""
    if valeur(ticket.categorie) != CategorieTicket.entretien.value:
        return
    if valeur(ticket.statut) != StatutTicket.résolu.value:
        return
    if not ticket.frequence_type or not ticket.prestataire_id:
        return
    contrats = session.exec(
        select(ContratEntretien).where(
            ContratEntretien.prestataire_id == ticket.prestataire_id,
            ContratEntretien.actif == True,  # noqa: E712 — colonne SQL, pas un booléen Python
        )
    ).all()
    retenu = next(
        (c for c in contrats if c.libelle and c.libelle.lower() in ticket.titre.lower()),
        contrats[0] if len(contrats) == 1 else None,
    )
    if retenu is None:
        return
    depuis = ticket.debut.date() if isinstance(ticket.debut, datetime) else (ticket.debut or date.today())
    suivante = date_prochaine_visite(retenu, depuis)
    if suivante:
        retenu.prochaine_visite = suivante
        session.add(retenu)


__all__ = ["apres_cloture", "date_prochaine_visite"]
