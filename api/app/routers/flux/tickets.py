"""Flux — rubrique Tickets : ouvertures, changements d'état, réponses, commentaires.

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

## Ce qui a été factorisé en même temps

Les quatre sources d'une ligne de ticket (état, réponse du CS, commentaire,
ticket neuf) recopiaient la même cascade de périmètre, et les blocs « réponse »
et « commentaire » étaient identiques **au caractère près** hors trois valeurs —
libellé, icône et préfixe d'identifiant — commentaire de six lignes compris,
recopié tel quel dans les deux. Deux écritures d'une même carte, c'est-à-dire
deux endroits à corriger : le 07/08/2026, il en a manqué un et la photo d'un
commentaire est restée invisible dans le fil.

Il n'en reste qu'une écriture : `_carte_mise_a_jour`, alimentée par
`_MISES_A_JOUR`. Ajouter un type d'évolution au fil est désormais une ligne de
table, pas un quatrième bloc à recopier.
"""
from sqlmodel import select

from app.models.core import STATUTS_TICKET_ACTIFS, Ticket, TicketEvolution
from app.utils.dates_fr import duree_jhm
from app.utils.fichiers import est_image
from app.utils.photos import parse_photos
from app.utils.visibility import ticket_visible

from app.utils.perimetres import perimetre_label
from .commun import ContexteFlux, auteur_nom, perimetres_de, strip_html
from .schemas import FluxItem
from app.utils.corrections import est_correction

#: Évolutions qui produisent une carte « ticket mis à jour » sans changer l'état.
#: (type en base, préfixe d'identifiant, libellé, icône)
#:
#: 🔴 LES ICÔNES SONT CELLES DE `front/src/lib/evolutions.ts`, et elles doivent le
#: rester. Le 19/08/2026, la même notion était écrite QUATRE fois avec TROIS
#: valeurs : le bouton disait « 💬 Commenter », les deux fils affichaient 📝, et
#: cette table 🔧. Signalé à l'écran — *« pourquoi mon commentaire a une icône de
#: type relance ? »*.
#:
#: ⚠️ Front et API ne peuvent pas partager ce fichier : les contextes de build
#: sont `./api` et `./front`, rien de la racine n'entre dans les images. Les deux
#: écritures sont donc inévitables — c'est `api/tests/test_icones_evolution.py`
#: qui les empêche de diverger, pas la bonne volonté.
#:
#: Le LIBELLÉ, lui, reste propre à cet écran : « Mise à jour » décrit une carte de
#: flux, pas une entrée de fil. Ce sont deux rendus du même fait, et seule
#: l'icône est commune.
_MISES_A_JOUR = (
    ("reponse", "tk_rep", "Réponse du CS", "↩️"),
    ("commentaire", "tk_com", "Mise à jour", "💬"),
)


def _pieces_jointes(evol, tk) -> dict:
    """Pièces jointes à montrer sur une carte « ticket mis à jour ».

    Celles de l'évolution si elle en porte, sinon celles du ticket. Réparties en
    `photos_urls` / `fichiers_urls` parce que `FluxCard` n'en fait pas le même
    usage : les premières alimentent la vignette, les secondes la liste dépliée.
    Le tri se fait par `est_image`, la même règle qu'`estImage` côté front.
    """
    urls = parse_photos(evol.fichiers_urls)
    if not urls:
        return {
            "photos_urls": parse_photos(tk.photos_urls),
            "fichiers_urls": parse_photos(tk.fichiers_urls),
        }
    return {
        "photos_urls": [u for u in urls if est_image(u)],
        "fichiers_urls": [u for u in urls if not est_image(u)],
    }


def _meta_ticket(tk) -> dict:
    """Le socle de `meta` commun aux quatre cartes de ticket."""
    return {
        "ticket_id": tk.id,
        "numero": tk.numero,
        "perimetre": perimetre_label(perimetres_de(tk)),
        "description": strip_html(tk.description, 300),
    }


def _carte_mise_a_jour(ctx: ContexteFlux, evol, tk, *, ident, detail, icon, statut) -> FluxItem:
    """Carte « ticket mis à jour » — la seule écriture, pour les trois origines.

    Les pièces jointes de l'**évolution** priment sur celles du ticket. La carte
    annonce une mise à jour et affiche déjà `evol_contenu` : lui faire porter les
    photos d'origine montrerait une image vieille de dix jours à côté d'un texte
    du jour. Repli sur le ticket si l'évolution n'en porte aucune, pour ne rien
    retirer aux cartes qui fonctionnaient.

    Constaté le 07/08/2026 : les blocs « réponse » et « commentaire » n'émettaient
    aucune clé de pièce jointe, donc la carte du fil ne pouvait rien afficher même
    quand l'évolution en portait — alors que la photo l'était déjà dans le ticket
    et dans l'e-mail.
    """
    return FluxItem(
        id=ident,
        type="ticket_mis_a_jour",
        date=evol.cree_le,
        cree_le=tk.cree_le,
        titre=tk.titre,
        detail=detail,
        icon=icon,
        badges=[f"#{tk.numero}", tk.categorie],
        lien="/tickets",
        meta={
            **_meta_ticket(tk),
            "statut": statut,
            **_pieces_jointes(evol, tk),
            #  ⚠️ 400 et non 300 (#531). La carte PLIÉE affiche désormais cet
            #  extrait sous le libellé, sur trois lignes au plus (`clamp-3`).
            #  300 caractères en remplissent 2,3 : la coupure venait de la
            #  longueur, pas du gabarit — l'extrait s'arrêtait avant que les
            #  trois lignes soient atteintes, et le réglage visible n'était
            #  donc pas celui qui décidait.
            "evol_contenu": strip_html(evol.contenu, 400) if evol.contenu else None,
            "evol_auteur": auteur_nom(ctx.session, evol.auteur_id),
        },
    )


