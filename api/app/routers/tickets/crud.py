"""Tickets — cycle de vie : lister, créer, lire, modifier, supprimer.

Extrait de `tickets.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.
"""
import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import Session, or_, select

from app.auth.deps import get_current_user, require_admin, peut_commander
from app.database import get_session
from app.models.core import (
    STATUTS_TICKET_CLOS,
    Notification,
    RoleUtilisateur,
    StatutTicket,
    StatutUtilisateur,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.schemas import TicketCreate, TicketRead, TicketUpdate
from app.utils.fichiers import chemins_locaux
from app.utils.liens import lien_ticket
from app.utils.photos import parse_photos, photos_internes
from app.utils.visibility import ticket_visible

from .commun import (
    STATUT_LABELS,
    config_site,
    generer_numero,
    ticket_read,
)
from .courriels import envoyer_email_externe, envoyer_email_syndic_cs

#  Seul sous-router à porter le préfixe : ses deux routes de collection ont un
#  chemin VIDE (`GET /tickets`, `POST /tickets`), et FastAPI refuse un chemin
#  vide sur un router sans préfixe. Les trois autres sous-modules déclarent des
#  chemins nus et reçoivent le préfixe au montage (cf. `__init__.py`).
router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketRead])
def list_tickets(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    stmt = select(Ticket)
    if not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        stmt = stmt.where(
            or_(Ticket.auteur_id == user.id, Ticket.saisi_pour_user_id == user.id)
        )
    tickets = session.exec(stmt.order_by(Ticket.cree_le.desc())).all()
    return [ticket_read(ticket, session) for ticket in tickets]


def _notifier_cs_creation(session: Session, ticket: Ticket, urgence: bool) -> None:
    """Notification in-app à tout le CS, plus le syndic si le ticket est urgent."""
    cs_members = session.exec(
        select(Utilisateur).where(
            Utilisateur.actif == True,  # noqa: E712
            or_(
                Utilisateur.roles_json.contains("conseil_syndical"),
                Utilisateur.roles_json.contains("admin"),
            ),
        )
    ).all()
    if urgence:
        syndics = session.exec(
            select(Utilisateur).where(Utilisateur.statut == StatutUtilisateur.syndic)
        ).all()
        cs_ids = {m.id for m in cs_members}
        cs_members = list(cs_members) + [s for s in syndics if s.id not in cs_ids]

    for member in cs_members:
        session.add(Notification(
            destinataire_id=member.id,
            type="ticket_update",
            titre=f"Nouveau ticket : {ticket.titre}",
            corps=ticket.description[:200],
            lien=lien_ticket(ticket.id),
            urgente=urgence,
        ))


def _alerter_bug(
    session: Session, ticket: Ticket, user: Utilisateur, background_tasks: BackgroundTasks
) -> None:
    """Un ticket « bug » prévient le gestionnaire du site : c'est du ressort admin."""
    cfg = config_site(session, "notify_ticket_bug_email", "site_email", "site_manager_user_id")
    if cfg.get("notify_ticket_bug_email") != "1":
        return

    from app.utils.email import get_site_manager_notification_email, send_email

    target_email, site_cfg = get_site_manager_notification_email(session)
    if not target_email:
        return
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
            "auteur": {"prenom": user.prenom, "nom": user.nom, "email": user.email},
            "residence": {"nom": site_cfg.get("site_nom") or cfg.get("site_nom") or "5Hostachy"},
            "app": {"url": site_cfg.get("site_url") or cfg.get("site_url") or "https://localhost"},
        },
    )


def _partager_sur_le_groupe(
    session: Session, ticket: Ticket, background_tasks: BackgroundTasks
) -> None:
    """Publie le ticket sur le groupe WhatsApp, première photo comprise.

    L'autorisation est vérifiée par l'appelant : le groupe diffuse à tous les
    résidents, il n'est pas ouvert à l'auteur d'un ticket quelconque.
    """
    from app.utils.fichiers import est_image
    from app.utils.whatsapp import config_whatsapp, envoyer_whatsapp_avec_log, whatsapp_actif

    wa_config = config_whatsapp(session)
    if not whatsapp_actif(wa_config):
        return
    #  La première photo accompagne le message, comme l'image d'une actualité :
    #  sur une fuite ou une dégradation, c'est elle qui porte l'information. Les
    #  documents joints ne partent pas — le bridge n'envoie qu'une image.
    premiere_photo = next((u for u in parse_photos(ticket.photos_urls) if est_image(u)), None)
    background_tasks.add_task(
        envoyer_whatsapp_avec_log,
        f"\U0001f3ab {ticket.titre}",
        ticket.description,
        ticket.categorie == "urgence",
        ticket.perimetre_cible,
        premiere_photo,
        wa_config,
    )


