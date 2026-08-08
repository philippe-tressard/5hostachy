"""Tickets — les e-mails que produit un ticket.

Extrait de `tickets.py` le 08/08/2026. Voir `__init__.py` pour la règle de
découpage.

Rassemble ce qui **compose et envoie** un message, pour que les routes ne
portent plus que la décision de l'envoyer. C'est aussi ce qui a permis de
supprimer le troisième exemplaire de la liste des destinataires : les deux
appelants (création d'un ticket, ajout d'une évolution) construisaient le même
e-mail `ticket_syndic` avec deux blocs de code distincts.
"""
from datetime import datetime
from typing import Optional

from fastapi import BackgroundTasks
from sqlmodel import Session, select

from app.models.core import MessageTicket, TicketEvolution, Utilisateur
from app.utils.dates_fr import date_courte, datetime_longue_paris as fmt_paris
from app.utils.fichiers import chemins_locaux

from .commun import (
    config_site,
    contexte_site,
    destinataires_syndic_cs,
    libelle_evolution,
)


def _contexte_ticket(ticket) -> dict:
    """Le bloc `ticket` attendu par tous les modèles — une seule description."""
    return {
        "id": ticket.id,
        "numero": ticket.numero,
        "titre": ticket.titre,
        "description": ticket.description or "",
        "categorie": ticket.categorie or "",
    }


def envoyer_email_syndic_cs(
    ticket,
    user: Utilisateur,
    background_tasks: BackgroundTasks,
    session: Session,
    *,
    syndic: bool,
    cs: bool,
    pieces_jointes: list[str],
    commentaire: Optional[str] = None,
    evolutions: Optional[list[TicketEvolution]] = None,
):
    """E-mail `ticket_syndic`, à la création comme à l'ajout d'une évolution.

    Les deux appelants écrivaient ce bloc séparément. La conséquence était déjà
    visible : la clé `fichiers`, que le modèle interroge derrière un `{% if %}`,
    n'était fournie que d'un côté — Jinja évalue un indéfini à faux sans rien
    signaler, et les photos partaient en pièce jointe sans être annoncées.
    Elle est calculée ici sur ce qui est **réellement attaché**, pas sur
    l'intention.
    """
    destinataires = destinataires_syndic_cs(session, syndic=syndic, cs=cs)
    if not destinataires:
        return

    from app.utils.email import send_email_group

    cfg = config_site(session, "reference_copro")

    messages_ctx = []
    historique = [{"date": date_courte(ticket.cree_le), "label": "Création du ticket"}]
    for ev in evolutions or []:
        historique.append({"date": fmt_paris(ev.cree_le), "label": libelle_evolution(ev, avec_extrait=True)})
        if ev.contenu:
            auteur_e = session.get(Utilisateur, ev.auteur_id)
            messages_ctx.append({
                "auteur_nom": f"{auteur_e.prenom} {auteur_e.nom}" if auteur_e else "?",
                "date": fmt_paris(ev.cree_le),
                "contenu": ev.contenu,
            })

    ctx = {
        "ticket": _contexte_ticket(ticket),
        "auteur": {"prenom": user.prenom, "nom": user.nom},
        **contexte_site(cfg),
        "reference_copro": cfg.get("reference_copro", ""),
        "is_commentaire": bool(commentaire and commentaire.strip()),
        "commentaire": commentaire or "",
        "date_commentaire": fmt_paris(datetime.utcnow()),
        "date_creation": date_courte(ticket.cree_le),
        "messages": messages_ctx,
        "historique": historique,
        "fichiers": bool(pieces_jointes),
    }

    background_tasks.add_task(
        send_email_group,
        code="ticket_syndic",
        to_recipients=destinataires,
        context=ctx,
        session=session,
        attachments=pieces_jointes or None,
    )


def envoyer_email_externe(
    ticket,
    user: Utilisateur,
    email_externe: str,
    background_tasks: BackgroundTasks,
    session: Session,
    *,
    is_commentaire: bool = True,
    nouveau_message: Optional[str] = None,
    fichiers_urls: Optional[list[str]] = None,
):
    """Envoie un e-mail vers une adresse externe avec l'historique du ticket."""
    from app.utils.email import send_email

    cfg = config_site(session)

    # Messages publics du ticket (historique)
    messages = session.exec(
        select(MessageTicket)
        .where(MessageTicket.ticket_id == ticket.id, MessageTicket.interne == False)  # noqa: E712
        .order_by(MessageTicket.cree_le)
    ).all()
    # Exclure le dernier si c'est le message courant
    msgs_for_history = messages[:-1] if (is_commentaire and messages) else messages
    msgs_ctx = []
    for m in msgs_for_history:
        auteur_m = session.get(Utilisateur, m.auteur_id)
        msgs_ctx.append({
            "auteur_nom": f"{auteur_m.prenom} {auteur_m.nom}" if auteur_m else "?",
            "date": fmt_paris(m.cree_le),
            "contenu": m.contenu,
        })

    attachments = chemins_locaux(fichiers_urls or [])

    ctx = {
        "ticket": _contexte_ticket(ticket),
        "auteur": {"prenom": user.prenom, "nom": user.nom},
        "date_ticket": fmt_paris(ticket.cree_le),
        "date_commentaire": fmt_paris(datetime.utcnow()),
        **contexte_site(cfg),
        "app": {"url": (cfg.get("site_url") or "https://localhost").rstrip("/")},
        "is_commentaire": is_commentaire,
        "commentaire": nouveau_message or "",
        "messages": msgs_ctx,
        "fichiers": bool(attachments),
    }

    background_tasks.add_task(
        send_email,
        code="ticket_externe",
        to=email_externe,
        context=ctx,
        attachments=attachments or None,
    )