def _evolutions(ctx: ContexteFlux, type_evolution: str):
    """Les évolutions d'un type donné, ticket joint, les plus récentes d'abord."""
    return ctx.session.exec(
        select(TicketEvolution, Ticket)
        .join(Ticket, TicketEvolution.ticket_id == Ticket.id)
        .where(
            TicketEvolution.type == type_evolution,
            TicketEvolution.cree_le >= ctx.since,
        )
        .order_by(TicketEvolution.cree_le.desc())
    ).all()


def collecter(ctx: ContexteFlux) -> list[FluxItem]:
    """Une seule ligne par ticket : la plus récente.

    L'historique complet reste consultable sur la fiche du ticket — le fil n'est
    qu'un résumé « quoi de neuf ».
    """
    cartes: list[FluxItem] = []
    vus: set[int] = set()

    # ── Changements d'état ───────────────────────────────────────────────────
    etats = _evolutions(ctx, "etat")
    for evol, tk in etats:
        if not ticket_visible(tk, ctx.user):
            continue
        vus.add(tk.id)
        nouveau = evol.nouveau_statut or ""
        if nouveau == "résolu":
            #  🔴 `jj:hh:mm`, et non un arrondi décimal d'heures (01/09/2026,
            #  demandé à l'écran). « Résolu en 23.9h » n'a de sens nulle part
            #  ailleurs sur le site et se convertit de tête ; le point décimal
            #  était en prime un point sur un site intégralement en français.
            #  Le format vit dans `dates_fr.duree_jhm` — une durée EST un format.
            duree = None
            if tk.ferme_le and tk.cree_le:
                duree = duree_jhm(tk.ferme_le - tk.cree_le)
            cartes.append(FluxItem(
                id=f"tk_{tk.id}",
                type="ticket_resolu",
                date=evol.cree_le,
                cree_le=tk.cree_le,
                titre=tk.titre,
                #  ⚠️ `is not None` et non `if duree`. L'ancien code testait un
                #  FLOAT : une résolution en moins de six minutes s'arrondissait à
                #  `0.0`, donc falsy, et la mention disparaissait — le ticket le
                #  plus vite résolu était le seul à ne pas le dire. `duree_jhm`
                #  rend `None` sur une donnée incohérente, jamais sur un zéro.
                detail=f"Résolu{f' en {duree}' if duree is not None else ''}",
                icon="✅",
                badges=[f"#{tk.numero}", tk.categorie],
                lien="/tickets",
                meta={
                    **_meta_ticket(tk),
                    "statut": "résolu",
                    #  Le nom dit désormais ce que la valeur EST : plus des heures
                    #  décimales, mais `jj:hh:mm`. Aucun écran ne la lisait — le
                    #  renommer maintenant évite qu'un futur lecteur croie à un nombre.
                    "duree": duree,
                    "cloture_le": tk.ferme_le.isoformat() if tk.ferme_le else None,
                    #  Même règle que les trois autres cartes de ticket : une photo
                    #  jointe au commentaire de clôture doit se voir.
                    **_pieces_jointes(evol, tk),
                },
            ))
        elif nouveau in STATUTS_TICKET_ACTIFS:
            cartes.append(_carte_mise_a_jour(
                ctx, evol, tk,
                ident=f"tk_{tk.id}",
                detail="Réouvert" if nouveau == "ouvert" else "Pris en charge",
                icon="🔧",
                statut=nouveau,
            ))

    # ── Réponses du CS et commentaires ───────────────────────────────────────
    for type_evolution, prefixe, detail, icon in _MISES_A_JOUR:
        for evol, tk in _evolutions(ctx, type_evolution):
            if not ticket_visible(tk, ctx.user):
                continue
            #  🔴 UNE CORRECTION N'EST PAS UNE NOUVELLE — même règle que les
            #  événements (01/09/2026). Corriger un ticket écrit « Correction :
            #  Périmètre » dans son Historique, et cela n'a rien à faire dans le
            #  fil de la copropriété. `app/utils/corrections.py`.
            if est_correction(evol):
                continue
            vus.add(tk.id)
            cartes.append(_carte_mise_a_jour(
                ctx, evol, tk,
                ident=f"{prefixe}_{evol.id}",
                detail=detail,
                icon=icon,
                statut=tk.statut,
            ))

    # ── Tickets récemment créés, sans aucune évolution ───────────────────────
    for tk in ctx.session.exec(
        select(Ticket).where(Ticket.cree_le >= ctx.since).order_by(Ticket.cree_le.desc())
    ).all():
        if tk.id in vus or not ticket_visible(tk, ctx.user):
            continue
        cartes.append(FluxItem(
            id=f"tk_{tk.id}",
            type="ticket_ouvert",
            date=tk.cree_le,
            cree_le=tk.cree_le,
            titre=tk.titre,
            detail="Nouveau ticket",
            icon="🎫",
            badges=[f"#{tk.numero}", tk.categorie],
            lien="/tickets",
            meta={
                **_meta_ticket(tk),
                "statut": tk.statut,
                "photos_urls": parse_photos(tk.photos_urls),
                "fichiers_urls": parse_photos(tk.fichiers_urls),
            },
        ))

    # Un seul événement par ticket dans le fil : le plus récent.
    dernier: dict[int, FluxItem] = {}
    for carte in cartes:
        tid = carte.meta.get("ticket_id")
        if tid not in dernier or carte.date > dernier[tid].date:
            dernier[tid] = carte
    return list(dernier.values())
