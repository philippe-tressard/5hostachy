"""Flux — rubrique Calendrier (événements).

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.
"""
from sqlalchemy import or_
from sqlmodel import select

from app.models.core import Evenement, Prestataire
from app.utils.liens import lien_element
from app.utils.photos import parse_photos
from app.utils.visibility import evenement_visible

from app.utils.perimetres import parse_perimetres, perimetre_label
from .commun import ContexteFlux, badges_marqueurs, strip_html
from .schemas import FluxItem

#: Icône par type d'événement. Définie **ici** et importée par `sante.py`, qui
#: la réutilise pour l'agenda « Prochaines échéances » : le même événement doit
#: porter la même icône dans le fil et dans l'agenda.
TYPE_EMOJI = {
    "travaux": "🔨",
    "coupure": "⚡",
    "ag": "🏛️",
    "maintenance": "🔧",
    "maintenance_recurrente": "🔧",
    "autre": "📌",
}

#: Périmètres qui concernent tout le monde, quel que soit le bâtiment.
_PERIMETRES_GLOBAUX = ("résidence", "parking", "cave", "aful")


def perimetres_evenement(ev) -> list[str]:
    """Périmètre d'un événement — `perimetre` seul, volontairement.

    Un `Evenement` n'a pas de `perimetre_cible`, et sa règle ignore
    `batiment_id` : passer par `commun.perimetres_de` changerait le périmètre
    affiché dès qu'un bâtiment est renseigné. Cf. `commun.perimetres_de`.
    """
    return parse_perimetres(ev.perimetre)


def collecter(ctx: ContexteFlux) -> list[FluxItem]:
    evts = ctx.session.exec(
        select(Evenement)
        .where(~Evenement.archivee, Evenement.affichable)
        #  Un événement épinglé échappe à la fenêtre glissante, comme une
        #  publication épinglée.
        .where(or_(Evenement.debut >= ctx.since, Evenement.epingle))
        .order_by(Evenement.debut.desc())
    ).all()

    cartes: list[FluxItem] = []
    for ev in evts:
        if not evenement_visible(ev, ctx.user):
            continue
        perims = perimetres_evenement(ev)

        prest_name = None
        if ev.prestataire_id:
            prest = ctx.session.get(Prestataire, ev.prestataire_id)
            if prest:
                prest_name = prest.nom

        badges = badges_marqueurs(ev) + [ev.type]
        if prest_name:
            badges.append(prest_name)

        # L'événement concerne-t-il le bâtiment de l'utilisateur ?
        concerne_bat = False
        if ctx.user.batiment_id:
            minuscules = {p.lower() for p in perims}
            concerne_bat = f"bat:{ctx.user.batiment_id}" in minuscules or any(
                p in _PERIMETRES_GLOBAUX for p in minuscules
            )

        cartes.append(FluxItem(
            id=f"ev_{ev.id}",
            type="evenement",
            #  Le fil est un JOURNAL : il répond à « quoi de neuf ? ». Ce qui s'y
            #  produit, c'est l'ANNONCE de l'événement, pas sa tenue — quand
            #  l'événement a lieu, rien ne se passe dans l'application. Dater la
            #  ligne au `debut` plaçait les événements futurs *dans l'avenir* du
            #  fil, où le front les écartait purement et simplement (01/08/2026 :
            #  un nettoyage programmé restait introuvable). L'agenda « Prochaines
            #  échéances » répond, lui, à « quoi ensuite ? » et reste daté au
            #  `debut` (cf. `sante.py`). Même objet, deux questions, deux dates —
            #  aucune n'est en trop.
            date=ev.cree_le,
            cree_le=ev.cree_le,
            titre=ev.titre,
            detail=strip_html(ev.description),
            icon=TYPE_EMOJI.get(ev.type, "📌"),
            badges=badges,
            lien=lien_element("ev", ev.id),
            meta={
                "ev_id": ev.id,
                "type": ev.type,
                "lieu": ev.lieu,
                "perimetre": perimetre_label(perims),
                "prestataire": prest_name,
                "debut": ev.debut.isoformat() if ev.debut else None,
                "fin": ev.fin.isoformat() if ev.fin else None,
                "concerne_mon_batiment": concerne_bat,
                "full_html": ev.description,
                "statut_kanban": ev.statut_kanban,
                "epingle": ev.epingle,
                #  Le fil sait déjà rendre `photos_urls` (tickets) : rien à écrire
                #  côté carte, il suffit de le fournir.
                "photos_urls": parse_photos(ev.photos_urls),
                "fichiers_urls": parse_photos(ev.fichiers_urls),
            },
        ))
    return cartes
