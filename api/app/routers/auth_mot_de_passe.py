"""Mot de passe : changement, oubli, réinitialisation.

Extrait de `routers/auth.py` le 14/08/2026, au fil de l'eau : ce fichier avait
atteint 736 lignes et le contrôle de modularité refuse qu'un fichier déjà
au-dessus de 500 grossisse (rang 1 §4). Il fallait y ajouter cinq lignes pour la
préférence d'affichage du profil (#339).

Ce bloc-ci est celui qui s'en détache le plus proprement : trois routes qui ne
partagent avec le reste ni état ni schéma, et dont le sujet — prouver qu'on est
soi quand on a perdu son mot de passe — a ses propres raisons de changer.

Le router porte le même préfixe `/auth` et est monté à part dans `main.py` :
FastAPI additionne les routers, les URL publiques sont donc rigoureusement
inchangées. `api/tests/test_endpoints_orphelins.py` le vérifie.
"""
from datetime import datetime, timedelta
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.auth.jwt import hash_password, verify_password
from app.database import get_session
from app.models.core import ConfigSite, PasswordResetToken, RefreshToken, Utilisateur
from app.utils.limiter import limiter
from app.utils.mots_de_passe import verifier_robustesse as _check_password_strength

router = APIRouter(prefix="/auth", tags=["auth"])


class ChangePasswordBody(BaseModel):
    mot_de_passe_actuel: str
    nouveau_mot_de_passe: str


@router.post("/change-password", status_code=204)
def change_password(
    body: ChangePasswordBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    if not verify_password(body.mot_de_passe_actuel, user.hashed_password or ""):
        raise HTTPException(400, "Mot de passe actuel incorrect.")
    _check_password_strength(body.nouveau_mot_de_passe)
    user.hashed_password = hash_password(body.nouveau_mot_de_passe)
    session.add(user)
    session.commit()


class PasswordResetRequest(BaseModel):
    email: str


@router.post("/mot-de-passe-oublie", status_code=204)
@limiter.limit("3/minute")
def request_password_reset(
    request: Request,
    body: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    Génère un token de réinitialisation et envoie un e-mail si le compte existe.
    Retourne toujours 204 pour éviter l'enumération d'adresses e-mail.
    """
    cfg_rows = session.exec(
        select(ConfigSite).where(ConfigSite.cle.in_(("site_url", "site_nom")))
    ).all()
    cfg = {row.cle: row.valeur for row in cfg_rows}
    site_url = (cfg.get("site_url") or "https://localhost").rstrip("/")
    site_nom = cfg.get("site_nom") or "5Hostachy"

    user = session.exec(select(Utilisateur).where(Utilisateur.email == body.email.strip().lower())).first()
    if user and user.actif:
        # Invalider les tokens de reset précédents non utilisés
        old_tokens = session.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used == False,  # noqa: E712
            )
        ).all()
        for t in old_tokens:
            t.used = True
            session.add(t)

        raw_token = secrets.token_urlsafe(32)
        prt = PasswordResetToken(
            user_id=user.id,
            token=raw_token,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        session.add(prt)
        session.commit()

        from app.utils.email import send_email
        background_tasks.add_task(
            send_email,
            code="reinitialisation_mdp",
            to=user.email,
            context={
                "destinataire": {"prenom": user.prenom},
                "lien": f"{site_url}/auth/reinitialisation-mdp?token={raw_token}",
                "expire_heures": 1,
                "residence": {"nom": site_nom},
                "app": {"url": site_url},
            },
        )

    return None


class PasswordResetConfirm(BaseModel):
    token: str
    nouveau_mot_de_passe: str


@router.post("/reinitialiser-mot-de-passe", status_code=204)
@limiter.limit("5/minute")
def reset_password(
    request: Request,
    body: PasswordResetConfirm,
    session: Session = Depends(get_session),
):
    """Utilise le token de réinitialisation pour définir un nouveau mot de passe."""
    _check_password_strength(body.nouveau_mot_de_passe)

    prt = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token == body.token)
    ).first()

    if not prt or prt.used or prt.expires_at < datetime.utcnow():
        raise HTTPException(400, "Lien de réinitialisation invalide ou expiré.")

    user = session.get(Utilisateur, prt.user_id)
    if not user or not user.actif:
        raise HTTPException(400, "Lien de réinitialisation invalide ou expiré.")

    user.hashed_password = hash_password(body.nouveau_mot_de_passe)
    prt.used = True

    # Révoquer toutes les sessions actives de l'utilisateur
    active_sessions = session.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked == False,  # noqa: E712
        )
    ).all()
    for rt in active_sessions:
        rt.revoked = True
        session.add(rt)

    session.add(user)
    session.add(prt)
    session.commit()
    return None
