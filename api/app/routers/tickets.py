"""Router tickets — création, suivi, messagerie, évolutions."""
import json
import os
import random
import string
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Ticket, MessageTicket, TicketEvolution, Utilisateur, Batiment,
    StatutTicket, RoleUtilisateur, StatutUtilisateur,
    Notification, ConfigSite, MembreSyndic, GenreCivilite,
)
from app.schemas import (
    TicketCreate, TicketRead, TicketUpdate, MessageCreate, MessageRead,
    TicketEvolutionCreate, TicketEvolutionRead, TicketEvolutionUpdate,
)
from app.utils.visibility import ticket_visible

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
        fichiers_urls=json.loads(e.fichiers_urls) if e.fichiers_urls else [],
    )


def _resolve_fichiers_attachments(fichiers_urls: list[str]) -> list[str]:
    """Convertit des URLs /uploads/... en chemins locaux /app/uploads/..."""
    paths = []
    for url in fichiers_urls:
        path = "/app" + url if url.startswith("/uploads/") else url
        if os.path.isfile(path):
            paths.append(path)
    return paths


def _fmt_paris(dt: datetime) -> str:
    return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Paris")).strftime("%-d %B %Y à %H:%M")


def _envoyer_email_externe_ticket(
    ticket,
    user: Utilisateur,
    email_externe: str,
    background_tasks: BackgroundTasks,
    session: Session,
    *,
    is_commentaire: bool = True,
    nouveau_message: str | None = None,
    fichiers_urls: list[str] | None = None,
):
    """Envoie un email vers une adresse externe avec l'historique du ticket."""
    from app.utils.email import send_email

    cfg_rows = session.exec(
        select(ConfigSite).where(ConfigSite.cle.in_(("site_nom", "site_url")))
    ).all()
    cfg = {r.cle: r.valeur for r in cfg_rows}

    # Messages publics du ticket (historique)
    messages = session.exec(
        select(MessageTicket)
        .where(MessageTicket.ticket_id == ticket.id, MessageTicket.interne == False)
        .order_by(MessageTicket.cree_le)
    ).all()
    # Exclure le dernier si c'est le message courant
    msgs_for_history = messages[:-1] if (is_commentaire and messages) else messages
    msgs_ctx = []
    for m in msgs_for_history:
        auteur_m = session.get(Utilisateur, m.auteur_id)
        msgs_ctx.append({
            "auteur_nom": f"{auteur_m.prenom} {auteur_m.nom}" if auteur_m else "?",
            "date": _fmt_paris(m.cree_le),
            "contenu": m.contenu,
        })

    attachments = _resolve_fichiers_attachments(fichiers_urls or [])

    ctx = {
        "ticket": {
            "id": ticket.id,
            "numero": ticket.numero,
            "titre": ticket.titre,
            "description": ticket.description or "",
            "categorie": ticket.categorie or "",
        },
        "auteur": {"prenom": user.prenom, "nom": user.nom},
        "date_ticket": _fmt_paris(ticket.cree_le),
        "date_commentaire": _fmt_paris(datetime.utcnow()),
        "residence": {"nom": cfg.get("site_nom", "5Hostachy")},
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


def _ticket_read(ticket: Ticket, session: Session) -> TicketRead:
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
        relance_count=len(session.exec(
            select(TicketEvolution).where(
                TicketEvolution.ticket_id == ticket.id,
                TicketEvolution.type == "relance",
            )
        ).all()),
    )


