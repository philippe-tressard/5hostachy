"""
Endpoints bailleur — gestion du bail locatif et inventaire des objets remis.
Accès réservé aux copropriétaires bailleurs (et admin / CS en lecture).
"""
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    LocationBail, RemiseObjet, Lot, Batiment,
    StatutBail, StatutObjet, TypeObjet,
    StatutUtilisateur, Utilisateur, RoleUtilisateur,
    Vigik, Telecommande, StatutAcces,
)

router = APIRouter(prefix="/bailleur", tags=["bailleur"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _require_bailleur(user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    if not user.has_role(RoleUtilisateur.propriétaire, RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé aux propriétaires")
    return user


def _get_bail_or_404(bail_id: int, user: Utilisateur, session: Session) -> LocationBail:
    bail = session.get(LocationBail, bail_id)
    if not bail:
        raise HTTPException(status_code=404, detail="Bail introuvable")
    if bail.bailleur_id != user.id and not user.has_role("admin", "conseil_syndical"):
        raise HTTPException(status_code=403, detail="Accès interdit")
    return bail


# ── Schemas in / out ─────────────────────────────────────────────────────────

class ObjetOut(BaseModel):
    id: int
    bail_id: int
    type: TypeObjet
    libelle: str
    quantite: int
    reference: Optional[str]
    statut: StatutObjet
    remis_le: Optional[date]
    rendu_le: Optional[date]
    notes: Optional[str]
    cree_le: datetime

    class Config:
        from_attributes = True


class BailOut(BaseModel):
    id: int
    lot_id: int
    bailleur_id: int
    locataire_id: Optional[int]
    locataire_nom: Optional[str]
    locataire_prenom: Optional[str]
    locataire_email: Optional[str]
    locataire_telephone: Optional[str]
    date_entree: date
    date_sortie_prevue: Optional[date]
    date_sortie_reelle: Optional[date]
    statut: StatutBail
    notes: Optional[str]
    cree_le: datetime
    mis_a_jour_le: datetime
    objets: List[ObjetOut] = []

    class Config:
        from_attributes = True


class BailCreate(BaseModel):
    lot_id: int
    locataire_id: Optional[int] = None
    locataire_nom: Optional[str] = None
    locataire_prenom: Optional[str] = None
    locataire_email: Optional[str] = None
    locataire_telephone: Optional[str] = None
    date_entree: date
    date_sortie_prevue: Optional[date] = None
    notes: Optional[str] = None


class BailCreateMulti(BaseModel):
    """Création d'un bail sur plusieurs lots simultanément (un LocationBail par lot)."""
    lot_ids: List[int]
    locataire_id: Optional[int] = None
    locataire_nom: Optional[str] = None
    locataire_prenom: Optional[str] = None
    locataire_email: Optional[str] = None
    locataire_telephone: Optional[str] = None
    date_entree: date
    date_sortie_prevue: Optional[date] = None
    notes: Optional[str] = None


class BailUpdate(BaseModel):
    locataire_id: Optional[int] = None
    locataire_nom: Optional[str] = None
    locataire_prenom: Optional[str] = None
    locataire_email: Optional[str] = None
    locataire_telephone: Optional[str] = None
    date_sortie_prevue: Optional[date] = None
    notes: Optional[str] = None


class BailTerminer(BaseModel):
    date_sortie_reelle: Optional[date] = None


class ObjetCreate(BaseModel):
    type: TypeObjet = TypeObjet.autre
    libelle: str
    quantite: int = 1
    reference: Optional[str] = None
    remis_le: Optional[date] = None
    notes: Optional[str] = None


class ObjetUpdate(BaseModel):
    libelle: Optional[str] = None
    quantite: Optional[int] = None
    reference: Optional[str] = None
    notes: Optional[str] = None


class RetourObjet(BaseModel):
    rendu_le: Optional[date] = None
    perdu: bool = False


# ── Routes baux ──────────────────────────────────────────────────────────────

@router.get("/mes-baux", response_model=List[BailOut])
def mes_baux(
    user: Utilisateur = Depends(_require_bailleur),
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
    user: Utilisateur = Depends(_require_bailleur),
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
    user: Utilisateur = Depends(_require_bailleur),
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
    user: Utilisateur = Depends(_require_bailleur),
    session: Session = Depends(get_session),
):
    return _get_bail_or_404(bail_id, user, session)


@router.patch("/baux/{bail_id}", response_model=BailOut)
def update_bail(
    bail_id: int,
    data: BailUpdate,
    user: Utilisateur = Depends(_require_bailleur),
    session: Session = Depends(get_session),
):
    bail = _get_bail_or_404(bail_id, user, session)
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
    user: Utilisateur = Depends(_require_bailleur),
    session: Session = Depends(get_session),
):
    bail = _get_bail_or_404(bail_id, user, session)
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


# ── Routes objets ─────────────────────────────────────────────────────────────

@router.get("/baux/{bail_id}/objets", response_model=List[ObjetOut])
def list_objets(
    bail_id: int,
    user: Utilisateur = Depends(_require_bailleur),
    session: Session = Depends(get_session),
):
    _get_bail_or_404(bail_id, user, session)
    objets = session.exec(
        select(RemiseObjet).where(RemiseObjet.bail_id == bail_id)
    ).all()
    return objets


@router.post("/baux/{bail_id}/objets", response_model=ObjetOut, status_code=201)
def ajouter_objet(
    bail_id: int,
    data: ObjetCreate,
    user: Utilisateur = Depends(_require_bailleur),
    session: Session = Depends(get_session),
):
    _get_bail_or_404(bail_id, user, session)
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
    user: Utilisateur = Depends(_require_bailleur),
    session: Session = Depends(get_session),
):
    _get_bail_or_404(bail_id, user, session)
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
    user: Utilisateur = Depends(_require_bailleur),
    session: Session = Depends(get_session),
):
    _get_bail_or_404(bail_id, user, session)
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
    user: Utilisateur = Depends(_require_bailleur),
    session: Session = Depends(get_session),
):
    _get_bail_or_404(bail_id, user, session)
    objet = session.get(RemiseObjet, obj_id)
    if not objet or objet.bail_id != bail_id:
        raise HTTPException(status_code=404, detail="Objet introuvable")
    session.delete(objet)
    session.commit()


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
    user: Utilisateur = Depends(_require_bailleur),
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
    user: Utilisateur = Depends(_require_bailleur),
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


