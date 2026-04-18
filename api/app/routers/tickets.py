"""Router tickets — création, suivi, messagerie, évolutions."""
import random
import string
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Ticket, MessageTicket, TicketEvolution, Utilisateur, Batiment,
    StatutTicket, RoleUtilisateur, StatutUtilisateur,
    Notification, ConfigSite, MembreSyndic,
)
from app.schemas import (
    TicketCreate, TicketRead, TicketUpdate, MessageCreate, MessageRead,
    TicketEvolutionCreate, TicketEvolutionRead,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])

STATUT_LABELS = {
    "ouvert": "Ouvert", "en_cours": "En cours",
    "résolu": "Résolu", "annulé": "Annulé", "fermé": "Fermé",
}


def _generate_numero() -> str:
    return "TK-" + "".join(random.choices(string.digits, k=6))


def _evol_read(e: TicketEvolution, session: Session) -> TicketEvolutionRead:
    auteur = session.get(Utilisateur, e.auteur_id)
    return TicketEvolutionRead(
        id=e.id, ticket_id=e.ticket_id, type=e.type,
        contenu=e.contenu, ancien_statut=e.ancien_statut,
        nouveau_statut=e.nouveau_statut, auteur_id=e.auteur_id,
        auteur_nom=f"{auteur.prenom} {auteur.nom}" if auteur else "?",
        cree_le=e.cree_le,
    )


def _ticket_read(ticket: Ticket, session: Session) -> TicketRead:
    auteur = session.get(Utilisateur, ticket.auteur_id)
    auteur_batiment_id = ticket.batiment_id or (auteur.batiment_id if auteur else None)
    batiment = session.get(Batiment, auteur_batiment_id) if auteur_batiment_id else None
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
        destinataire_syndic=ticket.destinataire_syndic,
        destinataire_cs=ticket.destinataire_cs,
        cree_le=ticket.cree_le,
        mis_a_jour_le=ticket.mis_a_jour_le,
    )


