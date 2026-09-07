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


# ── Baux dont le locataire n'a pas été rattaché ──────────────────────────────

@router.get("/audit/baux-sans-locataire")
def audit_baux_sans_locataire(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Les baux en cours dont aucun COMPTE n'est rattaché au locataire.

    ## 🔴 Pourquoi ce relevé existe (#808, 07/09/2026)

    Le rattachement d'un compte locataire à son bail est automatique, et il se
    fait sur l'**e-mail exact** (`_auto_match_baux_locataire`) : le bail doit
    porter la même adresse que celle de l'inscription. Il échoue donc dès que le
    bailleur a saisi une autre adresse, ou aucune — et surtout **quand le bail
    est créé après l'inscription**, puisque le rapprochement n'a lieu qu'à la
    validation du compte.

    ⚠️ Et il échoue **en silence** : la fonction rend `0`, personne n'est
    prévenu. Côté locataire, cela se voit ainsi — son compte est actif, mais il
    ne voit ni son lot, ni ses badges, ni sa fiche de location.

    Arbitrage du 06/09/2026 : *garder et observer*. Ce relevé est le moyen
    d'observer ; il n'y a **pas** de geste de rattachement, délibérément.
    L'endpoint qui le ferait existe (`POST /admin/baux/{id}/lier-locataire/{u}`)
    et attend de savoir si le cas se présente.

    ## Deux catégories, et les confondre ferait crier sur le cas normal

    - **`compte_probable`** — un compte existe au nom du locataire : le
      rattachement MANQUE, il est rattrapable.
    - **`sans_compte`** — personne ne s'est inscrit sous ce nom. C'est le cas
      **normal** d'un locataire qui n'utilise pas le site, et il ne doit pas se
      lire comme un défaut.
    """
    from app.models.core import LocationBail, StatutBail

    baux = session.exec(
        select(LocationBail).where(
            LocationBail.locataire_id.is_(None),  # type: ignore[union-attr]
            LocationBail.statut != StatutBail.termine,
        )
    ).all()

    #  Les comptes candidats : on cherche par NOM, pas par e-mail — c'est
    #  justement l'e-mail qui a échoué, le redemander ne trouverait rien.
    result = []
    for bail in baux:
        lot = session.get(Lot, bail.lot_id)
        bat = session.get(Batiment, lot.batiment_id) if lot and lot.batiment_id else None
        candidats = []
        if bail.locataire_nom:
            cible = bail.locataire_nom.strip().lower()
            for u in session.exec(select(Utilisateur).where(Utilisateur.actif == True)).all():  # noqa: E712
                if u.nom and u.nom.strip().lower() == cible:
                    candidats.append(
                        {"id": u.id, "nom": nom_affiche(u.prenom, u.nom), "email": u.email}
                    )
        result.append({
            "bail_id": bail.id,
            "lot": f"{lot.type.value if lot and hasattr(lot.type, 'value') else ''} {lot.numero}".strip()
            if lot else "?",
            "batiment": f"Bât. {bat.numero}" if bat else "—",
            "locataire_nom": nom_affiche(bail.locataire_prenom, bail.locataire_nom)
            if (bail.locataire_nom or bail.locataire_prenom) else "—",
            "locataire_email": bail.locataire_email,
            "date_entree": bail.date_entree,
            #  🔴 La catégorie est calculée ICI, une fois : la laisser à l'écran
            #  en ferait une seconde règle, et deux vues du même relevé pourraient
            #  ranger le même bail dans deux cases.
            "categorie": "compte_probable" if candidats else "sans_compte",
            "candidats": candidats,
        })
    #  Les rattachements manquants d'abord : c'est ce sur quoi on peut agir.
    result.sort(key=lambda r: (r["categorie"] != "compte_probable", r["locataire_nom"]))
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
