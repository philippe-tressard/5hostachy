"""Flux — rubrique Annuaire : nouveaux membres du conseil syndical et du syndic.

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

Visible de **tous les résidents** : savoir qui siège au CS ou représente le
syndic n'est pas une information réservée.
"""
from sqlmodel import select

from app.models.core import MembreCS, MembreSyndic, RoleUtilisateur

from .commun import ContexteFlux
from .schemas import FluxItem
from app.utils.noms import nom_affiche
from app.utils.roles_libelles import libelle_role


def _carte_membre(ident: str, membre, detail: str, badge: str, meta: dict) -> FluxItem:
    """Ce que les deux annuaires ont réellement en commun : la carte, pas la donnée.

    `meta` reste à l'appelant — un membre du CS a une présidence, un membre du
    syndic une fonction. Les fusionner derrière un discriminant rendrait le
    module plus court et moins clair.
    """
    return FluxItem(
        id=ident,
        type="annuaire",
        date=membre.cree_le,
        cree_le=membre.cree_le,
        #  « Prénom NOM », nom en capitales — la règle du site, écrite une
        #  seule fois (`utils/noms.py`). Ce titre rendait la casse tapée :
        #  « Jean-Sébastien CourT », signalé à l'écran le 31/08/2026.
        titre=nom_affiche(membre.prenom, membre.nom),
        detail=detail,
        icon="👥",
        badges=[badge],
        lien="/annuaire",
        meta=meta,
    )


def collecter(ctx: ContexteFlux) -> list[FluxItem]:
    membres_cs = ctx.session.exec(
        select(MembreCS).where(MembreCS.cree_le >= ctx.since).order_by(MembreCS.cree_le.desc())
    ).all()
    membres_syndic = ctx.session.exec(
        select(MembreSyndic)
        .where(MembreSyndic.cree_le >= ctx.since)
        .order_by(MembreSyndic.cree_le.desc())
    ).all()

    cartes = [
        _carte_membre(
            f"mcs_{m.id}",
            m,
            "Nouveau membre du conseil syndical" + (" — Président" if m.est_president else ""),
            #  Le badge vient de la table unique (#801) : « Conseil syndical »
            #  était écrit ici en dur, à côté de six autres écritures qui avaient
            #  déjà divergé sur la casse.
            libelle_role(RoleUtilisateur.conseil_syndical),
            {"membre_cs_id": m.id, "est_president": m.est_president},
        )
        for m in membres_cs
    ]
    cartes += [
        _carte_membre(
            f"msyn_{m.id}",
            m,
            "Nouveau membre du syndic" + (f" — {m.fonction}" if m.fonction else ""),
            "Syndic",
            {"membre_syndic_id": m.id, "fonction": m.fonction},
        )
        for m in membres_syndic
    ]
    return cartes
