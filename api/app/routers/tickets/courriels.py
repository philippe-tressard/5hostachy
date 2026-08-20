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

    ctx = contexte_ticket_syndic(
        ticket, user, session,
        pieces_jointes=pieces_jointes, commentaire=commentaire, evolutions=evolutions,
    )

    background_tasks.add_task(
        send_email_group,
        code="ticket_syndic",
        to_recipients=destinataires,
        context=ctx,
        session=session,
        attachments=pieces_jointes or None,
    )


def contexte_ticket_syndic(
    ticket,
    user: Utilisateur,
    session: Session,
    *,
    pieces_jointes: list[str],
    commentaire: Optional[str] = None,
    evolutions: Optional[list[TicketEvolution]] = None,
) -> dict:
    """Le contexte du modèle `ticket_syndic` — **écrit une seule fois**.

    ## Pourquoi il est sorti de l'envoi (#498, 19/08/2026)

    L'aperçu avant diffusion doit montrer **ce qui partira**, pas une
    reconstitution : un contexte rebâti de son côté deviendrait faux à la
    première évolution du gabarit, et personne ne s'en apercevrait — puisque
    c'est justement l'aperçu qu'on regarderait pour le vérifier
    (`standards/04` §14).

    L'envoi et l'aperçu appellent donc cette fonction, et
    `api/tests/test_apercu_diffusion.py` échoue si l'un des deux s'en écarte.

    ⚠️ Elle accepte un ticket **non persisté** — c'est tout l'intérêt : l'aperçu
    est demandé avant que l'objet existe. Les champs attribués à la création
    (`id`, `numero`) valent alors `None`, et c'est à l'écran de le dire plutôt
    que d'inventer un numéro.
    """
    cfg = config_site(session)

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
        "is_commentaire": bool(commentaire and commentaire.strip()),
        "commentaire": commentaire or "",
        "date_commentaire": fmt_paris(datetime.utcnow()),
        "date_creation": date_courte(ticket.cree_le),
        #  🔴 Du PLUS RÉCENT au plus ancien (#529, signalé à l'écran : « le
        #  dernier message n'est pas inclus en premier »).
        #
        #  L'historique est construit en ordre chronologique — c'est le bon ordre
        #  pour une frise. Mais le bloc « messages » d'un e-mail se lit comme un
        #  fil de discussion : on veut d'abord ce à quoi on répond, pas l'échange
        #  d'il y a trois semaines. Le destinataire de ce mail est le SYNDIC, qui
        #  reçoit une reprise de sa propre réponse : la remonter en tête est
        #  exactement ce qu'il cherche.
        #
        #  ⚠️ `historique` garde l'ordre chronologique : c'est une frise, et une
        #  frise à l'envers ne se lit pas. Deux blocs, deux ordres, deux raisons.
        "messages": list(reversed(messages_ctx)),
        "historique": historique,
        "fichiers": bool(pieces_jointes),
    }
    return ctx


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