@router.post("", response_model=TicketRead, status_code=201)
def create_ticket(
    body: TicketCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    if user.has_role(RoleUtilisateur.externe) and not user.has_role(
        RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Les utilisateurs externes ne peuvent pas créer de tickets",
        )

    #  Tous les champs « de commandement » (destinataires, saisie pour un tiers)
    #  sont neutralisés hors CS/admin. Le contrôle est ici, côté serveur : ce que
    #  l'interface masque n'est qu'un confort (socle 03 §1).
    est_cs = peut_commander(user)
    ticket = Ticket(
        numero=generer_numero(),
        titre=body.titre,
        description=body.description,
        categorie=body.categorie,
        auteur_id=user.id,
        lot_id=body.lot_id,
        batiment_id=body.batiment_id,
        perimetre_cible=json.dumps(body.perimetre_cible) if body.perimetre_cible else '["résidence"]',
        priorite="haute" if body.categorie == "urgence" else "normale",
        #  Le workflow est saisissable dès la création, mais en LISTE BLANCHE et
        #  réservé au CS : un résident qui déposerait un ticket déjà « résolu »
        #  le sortirait du suivi. Une valeur inconnue retombe sur « ouvert »
        #  plutôt que d'être refusée — le ticket doit exister même si le client
        #  envoie n'importe quoi (socle 03 §2, liste blanche ancrée).
        statut=(body.statut if est_cs and body.statut in {s.value for s in StatutTicket}
               else StatutTicket.ouvert),
        destinataire_syndic=body.destinataire_syndic if est_cs else False,
        destinataire_cs=body.destinataire_cs if est_cs else False,
        saisi_pour_user_id=body.saisi_pour_user_id if est_cs else None,
        saisi_pour_nom=body.saisi_pour_nom if est_cs else None,
        saisi_pour_email=body.saisi_pour_email if est_cs else None,
        # `photos_internes` écarte toute URL qui n'a pas été produite par notre
        # endpoint d'upload : sans ce filtre, un client pourrait faire pointer une
        # pièce jointe vers un site tiers, servi ensuite à chaque lecteur.
        photos_urls=json.dumps(photos_internes(body.photos_urls), ensure_ascii=False),
        fichiers_urls=json.dumps(photos_internes(body.fichiers_urls), ensure_ascii=False),
    )
    session.add(ticket)
    session.flush()

    _notifier_cs_creation(session, ticket, urgence=body.categorie == "urgence")

    if body.categorie == "bug":
        _alerter_bug(session, ticket, user, background_tasks)

    if body.partager_whatsapp and est_cs:
        _partager_sur_le_groupe(session, ticket, background_tasks)

    if ticket.destinataire_syndic or ticket.destinataire_cs:
        envoyer_email_syndic_cs(
            ticket, user, background_tasks, session,
            syndic=ticket.destinataire_syndic,
            cs=ticket.destinataire_cs,
            # Mêmes règles de résolution que partout ailleurs : URL interne →
            # chemin local, hors de /app/uploads on ignore.
            pieces_jointes=chemins_locaux(
                parse_photos(ticket.photos_urls) + parse_photos(ticket.fichiers_urls)
            ),
        )

    session.commit()
    session.refresh(ticket)

    # Email externe si adresse fournie (CS/Admin uniquement)
    email_ext = (body.email_externe or "").strip()
    if email_ext and est_cs:
        envoyer_email_externe(
            ticket, user, email_ext, background_tasks, session,
            is_commentaire=False,
            fichiers_urls=parse_photos(ticket.fichiers_urls),
        )

    return ticket_read(ticket, session)


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
    return ticket_read(ticket, session)


def _appliquer_contenu(body: TicketUpdate, ticket: Ticket) -> list[str]:
    """Champs de contenu, et la liste des changements qui alimentera l'historique."""
    changes: list[str] = []
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
        ticket.perimetre_cible = json.dumps(body.perimetre_cible)
        changes.append("Périmètre modifié")
    if body.fichiers_urls is not None:
        ticket.fichiers_urls = json.dumps(
            photos_internes(body.fichiers_urls), ensure_ascii=False
        )
        changes.append("Pièces jointes modifiées")
    return changes


def _appliquer_relations(body: TicketUpdate, ticket: Ticket) -> list[str]:
    """Champs relationnels et destinataires — réservés au CS/admin."""
    changes: list[str] = []
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
    return changes


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
            raise HTTPException(
                403, "Seul le CS ou un administrateur peut modifier le statut ou la priorité"
            )
        if body.statut is not None:
            ticket.statut = body.statut
            if body.statut in STATUTS_TICKET_CLOS:
                ticket.ferme_le = datetime.utcnow()
        if body.priorite is not None:
            ticket.priorite = body.priorite

    # Champs du contenu : auteur (ticket ouvert uniquement) ou CS/admin
    changes: list[str] = []
    content_fields = (
        body.titre is not None or body.description is not None
        or body.categorie is not None or body.perimetre_cible is not None
        or body.fichiers_urls is not None
    )
    if content_fields:
        if is_auteur and not is_cs_admin and ticket.statut != StatutTicket.ouvert:
            raise HTTPException(403, "Modification impossible : le ticket n'est plus ouvert")
        changes += _appliquer_contenu(body, ticket)

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
        changes += _appliquer_relations(body, ticket)

    ticket.mis_a_jour_le = datetime.utcnow()

    #  🔴 UNE ÉDITION ÉCRIT UNE CORRECTION, PAS UNE TRANSITION (cadre #430, #431)
    #
    #  Ce bloc écrivait une `TicketEvolution(type="etat")` dès que le statut
    #  changeait — la même forme, au même endroit du fil, que le changement d'état
    #  volontaire du conseil syndical. Tant que l'édition ne rouvrait pas le
    #  workflow, cela ne se voyait pas. Depuis que le cadre l'y rouvre — *l'édition
    #  corrige, et l'état s'y corrige comme les autres champs* —, corriger un état
    #  mal saisi apparaîtrait dans l'Historique comme une ÉTAPE DU WORKFLOW : le
    #  ticket aurait « été » en cours, alors qu'il n'y est jamais passé.
    #
    #  La correction reste **visible** — rien ne devient muet — mais elle se
    #  présente pour ce qu'elle est : une ligne de correction parmi les autres,
    #  sans `ancien_statut`/`nouveau_statut`, donc sans jalon de suivi.
    #
    #  La transition, elle, n'a pas disparu : elle passe par
    #  `POST /tickets/{id}/evolutions` (`evolutions.py`), qui l'inscrit avec sa
    #  date, son auteur, son courriel à l'auteur du ticket et ses canaux. C'est
    #  désormais le seul chemin qui la produit — les boutons « Changer le statut »
    #  de la fiche l'empruntent depuis #431.
    if body.statut is not None and body.statut != ancien_statut:
        changes.insert(
            0,
            f"État : {STATUT_LABELS.get(ancien_statut or '', 'Aucun')} → "
            f"{STATUT_LABELS.get(body.statut, body.statut)}",
        )

    # Auto-log de la correction
    if changes:
        prefix = "Correction" if is_cs_admin else "Correction auteur"
        session.add(TicketEvolution(
            ticket_id=ticket.id, type="commentaire",
            contenu=prefix + " : " + " ; ".join(changes),
            auteur_id=user.id, cree_le=datetime.utcnow(),
        ))

    # Notification auteur (in-app) — sauf si c'est l'auteur lui-même qui modifie
    if user.id != ticket.auteur_id:
        session.add(Notification(
            destinataire_id=ticket.auteur_id,
            type="ticket_update",
            titre=f"Ticket #{ticket.numero} mis à jour",
            corps=" ; ".join(changes) if changes else f"Nouveau statut : {ticket.statut}",
            lien=lien_ticket(ticket.id),
        ))
    session.add(ticket)

    #  ⚠️ PLUS DE COURRIEL « changement de statut » ICI (#431).
    #
    #  Ce chemin envoyait `ticket_statut_change` à l'auteur du ticket dès que le
    #  statut bougeait par un `PATCH`. Or un `PATCH` est désormais une
    #  **correction** : la Diffusion est absente de l'édition, motif `geste` —
    #  *une correction n'est pas une nouvelle*, et rejouer un canal à chaque
    #  faute de frappe rattrapée est exactement l'incident du triple envoi
    #  WhatsApp du 14/08/2026.
    #
    #  L'auteur n'est pas laissé dans le noir : la notification in-app ci-dessus
    #  part toujours, et elle porte le détail des corrections. Le courriel, lui,
    #  reste attaché à la vraie transition, dans `evolutions.py::_notifier_auteur`.
    session.commit()
    session.refresh(ticket)
    return ticket_read(ticket, session)


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
