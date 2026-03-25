"""Router boîte à idées — idées + upvotes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from datetime import datetime

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import Idee, Utilisateur, VoteIdee, RoleUtilisateur, StatutUtilisateur

router = APIRouter(prefix="/idees", tags=["id\u00e9es"])


def _deny_communaute_for_statut(user: Utilisateur) -> None:
    if user.statut in (StatutUtilisateur.syndic, StatutUtilisateur.mandataire):
        raise HTTPException(403, "La rubrique Communaut\u00e9 n'est pas accessible \u00e0 votre profil")
    if user.communaute_interdit:
        raise HTTPException(403, "Votre acc\u00e8s \u00e0 la Communaut\u00e9 a \u00e9t\u00e9 d\u00e9finitivement suspendu.")
    if user.communaute_ban_jusqu_au and user.communaute_ban_jusqu_au > datetime.utcnow():
        raise HTTPException(403, "Votre acc\u00e8s \u00e0 la Communaut\u00e9 est suspendu pour une p\u00e9riode probatoire d\u2019un mois. \u00c0 la 2\u1d49 infraction, vous serez banni d\u00e9finitivement.")


class IdeeCreate(BaseModel):
    titre: str
    description: str


class IdeeRead(BaseModel):
    id: int
    titre: str
    description: str
    auteur_id: int
    statut: str
    nb_votes: int = 0
    mon_vote: bool = False

    class Config:
        from_attributes = True


def _enrich(idees: list, user_id: int, session: Session) -> list[dict]:
    result = []
    for idee in idees:
        nb = len(session.exec(select(VoteIdee).where(VoteIdee.idee_id == idee.id)).all())
        mon_vote = bool(session.exec(
            select(VoteIdee).where(VoteIdee.idee_id == idee.id, VoteIdee.user_id == user_id)
        ).first())
        result.append({
            "id": idee.id, "titre": idee.titre, "description": idee.description,
            "auteur_id": idee.auteur_id, "statut": idee.statut,
            "cree_le": idee.cree_le, "nb_votes": nb, "mon_vote": mon_vote,
        })
    return result


@router.get("")
def list_idees(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    idees = session.exec(select(Idee).order_by(Idee.cree_le.desc())).all()
    return _enrich(idees, user.id, session)


@router.post("", status_code=201)
def create_idee(
    body: IdeeCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    if user.has_role(RoleUtilisateur.externe) and not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        raise HTTPException(403, "Les utilisateurs externes ne peuvent pas soumettre d'idées")
    idee = Idee(titre=body.titre, description=body.description, auteur_id=user.id)
    session.add(idee)
    session.commit()
    session.refresh(idee)
    return idee


@router.post("/{idee_id}/voter", status_code=201)
def voter(
    idee_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    if user.has_role(RoleUtilisateur.externe) and not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        raise HTTPException(403, "Les utilisateurs externes ne peuvent pas voter")
    idee = session.get(Idee, idee_id)
    if not idee:
        raise HTTPException(404, "Idée introuvable")

    existant = session.exec(
        select(VoteIdee).where(VoteIdee.idee_id == idee_id, VoteIdee.user_id == user.id)
    ).first()
    if existant:
        # toggle
        session.delete(existant)
        session.commit()
        return {"message": "Vote retiré"}

    session.add(VoteIdee(idee_id=idee_id, user_id=user.id))
    session.commit()
    return {"message": "Vote enregistré"}


class StatutUpdate(BaseModel):
    statut: str  # ouverte | retenue | rejetee | realisee


@router.patch("/{idee_id}/statut")
def update_statut(
    idee_id: int,
    body: StatutUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    idee = session.get(Idee, idee_id)
    if not idee:
        raise HTTPException(404, "Idée introuvable")
    idee.statut = body.statut
    session.add(idee)
    session.commit()
    return {"statut": idee.statut}


@router.delete("/{idee_id}", status_code=204)
def delete_idee(
    idee_id: int,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    """Supprimer une idée (admin / CS uniquement)."""
    idee = session.get(Idee, idee_id)
    if not idee:
        raise HTTPException(404, "Idée introuvable")
    # Supprimer les votes associés
    votes = session.exec(select(VoteIdee).where(VoteIdee.idee_id == idee_id)).all()
    for v in votes:
        session.delete(v)
    session.delete(idee)
    session.commit()