# ── Accès (Vigik / Télécommandes) liés à un bail ────────────────────────────

class AccesOut(BaseModel):
    id: int
    code: str
    type: str  # vigik | telecommande
    lot_id: Optional[int]
    lot_type: Optional[str] = None
    lot_label: Optional[str] = None
    statut: StatutAcces
    chez_locataire: bool
    bail_id: Optional[int]
    eligible_transfert: bool = False
    recommande: bool = False
    motif_non_eligible: Optional[str] = None
    cree_le: datetime

    class Config:
        from_attributes = True


class TransfertAccesIn(BaseModel):
    vigik_ids: List[int] = []
    tc_ids: List[int] = []


@router.get("/mes-acces", response_model=List[AccesOut])
def mes_acces(
    user: Utilisateur = Depends(_require_bailleur),
    session: Session = Depends(get_session),
):
    """Bailleur : voir tous ses Vigik et TC avec leur statut de présence."""
    vigiks = session.exec(select(Vigik).where(Vigik.user_id == user.id)).all()
    tcs = session.exec(select(Telecommande).where(Telecommande.user_id == user.id)).all()
    result = []
    lot_map = {l.id: l for l in session.exec(select(Lot)).all()}

    def _lot_info(lot_id: Optional[int]) -> tuple[Optional[str], Optional[str]]:
        lot = lot_map.get(lot_id) if lot_id else None
        if not lot:
            return None, None
        lot_type = lot.type.value if hasattr(lot.type, "value") else str(lot.type)
        bat = session.get(Batiment, lot.batiment_id) if lot.batiment_id else None
        bat_label = f"Bât. {bat.numero}" if bat else "Sans bâtiment"
        return lot_type, f"{bat_label} — Lot {lot.numero}"

    for v in vigiks:
        lot_type, lot_label = _lot_info(v.lot_id)
        result.append(AccesOut(id=v.id, code=v.code, type="vigik", lot_id=v.lot_id,
                                lot_type=lot_type, lot_label=lot_label,
                                statut=v.statut, chez_locataire=v.chez_locataire,
                                bail_id=v.bail_id, cree_le=v.cree_le))
    for tc in tcs:
        lot_type, lot_label = _lot_info(tc.lot_id)
        result.append(AccesOut(id=tc.id, code=tc.code, type="telecommande", lot_id=tc.lot_id,
                                lot_type=lot_type, lot_label=lot_label,
                                statut=tc.statut, chez_locataire=tc.chez_locataire,
                                bail_id=tc.bail_id, cree_le=tc.cree_le))
    return result


