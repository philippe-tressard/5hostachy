"""Admin — Commandes vigik / télécommande, et audit des liens utilisateur-lot.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Batiment,
    CommandeAcces,
    Lot,
    Notification,
    StatutCommande,
    UserLot,
    Utilisateur,
)
from datetime import datetime
from typing import Any
from app.utils.noms import nom_affiche

router = APIRouter()


# ── Commandes d'accès (vigik / télécommande) ────────────────────────────────

@router.get("/commandes-acces")
def list_commandes_acces(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return session.exec(
        select(CommandeAcces)
        .where(CommandeAcces.statut == StatutCommande.en_attente)
        .order_by(CommandeAcces.cree_le)
    ).all()


class CommandeAction(BaseModel):
    action: str  # accepter | refuser
    motif_refus: str | None = None


@router.post("/commandes-acces/{cmd_id}/traiter")
def traiter_commande(
    cmd_id: int,
    body: CommandeAction,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    cmd = session.get(CommandeAcces, cmd_id)
    if not cmd:
        raise HTTPException(404, "Commande introuvable")

    cmd.statut = StatutCommande.acceptee if body.action == "accepter" else StatutCommande.refusee
    cmd.traite_par_id = admin.id
    cmd.traite_le = datetime.utcnow()
    cmd.motif_refus = body.motif_refus

    notif = Notification(
        destinataire_id=cmd.user_id,
        type="vigik",
        titre=f"Commande {cmd.type} : {cmd.statut.value}",
        corps=body.motif_refus or "Votre demande a été traitée.",
        lien="/mon-lot",
    )
    session.add(cmd)
    session.add(notif)

    # ── Email au demandeur ────────────────────────────────────────────────
    # Les modèles `vigik_accepte` / `vigik_refuse` existaient depuis l'origine
    # sans qu'aucun code ne les envoie : le demandeur n'était prévenu que par une
    # notification dans l'application, qu'il ne voit que s'il l'ouvre. Pour une
    # demande de badge ou de télécommande — un objet qu'il faut ensuite venir
    # retirer — l'e-mail est le canal qui atteint vraiment (01/08/2026).
    accepte = cmd.statut == StatutCommande.acceptee
    demandeur = session.get(Utilisateur, cmd.user_id)
    if demandeur and demandeur.email:
        from app.utils.email import send_email
        ctx_vigik: dict[str, Any] = {
            "destinataire": {"prenom": demandeur.prenom, "nom": demandeur.nom},
            "type": cmd.type,
        }
        if not accepte:
            ctx_vigik["motif"] = body.motif_refus or "Aucun motif précisé."
        background_tasks.add_task(
            send_email,
            code="vigik_accepte" if accepte else "vigik_refuse",
            to=demandeur.email,
            context=ctx_vigik,
            destinataire_id=demandeur.id,
        )

    session.commit()
    return {"statut": cmd.statut}
# ── Audit associations user-lot ─────────────────────────────────────────────

@router.get("/audit/user-lots")
def audit_user_lots(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Liste toutes les associations user-lot avec détails pour audit.
    Permet de repérer les affectations erronées."""
    rows = session.exec(
        select(UserLot).where(UserLot.actif == True).order_by(UserLot.user_id)
    ).all()
    result = []
    for ul in rows:
        user = session.get(Utilisateur, ul.user_id)
        lot = session.get(Lot, ul.lot_id)
        bat = session.get(Batiment, lot.batiment_id) if lot and lot.batiment_id else None
        result.append({
            "user_lot_id": ul.id,
            "user_id": ul.user_id,
            "user_nom": nom_affiche(user.prenom, user.nom) if user else "?",
            "user_statut": user.statut.value if user and hasattr(user.statut, "value") else str(user.statut) if user else "?",
            "lot_id": ul.lot_id,
            "lot_numero": lot.numero if lot else "?",
            "lot_type": lot.type.value if lot and hasattr(lot.type, "value") else str(lot.type) if lot else "?",
            "batiment": f"Bât. {bat.numero}" if bat else "—",
            "type_lien": ul.type_lien.value if hasattr(ul.type_lien, "value") else str(ul.type_lien),
        })
    return result


@router.delete("/user-lots/{user_lot_id}")
def supprimer_user_lot(
    user_lot_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Supprime une association user-lot incorrecte.
    Nettoie aussi utilisateurs_json dans les LotImport correspondants pour
    éviter que l'auto-match recrée le lien au prochain passage."""
    ul = session.get(UserLot, user_lot_id)
    if not ul:
        raise HTTPException(404, "Association user-lot introuvable")
    uid_supprime = ul.user_id
    lot_id_supprime = ul.lot_id
    session.delete(ul)
    # Retirer ce user de l'utilisateurs_json de tout import lié à ce lot
    from app.models.core import LotImport
    imports_lies = session.exec(
        select(LotImport).where(LotImport.lot_id == lot_id_supprime)
    ).all()
    for imp in imports_lies:
        users = json.loads(imp.utilisateurs_json or "[]")
        nouveau = [e for e in users if e.get("user_id") != uid_supprime]
        if len(nouveau) != len(users):
            imp.utilisateurs_json = json.dumps(nouveau, ensure_ascii=False)
            session.add(imp)
    session.commit()
    return {"ok": True, "deleted_id": user_lot_id}
