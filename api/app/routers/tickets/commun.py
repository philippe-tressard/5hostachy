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

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.core import (
    Batiment,
    ConfigSite,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.schemas import TicketEvolutionRead, TicketRead
from app.utils.archivage import est_archivable, seuil_archivage_jours
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
from app.utils.noms import nom_affiche


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
        auteur_nom=nom_affiche(auteur.prenom, auteur.nom) if auteur else "?",
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
            saisi_pour_affichage = nom_affiche(sp_user.prenom, sp_user.nom)
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
        auteur_nom=nom_affiche(auteur.prenom, auteur.nom) if auteur else None,
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
        #  ⚠️ `seuil_archivage_jours` interroge la configuration, et l'on est ici
        #  dans une fonction appelée PAR TICKET : c'est un appel par ticket, et
        #  c'est assumé — la liste en compte quelques dizaines. Le factoriser
        #  demanderait de passer le seuil à tous les appelants de `ticket_read`,
        #  dont plusieurs n'en rendent qu'un. À revoir si la liste grossit, et à
        #  mesurer avant d'optimiser.
        archivee=est_archivable("ticket", ticket, seuil_jours=seuil_archivage_jours(session)),
        #  ⚠️ REMPLI, et pas seulement déclaré. C'est le défaut SYMÉTRIQUE de
        #  celui du 02/09 : un champ passé sans être au schéma est ignoré par
        #  Pydantic ; un champ au schéma et jamais rempli prend sa valeur par
        #  défaut — ici `False`, donc « aucun ticket n'est confidentiel ».
        #  `test_schemas_champs` ne voit que le premier, et il le dit.
        confidentiel=ticket.confidentiel,
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


def trier_par_activite(session: Session, tickets: list[Ticket]) -> list[Ticket]:
    """Les tickets, du plus RÉCEMMENT ACTIF au plus ancien.

    🔴 LE TRI SUIT L'ACTIVITÉ, PAS LA DATE DE DÉPÔT (05/09/2026), demandé à
    l'écran : *« s'il y a eu un commentaire sur un ticket, celui-ci remonte
    dans la liste — tri sur mise à jour, sauf édition pour une correction »*.

    Un dossier qui bouge doit se voir. Trié sur `cree_le`, un ticket ouvert il
    y a trois mois et commenté ce matin restait en bas, là où personne ne le
    relit.

    ⚠️ ET SURTOUT PAS SUR `mis_a_jour_le` : cette colonne bouge à CHAQUE
    écriture, y compris une correction de faute de frappe. Corriger un titre
    ferait remonter le ticket en tête sans qu'il se soit rien passé — c'est
    exactement ce que l'utilisateur exclut, et c'est la même distinction que
    l'archivage, qui se mesure sur `statut_change_le` et non sur
    `mis_a_jour_le` (`ux-patterns` §16).

    La date d'activité est donc celle de la dernière ENTRÉE du fil : un
    commentaire, un changement d'état, un message, une relance en créent une ;
    une correction pure n'en crée aucune (voir le `PATCH` de `crud.py`, qui
    n'écrit une entrée que si l'état a changé). Éditer une entrée existante ne
    touche pas son `cree_le` : le fil ne se réordonne pas quand on se relit.

    UNE seule requête groupée, pas une par ticket : la liste charge déjà tous
    les tickets, elle ne doit pas charger tous les fils.
    """
    derniere_activite = dict(
        session.exec(
            select(TicketEvolution.ticket_id, func.max(TicketEvolution.cree_le))
            .group_by(TicketEvolution.ticket_id)
        ).all()
    )
    #  📌 LES ÉPINGLÉS D'ABORD (05/09/2026) — c'est le sens même de l'option :
    #  « maintenue en tête ». Un booléen en première clé de tri, l'activité
    #  ensuite : entre deux tickets épinglés, le plus actif reste devant.
    return sorted(
        tickets,
        key=lambda t: (bool(t.epingle), derniere_activite.get(t.id) or t.cree_le),
        reverse=True,
    )


#: Les options de publication d'un ticket, et la colonne que chacune pilote.
#:
#: 🔴 **Une écriture, trois chemins.** La création, la correction (`PATCH`) et le
#: commentaire portent tous les trois ces options depuis le 05/09/2026, demandé à
#: l'écran :
#:
#: > « tous les autres options de publication doivent être aussi conservé dans
#: >   l'objet pour les tickets en édition et commentaire »
#:
#: Écrite trois fois, la règle aurait divergé au premier ajout — c'est ce qui
#: était arrivé aux destinataires (quatre copies, cf. l'en-tête de ce module).
#:
#: ⚠️ **Les clés ne sont pas les colonnes**, et c'est voulu :
#:
#: | Option (écran) | Ce qu'elle écrit |
#: |---|---|
#: | `epingle` | `ticket.epingle` |
#: | `urgente` | `ticket.priorite` — `haute` / `normale`, ce que fait déjà la catégorie « Urgence » |
#: | `confidentiel` | `ticket.confidentiel` (🛡️ « au seul conseil syndical ») |
#:
#: Il n'y a pas de quatrième ligne pour 🔒 « visible du seul périmètre » : un
#: ticket l'est DÉJÀ (`ticket_visible` n'ouvre pas à la copropriété, #339).
OPTIONS_TICKET = ("epingle", "urgente", "confidentiel")

#: Les options qui appartiennent au CONSEIL, pas à l'auteur.
#:
#: `confidentiel` décide qui a le droit de lire — un auteur corrige son texte, il
#: ne décide pas de son audience (#710). Épingler et marquer urgent ordonnent la
#: liste du conseil : même nature.
OPTIONS_RESERVEES_AU_CS = ("epingle", "urgente", "confidentiel")


def appliquer_options(ticket: Ticket, body, *, est_cs: bool) -> list[str]:
    """Pose sur le ticket les options que `body` déclare. Rend celles qui ont changé.

    `None` veut dire « ce corps ne dit rien de cette option » : le ticket garde
    la sienne. C'est la même convention que `perimetre_cible`, et c'est elle qui
    permet au même code de servir un `POST` complet et un commentaire qui ne
    touche qu'une case.

    ⚠️ **Le contrôle de droit est ICI**, pas dans les trois appelants : une règle
    d'autorisation recopiée ne se durcit pas, on en corrige deux sur trois
    (`standards/03-securite.md` §1). Un non-CS qui envoie ces champs les voit
    simplement ignorés — l'écran ne les lui propose pas.
    """
    changees: list[str] = []
    for option in OPTIONS_TICKET:
        valeur = getattr(body, option, None)
        if valeur is None:
            continue
        if option in OPTIONS_RESERVEES_AU_CS and not est_cs:
            continue
        if option == "urgente":
            #  Pas de colonne `urgente` : l'urgence d'un ticket EST sa priorité.
            nouvelle = "haute" if valeur else "normale"
            if str(ticket.priorite) != nouvelle:
                ticket.priorite = nouvelle
                changees.append(option)
            continue
        if getattr(ticket, option) != valeur:
            setattr(ticket, option, valeur)
            changees.append(option)
    return changees


def options_du_ticket(ticket: Ticket) -> dict[str, bool]:
    """L'état courant des options — ce que l'écran doit REPRENDRE à l'ouverture.

    Le pendant en lecture d'`appliquer_options` : les deux sens de la même table,
    au même endroit, pour qu'aucun ne puisse oublier une option que l'autre écrit.
    """
    return {
        "epingle": bool(ticket.epingle),
        "urgente": str(ticket.priorite) == "haute",
        "confidentiel": bool(ticket.confidentiel),
    }
