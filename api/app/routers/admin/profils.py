"""Admin — Workflow de validation des demandes de modification de profil.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Batiment,
    DemandeModificationProfil,
    Notification,
    StatutDemandeProfil,
    StatutUtilisateur,
    Utilisateur,
)
from datetime import datetime
from app.utils.noms import nom_affiche

router = APIRouter()


# ── Demandes de modification de profil ─────────────────────────────────

@router.get("/demandes-profil")
def list_demandes_profil(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Liste toutes les demandes de modification de profil en attente."""
    demandes = session.exec(
        select(DemandeModificationProfil)
        .where(DemandeModificationProfil.statut_demande == StatutDemandeProfil.en_attente)
        .order_by(DemandeModificationProfil.cree_le)
    ).all()
    result = []
    for d in demandes:
        utilisateur = session.get(Utilisateur, d.utilisateur_id)
        bat = session.get(Batiment, d.batiment_id_souhaite) if d.batiment_id_souhaite else None
        item = d.model_dump()
        item["utilisateur_nom"] = nom_affiche(utilisateur.prenom, utilisateur.nom) if utilisateur else "?"
        item["utilisateur_email"] = utilisateur.email if utilisateur else None
        item["statut_actuel"] = utilisateur.statut.value if utilisateur else None
        item["batiment_actuel"] = (f"Bât. {session.get(Batiment, utilisateur.batiment_id).numero}"
            if utilisateur and utilisateur.batiment_id else None)
        item["batiment_nom_souhaite"] = f"Bât. {bat.numero}" if bat else None
        result.append(item)
    return result


class DemandeProfilAction(BaseModel):
    action: str  # approuver | rejeter
    motif_refus: str | None = None


@router.post("/demandes-profil/{demande_id}/traiter")
def traiter_demande_profil(
    demande_id: int,
    body: DemandeProfilAction,
    session: Session = Depends(get_session),
    cs: Utilisateur = Depends(require_cs_or_admin),
):
    demande = session.get(DemandeModificationProfil, demande_id)
    if not demande:
        raise HTTPException(404, "Demande introuvable")
    if demande.statut_demande != StatutDemandeProfil.en_attente:
        raise HTTPException(400, "Cette demande a déjà été traitée.")

    utilisateur = session.get(Utilisateur, demande.utilisateur_id)
    if not utilisateur:
        raise HTTPException(404, "Utilisateur introuvable")

    if body.action == "approuver":
        if demande.statut_souhaite:
            utilisateur.statut = StatutUtilisateur(demande.statut_souhaite)
        if demande.batiment_id_souhaite:
            utilisateur.batiment_id = demande.batiment_id_souhaite
        demande.statut_demande = StatutDemandeProfil.approuvee
        notif = Notification(
            destinataire_id=utilisateur.id,
            type="system",
            titre="Modification de profil approuvée",
            corps="Votre demande de modification de profil a été approuvée.",
            lien="/profil",
        )
    elif body.action == "rejeter":
        demande.statut_demande = StatutDemandeProfil.rejetee
        demande.motif_refus = body.motif_refus
        notif = Notification(
            destinataire_id=utilisateur.id,
            type="system",
            titre="Modification de profil refusée",
            corps=body.motif_refus or "Votre demande de modification de profil a été refusée.",
            lien="/profil",
        )
    else:
        raise HTTPException(400, "Action invalide (approuver | rejeter)")

    demande.traite_par_id = cs.id
    demande.traite_le = datetime.utcnow()
    session.add(demande)
    session.add(utilisateur)
    session.add(notif)
    session.commit()
    return {"statut": demande.statut_demande}
