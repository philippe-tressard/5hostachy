"""Router calendrier — événements de la résidence."""
import json
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import Evenement, Notification, TypeEvenement, StatutKanban, Utilisateur, RoleUtilisateur, Prestataire, ContratEntretien, ConfigSite, MembreSyndic
from app.utils.liens import lien_element
from app.utils.whatsapp import envoyer_whatsapp_avec_log
from app.utils.photos import parse_photos, photos_internes
from app.utils.visibility import evenement_visible

router = APIRouter(prefix="/calendrier", tags=["calendrier"])

_WA_KEYS = {'whatsapp_enabled', 'whatsapp_api_url', 'whatsapp_api_key', 'whatsapp_group_jid', 'whatsapp_footer'}


class EvenementCreate(BaseModel):
    titre: str
    description: Optional[str] = None
    type: TypeEvenement = TypeEvenement.autre
    lieu: Optional[str] = None
    debut: datetime
    fin: Optional[datetime] = None
    perimetre: str = "résidence"
    batiment_id: Optional[int] = None
    statut_kanban: Optional[str] = None
    prestataire_id: Optional[int] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    affichable: bool = True
    partager_whatsapp: Optional[bool] = None
    envoyer_syndic: Optional[bool] = None
    envoyer_cs: Optional[bool] = None


class EvenementRead(BaseModel):
    id: int
    titre: str
    description: Optional[str] = None
    type: str
    lieu: Optional[str] = None
    debut: datetime
    fin: Optional[datetime] = None
    perimetre: str
    batiment_id: Optional[int] = None
    auteur_id: int
    auteur_nom: Optional[str] = None
    cree_le: datetime
    mis_a_jour_le: Optional[datetime] = None
    statut_kanban: Optional[str] = None
    prestataire_id: Optional[int] = None
    prestataire_nom: Optional[str] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    affichable: bool = True
    archivee: bool = False
    # Stocké en colonne comme un tableau JSON (convention Ticket.photos_urls) ;
    # exposé en liste pour que le front n'ait rien à désérialiser.
    photos_urls: list[str] = []

    class Config:
        from_attributes = True


class EvenementUpdate(BaseModel):
    titre: Optional[str] = None
    description: Optional[str] = None
    type: Optional[TypeEvenement] = None
    lieu: Optional[str] = None
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    perimetre: Optional[str] = None
    batiment_id: Optional[int] = None
    statut_kanban: Optional[str] = None
    archivee: Optional[bool] = None
    prestataire_id: Optional[int] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    affichable: Optional[bool] = None
    # Sert uniquement à RETIRER des photos : l'ajout passe par l'endpoint
    # d'upload, seul capable de valider et de redimensionner le fichier.
    photos_urls: Optional[list[str]] = None


_ROLES_AG = (RoleUtilisateur.propriétaire, RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)


def _ev_to_read(ev: Evenement, session: Session) -> EvenementRead:
    # La colonne stocke un tableau JSON, le schéma expose une liste : on convertit
    # AVANT la validation, sinon pydantic reçoit une chaîne là où il attend une
    # liste et rejette l'événement entier.
    brut = ev.model_dump()
    brut["photos_urls"] = parse_photos(ev.photos_urls)
    data = EvenementRead.model_validate(brut)
    auteur = session.get(Utilisateur, ev.auteur_id)
    data.auteur_nom = f"{auteur.prenom} {auteur.nom}" if auteur else "?"
    if ev.prestataire_id:
        prest = session.get(Prestataire, ev.prestataire_id)
        data.prestataire_nom = prest.nom if prest else None
    return data


@router.get("", response_model=list[EvenementRead])
def list_evenements(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    stmt = select(Evenement).order_by(Evenement.debut)
    evenements = session.exec(stmt).all()
    # CS/admin : accès complet (ils gèrent ici les maintenances récurrentes → ne pas
    # les masquer via evenement_visible). Non-CS/admin : filtrage périmètre + AG +
    # maintenance_recurrente interne, aligné sur flux.py — sinon un résident du bât. 2
    # voyait les événements ciblés bât. 1.
    is_cs = user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical)
    if not is_cs:
        evenements = [e for e in evenements if evenement_visible(e, user)]
    return [_ev_to_read(e, session) for e in evenements]


@router.get("/{ev_id}", response_model=EvenementRead)
def get_evenement(
    ev_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ev = session.get(Evenement, ev_id)
    if not ev:
        raise HTTPException(404, "Événement introuvable")
    # Contrôle complet périmètre + rôle AG (cf. list_evenements) : empêche l'accès
    # direct à /calendrier/{id} d'un événement ciblant un autre bâtiment. CS/admin :
    # accès total (gestion des maintenances récurrentes incluse).
    if not user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical) \
            and not evenement_visible(ev, user):
        raise HTTPException(403, "Accès refusé")
    return _ev_to_read(ev, session)


