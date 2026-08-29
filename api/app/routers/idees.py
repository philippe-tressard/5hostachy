"""Router boîte à idées — idées + upvotes + réponses."""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, peut_commenter, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Idee,
    ReponseCommunaute,
    RoleUtilisateur,
    Utilisateur,
    VoteIdee,
)
from app.utils.communaute import exiger_acces
from app.utils.liens import lien_element
from app.utils.reponses import (
    auteur_meta,
    enrich_reponse,
    notifier_nouvelle_reponse,
    notifier_votants_idee,
    tri_reponses,
)

router = APIRouter(prefix="/idees", tags=["idées"])

RUBRIQUE = "idee"

# Statuts « positifs » qui déclenchent une notification aux votants.
_STATUT_NOTIF_LABELS = {"retenue": "Retenue", "realisee": "Réalisée"}


def _reponses_for(idee_id: int, session: Session) -> list[dict]:
    """Réponses d'une idée : CS/admin en tête (plus de poids), puis chronologique."""
    reps = session.exec(
        select(ReponseCommunaute).where(
            ReponseCommunaute.rubrique == RUBRIQUE,
            ReponseCommunaute.cible_id == idee_id,
        )
    ).all()
    return tri_reponses([enrich_reponse(r, session) for r in reps])


class IdeeCreate(BaseModel):
    titre: str
    description: str
    #  Le périmètre arrive en LISTE de codes et se stocke en JSON : c'est la forme
    #  que `PerimetrePicker` produit et que `perimetreLabel` sait lire, des deux
    #  côtés. Vide vaut « toute la copropriété », comme partout ailleurs.
    perimetre_cible: Optional[list[str]] = None


class IdeeRead(BaseModel):
    id: int
    titre: str
    description: str
    auteur_id: int
    statut: str
    perimetre_cible: list[str] = []
    nb_votes: int = 0
    mon_vote: bool = False

    class Config:
        from_attributes = True


def _perimetre_liste(brut: Optional[str]) -> list[str]:
    """La colonne stocke un tableau JSON ; l'API expose une liste.

    ⚠️ Une valeur illisible rend le DÉFAUT et non une liste vide : `[]` signifierait
    « aucune restriction » côté visibilité, ce qui est le même effet ici, mais
    afficherait un badge 🔹 vide côté carte. Retomber sur le périmètre par défaut
    est le comportement qu'avaient toutes les idées avant la migration 0153.
    """
    if not brut:
        return ["résidence"]
    try:
        valeur = json.loads(brut)
    except (TypeError, ValueError):
        return ["résidence"]
    return valeur if isinstance(valeur, list) else ["résidence"]


def _enrich(idees: list, user_id: int, session: Session) -> list[dict]:
    result = []
    for idee in idees:
        nb = len(session.exec(select(VoteIdee).where(VoteIdee.idee_id == idee.id)).all())
        mon_vote = bool(session.exec(
            select(VoteIdee).where(VoteIdee.idee_id == idee.id, VoteIdee.user_id == user_id)
        ).first())
        reponses = _reponses_for(idee.id, session)
        result.append({
            "id": idee.id, "titre": idee.titre, "description": idee.description,
            "auteur_id": idee.auteur_id, "statut": idee.statut,
            #  Exposé en LISTE pour que le front n'ait rien à désérialiser — même
            #  contrat que les événements et les annonces.
            "perimetre_cible": _perimetre_liste(idee.perimetre_cible),
            "cree_le": idee.cree_le, "nb_votes": nb, "mon_vote": mon_vote,
            "reponses": reponses, "nb_reponses": len(reponses),
        })
    return result


