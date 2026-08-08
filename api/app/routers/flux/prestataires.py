"""Flux — rubrique Prestataires : devis et nouvelles fiches.

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

Les deux sources partagent une page (`/prestataires`) et surtout **la même règle
d'accès** : cette page est réservée au CS et aux admins (`require_cs_or_admin`).
Une ligne qui renverrait un résident vers elle lui donnerait un lien mort ; c'est
pourquoi ni le lien d'un devis ni la fiche entière ne lui sont proposés.
"""
from datetime import datetime, time

from sqlmodel import select

from app.models.core import DevisPrestataire, Prestataire, RoleUtilisateur
from app.utils.liens import lien_element
from app.utils.montants import montant_fr
from app.utils.photos import parse_photos
from app.utils.visibility import perimetre_visible

from .commun import ContexteFlux, parse_perimetres, perimetre_label
from .schemas import FluxItem

_DEVIS_LABELS = {
    "en_attente": "En attente",
    "accepte": "Accepté",
    "refuse": "Refusé",
    "realise": "Réalisé",
}
_DEVIS_ICONS = {"en_attente": "📋", "accepte": "✅", "refuse": "❌", "realise": "🏁"}


def _reserve_au_cs(ctx: ContexteFlux) -> bool:
    return ctx.user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)


def _collecter_devis(ctx: ContexteFlux) -> list[FluxItem]:
    if ctx.user.statut == "locataire":
        return []

    devis_list = ctx.session.exec(
        select(DevisPrestataire, Prestataire)
        .join(Prestataire, DevisPrestataire.prestataire_id == Prestataire.id)
        .where(DevisPrestataire.actif, DevisPrestataire.affichable)
        .order_by(DevisPrestataire.id.desc())
    ).all()

    cartes: list[FluxItem] = []
    for dv, prest in devis_list:
        #  `perimetre` seul : un devis n'a pas de `perimetre_cible` et sa règle
        #  ignore `batiment_id`. Cf. `commun.perimetres_de`.
        perims = parse_perimetres(dv.perimetre)
        if not perimetre_visible(perims, ctx.user):
            continue
        dv_date = (
            datetime.combine(dv.date_prestation, time(12, 0))
            if dv.date_prestation
            else (dv.mis_a_jour_le or dv.cree_le)
        )
        if not dv_date:
            continue
        montant = montant_fr(dv.montant_estime) if dv.montant_estime else None
        cartes.append(FluxItem(
            id=f"dv_{dv.id}",
            type="devis",
            date=dv_date,
            cree_le=dv.cree_le,
            titre=dv.titre,
            detail=f"{prest.nom}{f' · {montant}' if montant else ''}",
            icon=_DEVIS_ICONS.get(dv.statut, "📋"),
            badges=[_DEVIS_LABELS.get(dv.statut, dv.statut)],
            #  Pas de lien plutôt qu'une page interdite : cf. docstring du module.
            lien=lien_element("dv", dv.id) if _reserve_au_cs(ctx) else None,
            meta={
                "devis_id": dv.id,
                "statut": dv.statut,
                "montant": dv.montant_estime,
                "perimetre": perimetre_label(perims),
                "notes": dv.notes,
                "prestataire": prest.nom,
                "date_prestation": dv.date_prestation.isoformat() if dv.date_prestation else None,
                "fichiers_urls": parse_photos(dv.fichiers_urls),
            },
        ))
    return cartes


def _collecter_fiches(ctx: ContexteFlux) -> list[FluxItem]:
    #  On ne remonte une nouvelle fiche qu'au CS/admin : pour les autres, le lien
    #  mènerait à une page qu'ils n'ont pas le droit d'ouvrir.
    if not _reserve_au_cs(ctx):
        return []
    prestas = ctx.session.exec(
        select(Prestataire)
        .where(Prestataire.actif, Prestataire.cree_le >= ctx.since)
        .order_by(Prestataire.cree_le.desc())
    ).all()
    return [
        FluxItem(
            id=f"presta_{pr.id}",
            type="prestataire",
            date=pr.cree_le,
            cree_le=pr.cree_le,
            titre=pr.nom,
            detail=pr.specialite or "Nouveau prestataire",
            icon="\U0001f6e0️",
            badges=[pr.specialite] if pr.specialite else [],
            lien=lien_element("presta", pr.id),
            meta={"prestataire_id": pr.id, "specialite": pr.specialite},
        )
        for pr in prestas
    ]


def collecter(ctx: ContexteFlux) -> list[FluxItem]:
    return _collecter_devis(ctx) + _collecter_fiches(ctx)
