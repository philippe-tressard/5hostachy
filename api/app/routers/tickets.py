"""Router tickets â€” crÃ©ation, suivi, messagerie, Ã©volutions."""
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
from app.utils.visibility import ticket_visible

router = APIRouter(prefix="/tickets", tags=["tickets"])

STATUT_LABELS = {
    "ouvert": "Ouvert", "en_cours": "En cours",
    "rÃ©solu": "RÃ©solu", "annulÃ©": "AnnulÃ©", "fermÃ©": "FermÃ©",
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
        auteur_batiment_nom=f"BÃ¢t. {batiment.numero}" if batiment else None,
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
        non_relancable=ticket.non_relancable,
        non_relancable_motif=ticket.non_relancable_motif,
        relance_count=session.exec(
            select(TicketEvolution).where(
                TicketEvolution.ticket_id == ticket.id,
                TicketEvolution.type == "relance",
            )
        ).all().__len__(),
        cree_le=ticket.cree_le,
        mis_a_jour_le=ticket.mis_a_jour_le,
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Les utilisateurs externes ne peuvent pas crÃ©er de tickets")
    import json
    ticket = Ticket(
        numero=_generate_numero(),
        titre=body.titre,
        description=body.description,
        categorie=body.categorie,
        auteur_id=user.id,
        lot_id=body.lot_id,
        batiment_id=body.batiment_id,
        perimetre_cible=json.dumps(body.perimetre_cible) if body.perimetre_cible else '["rÃ©sidence"]',
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

    # â”€â”€ Email au syndic et/ou CS (option CS/Admin) â”€â”€
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
                # url = "/uploads/tickets/abc.jpg" â†’ "/app/uploads/tickets/abc.jpg"
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

        # Construire la liste de destinataires (dÃ©dupliquÃ©s)
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
    return _ticket_read(ticket, session)


# â”€â”€ Relance syndic â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

from pydantic import BaseModel as _BaseModel


class RelanceSyndicRequest(_BaseModel):
    ticket_ids: list[int]


@router.get("/relance-syndic", response_model=list[TicketRead])
def list_relance_syndic(
    session: Session = Depends(get_session),
    _user: Utilisateur = Depends(require_cs_or_admin),
):
    """Retourne les tickets adressÃ©s au syndic, non rÃ©solus/annulÃ©s/fermÃ©s,
    non taguÃ©s non_relancable, dont la derniÃ¨re modification date de plus de
    `relance_syndic_delai_jours` jours."""
    from datetime import timedelta

    cfg_delai = session.exec(
        select(ConfigSite).where(ConfigSite.cle == "relance_syndic_delai_jours")
    ).first()
    delai_jours = int(cfg_delai.valeur) if cfg_delai else 30

    seuil = datetime.utcnow() - timedelta(days=delai_jours)

    tickets = session.exec(
        select(Ticket).where(
            Ticket.destinataire_syndic == True,
            Ticket.statut.notin_(["rÃ©solu", "annulÃ©", "fermÃ©"]),
            Ticket.non_relancable == False,
            Ticket.mis_a_jour_le < seuil,
        ).order_by(Ticket.mis_a_jour_le)
    ).all()

    return [_ticket_read(t, session) for t in tickets]


@router.post("/relance-syndic", status_code=200)
def envoyer_relance_syndic(
    body: RelanceSyndicRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Envoie un mail de relance groupÃ© au syndic (est_principal=True) en CC
    des membres CS, et logue une Ã©volution 'relance' sur chaque ticket."""
    from app.utils.email import send_email_group
    from app.models.core import GenreCivilite, SyndicInfo

    if not body.ticket_ids:
        raise HTTPException(422, "Aucun ticket sÃ©lectionnÃ©")

    # Charger les tickets demandÃ©s
    tickets_relance: list[Ticket] = []
    for tid in body.ticket_ids:
        t = session.get(Ticket, tid)
        if not t:
            raise HTTPException(404, f"Ticket {tid} introuvable")
        if not t.destinataire_syndic:
            raise HTTPException(422, f"Ticket {tid} non adressÃ© au syndic")
        tickets_relance.append(t)

    # Config
    cfg_rows = session.exec(
        select(ConfigSite).where(
            ConfigSite.cle.in_(("site_nom", "site_url", "reference_copro"))
        )
    ).all()
    cfg_map = {r.cle: r.valeur for r in cfg_rows}
    now = datetime.utcnow()

    # Enregistrement des Ã©volutions relance
    for ticket in tickets_relance:
        relance_count = len(session.exec(
            select(TicketEvolution).where(
                TicketEvolution.ticket_id == ticket.id,
                TicketEvolution.type == "relance",
            )
        ).all())
        num = relance_count + 1
        evol = TicketEvolution(
            ticket_id=ticket.id,
            type="relance",
            contenu=f"Relance syndic nÂ°{num}",
            auteur_id=user.id,
            cree_le=now,
        )
        session.add(evol)
        ticket.mis_a_jour_le = now
        session.add(ticket)

    session.flush()

    # Gestionnaire principal syndic (destinataire principal)
    syndic_principal = session.exec(
        select(MembreSyndic).where(MembreSyndic.est_principal == True)
    ).first()

    if not syndic_principal or not syndic_principal.email:
        raise HTTPException(422, "Aucun gestionnaire syndic principal avec email configurÃ©")

    # CivilitÃ©
    civilite = "Madame"
    if syndic_principal.genre and syndic_principal.genre == GenreCivilite.monsieur:
        civilite = "Monsieur"
    nom_gestionnaire = f"{syndic_principal.prenom} {syndic_principal.nom}".strip()

    # Labels pÃ©rimÃ¨tre
    PERIM_LABELS: dict[str, str] = {
        "rÃ©sidence": "CopropriÃ©tÃ© entiÃ¨re",
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
                labels.append(f"BÃ¢t. {i[4:]}")
            else:
                labels.append(PERIM_LABELS.get(i, i))
        return " Â· ".join(labels)

    def _evol_label(e: TicketEvolution) -> str:
        if e.type == "etat":
            return f"Changement d'Ã©tat : {STATUT_LABELS.get(e.ancien_statut or '', e.ancien_statut or '?')} â†’ {STATUT_LABELS.get(e.nouveau_statut or '', e.nouveau_statut or '?')}"
        if e.type == "relance":
            return e.contenu or "Relance syndic"
        if e.type == "commentaire":
            return "Commentaire CS"
        if e.type == "reponse":
            return "RÃ©ponse"
        return e.type

    # Construire le contexte tickets
    tickets_ctx = []
    for ticket in tickets_relance:
        relance_count = len(session.exec(
            select(TicketEvolution).where(
                TicketEvolution.ticket_id == ticket.id,
                TicketEvolution.type == "relance",
            )
        ).all()) - 1  # -1 car on vient d'en ajouter une
        evols = session.exec(
            select(TicketEvolution).where(
                TicketEvolution.ticket_id == ticket.id
            ).order_by(TicketEvolution.cree_le)
        ).all()
        historique = [{"date": e.cree_le.strftime("%d/%m/%Y"), "label": _evol_label(e)} for e in evols]
        # Ajout de la crÃ©ation comme premier item
        historique.insert(0, {
            "date": ticket.cree_le.strftime("%d/%m/%Y"),
            "label": f"CrÃ©ation du ticket (statut : {STATUT_LABELS.get(ticket.statut, ticket.statut)})",
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

    # Destinataires : syndic principal (to) + membres CS (cc)
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
        raise HTTPException(403, "AccÃ¨s refusÃ©")
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
        raise HTTPException(403, "AccÃ¨s refusÃ©")

    ancien_statut = ticket.statut

    # Statut et prioritÃ© : CS/admin uniquement
    if body.statut is not None or body.priorite is not None:
        if not is_cs_admin:
            raise HTTPException(403, "Seul le CS ou un administrateur peut modifier le statut ou la prioritÃ©")
        if body.statut is not None:
            ticket.statut = body.statut
            if body.statut in (StatutTicket.rÃ©solu, StatutTicket.annulÃ©, StatutTicket.fermÃ©):
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
            changes.append(f"Titre : {ticket.titre} â†’ {body.titre}")
            ticket.titre = body.titre
        if body.description is not None:
            changes.append("Description modifiÃ©e")
            ticket.description = body.description
        if body.categorie is not None and body.categorie != ticket.categorie:
            changes.append(f"CatÃ©gorie : {ticket.categorie} â†’ {body.categorie}")
            ticket.categorie = body.categorie
        if body.perimetre_cible is not None:
            import json as _json
            ticket.perimetre_cible = _json.dumps(body.perimetre_cible)
            changes.append("PÃ©rimÃ¨tre modifiÃ©")

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
            changes.append("Lot modifiÃ©")
        if body.batiment_id is not None:
            ticket.batiment_id = body.batiment_id
            changes.append("BÃ¢timent modifiÃ©")
        if body.destinataire_syndic is not None:
            ticket.destinataire_syndic = body.destinataire_syndic
        if body.destinataire_cs is not None:
            ticket.destinataire_cs = body.destinataire_cs
        if body.saisi_pour_user_id is not None:
            ticket.saisi_pour_user_id = body.saisi_pour_user_id
            changes.append("RÃ©sident concernÃ© modifiÃ©")
        if body.saisi_pour_nom is not None:
            ticket.saisi_pour_nom = body.saisi_pour_nom
        if body.saisi_pour_email is not None:
            ticket.saisi_pour_email = body.saisi_pour_email
        if body.non_relancable is not None:
            ticket.non_relancable = body.non_relancable
        if body.non_relancable_motif is not None:
            ticket.non_relancable_motif = body.non_relancable_motif

    ticket.mis_a_jour_le = datetime.utcnow()

    # Auto-log Ã©volution sur changement de statut
    if body.statut is not None and body.statut != ancien_statut:
        evol = TicketEvolution(
            ticket_id=ticket.id, type="etat",
            contenu=f"Statut : {STATUT_LABELS.get(ancien_statut or '', 'Aucun')} â†’ {STATUT_LABELS.get(body.statut, body.statut)}",
            ancien_statut=ancien_statut, nouveau_statut=body.statut,
            auteur_id=user.id, cree_le=datetime.utcnow(),
        )
        session.add(evol)

    # Auto-log Ã©volution sur modification de contenu
    if changes:
        prefix = "Modification" if is_cs_admin else "Modification auteur"
        evol = TicketEvolution(
            ticket_id=ticket.id, type="commentaire",
            contenu=prefix + " : " + " ; ".join(changes),
            auteur_id=user.id, cree_le=datetime.utcnow(),
        )
        session.add(evol)

    # Notification auteur (in-app) â€” seulement si ce n'est pas l'auteur lui-mÃªme qui modifie
    if user.id != ticket.auteur_id:
        notif_corps = " ; ".join(changes) if changes else f"Nouveau statut : {ticket.statut}"
        notif = Notification(
            destinataire_id=ticket.auteur_id,
            type="ticket_update",
            titre=f"Ticket #{ticket.numero} mis Ã  jour",
            corps=notif_corps,
            lien=f"/tickets/{ticket.id}",
        )
        session.add(notif)
    session.add(ticket)

    # Notification auteur (email) â€” changement de statut par quelqu'un d'autre
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
        raise HTTPException(403, "AccÃ¨s refusÃ©")
    stmt = select(MessageTicket).where(MessageTicket.ticket_id == ticket_id)
    # Messages internes rÃ©servÃ©s CS/admin
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
        raise HTTPException(403, "Messages internes rÃ©servÃ©s au CS")

    msg = MessageTicket(
        ticket_id=ticket_id,
        auteur_id=user.id,
        contenu=body.contenu,
        interne=body.interne,
    )
    # Auto-log Ã©volution "rÃ©ponse"
    evol = TicketEvolution(
        ticket_id=ticket_id, type="reponse",
        contenu="Message interne" if body.interne else None,
        auteur_id=user.id, cree_le=datetime.utcnow(),
    )
    session.add(evol)
    ticket.mis_a_jour_le = datetime.utcnow()
    session.add(msg)
    session.add(ticket)

    # Notification email â€” nouveau message sur le ticket
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
            # CS/Admin rÃ©pond â†’ notifier l'auteur du ticket
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
                        titre=f"Nouvelle rÃ©ponse sur le ticket #{ticket.numero}",
                        corps=body.contenu[:200],
                        lien=f"/tickets/{ticket.id}",
                    ))
        else:
            # RÃ©sident rÃ©pond â†’ notifier les CS/Admin
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


# â”€â”€ Ã‰volutions (fil de suivi) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
        raise HTTPException(403, "AccÃ¨s refusÃ©")
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
        raise HTTPException(422, "nouveau_statut requis pour un changement d'Ã©tat")
    if body.type == "etat" and body.nouveau_statut not in ("ouvert", "en_cours", "rÃ©solu", "fermÃ©"):
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
        if body.nouveau_statut in ("rÃ©solu", "fermÃ©"):
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
            f"Ticket #{ticket.numero} â€” statut : {STATUT_LABELS.get(body.nouveau_statut, body.nouveau_statut)}"
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

    # â”€â”€ Notifications WhatsApp / syndic / CS optionnelles â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if body.partager_whatsapp or body.envoyer_syndic or body.envoyer_cs:
        from app.utils.whatsapp import envoyer_whatsapp_avec_log
        _WA_KEYS = {'whatsapp_enabled', 'whatsapp_api_url', 'whatsapp_api_key', 'whatsapp_group_jid', 'whatsapp_footer'}

        cfg_rows = session.exec(
            select(ConfigSite).where(ConfigSite.cle.in_(_WA_KEYS | {"reference_copro", "site_nom", "site_url"}))
        ).all()
        cfg_map = {r.cle: r.valeur for r in cfg_rows}

        if body.partager_whatsapp:
            wa_config = {k: cfg_map[k] for k in _WA_KEYS if k in cfg_map}
            if wa_config.get('whatsapp_enabled') == '1':
                msg = body.contenu or (
                    f"Ticket #{ticket.numero} â€” {ticket.titre} : statut â†’ {STATUT_LABELS.get(body.nouveau_statut or '', body.nouveau_statut or '')}"
                    if body.type == "etat" else ticket.titre
                )
                background_tasks.add_task(
                    envoyer_whatsapp_avec_log,
                    f"ðŸ”§ {ticket.titre}", msg, False, None, None, wa_config,
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

            ctx = {
                "ticket": {
                    "id": ticket.id, "numero": ticket.numero,
                    "titre": ticket.titre,
                    "description": body.contenu or "",
                    "categorie": ticket.categorie,
                },
                "auteur": {"prenom": user.prenom, "nom": user.nom},
                "residence": {"nom": cfg_map.get("site_nom", "5Hostachy")},
                "app": {"url": cfg_map.get("site_url", "https://localhost")},
                "reference_copro": cfg_map.get("reference_copro", ""),
            }
            if destinataires:
                background_tasks.add_task(
                    send_email_group, code="ticket_syndic",
                    to_recipients=destinataires, context=ctx,
                    session=session,
                )

    return _evol_read(evol, session)


# â”€â”€ Suppression (admin uniquement) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
