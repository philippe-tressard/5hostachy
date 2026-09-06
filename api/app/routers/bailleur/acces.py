"""Les accès (Vigik, télécommandes) qui suivent un bail — et la vue du locataire.

Un bailleur TRANSFÈRE ses badges au locataire pour la durée du bail, puis les
RÉCUPÈRE à la sortie. `mon-bail` est le pendant côté locataire : ce qu'il voit de
son propre bail, y compris les accès qui lui ont été confiés.

⚠️ C'est le plus gros des quatre modules (318 lignes), et il le restera : les
quatre routes se partagent la même logique de rapprochement bail ⇆ badges.
"""
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_proprietaire
from app.database import get_session
from app.models.core import (
    LocationBail, Lot, Batiment,
    StatutBail, Utilisateur, Vigik, Telecommande, StatutAcces,
)
from pydantic import BaseModel

from .commun import get_bail_or_404

router = APIRouter()


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
    user: Utilisateur = Depends(require_proprietaire),
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
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    """Accès (Vigik+TC) du bailleur avec règles d'éligibilité de transfert."""
    bail = get_bail_or_404(bail_id, user, session)
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
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    """Marquer des Vigik/TC comme étant chez le locataire."""
    bail = get_bail_or_404(bail_id, user, session)
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
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
):
    """Retour virtuel des accès chez_locataire=True pour ce bail.

    Si ``data.vigik_ids`` ou ``data.tc_ids`` sont fournis, seuls ces accès sont
    récupérés.  Sinon tous les accès du bail sont récupérés (comportement
    historique conservé).
    """
    get_bail_or_404(bail_id, user, session)
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
