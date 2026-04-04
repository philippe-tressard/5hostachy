"""Router sondages — création, vote, résultats."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    CommentaireSondage, Notification, OptionSondage, Sondage, Utilisateur, VoteSondage, RoleUtilisateur, StatutUtilisateur
)

router = APIRouter(prefix="/sondages", tags=["sondages"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_csv(val: Optional[str]) -> list[str]:
    if not val:
        return []
    return [v.strip() for v in val.split(",") if v.strip()]


def _can_access(s: Sondage, user: Utilisateur) -> bool:
    """Vérifie si l'utilisateur peut voir/voter à ce sondage."""
    # Admins et CS voient toujours tout
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True
    # Filtre profil
    profils = _parse_csv(s.profils_autorises)
    if profils and (user.statut is None or str(user.statut) not in profils):
        return False
    # Filtre bâtiment
    batiments = _parse_csv(s.batiments_ids)
    if batiments:
        if user.batiment_id is None or str(user.batiment_id) not in batiments:
            return False
    return True


def _deny_communaute_for_statut(user: Utilisateur) -> None:
    if user.statut in (StatutUtilisateur.syndic, StatutUtilisateur.mandataire):
        raise HTTPException(403, "La rubrique Communauté n'est pas accessible à votre profil")
    if user.communaute_interdit:
        raise HTTPException(403, "Votre accès à la Communauté a été définitivement suspendu.")
    if user.communaute_ban_jusqu_au and user.communaute_ban_jusqu_au > datetime.utcnow():
        raise HTTPException(403, "Votre accès à la Communauté est suspendu pour une période probatoire d\u2019un mois. À la 2\u1d49 infraction, vous serez banni définitivement.")


# ── schémas ──────────────────────────────────────────────────────────────────

class OptionCreate(BaseModel):
    libelle: str
    ordre: int = 0
    champ_libre: bool = False


class SondageCreate(BaseModel):
    question: str
    description: Optional[str] = None
    cloture_le: Optional[datetime] = None
    resultats_publics: bool = True
    options: list[OptionCreate]
    profils_autorises: Optional[List[str]] = None   # []  = tous les profils
    batiments_ids: Optional[List[int]] = None       # []  = toute la résidence


class SondageRead(BaseModel):
    id: int
    question: str
    description: Optional[str] = None
    cloture_le: Optional[datetime] = None
    cloture_forcee: bool = False
    resultats_publics: bool
    auteur_id: int
    cree_le: datetime
    profils_autorises: Optional[str] = None
    batiments_ids: Optional[str] = None
    nb_votants: int = 0

    class Config:
        from_attributes = True


class OptionRead(BaseModel):
    id: int
    libelle: str
    ordre: int
    nb_votes: int = 0
    champ_libre: bool = False

    class Config:
        from_attributes = True


class SondageDetail(SondageRead):
    options: list[OptionRead] = []
    mon_vote: Optional[int] = None
    cloture: bool = False


# ── endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[SondageRead])
def list_sondages(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    all_s = session.exec(select(Sondage).order_by(Sondage.cree_le.desc())).all()
    accessible = [s for s in all_s if _can_access(s, user)]
    if not accessible:
        return []
    # Compter les votants distincts par sondage en une seule requête
    ids = [s.id for s in accessible]
    counts = session.exec(
        select(VoteSondage.sondage_id, func.count(func.distinct(VoteSondage.user_id)))
        .where(VoteSondage.sondage_id.in_(ids))
        .group_by(VoteSondage.sondage_id)
    ).all()
    count_map = {row[0]: row[1] for row in counts}
    result = []
    for s in accessible:
        d = SondageRead.model_validate(s)
        d.nb_votants = count_map.get(s.id, 0)
        result.append(d)
    return result


@router.get("/{sondage_id}")
def get_sondage(
    sondage_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    s = session.get(Sondage, sondage_id)
    if not s:
        raise HTTPException(404, "Sondage introuvable")
    if not _can_access(s, user):
        raise HTTPException(403, "Vous n'êtes pas autorisé à accéder à ce sondage")

    options_db = session.exec(
        select(OptionSondage).where(OptionSondage.sondage_id == sondage_id)
    ).all()

    mon_vote = session.exec(
        select(VoteSondage).where(
            VoteSondage.sondage_id == sondage_id,
            VoteSondage.user_id == user.id,
        )
    ).first()

    cloture = s.cloture_forcee or (s.cloture_le is not None and s.cloture_le < datetime.utcnow())
    options_out = []
    for opt in sorted(options_db, key=lambda o: o.ordre):
        votes_opt = session.exec(
            select(VoteSondage).where(VoteSondage.option_id == opt.id)
        ).all()
        reponses = [v.reponse_libre for v in votes_opt if v.reponse_libre and v.reponse_libre.strip()]
        options_out.append({
            "id": opt.id, "libelle": opt.libelle, "ordre": opt.ordre,
            "nb_votes": len(votes_opt), "champ_libre": opt.champ_libre,
            "reponses_libres": reponses,
        })

    commentaires_db = session.exec(
        select(CommentaireSondage, Utilisateur)
        .join(Utilisateur, CommentaireSondage.auteur_id == Utilisateur.id)
        .where(CommentaireSondage.sondage_id == sondage_id)
        .order_by(CommentaireSondage.cree_le.asc())
    ).all()
    commentaires_out = [
        {
            "id": c.id, "contenu": c.contenu, "cree_le": c.cree_le,
            "auteur_id": c.auteur_id,
            "auteur_nom": f"{u.prenom} {u.nom}",
        }
        for c, u in commentaires_db
    ]

    return {
        "id": s.id, "question": s.question, "description": s.description,
        "cloture_le": s.cloture_le, "resultats_publics": s.resultats_publics,
        "auteur_id": s.auteur_id, "cree_le": s.cree_le,
        "profils_autorises": s.profils_autorises, "batiments_ids": s.batiments_ids,
        "options": options_out, "mon_vote": mon_vote.option_id if mon_vote else None,
        "cloture": cloture, "cloture_forcee": s.cloture_forcee, "commentaires": commentaires_out,
    }


@router.post("", status_code=201)
def create_sondage(
    body: SondageCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    profils_csv = ",".join(body.profils_autorises) if body.profils_autorises else None
    batiments_csv = ",".join(str(b) for b in body.batiments_ids) if body.batiments_ids else None

    s = Sondage(
        question=body.question,
        description=body.description,
        cloture_le=body.cloture_le,
        resultats_publics=body.resultats_publics,
        auteur_id=user.id,
        profils_autorises=profils_csv,
        batiments_ids=batiments_csv,
    )
    session.add(s)
    session.flush()

    for opt in body.options:
        session.add(OptionSondage(sondage_id=s.id, **opt.model_dump()))

    # Notifier uniquement les résidents ciblés
    q = select(Utilisateur).where(Utilisateur.actif == True, Utilisateur.id != user.id)
    residents = session.exec(q).all()
    profils_list = _parse_csv(profils_csv)
    batiments_list = _parse_csv(batiments_csv)
    for r in residents:
        if profils_list and str(r.statut) not in profils_list:
            continue
        if batiments_list and str(r.batiment_id) not in batiments_list:
            continue
        session.add(Notification(
            destinataire_id=r.id,
            type="sondage",
            titre=f"📊 Nouveau sondage : {s.question[:60]}",
            corps="Votre avis compte — participez au sondage.",
            lien=f"/sondages/{s.id}",
        ))

    session.commit()
    session.refresh(s)
    return s


class VoteBody(BaseModel):
    option_id: int
    commentaire: Optional[str] = None
    reponse_libre: Optional[str] = None


@router.post("/{sondage_id}/voter", status_code=201)
def voter(
    sondage_id: int,
    body: VoteBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    if user.has_role(RoleUtilisateur.externe) and not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        raise HTTPException(403, "Les utilisateurs externes ne peuvent pas voter")
    s = session.get(Sondage, sondage_id)
    if not s:
        raise HTTPException(404, "Sondage introuvable")
    if not _can_access(s, user):
        raise HTTPException(403, "Vous n'\u00eates pas autoris\u00e9 \u00e0 participer \u00e0 ce sondage")
    if s.cloture_forcee or (s.cloture_le and s.cloture_le < datetime.utcnow()):
        raise HTTPException(400, "Ce sondage est clôturé")

    existant = session.exec(
        select(VoteSondage).where(
            VoteSondage.sondage_id == sondage_id,
            VoteSondage.user_id == user.id,
        )
    ).first()
    if existant:
        raise HTTPException(400, "Vous avez déjà voté")

    opt = session.get(OptionSondage, body.option_id)
    if not opt or opt.sondage_id != sondage_id:
        raise HTTPException(400, "Option invalide")

    reponse_libre_val = body.reponse_libre.strip() if body.reponse_libre else None
    session.add(VoteSondage(
        sondage_id=sondage_id, option_id=body.option_id, user_id=user.id,
        reponse_libre=reponse_libre_val,
    ))

    if body.commentaire and body.commentaire.strip():
        session.add(CommentaireSondage(
            sondage_id=sondage_id,
            auteur_id=user.id,
            contenu=body.commentaire.strip(),
        ))

    session.commit()
    return {"message": "Vote enregistré"}


class CommentaireBody(BaseModel):
    contenu: str


@router.post("/{sondage_id}/commenter", status_code=201)
def commenter(
    sondage_id: int,
    body: CommentaireBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    s = session.get(Sondage, sondage_id)
    if not s:
        raise HTTPException(404, "Sondage introuvable")
    if not _can_access(s, user):
        raise HTTPException(403, "Accès refusé")
    if not body.contenu.strip():
        raise HTTPException(400, "Le commentaire ne peut pas être vide")
    c = CommentaireSondage(sondage_id=sondage_id, auteur_id=user.id, contenu=body.contenu.strip())
    session.add(c)
    session.commit()
    session.refresh(c)
    return {"id": c.id, "contenu": c.contenu, "cree_le": c.cree_le,
            "auteur_id": c.auteur_id, "auteur_nom": f"{user.prenom} {user.nom}"}


@router.delete("/{sondage_id}/commentaires/{commentaire_id}", status_code=204)
def supprimer_commentaire(
    sondage_id: int,
    commentaire_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    c = session.get(CommentaireSondage, commentaire_id)
    if not c or c.sondage_id != sondage_id:
        raise HTTPException(404, "Commentaire introuvable")
    # Seuls l'auteur, le CS et l'admin peuvent supprimer
    est_moderateur = user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)
    if c.auteur_id != user.id and not est_moderateur:
        raise HTTPException(403, "Non autorisé")
    session.delete(c)
    session.commit()


# ── Édition / suppression / clôture anticipée ──────────────────────────────

class SondageUpdate(BaseModel):
    question: Optional[str] = None
    description: Optional[str] = None
    cloture_le: Optional[datetime] = None
    resultats_publics: Optional[bool] = None


@router.patch("/{sondage_id}")
def modifier_sondage(
    sondage_id: int,
    body: SondageUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Modifier un sondage (auteur ou admin)."""
    s = session.get(Sondage, sondage_id)
    if not s:
        raise HTTPException(404, "Sondage introuvable")
    est_admin = user.has_role(RoleUtilisateur.admin)
    if s.auteur_id != user.id and not est_admin:
        raise HTTPException(403, "Seul l'auteur ou un admin peut modifier ce sondage")
    if s.cloture_forcee or (s.cloture_le and s.cloture_le < datetime.utcnow()):
        raise HTTPException(400, "Ce sondage est clôturé et ne peut plus être modifié")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(s, field, val)
    session.add(s)
    session.commit()
    session.refresh(s)
    return {"id": s.id, "question": s.question, "description": s.description,
            "cloture_le": s.cloture_le, "resultats_publics": s.resultats_publics}


@router.delete("/{sondage_id}", status_code=204)
def supprimer_sondage(
    sondage_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Supprimer un sondage et toutes ses données (auteur ou admin)."""
    s = session.get(Sondage, sondage_id)
    if not s:
        raise HTTPException(404, "Sondage introuvable")
    est_admin = user.has_role(RoleUtilisateur.admin)
    if s.auteur_id != user.id and not est_admin:
        raise HTTPException(403, "Seul l'auteur ou un admin peut supprimer ce sondage")
    # Suppression en cascade
    for c in session.exec(select(CommentaireSondage).where(CommentaireSondage.sondage_id == sondage_id)).all():
        session.delete(c)
    for v in session.exec(select(VoteSondage).where(VoteSondage.sondage_id == sondage_id)).all():
        session.delete(v)
    for o in session.exec(select(OptionSondage).where(OptionSondage.sondage_id == sondage_id)).all():
        session.delete(o)
    session.delete(s)
    session.commit()


@router.patch("/{sondage_id}/cloturer", status_code=200)
def cloturer_sondage(
    sondage_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Stopper un sondage immédiatement (auteur ou admin)."""
    s = session.get(Sondage, sondage_id)
    if not s:
        raise HTTPException(404, "Sondage introuvable")
    est_admin = user.has_role(RoleUtilisateur.admin)
    if s.auteur_id != user.id and not est_admin:
        raise HTTPException(403, "Seul l'auteur ou un admin peut clôturer ce sondage")
    s.cloture_forcee = True
    session.add(s)
    session.commit()
    return {"message": "Sondage clôturé"}
