"""Router notifications — liste, marquer lue, tout marquer lu."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Notification, Utilisateur
from app.schemas import NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return session.exec(
        select(Notification)
        .where(Notification.destinataire_id == user.id)
        .order_by(Notification.cree_le.desc())
    ).all()


@router.patch("/{notif_id}/lue", response_model=NotificationRead)
def marquer_lue(
    notif_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    notif = session.get(Notification, notif_id)
    if not notif or notif.destinataire_id != user.id:
        raise HTTPException(404, "Notification introuvable")
    notif.lue = True
    session.add(notif)
    session.commit()
    session.refresh(notif)
    return notif


@router.post("/tout-marquer-lu")
def tout_marquer_lu(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    notifs = session.exec(
        select(Notification)
        .where(Notification.destinataire_id == user.id)
        .where(Notification.lue == False)
    ).all()
    for n in notifs:
        n.lue = True
        session.add(n)
    session.commit()
    return {"marquees": len(notifs)}


@router.delete("/{notif_id}", status_code=204)
def supprimer_notification(
    notif_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    notif = session.get(Notification, notif_id)
    if not notif or notif.destinataire_id != user.id:
        raise HTTPException(404, "Notification introuvable")
    session.delete(notif)
    session.commit()
