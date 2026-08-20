"""Flux — rubrique Calendrier (événements).

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.
"""
from sqlalchemy import or_
from sqlmodel import select

from app.models.core import Evenement, Prestataire
from app.models.evenement import EvenementEvolution
#  Les libellés du Kanban viennent de LEUR source — celle qui les valide à
#  l'écriture (`calendrier_historique`). Les recopier ici en ferait une seconde
#  table, et le fil afficherait « fournisseur » le jour où l'autre dirait
#  « Prestataire ». Les périmètres (#316), les canaux, les statuts de ticket
#  (#415) et les pages (#401) ont tous divergé de cette façon.
from app.routers.calendrier_historique import KANBAN_LABELS
from app.utils.fichiers import est_image
from app.utils.liens import lien_element
from app.utils.photos import parse_photos
from app.utils.visibility import evenement_visible

from app.utils.perimetres import (
    a_portee_globale,
    batiments_cibles,
    parse_perimetres,
    perimetre_label,
)
from .commun import ContexteFlux, auteur_nom, badges_marqueurs, strip_html
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

def perimetres_evenement(ev) -> list[str]:
    """Périmètre d'un événement — `perimetre` seul, volontairement.

    Un `Evenement` n'a pas de `perimetre_cible`, et sa règle ignore
    `batiment_id` : passer par `commun.perimetres_de` changerait le périmètre
    affiché dès qu'un bâtiment est renseigné. Cf. `commun.perimetres_de`.
    """
    return parse_perimetres(ev.perimetre)


def _pieces_evolution(evol, ev) -> dict:
    """Pièces à montrer sur une carte de suivi : celles de l'entrée, sinon
    celles de l'événement.

    Même règle et même raison que `flux/tickets.py` : la carte annonce une mise
    à jour et affiche le commentaire du jour ; lui faire porter les photos
    d'origine montrerait une image vieille de trois semaines à côté d'un texte
    de ce matin. Repli sur l'événement pour ne rien retirer aux cartes qui
    fonctionnaient.
    """
    urls = parse_photos(evol.fichiers_urls)
    if not urls:
        return {
            "photos_urls": parse_photos(ev.photos_urls),
            "fichiers_urls": parse_photos(ev.fichiers_urls),
        }
    return {
        "photos_urls": [u for u in urls if est_image(u)],
        "fichiers_urls": [u for u in urls if not est_image(u)],
    }


def _evolutions(ctx: ContexteFlux):
    """Les entrées d'Historique de la fenêtre, événement joint, récentes d'abord."""
    return ctx.session.exec(
        select(EvenementEvolution, Evenement)
        .join(Evenement, EvenementEvolution.evenement_id == Evenement.id)
        .where(
            EvenementEvolution.cree_le >= ctx.since,
            ~Evenement.archivee,
            Evenement.affichable,
        )
        .order_by(EvenementEvolution.cree_le.desc())
    ).all()


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
        #  La liste des périmètres transverses était recopiée ici ; elle vient
        #  maintenant de l'arbre, via les mêmes primitives que la règle de
        #  visibilité et que la résolution des destinataires.
        concerne_bat = False
        if ctx.user.batiment_id:
            concerne_bat = (
                a_portee_globale(perims)
                or ctx.user.batiment_id in batiments_cibles(perims)
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

    #  ── L'Historique ────────────────────────────────────────────────────────
    #
    #  🔴 Le fil est un JOURNAL : ce qui s'y produit doit être daté du jour où ça
    #  s'est produit. Une affaire passée chez le prestataire ce matin restait
    #  datée de son annonce, donc invisible parmi les nouveautés — alors que
    #  c'est précisément le genre d'avancée qu'on vient y chercher.
    for evol, ev in _evolutions(ctx):
        if not evenement_visible(ev, ctx.user):
            continue
        etat = KANBAN_LABELS.get(evol.nouveau_statut or "", "")
        #  Un `etat` porte sa colonne, un `commentaire` n'en a pas : c'est cette
        #  absence qui distingue une étape franchie d'une simple mise à jour, et
        #  c'est déjà ce que le fil de l'événement lit pour ne pas dessiner un
        #  jalon là où il n'y en a pas.
        detail = f"Suivi : {etat}" if etat else "Mise à jour"
        prest = ctx.session.get(Prestataire, ev.prestataire_id) if ev.prestataire_id else None
        cartes.append(FluxItem(
            id=f"ev_evol_{evol.id}",
            #  🔴 Le type reste `evenement`, et ce n'est PAS un raccourci.
            #
            #  Le front teste `item.type === 'evenement'` à SIX endroits : le
            #  libellé, la couleur, le fond, le lien « Voir l'événement », la règle
            #  d'urgence (une coupure), celle du « non résolu » (colonne Kanban) —
            #  et, sur le tableau de bord, le filtre qui **masque les AG** à qui
            #  n'y a pas droit. Un type neuf passerait à côté des six.
            #
            #  ⚠️ Le sixième est le seul qui compte vraiment : une AG mise à jour
            #  serait devenue visible de tous, en silence. Les tickets ont trois
            #  types et les listent partout ; c'est cette duplication-là qui vient
            #  de coûter l'affichage du commentaire dans `FluxCard`.
            #
            #  C'est la DONNÉE qui porte la différence : `evol_contenu` est présent,
            #  donc la carte rend le bloc de suivi. Rien à énumérer.
            type="evenement",
            #  Daté de l'ENTRÉE, pas de l'événement — c'est tout l'objet.
            date=evol.cree_le,
            cree_le=ev.cree_le,
            titre=ev.titre,
            detail=detail,
            icon="\U0001f504" if etat else "\U0001f527",
            badges=badges_marqueurs(ev) + [ev.type] + ([prest.nom] if prest else []),
            lien=lien_element("ev", ev.id),
            meta={
                "ev_id": ev.id,
                "type": ev.type,
                "lieu": ev.lieu,
                "perimetre": perimetre_label(perimetres_evenement(ev)),
                "prestataire": prest.nom if prest else None,
                "debut": ev.debut.isoformat() if ev.debut else None,
                "fin": ev.fin.isoformat() if ev.fin else None,
                "statut_kanban": ev.statut_kanban,
                "epingle": ev.epingle,
                #  `full_html` reste la description de l'ÉVÉNEMENT : la carte
                #  dépliée doit rappeler de quoi il s'agit. Le texte du jour, lui,
                #  vit dans `evol_contenu`, rendu à part — exactement comme sur un
                #  ticket mis à jour.
                "full_html": ev.description,
                #  ⚠️ 400 et non 300 (#531). La carte PLIÉE affiche désormais cet
                #  extrait sous le libellé, sur trois lignes au plus (`clamp-3`).
                #  300 caractères en remplissent 2,3 : la coupure venait de la
                #  longueur, pas du gabarit — l'extrait s'arrêtait avant que les
                #  trois lignes soient atteintes, et le réglage visible n'était
                #  donc pas celui qui décidait.
                "evol_contenu": strip_html(evol.contenu, 400) if evol.contenu else None,
                "evol_auteur": auteur_nom(ctx.session, evol.auteur_id),
                **_pieces_evolution(evol, ev),
            },
        ))

    #  Une seule ligne par événement : la plus récente. L'Historique complet reste
    #  sur la fiche — le fil ne répond qu'à « quoi de neuf ». Même règle, et même
    #  écriture, que pour les tickets.
    dernier: dict[int, FluxItem] = {}
    for carte in cartes:
        eid = carte.meta.get("ev_id")
        if eid not in dernier or carte.date > dernier[eid].date:
            dernier[eid] = carte
    return list(dernier.values())
