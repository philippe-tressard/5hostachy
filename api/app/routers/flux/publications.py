"""Flux — rubrique Actualités (publications).

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

⚠️ Ce module s'appelle `publications` **dans le paquet `flux`** ; il importe le
router `app.routers.publications`, qui est un autre fichier. L'import est absolu,
donc sans ambiguïté pour Python — la précision est là pour le lecteur.
"""
from sqlalchemy import or_
from sqlmodel import select

from app.models.core import ConfigSite, Publication
from app.utils.liens import lien_element
from app.utils.visibility import publication_visible

#  Réutilise la MÊME règle d'archivage dynamique que /actualités pour éviter la
#  divergence dashboard ⇆ liste : une publication résolue/ancienne ne doit pas
#  rester affichée dans le fil (ni en « URGENCE ») alors qu'elle est masquée de
#  /actualités. Cf. bug 17/07/2026 (pub « Services techniques » visible seulement
#  au dashboard). Pas de cycle : le router publications n'importe pas le flux.
from app.routers.publications import (
    ARCHIVAGE_DELAI_HEURES,
    PUBLIE_VISIBILITE_JOURS,
    _is_archived,
)

from app.utils.perimetres import perimetre_label
from app.utils.photos import parse_photos
from .commun import ContexteFlux, auteur_nom, badges_marqueurs, perimetres_de, strip_html
from .schemas import FluxItem

_STATUT_LABELS = {"en_cours": "En cours", "resolu": "Résolu", "annule": "Annulé"}


def _seuil(session, cle: str, defaut: int) -> int:
    """Seuil d'archivage, surchargeable en configuration comme dans /actualités."""
    row = session.get(ConfigSite, cle)
    return int(row.valeur) if row and row.valeur.isdigit() else defaut


def collecter(ctx: ContexteFlux) -> list[FluxItem]:
    #  Un élément ÉPINGLÉ échappe à la fenêtre glissante : il a été explicitement
    #  désigné comme « à ne pas perdre de vue », il serait absurde qu'il s'efface
    #  de lui-même. Même exemption pour les événements.
    pubs = ctx.session.exec(
        select(Publication)
        .where(
            or_(Publication.cree_le >= ctx.since, Publication.epingle),
            ~Publication.brouillon,
            ~Publication.archivee,
        )
        .order_by(Publication.cree_le.desc())
    ).all()

    delai_heures = _seuil(ctx.session, "archivage_delai_heures", ARCHIVAGE_DELAI_HEURES)
    publie_jours = _seuil(ctx.session, "publie_visibilite_jours", PUBLIE_VISIBILITE_JOURS)

    cartes: list[FluxItem] = []
    for p in pubs:
        #  Exclut les publications archivées dynamiquement (résolues/anciennes) —
        #  cohérence avec /actualités : sinon elles restent au dashboard sans être
        #  accessibles depuis la liste principale.
        if _is_archived(p, delai_heures, publie_jours):
            continue
        if not publication_visible(p, ctx.user):
            continue

        badges = badges_marqueurs(p)
        if p.statut and p.statut != "publie":
            badges.append(_STATUT_LABELS.get(p.statut, p.statut))
        auteur = auteur_nom(ctx.session, p.auteur_id)
        #  500 car. : assez pour déborder 3 lignes en pleine largeur → le clamp-3
        #  (front) coupe proprement en fin de 3ᵉ ligne. 300 laissait la 3ᵉ ligne
        #  incomplète.
        contenu_extrait = strip_html(p.contenu, 500) if getattr(p, "contenu", None) else ""
        detail_parts = [x for x in [auteur, contenu_extrait] if x]

        cartes.append(FluxItem(
            id=f"pub_{p.id}",
            type="publication",
            #  PAS `mis_a_jour_le` : cocher ou décocher « Épinglé » / « Urgent »
            #  écrit ce champ, et la publication remontait alors en tête du fil à
            #  la date du jour, pastille NEW comprise (exigé le 01/08/2026).
            #  Agir sur un marqueur est une action éditoriale, pas un événement de
            #  la copropriété : la ligne garde donc la date de son annonce et
            #  reprend simplement sa place dans la chronologie.
            date=p.publiee_le or p.cree_le,
            cree_le=p.cree_le,
            titre=p.titre,
            detail=" — ".join(detail_parts) if detail_parts else None,
            icon="📰",
            badges=badges,
            lien=lien_element("pub", p.id),
            meta={
                "pub_id": p.id,
                "epingle": p.epingle,
                "urgente": p.urgente,
                "full_html": p.contenu,
                "auteur": auteur,
                "photos_urls": parse_photos(getattr(p, "photos_urls", None)),
                "statut": p.statut,
                "perimetre": perimetre_label(perimetres_de(p)),
            },
        ))
    return cartes