@router.get("", response_model=list[TicketRead])
def list_tickets(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    from sqlmodel import or_
    stmt = select(Ticket)
    if not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        stmt = stmt.where(
            or_(Ticket.auteur_id == user.id, Ticket.saisi_pour_user_id == user.id)
        )
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
        saisi_pour_user_id=body.saisi_pour_user_id if user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin) else None,
        saisi_pour_nom=body.saisi_pour_nom if user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin) else None,
        saisi_pour_email=body.saisi_pour_email if user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin) else None,
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
        from app.utils.email import send_email_group
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
                # url = "/uploads/tickets/abc.jpg" → "/app/uploads/tickets/abc.jpg"
                fpath = os.path.join("/app", url.lstrip("/"))
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

        if destinataires:
            background_tasks.add_task(
                send_email_group,
                code="ticket_syndic",
                to_recipients=destinataires,
                context=ctx,
                session=session,
                attachments=photo_paths or None,
            )

    session.commit()
    session.refresh(ticket)

    # Email externe si adresse fournie (CS/Admin uniquement)
    email_ext = body.email_externe
    if email_ext and email_ext.strip() and user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        _envoyer_email_externe_ticket(
            ticket, user, email_ext.strip(), background_tasks, session,
            is_commentaire=False,
        )

    return _ticket_read(ticket, session)


# ── Relance syndic ────────────────────────────────────────────────────────

from pydantic import BaseModel as _BaseModel


class RelanceSyndicRequest(_BaseModel):
    ticket_ids: list[int]


class RelanceSyndicResponse(_BaseModel):
    delai_jours: int
    tickets: list[TicketRead]


@router.get("/relance-syndic", response_model=RelanceSyndicResponse)
def list_relance_syndic(
    session: Session = Depends(get_session),
    _user: Utilisateur = Depends(require_cs_or_admin),
):
    """Retourne tous les tickets adressés au syndic, non résolus/annulés/fermés
    et non tagués non_relancable, avec le délai de relance configuré.
    Le frontend distingue les tickets éligibles (passé le délai) des candidats
    (pas encore au délai)."""
    cfg_delai = session.exec(
        select(ConfigSite).where(ConfigSite.cle == "relance_syndic_delai_jours")
    ).first()
    delai_jours = int(cfg_delai.valeur) if cfg_delai else 30

    tickets = session.exec(
        select(Ticket).where(
            Ticket.destinataire_syndic == True,
            Ticket.statut.notin_(["résolu", "annulé", "fermé"]),
            Ticket.non_relancable == False,
        ).order_by(Ticket.mis_a_jour_le)
    ).all()

    return RelanceSyndicResponse(
        delai_jours=delai_jours,
        tickets=[_ticket_read(t, session) for t in tickets],
    )


