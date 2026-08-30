"""Tickets — notions partagées par les cinq sous-domaines.

Extrait de `tickets.py` (1238 lignes) le 08/08/2026. Voir `__init__.py` pour la
règle de découpage.

Trois duplications que le fichier long avait fabriquées vivent désormais ici :

- **la liste des destinataires syndic / CS**, écrite à l'identique **trois fois**
  (création d'un ticket, relance syndic, ajout d'une évolution). Trois blocs de
  vingt lignes qui déduplicaient les adresses chacun dans leur coin — le jour où
  la règle change, il fallait la corriger trois fois et personne ne l'aurait su ;
- **la lecture de `site_nom` / `site_url`**, refaite **quatre fois** ;
- **le libellé d'une évolution**, écrit deux fois avec deux résultats différents
  (« Commentaire CS » d'un côté, « Commentaire : … » de l'autre).
"""
import json
import random
import string

from sqlmodel import Session, select

from app.models.core import (
    Batiment,
    ConfigSite,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.schemas import TicketEvolutionRead, TicketRead
from app.utils.photos import parse_photos

#: Libellé lisible de chaque état — e-mails, notifications, fil d'évolutions.
#:
#: Les quatre premières clés sont les états du workflow (`StatutTicket`) ;
#: `fermé` n'en est plus un depuis le 17/08/2026 (#415, migration 0149) mais
#: reste **affichable** : le fil de tickets anciens raconte « Ouvert → Fermé »,
#: et une ligne d'histoire ne se réécrit pas. Sans ce libellé, ces évolutions
#: afficheraient la valeur brute.
#:
#: Un couvercle vérifie que ce dictionnaire couvre l'énumération et rien de
#: fantaisiste : `api/tests/test_statuts_tickets.py`.
STATUT_LABELS = {
    "ouvert": "Ouvert", "en_cours": "En cours",
    "résolu": "Résolu", "annulé": "Annulé",
    "fermé": "Fermé",  # historique seulement — cf. STATUTS_TICKET_HISTORIQUES
}


def generer_numero() -> str:
    return "TK-" + "".join(random.choices(string.digits, k=6))


# ── Configuration du site ────────────────────────────────────────────────────

def config_site(session: Session, *cles: str) -> dict:
    """Valeurs de `ConfigSite`, avec `site_nom` et `site_url` toujours incluses.

    Ces deux clés alimentent le pied de chaque e-mail : les demander partout
    évitait déjà de les oublier, mais au prix de quatre requêtes écrites à la
    main. Une seule écriture ici.
    """
    voulues = {"site_nom", "site_url"} | set(cles)
    lignes = session.exec(select(ConfigSite).where(ConfigSite.cle.in_(voulues))).all()
    return {r.cle: r.valeur for r in lignes}


def contexte_site(cfg: dict) -> dict:
    """Le bloc `residence` / `app` que tous les modèles d'e-mail attendent."""
    return {
        "residence": {"nom": cfg.get("site_nom", "5Hostachy")},
        "app": {"url": cfg.get("site_url", "https://localhost")},
    }


# ── Destinataires ────────────────────────────────────────────────────────────
#
# 🔴 LA RÈGLE A DÉMÉNAGÉ le 31/08/2026, et ces deux noms n'en sont plus que des
# renvois. Ce fichier portait le corps, avec ce commentaire : *« elle est le seul
# endroit où cette règle s'écrit »*. C'était faux — le calendrier, les
# publications et les sondages en portaient chacun une copie, identique à la
# variable près, et sans un mot d'explication.
#
# ⚠️ C'est la forme la plus coûteuse de la duplication : le seul fichier qui
# parlait du sujet affirmait que le problème n'existait pas. Une relecture qui
# ouvrait celui-ci en repartait rassurée.
#
# Le corps vit dans `app/utils/destinataires.py`, que `CLAUDE.md` désigne comme
# la source unique des destinataires. Les alias restent parce que six modules et
# la documentation du paquet les nomment : les supprimer serait un second lot,
# et il n'apporterait rien de plus que du renommage.
from app.utils.destinataires import (  # noqa: F401  (ré-export volontaire)
    destinataires_syndic_cs,
    syndic_principal,
)


# ── Libellés d'évolution ─────────────────────────────────────────────────────

def libelle_evolution(e: TicketEvolution, *, avec_extrait: bool = False) -> str:
    """Ligne d'historique décrivant une évolution.

    `avec_extrait` reproduit la nuance qui existait entre les deux écritures
    d'origine : l'e-mail d'évolution montrait un extrait du commentaire, celui de
    relance se contentait de « Commentaire CS ». La différence est voulue — un
    paramètre, pas deux fonctions qui divergeront.
    """
    if e.type == "etat":
        return (
            "Changement d'état : "
            f"{STATUT_LABELS.get(e.ancien_statut or '', e.ancien_statut or '?')} → "
            f"{STATUT_LABELS.get(e.nouveau_statut or '', e.nouveau_statut or '?')}"
        )
    if e.type == "relance":
        return e.contenu or "Relance syndic"
    if e.type == "commentaire":
        return f"Commentaire : {(e.contenu or '')[:100]}" if avec_extrait else "Commentaire CS"
    if e.type == "reponse":
        return "Réponse"
    return e.type


# ── Sérialisation ────────────────────────────────────────────────────────────

def evol_read(e: TicketEvolution, session: Session) -> TicketEvolutionRead:
    auteur = session.get(Utilisateur, e.auteur_id)
    return TicketEvolutionRead(
        id=e.id, ticket_id=e.ticket_id, type=e.type,
        contenu=e.contenu, ancien_statut=e.ancien_statut,
        nouveau_statut=e.nouveau_statut, auteur_id=e.auteur_id,
        auteur_nom=f"{auteur.prenom} {auteur.nom}" if auteur else "?",
        cree_le=e.cree_le,
        fichiers_urls=json.loads(e.fichiers_urls) if e.fichiers_urls else [],
        #  `None` — et non `[]` — quand l'entrée ne parle pas du périmètre : le
        #  front distingue « n'en parle pas » de « plus aucun périmètre » (#497).
        perimetre_cible=json.loads(e.perimetre_cible) if e.perimetre_cible else None,
    )


def apercu_pieces(ticket: Ticket, session: Session) -> list[str]:
    """Les pièces à montrer en vignette sur la carte REPLIÉE (#464).

    Celles du ticket si elle en porte ; sinon celles de l'entrée d'Historique **la
    plus récente** qui en porte.

    ## Pourquoi ce repli existe

    Sur un ticket suivi, les photos arrivent souvent par le fil — « voici ce qu'a
    constaté le plombier ». La carte restait alors nue, là où le même dossier saisi
    avec ses photos dès l'ouverture montrait sa vignette. Deux tickets, même
    contenu visible, deux apparences dans la liste.

    Le calendrier faisait déjà ce repli côté front (`apercuAvecRepli`), parce que
    son API livre le fil avec l'objet. Les tickets chargent leurs évolutions à la
    demande : le repli se calcule donc **ici**, et ne transporte que les URLs.

    ⚠️ La plus RÉCENTE, jamais la première : sinon un dossier qui a avancé
    montrerait indéfiniment la photo du jour de son ouverture.
    """
    propres = parse_photos(ticket.photos_urls) + parse_photos(ticket.fichiers_urls)
    if propres:
        return propres
    #  Une seule requête, triée par date décroissante, et on s'arrête à la
    #  première entrée qui porte quelque chose. Pas de N+1 : c'est un `SELECT` par
    #  ticket, comme les trois que `ticket_read` fait déjà.
    evols = session.exec(
        select(TicketEvolution)
        .where(TicketEvolution.ticket_id == ticket.id)
        .order_by(TicketEvolution.cree_le.desc())
    ).all()
    for evol in evols:
        pieces = parse_photos(evol.fichiers_urls)
        if pieces:
            return pieces
    return []


def ticket_read(ticket: Ticket, session: Session) -> TicketRead:
    auteur = session.get(Utilisateur, ticket.auteur_id)
    #  🔴 LE BÂTIMENT DU DEMANDEUR, ET RIEN D'AUTRE (#653, 30/08/2026).
    #
    #  Cette ligne était :
    #
    #      auteur_batiment_id = ticket.batiment_id or (auteur.batiment_id if auteur else None)
    #
    #  Le champ s'appelle `auteur_batiment_nom`, la carte le rend sous 📍 avec le
    #  commentaire « LE BÂTIMENT DU DEMANDEUR » — et le calcul prenait d'abord
    #  celui du TICKET. Dès qu'un ticket portait un `batiment_id`, le badge
    #  affichait le bâtiment visé sous une étiquette qui annonce celui de la
    #  personne : un membre du CS lisait « Philippe TRESSARD 📍 Bât. 4 » et en
    #  déduisait où habite Philippe. Signalé à l'écran, sur une carte où « Bât. 4 »
    #  apparaissait deux fois — une fois comme périmètre, une fois comme ce badge.
    #
    #  ⚠️ AUCUN REPLI, et c'est le cœur du correctif. Quand l'auteur n'a pas de
    #  bâtiment renseigné, on n'affiche RIEN : retomber sur celui du ticket
    #  remettrait une valeur juste sous une étiquette fausse, ce qui est
    #  exactement le défaut qu'on retire. Le périmètre visé est déjà rendu à côté,
    #  par le badge 🔹 — le taire ici ne perd aucune information.
    #
    #  📖 `ticketScope()` (front) porte le repli, LUI, et l'annonce : « le bâtiment
    #  de l'auteur, à défaut le bâtiment ciblé, à défaut la résidence ». Il devient
    #  juste par ce correctif — il recevait jusqu'ici un premier terme qui pouvait
    #  déjà être le second.
    auteur_batiment_id = auteur.batiment_id if auteur else None
    batiment = session.get(Batiment, auteur_batiment_id) if auteur_batiment_id else None
    # Calcul de l'affichage "saisi pour"
    saisi_pour_affichage: str | None = None
    if ticket.saisi_pour_user_id:
        sp_user = session.get(Utilisateur, ticket.saisi_pour_user_id)
        if sp_user:
            saisi_pour_affichage = f"{sp_user.prenom} {sp_user.nom}"
    elif ticket.saisi_pour_nom:
        saisi_pour_affichage = ticket.saisi_pour_nom
    return TicketRead(
        id=ticket.id,
        numero=ticket.numero,
        titre=ticket.titre,
        description=ticket.description,
        categorie=ticket.categorie,
        statut=ticket.statut,
        priorite=ticket.priorite,
        auteur_id=ticket.auteur_id,
        auteur_nom=f"{auteur.prenom} {auteur.nom}" if auteur else None,
        auteur_batiment_nom=f"Bât. {batiment.numero}" if batiment else None,
        lot_id=ticket.lot_id,
        batiment_id=ticket.batiment_id,
        perimetre_cible=ticket.perimetre_cible,
        photos_urls=ticket.photos_urls,
        fichiers_urls=ticket.fichiers_urls,
        apercu_pieces=apercu_pieces(ticket, session),
        destinataire_syndic=ticket.destinataire_syndic,
        destinataire_cs=ticket.destinataire_cs,
        saisi_pour_user_id=ticket.saisi_pour_user_id,
        saisi_pour_nom=ticket.saisi_pour_nom,
        saisi_pour_email=ticket.saisi_pour_email,
        saisi_pour_affichage=saisi_pour_affichage,
        cree_le=ticket.cree_le,
        mis_a_jour_le=ticket.mis_a_jour_le,
        non_relancable=ticket.non_relancable,
        non_relancable_motif=ticket.non_relancable_motif,
        relance_count=compter_relances(session, ticket.id),
    )


def compter_relances(session: Session, ticket_id: int) -> int:
    """Nombre de relances syndic déjà envoyées — compté à trois endroits avant."""
    return len(session.exec(
        select(TicketEvolution).where(
            TicketEvolution.ticket_id == ticket_id,
            TicketEvolution.type == "relance",
        )
    ).all())
