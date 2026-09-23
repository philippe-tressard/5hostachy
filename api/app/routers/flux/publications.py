"""Flux — rubrique Actualités : les affaires de catégorie « Actualité » (#1091).

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

🔴 Depuis le lot 4 du chantier v2.0.0, une actualité EST une affaire (catégorie
« Actualité », état `publie`). Ce module ne lit plus `Publication` : il lit les
affaires de cette catégorie, et le collecteur des affaires suivies les saute —
sinon chacune paraîtrait deux fois, sous deux formes. La carte, elle, garde sa
forme d'actualité (`type="publication"`) : c'est ce que l'écran sait rendre, et
ce que le résident reconnaît.

Le nom du module est resté : il nomme une RUBRIQUE du fil, pas un modèle.
"""
from sqlalchemy import or_
from sqlmodel import select

from app.models.core import Ticket
from app.utils.archivage import est_archivable, seuil_archivage_jours
from app.utils.copie_auteur import proprietaire
from app.utils.liens import lien_ticket
from app.utils.nature_affaire import ACTUALITE
from app.utils.photos import parse_photos
from app.utils.visibility import ticket_visible

from .commun import ContexteFlux, badges_marqueurs, perimetres_de, strip_html
from .schemas import FluxItem


def collecter(ctx: ContexteFlux) -> list[FluxItem]:
    #  Un élément ÉPINGLÉ échappe à la fenêtre glissante : il a été explicitement
    #  désigné comme « à ne pas perdre de vue ». La péremption, elle, passe
    #  avant l'épinglage — `est_archivable` en décide (#1093).
    actualites = ctx.session.exec(
        select(Ticket)
        .where(
            Ticket.categorie == ACTUALITE,
            or_(Ticket.cree_le >= ctx.since, Ticket.epingle),
            ~Ticket.archive_manuel,
        )
        .order_by(Ticket.cree_le.desc())
    ).all()

    seuil_jours = seuil_archivage_jours(ctx.session)

    cartes: list[FluxItem] = []
    for t in actualites:
        #  La MÊME règle que la liste des affaires : une actualité que la liste
        #  range aux archives ne reste pas au fil sans y être accessible.
        if est_archivable("ticket", t, seuil_jours=seuil_jours):
            continue
        if not ticket_visible(t, ctx.user):
            continue
        #  Le PROPRIÉTAIRE, pas l'auteur : le « Saisi pour » s'il existe (12/09).
        auteur = proprietaire(ctx.session, t)[0]
        #  500 car. : assez pour déborder 3 lignes en pleine largeur → le clamp-3
        #  (front) coupe proprement en fin de 3ᵉ ligne. L'auteur n'est PAS
        #  préfixé à l'extrait : `meta["auteur"]` le rend en fin de rangée.
        extrait = strip_html(t.description, 500) if t.description else ""
        cartes.append(FluxItem(
            id=f"tk_{t.id}",
            type="publication",
            #  PAS `mis_a_jour_le` : cocher ou décocher « Épinglé » / « Urgent »
            #  écrit ce champ, et l'actualité remontait alors en tête du fil à
            #  la date du jour, pastille NEW comprise (exigé le 01/08/2026).
            #  Agir sur un marqueur est une action éditoriale, pas un événement de
            #  la copropriété : la ligne garde donc la date de son annonce et
            #  reprend simplement sa place dans la chronologie.
            date=t.cree_le,
            cree_le=t.cree_le,
            titre=t.titre,
            detail=extrait or None,
            icon="📰",
            badges=badges_marqueurs(t),
            lien=lien_ticket(t.id),
            meta={
                "ticket_id": t.id,
                "epingle": t.epingle,
                "urgente": t.priorite == "haute",
                "full_html": t.description,
                "auteur": auteur,
                "photos_urls": parse_photos(t.photos_urls),
                "perimetre_codes": perimetres_de(t),
            },
        ))
    return cartes
