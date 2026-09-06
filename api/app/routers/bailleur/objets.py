"""L'inventaire d'un bail — ce qui a été remis au locataire, et ce qu'il rend.

## Ce que ces cinq routes gouvernent

Une remise (`POST`), une correction (`PATCH`), un retour ou une perte
(`POST …/retour`), une suppression, et la lecture.

🔴 **Le retour a son propre geste, et ce n'est pas un caprice** : il pose le
statut ET la date ensemble. `ObjetUpdate` ne les expose donc pas — les ouvrir
donnerait deux chemins vers le même fait, dont un capable d'écrire « rendu »
sans date.

⚠️ Jusqu'au 06/09/2026, `POST …/objets` n'était appelé par AUCUN écran, et
`BailCreateMulti` ne porte pas d'objets : il était donc impossible d'enregistrer
quoi que ce soit dans cet inventaire. L'écran manquait, pas le serveur (#806).
"""
from datetime import date, datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.deps import require_proprietaire
from app.database import get_session
from app.models.core import (
    RemiseObjet, StatutObjet, Utilisateur,
)

from .commun import ObjetCreate, ObjetOut, ObjetUpdate, RetourObjet, get_bail_or_404

router = APIRouter()

# ── Routes objets ─────────────────────────────────────────────────────────────

@router.get("/baux/{bail_id}/objets", response_model=List[ObjetOut])
def list_objets(
    bail_id: int,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    get_bail_or_404(bail_id, user, session)
    objets = session.exec(
        select(RemiseObjet).where(RemiseObjet.bail_id == bail_id)
    ).all()
    return objets


@router.post("/baux/{bail_id}/objets", response_model=ObjetOut, status_code=201)
def ajouter_objet(
    bail_id: int,
    data: ObjetCreate,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    get_bail_or_404(bail_id, user, session)
    objet = RemiseObjet(
        bail_id=bail_id,
        type=data.type,
        libelle=data.libelle,
        quantite=data.quantite,
        reference=data.reference,
        statut=StatutObjet.en_possession,
        remis_le=data.remis_le,
        notes=data.notes,
        cree_le=datetime.utcnow(),
    )
    session.add(objet)
    session.commit()
    session.refresh(objet)
    return objet


@router.patch("/baux/{bail_id}/objets/{obj_id}", response_model=ObjetOut)
def update_objet(
    bail_id: int,
    obj_id: int,
    data: ObjetUpdate,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    get_bail_or_404(bail_id, user, session)
    objet = session.get(RemiseObjet, obj_id)
    if not objet or objet.bail_id != bail_id:
        raise HTTPException(status_code=404, detail="Objet introuvable")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(objet, k, v)
    session.add(objet)
    session.commit()
    session.refresh(objet)
    return objet


@router.post("/baux/{bail_id}/objets/{obj_id}/retour", response_model=ObjetOut)
def retour_objet(
    bail_id: int,
    obj_id: int,
    data: RetourObjet,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    get_bail_or_404(bail_id, user, session)
    objet = session.get(RemiseObjet, obj_id)
    if not objet or objet.bail_id != bail_id:
        raise HTTPException(status_code=404, detail="Objet introuvable")
    objet.statut = StatutObjet.perdu if data.perdu else StatutObjet.rendu
    objet.rendu_le = data.rendu_le or date.today()
    session.add(objet)
    session.commit()
    session.refresh(objet)
    return objet


@router.delete("/baux/{bail_id}/objets/{obj_id}", status_code=204)
def supprimer_objet(
    bail_id: int,
    obj_id: int,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    get_bail_or_404(bail_id, user, session)
    objet = session.get(RemiseObjet, obj_id)
    if not objet or objet.bail_id != bail_id:
        raise HTTPException(status_code=404, detail="Objet introuvable")
    session.delete(objet)
    session.commit()