@router.post("/relance-syndic", status_code=200)
def envoyer_relance_syndic(
    body: RelanceSyndicRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Envoie un mail de relance groupé au syndic (est_principal=True) en CC
    des membres CS, et logue une évolution 'relance' sur chaque ticket."""
    from app.utils.email import send_email_group

    if not body.ticket_ids:
        raise HTTPException(422, "Aucun ticket sélectionné")

    tickets_relance: list[Ticket] = []
    for tid in body.ticket_ids:
        t = session.get(Ticket, tid)
        if not t:
            raise HTTPException(404, f"Ticket {tid} introuvable")
        if not t.destinataire_syndic:
            raise HTTPException(422, f"Ticket {tid} non adressé au syndic")
        tickets_relance.append(t)

    cfg_rows = session.exec(
        select(ConfigSite).where(
            ConfigSite.cle.in_(("site_nom", "site_url", "reference_copro"))
        )
    ).all()
    cfg_map = {r.cle: r.valeur for r in cfg_rows}
    now = datetime.utcnow()

    for ticket in tickets_relance:
        relance_count = len(session.exec(
            select(TicketEvolution).where(
                TicketEvolution.ticket_id == ticket.id,
                TicketEvolution.type == "relance",
            )
        ).all())
        evol = TicketEvolution(
            ticket_id=ticket.id,
            type="relance",
            contenu=f"Relance syndic n°{relance_count + 1}",
            auteur_id=user.id,
            cree_le=now,
        )
        session.add(evol)
        ticket.mis_a_jour_le = now
        session.add(ticket)

    session.flush()

    syndic_principal = session.exec(
        select(MembreSyndic).where(MembreSyndic.est_principal == True)
    ).first()

    if not syndic_principal or not syndic_principal.email:
        raise HTTPException(422, "Aucun gestionnaire syndic principal avec email configuré")

    civilite = "Monsieur" if syndic_principal.genre == GenreCivilite.monsieur else "Madame"
    nom_gestionnaire = f"{syndic_principal.prenom} {syndic_principal.nom}".strip()

    PERIM_LABELS: dict[str, str] = {
        "résidence": "Copropriété entière",
        "parking": "Parking",
        "cave": "Cave",
    }

    def _perim_label(perim_json: str | None) -> str:
        if not perim_json:
            return ""
        import json as _json
        try:
            items = _json.loads(perim_json)
        except Exception:
            return perim_json
        labels = []
        for i in items:
            if i.startswith("bat:"):
                labels.append(f"Bât. {i[4:]}")
            else:
                labels.append(PERIM_LABELS.get(i, i))
        return " · ".join(labels)

    def _evol_label(e: TicketEvolution) -> str:
        if e.type == "etat":
            return (
                f"Changement d'état : "
                f"{STATUT_LABELS.get(e.ancien_statut or '', e.ancien_statut or '?')} → "
                f"{STATUT_LABELS.get(e.nouveau_statut or '', e.nouveau_statut or '?')}"
            )
        if e.type == "relance":
            return e.contenu or "Relance syndic"
        if e.type == "commentaire":
            return "Commentaire CS"
        if e.type == "reponse":
            return "Réponse"
        return e.type

    tickets_ctx = []
    for ticket in tickets_relance:
        relance_count = len(session.exec(
            select(TicketEvolution).where(
                TicketEvolution.ticket_id == ticket.id,
                TicketEvolution.type == "relance",
            )
        ).all()) - 1
        evols = session.exec(
            select(TicketEvolution).where(
                TicketEvolution.ticket_id == ticket.id
            ).order_by(TicketEvolution.cree_le)
        ).all()
        historique = [{"date": e.cree_le.strftime("%d/%m/%Y"), "label": _evol_label(e)} for e in evols]
        historique.insert(0, {
            "date": ticket.cree_le.strftime("%d/%m/%Y"),
            "label": f"Création du ticket (statut : {STATUT_LABELS.get(ticket.statut, ticket.statut)})",
        })
        tickets_ctx.append({
            "numero": ticket.numero,
            "titre": ticket.titre,
            "categorie": ticket.categorie,
            "priorite": ticket.priorite,
            "perimetre": _perim_label(ticket.perimetre_cible),
            "description": ticket.description,
            "relance_count": relance_count,
            "historique": historique,
        })

    ctx = {
        "civilite": civilite,
        "nom_gestionnaire": nom_gestionnaire,
        "residence": {"nom": cfg_map.get("site_nom", "5Hostachy")},
        "reference_copro": cfg_map.get("reference_copro", ""),
        "tickets": tickets_ctx,
    }

    to_recipients: list[tuple[int | None, str]] = [
        (syndic_principal.user_id, syndic_principal.email)
    ]
    seen_emails: set[str] = {syndic_principal.email.lower()}

    cc_recipients: list[tuple[int | None, str]] = []
    cs_users = session.exec(
        select(Utilisateur.id, Utilisateur.email).where(
            Utilisateur.actif == True,
            Utilisateur.email.isnot(None),
            Utilisateur.roles_json.contains("conseil_syndical"),
        )
    ).all()
    for uid, email in cs_users:
        if email and email.lower() not in seen_emails:
            cc_recipients.append((uid, email))
            seen_emails.add(email.lower())

    background_tasks.add_task(
        send_email_group,
        code="relance_syndic",
        to_recipients=to_recipients,
        context=ctx,
        session=session,
        cc_recipients=cc_recipients or None,
    )

    session.commit()

    return {"sent": len(tickets_relance), "relance_to": syndic_principal.email}


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")
    if not ticket_visible(ticket, user):
        raise HTTPException(403, "Accès refusé")
    return _ticket_read(ticket, session)


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(
    ticket_id: int,
    body: TicketUpdate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")

    is_cs_admin = user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)
    is_auteur = ticket.auteur_id == user.id

    if not is_cs_admin and not is_auteur:
        raise HTTPException(403, "Accès refusé")

    ancien_statut = ticket.statut

    # Statut et priorité : CS/admin uniquement
    if body.statut is not None or body.priorite is not None:
        if not is_cs_admin:
            raise HTTPException(403, "Seul le CS ou un administrateur peut modifier le statut ou la priorité")
        if body.statut is not None:
            ticket.statut = body.statut
            if body.statut in (StatutTicket.résolu, StatutTicket.annulé, StatutTicket.fermé):
                ticket.ferme_le = datetime.utcnow()
        if body.priorite is not None:
            ticket.priorite = body.priorite

    # Champs du contenu : auteur (ticket ouvert uniquement) ou CS/admin
    changes: list[str] = []
    content_fields = (
        body.titre is not None or body.description is not None
        or body.categorie is not None or body.perimetre_cible is not None
    )
    if content_fields:
        if is_auteur and not is_cs_admin:
            if ticket.statut != StatutTicket.ouvert:
                raise HTTPException(403, "Modification impossible : le ticket n'est plus ouvert")
        if body.titre is not None and body.titre != ticket.titre:
            changes.append(f"Titre : {ticket.titre} → {body.titre}")
            ticket.titre = body.titre
        if body.description is not None:
            changes.append("Description modifiée")
            ticket.description = body.description
        if body.categorie is not None and body.categorie != ticket.categorie:
            changes.append(f"Catégorie : {ticket.categorie} → {body.categorie}")
            ticket.categorie = body.categorie
        if body.perimetre_cible is not None:
            import json as _json
            ticket.perimetre_cible = _json.dumps(body.perimetre_cible)
            changes.append("Périmètre modifié")

    # Champs relationnels/destinataires : CS/admin uniquement
    extra_fields = (
        body.lot_id is not None or body.batiment_id is not None
        or body.destinataire_syndic is not None or body.destinataire_cs is not None
        or body.saisi_pour_user_id is not None or body.saisi_pour_nom is not None
        or body.saisi_pour_email is not None
    )
    if extra_fields:
        if not is_cs_admin:
            raise HTTPException(403, "Seul le CS ou un administrateur peut modifier ces champs")
        if body.lot_id is not None:
            ticket.lot_id = body.lot_id
            changes.append("Lot modifié")
        if body.batiment_id is not None:
            ticket.batiment_id = body.batiment_id
            changes.append("Bâtiment modifié")
        if body.destinataire_syndic is not None:
            ticket.destinataire_syndic = body.destinataire_syndic
        if body.destinataire_cs is not None:
            ticket.destinataire_cs = body.destinataire_cs
        if body.saisi_pour_user_id is not None:
            ticket.saisi_pour_user_id = body.saisi_pour_user_id
            changes.append("Résident concerné modifié")
        if body.saisi_pour_nom is not None:
            ticket.saisi_pour_nom = body.saisi_pour_nom
        if body.saisi_pour_email is not None:
            ticket.saisi_pour_email = body.saisi_pour_email
        if body.non_relancable is not None:
            ticket.non_relancable = body.non_relancable
        if body.non_relancable_motif is not None:
            ticket.non_relancable_motif = body.non_relancable_motif

    ticket.mis_a_jour_le = datetime.utcnow()

    # Auto-log évolution sur changement de statut
    if body.statut is not None and body.statut != ancien_statut:
        evol = TicketEvolution(
            ticket_id=ticket.id, type="etat",
            contenu=f"Statut : {STATUT_LABELS.get(ancien_statut or '', 'Aucun')} → {STATUT_LABELS.get(body.statut, body.statut)}",
            ancien_statut=ancien_statut, nouveau_statut=body.statut,
            auteur_id=user.id, cree_le=datetime.utcnow(),
        )
        session.add(evol)

    # Auto-log évolution sur modification de contenu
    if changes:
        prefix = "Modification" if is_cs_admin else "Modification auteur"
        evol = TicketEvolution(
            ticket_id=ticket.id, type="commentaire",
            contenu=prefix + " : " + " ; ".join(changes),
            auteur_id=user.id, cree_le=datetime.utcnow(),
        )
        session.add(evol)

    # Notification auteur (in-app) — seulement si ce n'est pas l'auteur lui-même qui modifie
    if user.id != ticket.auteur_id:
        notif_corps = " ; ".join(changes) if changes else f"Nouveau statut : {ticket.statut}"
        notif = Notification(
            destinataire_id=ticket.auteur_id,
            type="ticket_update",
            titre=f"Ticket #{ticket.numero} mis à jour",
            corps=notif_corps,
            lien=f"/tickets/{ticket.id}",
        )
        session.add(notif)
    session.add(ticket)

    # Notification auteur (email) — changement de statut par quelqu'un d'autre
    if body.statut is not None and body.statut != ancien_statut and ticket.auteur_id != user.id:
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
    if not ticket_visible(ticket, user):
        raise HTTPException(403, "Accès refusé")
    stmt = select(MessageTicket).where(MessageTicket.ticket_id == ticket_id)
    # Messages internes réservés CS/admin
    if not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
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
    if body.interne and not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        raise HTTPException(403, "Messages internes réservés au CS")

    msg = MessageTicket(
        ticket_id=ticket_id,
        auteur_id=user.id,
        contenu=body.contenu,
        interne=body.interne,
        fichiers_urls=json.dumps(body.fichiers_urls, ensure_ascii=False),
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

    # Email externe (CS/Admin uniquement, après commit pour avoir l'id)
    if body.email_externe and body.email_externe.strip() and not body.interne:
        _envoyer_email_externe_ticket(
            ticket, user, body.email_externe.strip(), background_tasks, session,
            is_commentaire=True,
            nouveau_message=body.contenu,
            fichiers_urls=body.fichiers_urls,
        )

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


@router.patch("/{ticket_id}/evolutions/{evol_id}", response_model=TicketEvolutionRead)
def update_evolution(
    ticket_id: int,
    evol_id: int,
    body: TicketEvolutionUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    evol = session.get(TicketEvolution, evol_id)
    if not evol or evol.ticket_id != ticket_id:
        raise HTTPException(404, "Évolution introuvable")
    if evol.type not in ("commentaire", "etat"):
        raise HTTPException(422, "Ce type d'évolution ne peut pas être modifié")
    if evol.auteur_id != user.id and not user.has_role(RoleUtilisateur.admin):
        raise HTTPException(403, "Accès refusé")
    if body.contenu is not None:
        evol.contenu = body.contenu
    if body.fichiers_urls is not None:
        evol.fichiers_urls = json.dumps(body.fichiers_urls)
    session.add(evol)
    session.commit()
    session.refresh(evol)
    return _evol_read(evol, session)


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
        fichiers_urls=json.dumps(body.fichiers_urls, ensure_ascii=False),
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

    # ── Notifications WhatsApp / syndic / CS optionnelles ──────────────────
    if body.partager_whatsapp or body.envoyer_syndic or body.envoyer_cs:
        from app.utils.whatsapp import envoyer_whatsapp_avec_log
        _WA_KEYS = {'whatsapp_enabled', 'whatsapp_api_url', 'whatsapp_api_key', 'whatsapp_group_jid', 'whatsapp_footer'}

        cfg_rows = session.exec(
            select(ConfigSite).where(ConfigSite.cle.in_(_WA_KEYS | {"reference_copro", "site_nom", "site_url"}))
        ).all()
        cfg_map = {r.cle: r.valeur for r in cfg_rows}

        # Évolutions précédentes (excl. celle qui vient d'être créée) — communes WhatsApp + email
        evols_hist = session.exec(
            select(TicketEvolution).where(
                TicketEvolution.ticket_id == ticket.id,
                TicketEvolution.id != evol.id,
            )
            .order_by(TicketEvolution.cree_le)
        ).all()

        # Messages précédents avec contenu (pour WhatsApp + template email)
        messages_ctx = []
        for ev in evols_hist:
            if not ev.contenu:
                continue
            auteur_e = session.get(Utilisateur, ev.auteur_id)
            messages_ctx.append({
                "auteur_nom": f"{auteur_e.prenom} {auteur_e.nom}" if auteur_e else "?",
                "date": _fmt_paris(ev.cree_le),
                "contenu": ev.contenu,
            })

        if body.partager_whatsapp:
            wa_config = {k: cfg_map[k] for k in _WA_KEYS if k in cfg_map}
            if wa_config.get('whatsapp_enabled') == '1':
                msg = body.contenu or (
                    f"Ticket #{ticket.numero} — {ticket.titre} : statut → {STATUT_LABELS.get(body.nouveau_statut or '', body.nouveau_statut or '')}"
                    if body.type == "etat" else ticket.titre
                )
                if msg and messages_ctx:
                    site_url = (cfg_map.get('site_url') or '').rstrip('/')
                    nb = len(messages_ctx)
                    msg += (
                        f"\n\n\U0001f4dc Cet échange comporte {nb} commentaire(s) précédent(s).\n"
                        f"Consultez l'historique complet sur l'application :\n"
                        f"\U0001f449 {site_url}/tickets/{ticket.id}"
                    )
                background_tasks.add_task(
                    envoyer_whatsapp_avec_log,
                    f"\U0001f527 {ticket.titre}", msg, False, ticket.perimetre_cible, None, wa_config,
                )

        if body.envoyer_syndic or body.envoyer_cs:
            from app.utils.email import send_email_group
            destinataires: list[tuple[int | None, str]] = []
            seen_emails: set[str] = set()

            if body.envoyer_syndic:
                syndic_principal = session.exec(
                    select(MembreSyndic).where(MembreSyndic.est_principal == True)
                ).first()
                if syndic_principal and syndic_principal.email:
                    destinataires.append((syndic_principal.user_id, syndic_principal.email))
                    seen_emails.add(syndic_principal.email.lower())

            if body.envoyer_cs:
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

            # Historique résumé pour le tableau email
            historique = [{"date": ticket.cree_le.strftime("%d/%m/%Y"), "label": "Création du ticket"}]
            for ev in evols_hist:
                if ev.type == "etat":
                    lbl = (f"Changement d'état : "
                           f"{STATUT_LABELS.get(ev.ancien_statut or '', '?')} → "
                           f"{STATUT_LABELS.get(ev.nouveau_statut or '', '?')}")
                elif ev.type == "relance":
                    lbl = ev.contenu or "Relance syndic"
                elif ev.type == "commentaire":
                    lbl = f"Commentaire : {(ev.contenu or '')[:100]}"
                else:
                    lbl = ev.type
                historique.append({"date": _fmt_paris(ev.cree_le), "label": lbl})

            ctx = {
                "ticket": {
                    "id": ticket.id, "numero": ticket.numero,
                    "titre": ticket.titre,
                    "description": ticket.description or "",
                    "categorie": ticket.categorie,
                },
                "auteur": {"prenom": user.prenom, "nom": user.nom},
                "residence": {"nom": cfg_map.get("site_nom", "5Hostachy")},
                "app": {"url": cfg_map.get("site_url", "https://localhost")},
                "reference_copro": cfg_map.get("reference_copro", ""),
                "is_commentaire": bool(body.contenu and body.contenu.strip()),
                "commentaire": body.contenu or "",
                "date_commentaire": _fmt_paris(datetime.utcnow()),
                "date_creation": ticket.cree_le.strftime("%d/%m/%Y"),
                "messages": messages_ctx,
                "historique": historique,
                "fichiers": bool(body.fichiers_urls),
            }
            if destinataires:
                background_tasks.add_task(
                    send_email_group, code="ticket_syndic",
                    to_recipients=destinataires, context=ctx,
                    session=session,
                )

    # Email externe (CS/Admin uniquement)
    if body.email_externe and body.email_externe.strip():
        _envoyer_email_externe_ticket(
            ticket, user, body.email_externe.strip(), background_tasks, session,
            is_commentaire=True,
            nouveau_message=body.contenu,
            fichiers_urls=body.fichiers_urls,
        )

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
