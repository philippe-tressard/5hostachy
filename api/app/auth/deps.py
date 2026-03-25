from fastapi import Depends, HTTPException, Cookie, status
from sqlmodel import Session, select

from app.auth.jwt import decode_token
from app.database import get_session
from app.models.core import Utilisateur, RoleUtilisateur


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
