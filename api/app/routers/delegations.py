"""Router délégations aidant — gestion des accès délégués pour les proches."""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlmodel import Session, select, or_

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import Delegation, StatutDelegation, Utilisateur

router = APIRouter(prefix="/delegations", tags=["délégations aidant"])


# ── Schemas ─────────────────────────────────────────────────────────────────

class DelegationCreate(BaseModel):
    mandant_id: int
    aidant_id: int
    motif: str = ""
    date_fin: Optional[str] = None  # ISO date, null = illimité


class DelegationRead(BaseModel):
    id: int
    mandant_id: int
    mandant_nom: str
    aidant_id: int
    aidant_nom: str
    statut: str
    motif: str
    date_debut: str
    date_fin: Optional[str]
    cree_le: str
    revoque_le: Optional[str]


class DelegationUpdate(BaseModel):
    motif: Optional[str] = None
    date_fin: Optional[str] = None


# ── Helpers ─────────────────────────────────────────────────────────────────

def _user_display(u: Utilisateur) -> str:
    return f"{u.prenom} {u.nom}"


def _to_read(d: Delegation, session: Session) -> dict:
    mandant = session.get(Utilisateur, d.mandant_id)
    aidant = session.get(Utilisateur, d.aidant_id)
    return {
        "id": d.id,
        "mandant_id": d.mandant_id,
        "mandant_nom": _user_display(mandant) if mandant else "?",
        "aidant_id": d.aidant_id,
        "aidant_nom": _user_display(aidant) if aidant else "?",
        "statut": d.statut.value if isinstance(d.statut, StatutDelegation) else d.statut,
        "motif": d.motif,
        "date_debut": d.date_debut.isoformat() if d.date_debut else None,
        "date_fin": d.date_fin.isoformat() if d.date_fin else None,
        "cree_le": d.cree_le.isoformat() if d.cree_le else None,
        "revoque_le": d.revoque_le.isoformat() if d.revoque_le else None,
    }


# ── Endpoints CS/Admin ──────────────────────────────────────────────────────

@router.get("", response_model=list[dict])
def list_delegations(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Liste les délégations visibles par l'utilisateur.
    - CS/Admin : toutes
    - Aidant : ses délégations
    - Mandant : les délégations le concernant
    """
    if user.has_role("conseil_syndical", "admin"):
        delegations = session.exec(
            select(Delegation).order_by(Delegation.cree_le.desc())
        ).all()
    else:
        delegations = session.exec(
            select(Delegation)
            .where(or_(Delegation.aidant_id == user.id, Delegation.mandant_id == user.id))
            .order_by(Delegation.cree_le.desc())
        ).all()
    return [_to_read(d, session) for d in delegations]


@router.post("", status_code=201)
def create_delegation(
    body: DelegationCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Créer une délégation (CS/Admin uniquement)."""
    mandant = session.get(Utilisateur, body.mandant_id)
    if not mandant:
        raise HTTPException(404, "Mandant introuvable")
    aidant = session.get(Utilisateur, body.aidant_id)
    if not aidant:
        raise HTTPException(404, "Aidant introuvable")
    if body.mandant_id == body.aidant_id:
        raise HTTPException(400, "Le mandant et l'aidant doivent être différents")

    # Vérifier qu'il n'y a pas déjà une délégation active entre ces deux personnes
    existing = session.exec(
        select(Delegation).where(
            Delegation.mandant_id == body.mandant_id,
            Delegation.aidant_id == body.aidant_id,
            Delegation.statut == StatutDelegation.active,
        )
    ).first()
    if existing:
        raise HTTPException(400, "Une délégation active existe déjà entre ces deux personnes")

    delegation = Delegation(
        mandant_id=body.mandant_id,
        aidant_id=body.aidant_id,
        motif=body.motif,
        date_debut=date.today(),
        date_fin=date.fromisoformat(body.date_fin) if body.date_fin else None,
        cree_par_id=user.id,
        cree_le=datetime.utcnow(),
        statut=StatutDelegation.en_attente,
    )
    session.add(delegation)
    session.commit()
    session.refresh(delegation)
    return _to_read(delegation, session)


@router.patch("/{delegation_id}")
def update_delegation(
    delegation_id: int,
    body: DelegationUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Modifier une délégation (motif, date de fin)."""
    d = session.get(Delegation, delegation_id)
    if not d:
        raise HTTPException(404, "Délégation introuvable")
    if body.motif is not None:
        d.motif = body.motif
    if body.date_fin is not None:
        d.date_fin = date.fromisoformat(body.date_fin) if body.date_fin else None
    session.add(d)
    session.commit()
    session.refresh(d)
    return _to_read(d, session)


# ── Acceptation par l'aidant ────────────────────────────────────────────────

@router.post("/{delegation_id}/accepter")
def accepter_delegation(
    delegation_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """L'aidant accepte la délégation."""
    d = session.get(Delegation, delegation_id)
    if not d:
        raise HTTPException(404, "Délégation introuvable")
    if d.aidant_id != user.id:
        raise HTTPException(403, "Seul l'aidant désigné peut accepter")
    if d.statut != StatutDelegation.en_attente:
        raise HTTPException(400, f"Impossible d'accepter (statut actuel : {d.statut})")
    d.statut = StatutDelegation.active
    session.add(d)
    session.commit()
    session.refresh(d)
    return _to_read(d, session)


# ── Révocation ──────────────────────────────────────────────────────────────

@router.post("/{delegation_id}/revoquer")
def revoquer_delegation(
    delegation_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Révoquer une délégation (par le mandant, l'aidant, ou un CS/Admin)."""
    d = session.get(Delegation, delegation_id)
    if not d:
        raise HTTPException(404, "Délégation introuvable")

    is_cs_admin = user.has_role("conseil_syndical", "admin")
    is_party = user.id in (d.mandant_id, d.aidant_id)
    if not is_cs_admin and not is_party:
        raise HTTPException(403, "Non autorisé")

    if d.statut in (StatutDelegation.revoquee, StatutDelegation.expiree):
        raise HTTPException(400, "Délégation déjà terminée")

    d.statut = StatutDelegation.revoquee
    d.revoque_le = datetime.utcnow()
    d.revoque_par_id = user.id
    session.add(d)
    session.commit()
    session.refresh(d)
    return _to_read(d, session)


# ── « Agir en tant que » ────────────────────────────────────────────────────

@router.get("/mes-mandants")
def mes_mandants(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Retourne la liste des personnes pour lesquelles l'utilisateur peut agir.
    Utilisé par le switcher frontend.
    """
    today = date.today()
    delegations = session.exec(
        select(Delegation).where(
            Delegation.aidant_id == user.id,
            Delegation.statut == StatutDelegation.active,
            Delegation.date_debut <= today,
            or_(Delegation.date_fin.is_(None), Delegation.date_fin >= today),  # type: ignore[arg-type]
        )
    ).all()
    result = []
    for d in delegations:
        mandant = session.get(Utilisateur, d.mandant_id)
        if mandant:
            result.append({
                "delegation_id": d.id,
                "mandant_id": mandant.id,
                "mandant_nom": _user_display(mandant),
                "mandant_batiment_id": mandant.batiment_id,
            })
    return result