@router.get("/baux/{bail_id}/acces", response_model=List[AccesOut])
def acces_du_bail(
    bail_id: int,
    user: Utilisateur = Depends(_require_bailleur),
    session: Session = Depends(get_session),
):
    """Accès (Vigik+TC) du bailleur avec règles d'éligibilité de transfert."""
    bail = _get_bail_or_404(bail_id, user, session)
    bail_lot = session.get(Lot, bail.lot_id)
    bail_lot_type = (bail_lot.type.value if (bail_lot and hasattr(bail_lot.type, "value")) else str(bail_lot.type)) if bail_lot else ""
    vigiks = session.exec(select(Vigik).where(Vigik.user_id == user.id)).all()
    tcs = session.exec(select(Telecommande).where(Telecommande.user_id == user.id)).all()
    lot_map = {l.id: l for l in session.exec(select(Lot)).all()}

    def _lot_info(lot_id: Optional[int]) -> tuple[Optional[str], Optional[str]]:
        lot = lot_map.get(lot_id) if lot_id else None
        if not lot:
            return None, None
        lot_type = lot.type.value if hasattr(lot.type, "value") else str(lot.type)
        bat = session.get(Batiment, lot.batiment_id) if lot.batiment_id else None
        bat_label = f"Bât. {bat.numero}" if bat else "Sans bâtiment"
        return lot_type, f"{bat_label} — Lot {lot.numero}"

    def _eligibility(acces_type: str, lot_type: Optional[str], statut: StatutAcces, chez_locataire: bool, current_bail_id: Optional[int]) -> tuple[bool, Optional[str]]:
        if statut != StatutAcces.actif:
            return False, "Accès inactif"
        if chez_locataire and current_bail_id != bail_id:
            return False, "Déjà affecté à un autre bail"
        if acces_type == "vigik":
            if bail_lot_type != "appartement":
                return False, "Vigik non autorisé pour un bail parking/cave"
            if lot_type in ("parking", "cave"):
                return False, "Vigik issu d'un lot parking/cave non applicable"
        return True, None

    result = []
    # Bail parking/cave : pas de Vigik affiché (TC uniquement)
    if bail_lot_type == "appartement":
        for v in vigiks:
            lot_type, lot_label = _lot_info(v.lot_id)
            eligible, reason = _eligibility("vigik", lot_type, v.statut, v.chez_locataire, v.bail_id)
            recommended = bool(eligible and not v.chez_locataire and (v.lot_id is None or v.lot_id == bail.lot_id))
            result.append(AccesOut(id=v.id, code=v.code, type="vigik", lot_id=v.lot_id,
                                    lot_type=lot_type, lot_label=lot_label,
                                    statut=v.statut, chez_locataire=v.chez_locataire,
                                    bail_id=v.bail_id,
                                    eligible_transfert=eligible,
                                    recommande=recommended,
                                    motif_non_eligible=reason,
                                    cree_le=v.cree_le))
    for tc in tcs:
        lot_type, lot_label = _lot_info(tc.lot_id)
        eligible, reason = _eligibility("telecommande", lot_type, tc.statut, tc.chez_locataire, tc.bail_id)
        recommended = bool(eligible and not tc.chez_locataire and (tc.lot_id is None or tc.lot_id == bail.lot_id))
        result.append(AccesOut(id=tc.id, code=tc.code, type="telecommande", lot_id=tc.lot_id,
                                lot_type=lot_type, lot_label=lot_label,
                                statut=tc.statut, chez_locataire=tc.chez_locataire,
                                bail_id=tc.bail_id,
                                eligible_transfert=eligible,
                                recommande=recommended,
                                motif_non_eligible=reason,
                                cree_le=tc.cree_le))
    return result


