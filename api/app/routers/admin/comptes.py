"""Admin — Validation des comptes en attente et appariement des accès.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Delegation,
    Notification,
    StatutAcces,
    StatutDelegation,
    StatutUtilisateur,
    Telecommande,
    UserLot,
    Utilisateur,
    Vigik,
)
from app.schemas import UserRead
from typing import Any

router = APIRouter()


# ── Gestion des comptes ──────────────────────────────────────────────────────

class CompteEnAttenteItem(BaseModel):
    """User en attente enrichi du nombre de lots trouvés dans l'import."""
    user: UserRead
    lots_prevus: int  # 0 = pas dans l'import Lots


class CompteTraiteResult(BaseModel):
    """Résultat de la validation / refus d'un compte."""
    user: UserRead
    auto_match: dict[str, Any] = {}


@router.get("/comptes-en-attente", response_model=list[UserRead])
def comptes_en_attente(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return session.exec(select(Utilisateur).where(Utilisateur.actif == False)).all()


@router.get("/comptes-en-attente/enrichis", response_model=list[CompteEnAttenteItem])
def comptes_en_attente_enrichis(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Comptes en attente enrichis du nombre de lots trouvés dans l'import.
    Permet à l'admin de vérifier si un copropriétaire est bien dans le fichier Lots."""
    from app.utils.auto_match_service import count_lots_for_user
    users = session.exec(select(Utilisateur).where(Utilisateur.actif == False)).all()
    return [
        CompteEnAttenteItem(
            user=UserRead.model_validate(u),
            lots_prevus=count_lots_for_user(u.nom, u.prenom, session),
        )
        for u in users
    ]


class CompteAction(BaseModel):
    action: str  # valider | refuser
    motif: str | None = None


@router.post("/comptes/{user_id}/traiter", response_model=CompteTraiteResult)
def traiter_compte(
    user_id: int,
    body: CompteAction,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    user = session.get(Utilisateur, user_id)
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    if body.action == "valider":
        user.actif = True
        notif_titre = "Votre compte a été activé"
        notif_corps = "Bienvenue sur l'application de la résidence."
    elif body.action == "refuser":
        notif_titre = "Votre compte n'a pas pu être activé"
        notif_corps = body.motif or "Contactez le conseil syndical pour plus d'informations."
    else:
        raise HTTPException(400, "Action invalide (valider | refuser)")

    notif = Notification(
        destinataire_id=user.id,
        type="system",
        titre=notif_titre,
        corps=notif_corps,
    )
    session.add(user)
    session.add(notif)

    # ── Email de confirmation au résident ─────────────────────────────────
    if user.email:
        from app.utils.email import send_email
        email_code = "compte_active" if body.action == "valider" else "compte_refuse"
        email_ctx: dict[str, Any] = {
            "destinataire": {"prenom": user.prenom, "nom": user.nom},
        }
        if body.action == "refuser" and body.motif:
            email_ctx["motif"] = body.motif
        background_tasks.add_task(
            send_email,
            code=email_code,
            to=user.email,
            context=email_ctx,
        )

    # Auto-match sur les 3 systèmes d'import dès qu'un compte est validé
    auto_match_result: dict[str, Any] = {}
    if body.action == "valider":
        from app.utils.auto_match_service import (
            auto_match_pour_utilisateur, notifier_gestionnaire_appariement,
        )
        auto_match_result = auto_match_pour_utilisateur(user, session)
        # Des accès ont pu être créés sans validation préalable : le
        # gestionnaire du site doit pouvoir le vérifier sans aller le chercher.
        notifier_gestionnaire_appariement(user, auto_match_result, background_tasks, session)

        # ── Aidant / mandataire : copier lots, TC, vigik de l'aidé ───────
        if user.statut in (StatutUtilisateur.aidant, StatutUtilisateur.mandataire) and user.nom_aide and user.prenom_aide:
            from sqlalchemy import func
            aide = session.exec(
                select(Utilisateur).where(
                    func.lower(Utilisateur.nom) == user.nom_aide.strip().lower(),
                    func.lower(Utilisateur.prenom) == user.prenom_aide.strip().lower(),
                    Utilisateur.actif == True,
                )
            ).first()
            aide_result = {"aide_trouve": False, "lots": 0, "tc": 0, "vigik": 0, "delegation": False}
            if aide:
                aide_result["aide_trouve"] = True
                aide_result["aide_nom"] = f"{aide.prenom} {aide.nom}"
                # Copier les lots
                aide_lots = session.exec(select(UserLot).where(UserLot.user_id == aide.id, UserLot.actif == True)).all()
                for ul in aide_lots:
                    exists = session.exec(select(UserLot).where(UserLot.user_id == user.id, UserLot.lot_id == ul.lot_id)).first()
                    if not exists:
                        session.add(UserLot(user_id=user.id, lot_id=ul.lot_id, type_lien=ul.type_lien, quote_part=ul.quote_part))
                        aide_result["lots"] += 1
                # Copier les télécommandes
                aide_tcs = session.exec(select(Telecommande).where(Telecommande.user_id == aide.id, Telecommande.statut == StatutAcces.actif)).all()
                for tc in aide_tcs:
                    exists = session.exec(select(Telecommande).where(Telecommande.user_id == user.id, Telecommande.code == tc.code)).first()
                    if not exists:
                        session.add(Telecommande(user_id=user.id, code=tc.code, lot_id=tc.lot_id, statut=StatutAcces.actif))
                        aide_result["tc"] += 1
                # Copier les vigik
                aide_vigiks = session.exec(select(Vigik).where(Vigik.user_id == aide.id, Vigik.statut == StatutAcces.actif)).all()
                for v in aide_vigiks:
                    exists = session.exec(select(Vigik).where(Vigik.user_id == user.id, Vigik.code == v.code)).first()
                    if not exists:
                        session.add(Vigik(user_id=user.id, code=v.code, lot_id=v.lot_id, statut=StatutAcces.actif))
                        aide_result["vigik"] += 1
                # Créer la délégation automatiquement
                existing_del = session.exec(
                    select(Delegation).where(
                        Delegation.mandant_id == aide.id,
                        Delegation.aidant_id == user.id,
                        Delegation.statut.in_([StatutDelegation.en_attente, StatutDelegation.active]),
                    )
                ).first()
                if not existing_del:
                    session.add(Delegation(
                        mandant_id=aide.id,
                        aidant_id=user.id,
                        motif="Affectation automatique à l'activation du compte",
                        cree_par_id=admin.id,
                        statut=StatutDelegation.active,
                    ))
                    aide_result["delegation"] = True
            auto_match_result["aide_match"] = aide_result

    session.commit()
    session.refresh(user)
    return CompteTraiteResult(user=UserRead.model_validate(user), auto_match=auto_match_result)


@router.post("/utilisateurs/{user_id}/auto-match", status_code=200)
def relancer_auto_match(
    user_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Rejoue le match automatique (lots, vigik, TC) pour un utilisateur déjà validé.
    Utile quand un import a été résolu après la validation du compte."""
    user = session.get(Utilisateur, user_id)
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    from app.utils.auto_match_service import auto_match_pour_utilisateur
    result = auto_match_pour_utilisateur(user, session)
    session.commit()
    return {"ok": True, "auto_match": result}
