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
from typing import Optional

from sqlmodel import Session, select

from app.models.core import (
    Batiment,
    ConfigSite,
    MembreSyndic,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.schemas import TicketEvolutionRead, TicketRead

STATUT_LABELS = {
    "ouvert": "Ouvert", "en_cours": "En cours",
    "résolu": "Résolu", "annulé": "Annulé", "fermé": "Fermé",
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

def destinataires_syndic_cs(
    session: Session,
    *,
    syndic: bool,
    cs: bool,
    deja_vus: Optional[set[str]] = None,
) -> list[tuple[int | None, str]]:
    """(user_id, e-mail) du syndic principal puis des membres du CS, dédoublonnés.

    Le syndic passe en premier et gagne le doublon : c'est lui le destinataire
    principal d'un e-mail de ticket, un membre du CS qui serait aussi le syndic
    ne doit pas le recevoir deux fois.

    `deja_vus` permet à la relance syndic d'exclure du CC les adresses déjà
    placées en destinataire principal, sans réécrire la déduplication.

    ⚠️ Cette fonction décide **qui reçoit un e-mail de ticket**. Elle est le seul
    endroit où cette règle s'écrit — la disperser à nouveau, c'est réintroduire
    l'angle mort d'une rubrique oubliée (`standards/02-factorisation.md` §2).
    """
    destinataires: list[tuple[int | None, str]] = []
    vus: set[str] = set(deja_vus or ())

    if syndic:
        principal = session.exec(
            select(MembreSyndic).where(MembreSyndic.est_principal == True)  # noqa: E712
        ).first()
        if principal and principal.email:
            destinataires.append((principal.user_id, principal.email))
            vus.add(principal.email.lower())

    if cs:
        membres = session.exec(
            select(Utilisateur.id, Utilisateur.email).where(
                Utilisateur.actif == True,  # noqa: E712
                Utilisateur.email.isnot(None),
                Utilisateur.roles_json.contains("conseil_syndical"),
            )
        ).all()
        for uid, email in membres:
            if email and email.lower() not in vus:
                destinataires.append((uid, email))
                vus.add(email.lower())

    return destinataires


def syndic_principal(session: Session) -> Optional[MembreSyndic]:
    """Le gestionnaire syndic principal, ou None s'il n'est pas configuré."""
    return session.exec(
        select(MembreSyndic).where(MembreSyndic.est_principal == True)  # noqa: E712
    ).first()


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
    )


def ticket_read(ticket: Ticket, session: Session) -> TicketRead:
    auteur = session.get(Utilisateur, ticket.auteur_id)
    auteur_batiment_id = ticket.batiment_id or (auteur.batiment_id if auteur else None)
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
