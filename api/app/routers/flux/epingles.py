"""Flux — décompte des éléments épinglés, toutes rubriques confondues.

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, select

from app.utils.nature_affaire import ACTUALITE
from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Evenement, Ticket, Utilisateur

from .schemas import EpinglesCompte

router = APIRouter()


@router.get("/epingles", response_model=EpinglesCompte)
def compter_epingles(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Combien d'éléments occupent le bandeau « Épinglé », toutes rubriques confondues.

    Sert l'avertissement de plafond souple affiché au moment de cocher la case
    « Épingler », dans les actualités comme dans le calendrier. Ce compte ne peut
    pas être fait côté client : chaque page ne connaît que sa propre rubrique et
    afficherait donc un total partiel — deux avertissements qui se contrediraient.

    Mêmes filtres que le fil : un brouillon ou un événement non affichable est
    peut-être coché « épinglé », il n'occupe pas le bandeau pour autant.
    """
    #  Les actualités sont des affaires depuis le lot 4 (#1091). Le champ de la
    #  réponse garde son nom : c'est la RUBRIQUE que l'écran affiche.
    publications = session.exec(
        select(func.count(Ticket.id)).where(
            Ticket.categorie == ACTUALITE, Ticket.epingle, ~Ticket.archive_manuel,
        )
    ).one() or 0
    evenements = session.exec(
        select(func.count(Evenement.id)).where(
            Evenement.epingle, ~Evenement.archivee, Evenement.affichable
        )
    ).one() or 0
    return EpinglesCompte(
        total=publications + evenements,
        publications=publications,
        evenements=evenements,
    )