@router.get("", response_model=list[TicketRead])
def list_tickets(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    stmt = select(Ticket)
    if not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        stmt = stmt.where(Ticket.auteur_id == user.id)
    tickets = session.exec(stmt.order_by(Ticket.cree_le.desc())).all()
    return [_ticket_read(ticket, session) for ticket in tickets]


@router.post("", response_model=TicketRead, status_code=201)
def create_ticket(
    body: TicketCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    if user.has_role(RoleUtilisateur.externe) and not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Les utilisateurs externes ne peuvent pas créer de tickets")
    import json
    ticket = Ticket(
        numero=_generate_numero(),
        titre=body.titre,
        description=body.description,
        categorie=body.categorie,
        auteur_id=user.id,
        lot_id=body.lot_id,
        batiment_id=body.batiment_id,
        perimetre_cible=json.dumps(body.perimetre_cible) if body.perimetre_cible else '["résidence"]',
        priorite="haute" if body.categorie == "urgence" else "normale",
        destinataire_syndic=body.destinataire_syndic if user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin) else False,
        destinataire_cs=body.destinataire_cs if user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin) else False,
    )
    session.add(ticket)
    session.flush()

    # Notification CS
    from sqlmodel import or_
    cs_members = session.exec(
        select(Utilisateur).where(
            Utilisateur.actif == True,
            or_(
                Utilisateur.roles_json.contains("conseil_syndical"),
                Utilisateur.roles_json.contains("admin"),
            )
        )
    ).all()
    if body.categorie == "urgence":
        syndics = session.exec(
            select(Utilisateur).where(Utilisateur.statut == StatutUtilisateur.syndic)
        ).all()
        cs_ids = {m.id for m in cs_members}
        cs_members = list(cs_members) + [s for s in syndics if s.id not in cs_ids]

    for member in cs_members:
        notif = Notification(
            destinataire_id=member.id,
            type="ticket_update",
            titre=f"Nouveau ticket : {ticket.titre}",
            corps=ticket.description[:200],
            lien=f"/tickets/{ticket.id}",
            urgente=body.categorie == "urgence",
        )
        session.add(notif)

    if body.categorie == "bug":
        cfg_rows = session.exec(
            select(ConfigSite).where(
                ConfigSite.cle.in_(("notify_ticket_bug_email", "site_email", "site_nom", "site_url", "site_manager_user_id"))
            )
        ).all()
        cfg = {row.cle: row.valeur for row in cfg_rows}
        notify_bug_email = cfg.get("notify_ticket_bug_email") == "1"
        from app.utils.email import get_site_manager_notification_email, send_email

        target_email, site_cfg = get_site_manager_notification_email(session)
        if notify_bug_email and target_email:
            background_tasks.add_task(
                send_email,
                code="ticket_bug_admin",
                to=target_email,
                context={
                    "ticket": {
                        "id": ticket.id,
                        "numero": ticket.numero,
                        "titre": ticket.titre,
                        "description": ticket.description,
                        "categorie": ticket.categorie,
                    },
                    "auteur": {
                        "prenom": user.prenom,
                        "nom": user.nom,
                        "email": user.email,
                    },
                    "residence": {
                        "nom": site_cfg.get("site_nom") or cfg.get("site_nom") or "5Hostachy",
                    },
                    "app": {
                        "url": site_cfg.get("site_url") or cfg.get("site_url") or "https://localhost",
                    },
                },
            )

    # ── Email au syndic et/ou CS (option CS/Admin) ──
    if ticket.destinataire_syndic or ticket.destinataire_cs:
        from app.utils.email import get_site_manager_notification_email, send_email
        import json as _json, os

        # Config
        cfg_site = session.exec(
            select(ConfigSite).where(
                ConfigSite.cle.in_(("reference_copro", "site_nom", "site_url"))
            )
        ).all()
        cfg_map = {r.cle: r.valeur for r in cfg_site}
        reference_copro = cfg_map.get("reference_copro", "")

        # Photos jointes
        photo_paths: list[str] = []
        if ticket.photos_urls:
            try:
                urls = _json.loads(ticket.photos_urls) if isinstance(ticket.photos_urls, str) else ticket.photos_urls
            except Exception:
                urls = []
            for url in (urls or []):
                fname = os.path.basename(url)
                fpath = os.path.join("/app/uploads", fname)
                if os.path.isfile(fpath):
                    photo_paths.append(fpath)

        ctx = {
            "ticket": {
                "id": ticket.id,
                "numero": ticket.numero,
                "titre": ticket.titre,
                "description": ticket.description,
                "categorie": ticket.categorie,
            },
            "auteur": {
                "prenom": user.prenom,
                "nom": user.nom,
            },
            "residence": {
                "nom": cfg_map.get("site_nom", "5Hostachy"),
            },
            "app": {
                "url": cfg_map.get("site_url", "https://localhost"),
            },
            "reference_copro": reference_copro,
        }

        # Construire la liste de destinataires (dédupliqués)
        destinataires: list[tuple[int | None, str]] = []
        seen_emails: set[str] = set()

        if ticket.destinataire_syndic:
            syndic_principal = session.exec(
                select(MembreSyndic).where(MembreSyndic.est_principal == True)
            ).first()
            if syndic_principal and syndic_principal.email:
                destinataires.append((syndic_principal.user_id, syndic_principal.email))
                seen_emails.add(syndic_principal.email.lower())

        if ticket.destinataire_cs:
            cs_users = session.exec(
                select(Utilisateur.id, Utilisateur.email)
                .where(
                    Utilisateur.actif == True,
                    Utilisateur.email.isnot(None),
                    Utilisateur.roles_json.contains("conseil_syndical"),
                )
            ).all()
            for uid, email in cs_users:
                if email and email.lower() not in seen_emails:
                    destinataires.append((uid, email))
                    seen_emails.add(email.lower())

        for dest_id, dest_email in destinataires:
            background_tasks.add_task(
                send_email,
                code="ticket_syndic",
                to=dest_email,
                context=ctx,
                session=session,
                destinataire_id=dest_id,
                attachments=photo_paths or None,
            )

    session.commit()
    session.refresh(ticket)
    return _ticket_read(ticket, session)


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")
    if user.role == RoleUtilisateur.résident and ticket.auteur_id != user.id:
        raise HTTPException(403, "Accès refusé")
    return _ticket_read(ticket, session)


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(
    ticket_id: int,
    body: TicketUpdate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")

    ancien_statut = ticket.statut

    if body.statut:
        ticket.statut = body.statut
        if body.statut in (StatutTicket.résolu, StatutTicket.annulé, StatutTicket.fermé):
            ticket.ferme_le = datetime.utcnow()
    if body.priorite:
        ticket.priorite = body.priorite

    ticket.mis_a_jour_le = datetime.utcnow()

    # Auto-log évolution sur changement de statut
    if body.statut and body.statut != ancien_statut:
        evol = TicketEvolution(
            ticket_id=ticket.id, type="etat",
            contenu=f"Statut : {STATUT_LABELS.get(ancien_statut or '', 'Aucun')} → {STATUT_LABELS.get(body.statut, body.statut)}",
            ancien_statut=ancien_statut, nouveau_statut=body.statut,
            auteur_id=user.id, cree_le=datetime.utcnow(),
        )
        session.add(evol)

    # Notification auteur (in-app)
    notif = Notification(
        destinataire_id=ticket.auteur_id,
        type="ticket_update",
        titre=f"Ticket #{ticket.numero} mis à jour",
        corps=f"Nouveau statut : {ticket.statut}",
        lien=f"/tickets/{ticket.id}",
    )
    session.add(notif)
    session.add(ticket)

    # Notification auteur (email) — changement de statut
    if body.statut and body.statut != ancien_statut and ticket.auteur_id != user.id:
        auteur = session.get(Utilisateur, ticket.auteur_id)
        if auteur and auteur.email:
            from app.utils.email import send_email
            cfg_rows = session.exec(
                select(ConfigSite).where(ConfigSite.cle.in_(("site_nom", "site_url")))
            ).all()
            cfg_map = {r.cle: r.valeur for r in cfg_rows}
            background_tasks.add_task(
                send_email,
                code="ticket_statut_change",
                to=auteur.email,
                context={
                    "ticket": {
                        "id": ticket.id,
                        "numero": ticket.numero,
                        "titre": ticket.titre,
                        "statut": STATUT_LABELS.get(body.statut, body.statut),
                        "ancien_statut": STATUT_LABELS.get(ancien_statut or "", "Aucun"),
                    },
                    "auteur_action": {"prenom": user.prenom, "nom": user.nom},
                    "residence": {"nom": cfg_map.get("site_nom", "5Hostachy")},
                    "app": {"url": cfg_map.get("site_url", "https://localhost")},
                },
                destinataire_id=ticket.auteur_id,
            )

    session.commit()
    session.refresh(ticket)
    return _ticket_read(ticket, session)


@router.get("/{ticket_id}/messages", response_model=list[MessageRead])
def get_messages(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")
    stmt = select(MessageTicket).where(MessageTicket.ticket_id == ticket_id)
    if user.role == RoleUtilisateur.résident:
        stmt = stmt.where(MessageTicket.interne == False)
    return session.exec(stmt.order_by(MessageTicket.cree_le)).all()


@router.post("/{ticket_id}/messages", response_model=MessageRead, status_code=201)
def add_message(
    ticket_id: int,
    body: MessageCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")
    if body.interne and user.role == RoleUtilisateur.résident:
        raise HTTPException(403, "Messages internes réservés au CS")

    msg = MessageTicket(
        ticket_id=ticket_id,
        auteur_id=user.id,
        contenu=body.contenu,
        interne=body.interne,
    )
    # Auto-log évolution "réponse"
    evol = TicketEvolution(
        ticket_id=ticket_id, type="reponse",
        contenu="Message interne" if body.interne else None,
        auteur_id=user.id, cree_le=datetime.utcnow(),
    )
    session.add(evol)
    ticket.mis_a_jour_le = datetime.utcnow()
    session.add(msg)
    session.add(ticket)

    # Notification email — nouveau message sur le ticket
    if not body.interne:
        from sqlmodel import or_
        from app.utils.email import send_email
        cfg_rows = session.exec(
            select(ConfigSite).where(ConfigSite.cle.in_(("site_nom", "site_url")))
        ).all()
        cfg_map = {r.cle: r.valeur for r in cfg_rows}
        ctx = {
            "ticket": {
                "id": ticket.id,
                "numero": ticket.numero,
                "titre": ticket.titre,
            },
            "message": {"contenu": body.contenu[:300]},
            "auteur_action": {"prenom": user.prenom, "nom": user.nom},
            "residence": {"nom": cfg_map.get("site_nom", "5Hostachy")},
            "app": {"url": cfg_map.get("site_url", "https://localhost")},
        }
        is_cs = user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)
        if is_cs:
            # CS/Admin répond → notifier l'auteur du ticket
            if ticket.auteur_id != user.id:
                auteur = session.get(Utilisateur, ticket.auteur_id)
                if auteur and auteur.email:
                    background_tasks.add_task(
                        send_email, code="ticket_nouveau_message",
                        to=auteur.email, context=ctx,
                        destinataire_id=ticket.auteur_id,
                    )
                    session.add(Notification(
                        destinataire_id=ticket.auteur_id,
                        type="ticket_update",
                        titre=f"Nouvelle réponse sur le ticket #{ticket.numero}",
                        corps=body.contenu[:200],
                        lien=f"/tickets/{ticket.id}",
                    ))
        else:
            # Résident répond → notifier les CS/Admin
            cs_members = session.exec(
                select(Utilisateur).where(
                    Utilisateur.actif == True,
                    Utilisateur.email.isnot(None),
                    or_(
                        Utilisateur.roles_json.contains("conseil_syndical"),
                        Utilisateur.roles_json.contains("admin"),
                    ),
                )
            ).all()
            for member in cs_members:
                if member.id != user.id:
                    background_tasks.add_task(
                        send_email, code="ticket_nouveau_message",
                        to=member.email, context=ctx,
                        destinataire_id=member.id,
                    )
                    session.add(Notification(
                        destinataire_id=member.id,
                        type="ticket_update",
                        titre=f"Nouveau message sur le ticket #{ticket.numero}",
                        corps=body.contenu[:200],
                        lien=f"/tickets/{ticket.id}",
                    ))

    session.commit()
    session.refresh(msg)
    return msg


# ── Évolutions (fil de suivi) ─────────────────────────────────────────────

@router.get("/{ticket_id}/evolutions", response_model=list[TicketEvolutionRead])
def get_evolutions(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")
    if not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin) and ticket.auteur_id != user.id:
        raise HTTPException(403, "Accès refusé")
    evols = session.exec(
        select(TicketEvolution).where(TicketEvolution.ticket_id == ticket_id)
        .order_by(TicketEvolution.cree_le)
    ).all()
    return [_evol_read(e, session) for e in evols]


@router.post("/{ticket_id}/evolutions", response_model=TicketEvolutionRead, status_code=201)
def add_evolution(
    ticket_id: int,
    body: TicketEvolutionCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")
    if body.type not in ("commentaire", "etat"):
        raise HTTPException(422, "Type invalide (commentaire ou etat)")
    if body.type == "etat" and not body.nouveau_statut:
        raise HTTPException(422, "nouveau_statut requis pour un changement d'état")
    if body.type == "etat" and body.nouveau_statut not in ("ouvert", "en_cours", "résolu", "fermé"):
        raise HTTPException(422, "statut invalide")

    ancien_statut = ticket.statut if body.type == "etat" else None
    evol = TicketEvolution(
        ticket_id=ticket_id, type=body.type,
        contenu=body.contenu,
        ancien_statut=ancien_statut,
        nouveau_statut=body.nouveau_statut if body.type == "etat" else None,
        auteur_id=user.id, cree_le=datetime.utcnow(),
    )
    session.add(evol)

    if body.type == "etat":
        ticket.statut = body.nouveau_statut
        if body.nouveau_statut in ("résolu", "fermé"):
            ticket.ferme_le = datetime.utcnow()
        ticket.mis_a_jour_le = datetime.utcnow()
        session.add(ticket)

    # Notification auteur du ticket (email + in-app)
    if ticket.auteur_id != user.id:
        from app.utils.email import send_email
        cfg_rows = session.exec(
            select(ConfigSite).where(ConfigSite.cle.in_(("site_nom", "site_url")))
        ).all()
        cfg_map = {r.cle: r.valeur for r in cfg_rows}
        if body.type == "etat":
            auteur = session.get(Utilisateur, ticket.auteur_id)
            if auteur and auteur.email:
                background_tasks.add_task(
                    send_email, code="ticket_statut_change",
                    to=auteur.email,
                    context={
                        "ticket": {
                            "id": ticket.id, "numero": ticket.numero,
                            "titre": ticket.titre,
                            "statut": STATUT_LABELS.get(body.nouveau_statut, body.nouveau_statut),
                            "ancien_statut": STATUT_LABELS.get(ancien_statut or "", "Aucun"),
                        },
                        "auteur_action": {"prenom": user.prenom, "nom": user.nom},
                        "residence": {"nom": cfg_map.get("site_nom", "5Hostachy")},
                        "app": {"url": cfg_map.get("site_url", "https://localhost")},
                    },
                    destinataire_id=ticket.auteur_id,
                )
        elif body.type == "commentaire" and body.contenu:
            auteur = session.get(Utilisateur, ticket.auteur_id)
            if auteur and auteur.email:
                background_tasks.add_task(
                    send_email, code="ticket_nouveau_message",
                    to=auteur.email,
                    context={
                        "ticket": {
                            "id": ticket.id, "numero": ticket.numero,
                            "titre": ticket.titre,
                        },
                        "message": {"contenu": body.contenu[:300]},
                        "auteur_action": {"prenom": user.prenom, "nom": user.nom},
                        "residence": {"nom": cfg_map.get("site_nom", "5Hostachy")},
                        "app": {"url": cfg_map.get("site_url", "https://localhost")},
                    },
                    destinataire_id=ticket.auteur_id,
                )
        # Notification in-app
        titre_notif = (
            f"Ticket #{ticket.numero} — statut : {STATUT_LABELS.get(body.nouveau_statut, body.nouveau_statut)}"
            if body.type == "etat"
            else f"Nouveau commentaire sur le ticket #{ticket.numero}"
        )
        session.add(Notification(
            destinataire_id=ticket.auteur_id,
            type="ticket_update",
            titre=titre_notif,
            corps=(body.contenu or "")[:200],
            lien=f"/tickets/{ticket.id}",
        ))

    session.commit()
    session.refresh(evol)
    return _evol_read(evol, session)


# ── Suppression (admin uniquement) ────────────────────────────────────────

@router.delete("/{ticket_id}", status_code=204)
def delete_ticket(
    ticket_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")
    for evol in list(ticket.evolutions):
        session.delete(evol)
    for msg in list(ticket.messages):
        session.delete(msg)
    session.delete(ticket)
    session.commit()