@router.post("/baux/{bail_id}/transferer-acces", response_model=List[AccesOut])
def transferer_acces(
    bail_id: int,
    data: TransfertAccesIn,
    user: Utilisateur = Depends(_require_bailleur),
    session: Session = Depends(get_session),
):
    """Marquer des Vigik/TC comme étant chez le locataire."""
    bail = _get_bail_or_404(bail_id, user, session)
    if bail.statut == StatutBail.termine:
        raise HTTPException(400, "Bail terminé — impossible de transférer des accès")
    bail_lot = session.get(Lot, bail.lot_id)
    bail_lot_type = (bail_lot.type.value if (bail_lot and hasattr(bail_lot.type, "value")) else str(bail_lot.type)) if bail_lot else ""
    lot_map = {l.id: l for l in session.exec(select(Lot)).all()}

    def _assert_transferable(acces_type: str, lot_id: Optional[int], statut: StatutAcces, chez_locataire: bool, current_bail_id: Optional[int]):
        if statut != StatutAcces.actif:
            raise HTTPException(400, "Certains accès sélectionnés sont inactifs")
        if chez_locataire and current_bail_id != bail_id:
            raise HTTPException(400, "Un ou plusieurs accès sont déjà affectés à un autre bail")
        lot = lot_map.get(lot_id) if lot_id else None
        lot_type = (lot.type.value if (lot and hasattr(lot.type, "value")) else str(lot.type)) if lot else None
        if acces_type == "vigik":
            if bail_lot_type != "appartement":
                raise HTTPException(400, "Vigik non autorisé pour un bail parking/cave")
            if lot_type is not None and lot_type != "appartement":
                raise HTTPException(400, "Vigik uniquement issu d'un lot appartement")

    updated = []
    for vid in data.vigik_ids:
        v = session.get(Vigik, vid)
        if v and v.user_id == user.id:
            _assert_transferable("vigik", v.lot_id, v.statut, v.chez_locataire, v.bail_id)
            v.chez_locataire = True
            v.bail_id = bail_id
            session.add(v)
            updated.append(AccesOut(id=v.id, code=v.code, type="vigik", lot_id=v.lot_id,
                                     statut=v.statut, chez_locataire=v.chez_locataire,
                                     bail_id=v.bail_id, cree_le=v.cree_le))
    for tcid in data.tc_ids:
        tc = session.get(Telecommande, tcid)
        if tc and tc.user_id == user.id:
            _assert_transferable("telecommande", tc.lot_id, tc.statut, tc.chez_locataire, tc.bail_id)
            tc.chez_locataire = True
            tc.bail_id = bail_id
            session.add(tc)
            updated.append(AccesOut(id=tc.id, code=tc.code, type="telecommande", lot_id=tc.lot_id,
                                     statut=tc.statut, chez_locataire=tc.chez_locataire,
                                     bail_id=tc.bail_id, cree_le=tc.cree_le))
    session.commit()
    return updated


@router.post("/baux/{bail_id}/recuperer-acces", response_model=List[AccesOut])
def recuperer_acces(
    bail_id: int,
    data: TransfertAccesIn = TransfertAccesIn(),
    user: Utilisateur = Depends(_require_bailleur),
    session: Session = Depends(get_session),
):
    """Retour virtuel des accès chez_locataire=True pour ce bail.

    Si ``data.vigik_ids`` ou ``data.tc_ids`` sont fournis, seuls ces accès sont
    récupérés.  Sinon tous les accès du bail sont récupérés (comportement
    historique conservé).
    """
    _get_bail_or_404(bail_id, user, session)
    selective = bool(data.vigik_ids or data.tc_ids)
    updated = []

    vigik_q = select(Vigik).where(Vigik.bail_id == bail_id, Vigik.user_id == user.id)
    if selective and data.vigik_ids:
        vigik_q = vigik_q.where(Vigik.id.in_(data.vigik_ids))
    elif selective:
        vigik_q = vigik_q.where(Vigik.id == -1)  # aucun vigik demandé

    for v in session.exec(vigik_q).all():
        v.chez_locataire = False
        v.bail_id = None
        session.add(v)
        updated.append(AccesOut(id=v.id, code=v.code, type="vigik", lot_id=v.lot_id,
                                 statut=v.statut, chez_locataire=False, bail_id=None, cree_le=v.cree_le))

    tc_q = select(Telecommande).where(Telecommande.bail_id == bail_id, Telecommande.user_id == user.id)
    if selective and data.tc_ids:
        tc_q = tc_q.where(Telecommande.id.in_(data.tc_ids))
    elif selective:
        tc_q = tc_q.where(Telecommande.id == -1)

    for tc in session.exec(tc_q).all():
        tc.chez_locataire = False
        tc.bail_id = None
        session.add(tc)
        updated.append(AccesOut(id=tc.id, code=tc.code, type="telecommande", lot_id=tc.lot_id,
                                 statut=tc.statut, chez_locataire=False, bail_id=None, cree_le=tc.cree_le))
    session.commit()
    return updated


