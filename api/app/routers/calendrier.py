"""Router calendrier — événements de la résidence."""
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import Evenement, Notification, TypeEvenement, StatutKanban, Utilisateur, RoleUtilisateur, Prestataire, ContratEntretien

router = APIRouter(prefix="/calendrier", tags=["calendrier"])


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


_ROLES_AG = (RoleUtilisateur.propriétaire, RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)


def _can_see_ag(user: Utilisateur) -> bool:
    return user.has_role(*_ROLES_AG)


def _ev_to_read(ev: Evenement, session: Session) -> EvenementRead:
    data = EvenementRead.model_validate(ev)
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
    if not _can_see_ag(user):
        evenements = [e for e in evenements if e.type != TypeEvenement.ag]
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
    if ev.type == TypeEvenement.ag and not _can_see_ag(user):
        raise HTTPException(403, "Accès refusé")
    return _ev_to_read(ev, session)


@router.post("", response_model=EvenementRead, status_code=201)
def create_evenement(
    body: EvenementCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    ev = Evenement(
        **body.model_dump(),
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
                lien="/calendrier",
                urgente=(body.type == TypeEvenement.coupure),
            ))

    session.commit()
    session.refresh(ev)
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