@router.get("")
def list_idees(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    idees = session.exec(select(Idee).order_by(Idee.cree_le.desc())).all()
    return _enrich(idees, user.id, session)


@router.post("", status_code=201)
def create_idee(
    body: IdeeCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    if user.has_role(RoleUtilisateur.externe) and not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        raise HTTPException(403, "Les utilisateurs externes ne peuvent pas soumettre d'idées")
    idee = Idee(
        titre=body.titre, description=body.description, auteur_id=user.id,
        #  Liste vide == aucune restriction : on retombe sur le défaut, comme le
        #  serveur le fait déjà pour les publications et les sondages.
        perimetre_cible=json.dumps(body.perimetre_cible or ["résidence"], ensure_ascii=False),
    )
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
    exiger_acces(user)
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
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    idee = session.get(Idee, idee_id)
    if not idee:
        raise HTTPException(404, "Idée introuvable")
    ancien = idee.statut
    idee.statut = body.statut
    if body.statut != ancien:
        #  ⚠️ Horodater le CHANGEMENT, pas la requête : c'est cette date que lit
        #  l'archivage automatique (`app/utils/archivage.py`). La renseigner à
        #  chaque appel, même sans changement, repousserait l'archivage d'un mois
        #  à chaque clic — le défaut que `PetiteAnnonce` évite déjà en se datant
        #  sur `statut_change_le` et non sur `mis_a_jour_le`.
        idee.statut_change_le = datetime.utcnow()
    session.add(idee)
    # Passage à un statut positif (retenue/réalisée) → prévenir les votants.
    if body.statut != ancien and body.statut in _STATUT_NOTIF_LABELS:
        votant_ids = [
            v.user_id for v in session.exec(
                select(VoteIdee).where(VoteIdee.idee_id == idee_id)
            ).all()
        ]
        notifier_votants_idee(
            session, background_tasks,
            votant_ids=votant_ids,
            idee_titre=idee.titre,
            statut_label=_STATUT_NOTIF_LABELS[body.statut],
            # Onglet + ancre : la Communauté a trois rubriques, `/sondages` seul
            # déposait le lecteur sur les sondages (cf. app/utils/liens.py).
            lien_path=lien_element("idee", idee_id),
            exclure_id=user.id,
        )
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
    # Supprimer les votes + réponses associés
    votes = session.exec(select(VoteIdee).where(VoteIdee.idee_id == idee_id)).all()
    for v in votes:
        session.delete(v)
    reps = session.exec(
        select(ReponseCommunaute).where(
            ReponseCommunaute.rubrique == RUBRIQUE,
            ReponseCommunaute.cible_id == idee_id,
        )
    ).all()
    for r in reps:
        session.delete(r)
    session.delete(idee)
    session.commit()


# ── Réponses aux idées ─────────────────────────────────────────────────────────

class ReponseCreate(BaseModel):
    contenu: str


@router.get("/{idee_id}/reponses")
def list_reponses(
    idee_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    idee = session.get(Idee, idee_id)
    if not idee:
        raise HTTPException(404, "Idée introuvable")
    return _reponses_for(idee_id, session)


@router.post("/{idee_id}/reponses", status_code=201)
def create_reponse(
    idee_id: int,
    body: ReponseCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    if user.has_role(RoleUtilisateur.externe) and not user.has_role(
        RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin
    ):
        raise HTTPException(403, "Les utilisateurs externes ne peuvent pas répondre")
    contenu = (body.contenu or "").strip()
    if not contenu:
        raise HTTPException(422, "La réponse ne peut pas être vide")
    idee = session.get(Idee, idee_id)
    if not idee:
        raise HTTPException(404, "Idée introuvable")
    rep = ReponseCommunaute(rubrique=RUBRIQUE, cible_id=idee_id, auteur_id=user.id, contenu=contenu)
    session.add(rep)
    # Notifier le créateur de l'idée (in-app + email selon préférences)
    notifier_nouvelle_reponse(
        session, background_tasks,
        createur_id=idee.auteur_id, auteur=user,
        rubrique_label="votre idée", sujet=idee.titre,
        extrait=contenu, lien_path=lien_element("idee", idee_id),
    )
    session.commit()
    session.refresh(rep)
    return {"id": rep.id, "cible_id": rep.cible_id, "auteur_id": rep.auteur_id,
            "contenu": rep.contenu, "cree_le": rep.cree_le, **auteur_meta(user, session)}


@router.delete("/{idee_id}/reponses/{rep_id}", status_code=204)
def delete_reponse(
    idee_id: int,
    rep_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Supprimer une réponse : son auteur, ou un CS/admin."""
    exiger_acces(user)
    rep = session.get(ReponseCommunaute, rep_id)
    if not rep or rep.rubrique != RUBRIQUE or rep.cible_id != idee_id:
        raise HTTPException(404, "Réponse introuvable")
    #  L'auteur, ou un modérateur — règle du module central.
    if not peut_commenter(rep, user):
        raise HTTPException(403, "Vous ne pouvez supprimer que vos propres réponses")
    session.delete(rep)
    session.commit()
