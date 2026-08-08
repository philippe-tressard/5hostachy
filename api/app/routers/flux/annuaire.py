"""Flux — rubrique Annuaire : nouveaux membres du conseil syndical et du syndic.

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

Visible de **tous les résidents** : savoir qui siège au CS ou représente le
syndic n'est pas une information réservée.
"""
from sqlmodel import select

from app.models.core import MembreCS, MembreSyndic

from .commun import ContexteFlux
from .schemas import FluxItem


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
        titre=f"{membre.prenom} {membre.nom}",
        detail=detail,
        icon="\U0001f465",
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
            "Conseil syndical",
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