# ── Vue locataire : voir les accès reçus de son bailleur ──────────────────────

@router.get("/mes-acces-recus", response_model=List[AccesOut])
def mes_acces_recus(
    user: Utilisateur = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Locataire : voir les Vigik/TC qui lui ont été confiés par son bailleur."""
    result = []
    # Trouver les baux où cet utilisateur est locataire_id
    baux = session.exec(select(LocationBail).where(
        LocationBail.locataire_id == user.id,
        LocationBail.statut != StatutBail.termine,
    )).all()
    bail_ids = [b.id for b in baux]
    if not bail_ids:
        return []
    for bid in bail_ids:
        for v in session.exec(select(Vigik).where(Vigik.bail_id == bid, Vigik.chez_locataire == True)).all():
            result.append(AccesOut(id=v.id, code=v.code, type="vigik", lot_id=v.lot_id,
                                    statut=v.statut, chez_locataire=True, bail_id=bid, cree_le=v.cree_le))
        for tc in session.exec(select(Telecommande).where(Telecommande.bail_id == bid, Telecommande.chez_locataire == True)).all():
            result.append(AccesOut(id=tc.id, code=tc.code, type="telecommande", lot_id=tc.lot_id,
                                    statut=tc.statut, chez_locataire=True, bail_id=bid, cree_le=tc.cree_le))
    return result


# ── Vue locataire : son bail actif ────────────────────────────────────────────

class BailLocataireOut(BaseModel):
    id: int
    lot_id: int
    lot_numero: Optional[str] = None
    lot_type: Optional[str] = None
    lot_type_appartement: Optional[str] = None
    lot_etage: Optional[int] = None
    lot_superficie: Optional[float] = None
    lot_batiment_nom: Optional[str] = None
    bailleur_nom: str
    bailleur_prenom: str
    bailleur_email: Optional[str]
    bailleur_telephone: Optional[str]
    date_entree: date
    date_sortie_prevue: Optional[date]
    statut: StatutBail
    acces: List[AccesOut] = []

    class Config:
        from_attributes = True


@router.get("/mon-bail", response_model=Optional[BailLocataireOut])
def mon_bail(
    user: Utilisateur = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Locataire inscrit : voir son bail actif et les accès confiés par le bailleur."""
    bail = session.exec(select(LocationBail).where(
        LocationBail.locataire_id == user.id,
        LocationBail.statut != StatutBail.termine,
    )).first()
    if not bail:
        return None
    bailleur = session.get(Utilisateur, bail.bailleur_id)
    bail_lot = session.get(Lot, bail.lot_id)
    bail_bat = session.get(Batiment, bail_lot.batiment_id) if (bail_lot and bail_lot.batiment_id) else None
    acces_list = []
    for v in session.exec(select(Vigik).where(Vigik.bail_id == bail.id, Vigik.chez_locataire == True)).all():
        acces_list.append(AccesOut(id=v.id, code=v.code, type="vigik", lot_id=v.lot_id,
                                    statut=v.statut, chez_locataire=True, bail_id=bail.id, cree_le=v.cree_le))
    for tc in session.exec(select(Telecommande).where(Telecommande.bail_id == bail.id, Telecommande.chez_locataire == True)).all():
        acces_list.append(AccesOut(id=tc.id, code=tc.code, type="telecommande", lot_id=tc.lot_id,
                                    statut=tc.statut, chez_locataire=True, bail_id=bail.id, cree_le=tc.cree_le))
    return BailLocataireOut(
        id=bail.id,
        lot_id=bail.lot_id,
        lot_numero=bail_lot.numero if bail_lot else None,
        lot_type=(bail_lot.type.value if hasattr(bail_lot.type, 'value') else str(bail_lot.type)) if bail_lot else None,
        lot_type_appartement=bail_lot.type_appartement if bail_lot else None,
        lot_etage=bail_lot.etage if bail_lot else None,
        lot_superficie=bail_lot.superficie if bail_lot else None,
        lot_batiment_nom=bail_bat.nom if bail_bat else None,
        bailleur_nom=bailleur.nom if bailleur else "",
        bailleur_prenom=bailleur.prenom if bailleur else "",
        bailleur_email=bailleur.email if bailleur else None,
        bailleur_telephone=bailleur.telephone if bailleur else None,
        date_entree=bail.date_entree,
        date_sortie_prevue=bail.date_sortie_prevue,
        statut=bail.statut,
        acces=acces_list,
    )

