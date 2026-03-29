from fastapi import Depends, HTTPException, Cookie, Header, status
from datetime import date
from sqlmodel import Session, select, or_

from app.auth.jwt import decode_token
from app.database import get_session
from app.models.core import Delegation, StatutDelegation, Utilisateur, RoleUtilisateur


def _get_current_user(
    access_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
) -> Utilisateur:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non authentifié")

    payload = decode_token(access_token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    user_id: int = payload.get("sub")
    user = session.get(Utilisateur, int(user_id))
    if not user or not user.actif:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable ou inactif")
    return user


def get_current_user(user: Utilisateur = Depends(_get_current_user)) -> Utilisateur:
    return user


def get_acting_user(
    x_acting_as: int | None = Header(default=None, alias="X-Acting-As"),
    user: Utilisateur = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Utilisateur:
    """Retourne l'utilisateur effectif : le mandant si l'aidant agit en délégation,
    sinon l'utilisateur connecté lui-même."""
    if x_acting_as is None or x_acting_as == user.id:
        return user

    today = date.today()
    delegation = session.exec(
        select(Delegation).where(
            Delegation.aidant_id == user.id,
            Delegation.mandant_id == x_acting_as,
            Delegation.statut == StatutDelegation.active,
            Delegation.date_debut <= today,
            or_(Delegation.date_fin.is_(None), Delegation.date_fin >= today),  # type: ignore[arg-type]
        )
    ).first()

    if not delegation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aucune délégation active pour cet utilisateur",
        )

    mandant = session.get(Utilisateur, x_acting_as)
    if not mandant or not mandant.actif:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Mandant introuvable ou inactif")
    return mandant


def require_role(*roles: RoleUtilisateur):
    def checker(user: Utilisateur = Depends(get_current_user)):
        if not user.has_role(*roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Droits insuffisants")
        return user
    return checker


def require_proprietaire(user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    if not user.has_role(RoleUtilisateur.propriétaire, RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé aux propriétaires")
    return user


def require_cs_or_admin(user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    if not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé au conseil syndical et à l'admin")
    return user


def require_admin(user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    if not user.has_role(RoleUtilisateur.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé à l'admin")
    return user
