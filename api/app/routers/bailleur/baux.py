"""Le cycle de vie d'un bail — le créer, le lire, le corriger, le terminer.

Y est jointe la RECHERCHE d'un locataire inscrit : elle ne sert qu'ici, au
moment de rattacher un compte à un bail qu'on crée ou qu'on corrige.

⚠️ `ObjetOut` et `BailOut` viennent de `commun` : ce sont les schémas que les
quatre modules partagent. Les redéclarer donnerait deux formes de la même
réponse, libres de diverger au premier champ ajouté.
"""
from datetime import date, datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.deps import require_cs_or_admin, require_proprietaire
from app.database import get_session
from app.models.core import (
    LocationBail, RemiseObjet, Lot, StatutBail, StatutUtilisateur, Utilisateur, Vigik, Telecommande,
)
from pydantic import BaseModel

from .commun import BailCreate, BailCreateMulti, BailOut, BailTerminer, BailUpdate, get_bail_or_404

router = APIRouter()

# ── Routes baux ──────────────────────────────────────────────────────────────

@router.get("/mes-baux", response_model=List[BailOut])
def mes_baux(
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    baux = session.exec(
        select(LocationBail).where(LocationBail.bailleur_id == user.id)
        .order_by(LocationBail.cree_le.desc())
    ).all()
    return baux


@router.get("/tous-les-baux", response_model=List[BailOut])
def tous_les_baux(
    user: Utilisateur = Depends(require_cs_or_admin),
    session: Session = Depends(get_session),
):
    """Admin / CS : liste de tous les baux (tous statuts, tous bailleurs)."""
    return session.exec(
        select(LocationBail).order_by(LocationBail.cree_le.desc())
    ).all()


@router.delete("/baux/{bail_id}", status_code=204)
def supprimer_bail(
    bail_id: int,
    user: Utilisateur = Depends(require_cs_or_admin),
    session: Session = Depends(get_session),
):
    """Admin / CS : supprimer un bail et ses objets associés."""
    bail = session.get(LocationBail, bail_id)
    if not bail:
        raise HTTPException(status_code=404, detail="Bail introuvable")
    # Libérer les accès confiés au locataire
    for v in session.exec(select(Vigik).where(Vigik.bail_id == bail_id)).all():
        v.chez_locataire = False
        v.bail_id = None
        session.add(v)
    for tc in session.exec(select(Telecommande).where(Telecommande.bail_id == bail_id)).all():
        tc.chez_locataire = False
        tc.bail_id = None
        session.add(tc)
    # Supprimer les objets remis
    for obj in session.exec(select(RemiseObjet).where(RemiseObjet.bail_id == bail_id)).all():
        session.delete(obj)
    session.delete(bail)
    session.commit()


@router.post("/lots/{lot_id}/bail", response_model=BailOut, status_code=201)
def creer_bail(
    lot_id: int,
    data: BailCreate,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    lot = session.get(Lot, lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot introuvable")

    # Vérifier qu'il n'y a pas déjà un bail actif
    bail_actif = session.exec(
        select(LocationBail).where(
            LocationBail.lot_id == lot_id,
            LocationBail.statut.in_([StatutBail.actif, StatutBail.en_cours_sortie]),
        )
    ).first()
    if bail_actif:
        raise HTTPException(status_code=409, detail="Ce lot a déjà un bail en cours")

    now = datetime.utcnow()
    bail = LocationBail(
        lot_id=lot_id,
        bailleur_id=user.id,
        locataire_id=data.locataire_id,
        locataire_nom=data.locataire_nom,
        locataire_prenom=data.locataire_prenom,
        locataire_email=data.locataire_email,
        locataire_telephone=data.locataire_telephone,
        date_entree=data.date_entree,
        date_sortie_prevue=data.date_sortie_prevue,
        notes=data.notes,
        statut=StatutBail.actif,
        cree_le=now,
        mis_a_jour_le=now,
    )
    session.add(bail)
    session.commit()
    session.refresh(bail)
    return bail


@router.post("/baux/creer-multi", response_model=List[BailOut], status_code=201)
def creer_bail_multi(
    data: BailCreateMulti,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    """Créer un bail sur plusieurs lots en une seule opération."""
    if not data.lot_ids:
        raise HTTPException(status_code=422, detail="Au moins un lot est requis")

    created: List[LocationBail] = []
    now = datetime.utcnow()
    for lot_id in data.lot_ids:
        lot = session.get(Lot, lot_id)
        if not lot:
            raise HTTPException(status_code=404, detail=f"Lot {lot_id} introuvable")
        bail_actif = session.exec(
            select(LocationBail).where(
                LocationBail.lot_id == lot_id,
                LocationBail.statut.in_([StatutBail.actif, StatutBail.en_cours_sortie]),
            )
        ).first()
        if bail_actif:
            raise HTTPException(
                status_code=409,
                detail=f"Le lot {lot.numero} a déjà un bail en cours",
            )
        bail = LocationBail(
            lot_id=lot_id,
            bailleur_id=user.id,
            locataire_id=data.locataire_id,
            locataire_nom=data.locataire_nom,
            locataire_prenom=data.locataire_prenom,
            locataire_email=data.locataire_email,
            locataire_telephone=data.locataire_telephone,
            date_entree=data.date_entree,
            date_sortie_prevue=data.date_sortie_prevue,
            notes=data.notes,
            statut=StatutBail.actif,
            cree_le=now,
            mis_a_jour_le=now,
        )
        session.add(bail)
        created.append(bail)
    session.commit()
    for b in created:
        session.refresh(b)
    return created


@router.get("/baux/{bail_id}", response_model=BailOut)
def get_bail(
    bail_id: int,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    return get_bail_or_404(bail_id, user, session)


@router.patch("/baux/{bail_id}", response_model=BailOut)
def update_bail(
    bail_id: int,
    data: BailUpdate,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    bail = get_bail_or_404(bail_id, user, session)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(bail, k, v)
    bail.mis_a_jour_le = datetime.utcnow()
    session.add(bail)
    session.commit()
    session.refresh(bail)
    return bail


@router.post("/baux/{bail_id}/terminer", response_model=BailOut)
def terminer_bail(
    bail_id: int,
    data: BailTerminer,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    bail = get_bail_or_404(bail_id, user, session)
    # Retour automatique de tous les accès confiés au locataire
    for v in session.exec(select(Vigik).where(Vigik.bail_id == bail_id, Vigik.user_id == user.id)).all():
        v.chez_locataire = False
        v.bail_id = None
        session.add(v)
    for tc in session.exec(select(Telecommande).where(Telecommande.bail_id == bail_id, Telecommande.user_id == user.id)).all():
        tc.chez_locataire = False
        tc.bail_id = None
        session.add(tc)
    bail.statut = StatutBail.termine
    bail.date_sortie_reelle = data.date_sortie_reelle or date.today()
    bail.mis_a_jour_le = datetime.utcnow()
    session.add(bail)
    session.commit()
    session.refresh(bail)
    return bail



# ── Recherche locataire inscrit ────────────────────────────────────────────────

class LocataireInfo(BaseModel):
    id: int
    nom: str
    prenom: str
    email: str
    actif: bool

    class Config:
        from_attributes = True


@router.get("/locataires-suggeres", response_model=List[LocataireInfo])
def locataires_suggeres(
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    """Locataires inscrits qui ont déclaré ce bailleur dans leur nom_proprietaire."""
    bailleur_mots = {m for m in f"{user.prenom} {user.nom}".lower().split() if len(m) > 2}
    if not bailleur_mots:
        return []
    candidats = session.exec(
        select(Utilisateur).where(
            Utilisateur.statut == StatutUtilisateur.locataire,
            Utilisateur.nom_proprietaire.isnot(None),  # type: ignore[attr-defined]
        )
    ).all()
    result = []
    for u in candidats:
        if not u.nom_proprietaire:
            continue
        np = u.nom_proprietaire.lower()
        if any(mot in np for mot in bailleur_mots):
            result.append(LocataireInfo(id=u.id, nom=u.nom, prenom=u.prenom, email=u.email, actif=u.actif))
    return result


@router.get("/search-locataire", response_model=List[LocataireInfo])
def search_locataire(
    q: str,
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    """Chercher un utilisateur inscrit par email ou nom/prénom pour l'associer à un bail."""
    q = q.strip()
    if not q:
        return []
    if "@" in q:
        # Recherche exacte par email
        results = session.exec(
            select(Utilisateur).where(Utilisateur.email == q.lower())
        ).all()
    else:
        # Recherche partielle insensible à la casse par nom ou prénom
        pattern = f"%{q.lower()}%"
        results = session.exec(
            select(Utilisateur).where(
                (Utilisateur.nom.ilike(pattern))
                | (Utilisateur.prenom.ilike(pattern))
            ).limit(10)
        ).all()
    return [
        LocataireInfo(id=u.id, nom=u.nom, prenom=u.prenom, email=u.email, actif=u.actif)
        for u in results
    ]
