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


def peut_commander(user: Utilisateur) -> bool:
    """Cet utilisateur peut-il fixer les champs « de commandement » ?

    Les champs de commandement sont ceux qui engagent autre chose que leur
    auteur : à qui la demande est adressée (syndic, conseil syndical), pour qui
    elle est saisie, et où elle en est dans son workflow. Un résident ne les
    fixe pas — sinon il peut adresser un ticket au syndic sans passer par le CS,
    ou déposer un signalement déjà « Résolu », donc hors du suivi, sans que
    personne l'ait regardé.

    POURQUOI ICI ET PAS DANS LE ROUTEUR (16/08/2026). Cette règle était écrite
    en ligne, une fois par champ — `destinataire_syndic if est_cs else False`,
    répété cinq fois — et j'allais en ajouter une sixième pour le workflow.
    Une règle d'autorisation recopiée à côté de chaque champ ne se durcit pas :
    on en corrige quatre sur six. Elle vit donc ici, avec les autres, où
    `test_autorisation.py` la voit (socle 03 §1, exigence 0c du pré-check).

    C'est un PRÉDICAT, pas une dépendance FastAPI : il ne refuse pas la requête,
    il dit si l'on retient la valeur demandée ou le défaut. Refuser serait faux —
    un résident a le droit de créer un ticket, simplement pas d'en fixer
    l'adressage ni l'étape.
    """
    return user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)