@router.post("", response_model=EvenementRead, status_code=201)
def create_evenement(
    body: EvenementCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    ev = Evenement(
        **body.model_dump(exclude_none=True),
        auteur_id=user.id,
    )
    session.add(ev)
    session.flush()

    # Notifier les résidents — urgences immédiates
    if body.type in (TypeEvenement.coupure, TypeEvenement.travaux):
        residents = session.exec(
            select(Utilisateur).where(Utilisateur.actif == True)
        ).all()
        for r in residents:
            session.add(Notification(
                destinataire_id=r.id,
                type="calendrier",
                titre=f"📅 {body.type.value.capitalize()} : {body.titre}",
                corps=body.description or "",
                # `session.flush()` juste au-dessus a attribué l'id : le lecteur
                # arrive sur l'événement annoncé, pas en haut du calendrier.
                lien=lien_element("ev", ev.id),
                urgente=(body.type == TypeEvenement.coupure),
            ))

    session.commit()
    session.refresh(ev)

    # ── Notifications WhatsApp / syndic / CS optionnelles ──────────────────
    if body.partager_whatsapp or body.envoyer_syndic or body.envoyer_cs:
        cfg_rows = session.exec(
            select(ConfigSite).where(ConfigSite.cle.in_(
                _WA_KEYS | {"reference_copro", "site_nom", "site_url"}
            ))
        ).all()
        cfg_map = {r.cle: r.valeur for r in cfg_rows}

        if body.partager_whatsapp:
            wa_config = {k: cfg_map[k] for k in _WA_KEYS if k in cfg_map}
            if wa_config.get('whatsapp_enabled') == '1':
                background_tasks.add_task(
                    envoyer_whatsapp_avec_log,
                    f"📅 {body.titre}", body.description or "", False, None, None, wa_config,
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
                    "id": ev.id,
                    "numero": str(ev.id),
                    "titre": ev.titre,
                    "description": ev.description or "",
                    "categorie": ev.type.value if ev.type else "",
                },
                "auteur": {"prenom": user.prenom, "nom": user.nom},
                "residence": {"nom": cfg_map.get("site_nom", "5Hostachy")},
                "app": {"url": cfg_map.get("site_url", "https://localhost")},
                "reference_copro": cfg_map.get("reference_copro", ""),
            }
            if destinataires:
                background_tasks.add_task(
                    send_email_group, code="calendrier_evenement_cree",
                    to_recipients=destinataires, context=ctx,
                    session=session,
                )

    return _ev_to_read(ev, session)


def _next_visit_date(contrat: ContratEntretien, from_date: date) -> date | None:
    """Calcule la prochaine visite à partir de la fréquence du contrat."""
    ft, fv = contrat.frequence_type, contrat.frequence_valeur
    if not ft or not fv:
        return None
    if ft == "semaines":
        return from_date + timedelta(weeks=fv)
    if ft == "mois":
        month = from_date.month + fv
        year = from_date.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(from_date.day, 28)
        return date(year, month, day)
    if ft == "fois_par_an":
        interval_months = max(1, 12 // fv)
        month = from_date.month + interval_months
        year = from_date.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(from_date.day, 28)
        return date(year, month, day)
    return None


def _update_contrat_prochaine_visite(ev: Evenement, session: Session) -> None:
    """Met à jour prochaine_visite du contrat lié quand un événement maintenance_recurrente passe en terminé."""
    if ev.type != TypeEvenement.maintenance_recurrente or not ev.prestataire_id:
        return
    contrats = session.exec(
        select(ContratEntretien).where(
            ContratEntretien.prestataire_id == ev.prestataire_id,
            ContratEntretien.actif == True,
        )
    ).all()
    if not contrats:
        return
    # Match par libellé dans le titre (format "Prestataire — Libellé")
    best = None
    for c in contrats:
        if c.libelle and c.libelle.lower() in ev.titre.lower():
            best = c
            break
    if not best:
        best = contrats[0] if len(contrats) == 1 else None
    if not best:
        return
    next_date = _next_visit_date(best, ev.debut.date() if isinstance(ev.debut, datetime) else ev.debut)
    if next_date:
        best.prochaine_visite = next_date
        session.add(best)


@router.patch("/{ev_id}", response_model=EvenementRead)
def update_evenement(
    ev_id: int,
    body: EvenementUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    ev = session.get(Evenement, ev_id)
    if not ev:
        raise HTTPException(404, "Événement introuvable")
    data = body.model_dump(exclude_unset=True)
    if data.get('archivee') is True and ev.statut_kanban != "termine":
        raise HTTPException(422, "Seuls les événements terminés peuvent être archivés")
    if "photos_urls" in data:
        # Liste → tableau JSON, en ne conservant que nos propres URLs (cf.
        # _photos_internes). Ce champ ne sert qu'à retirer des photos.
        data["photos_urls"] = json.dumps(photos_internes(data["photos_urls"] or []))
    old_statut = ev.statut_kanban
    for k, v in data.items():
        setattr(ev, k, v)
    ev.mis_a_jour_le = datetime.utcnow()
    # Si le statut passe à "termine", mettre à jour la prochaine visite du contrat
    if data.get('statut_kanban') == 'termine' and old_statut != 'termine':
        _update_contrat_prochaine_visite(ev, session)
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return _ev_to_read(ev, session)


@router.delete("/{ev_id}", status_code=204)
def delete_evenement(
    ev_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    ev = session.get(Evenement, ev_id)
    if not ev:
        raise HTTPException(404, "Événement introuvable")
    session.delete(ev)
    session.commit()
