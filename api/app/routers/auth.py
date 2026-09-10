"""Router auth — inscription, connexion, déconnexion, refresh.

Le bloc « profil » — `GET /me`, `PATCH /me` et les demandes de modification — est
parti dans `auth_profil.py` le 09/09/2026, au fil de l'eau : ce fichier était à
561 lignes et le contrôle de modularité refuse qu'un fichier déjà au-dessus de
500 grossisse (rang 1 §4). Il fallait y ajouter l'alerte de divergence d'étage.

C'est la TROISIÈME extraction de ce fichier — après le mot de passe (14/08/2026)
et la télémétrie —, et la césure est la même à chaque fois : *prouver qu'on est
soi* reste ici, *décrire qui l'on est* s'en va. Le router garde le préfixe
`/auth` et est monté à part dans `main.py` : FastAPI additionne les routers, les
URL publiques sont donc rigoureusement inchangées.
"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, Cookie, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_and_rehash,
)
from app.auth.deps import get_current_user
from app.config import get_settings
from app.database import get_session
from app.models.core import (Utilisateur, RefreshToken, EmailVerificationToken, StatutUtilisateur, RoleUtilisateur, Batiment,
    ConfigSite)
from app.schemas import UserCreate, UserRead, LoginRequest
from app.utils.lecture_utilisateur import construire_user_read
from app.utils.limiter import limiter
from app.utils.mots_de_passe import verifier_robustesse as _check_password_strength

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


COOKIE_OPTS = dict(httponly=True, secure=settings.cookie_secure, samesite="strict", path="/")


@router.get("/batiments")
def list_batiments(session: Session = Depends(get_session)):
    """Liste publique des bâtiments pour le formulaire d'inscription."""
    return session.exec(select(Batiment).order_by(Batiment.numero)).all()


@router.post("/register", response_model=UserRead, status_code=201)
@limiter.limit("5/minute")
def register(
    request: Request,
    body: UserCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Créer un compte. Pour les profils syndic et mandataire, société et fonction sont obligatoires."""
    if body.statut in (StatutUtilisateur.syndic, StatutUtilisateur.mandataire):
        if not body.societe or not body.fonction:
            raise HTTPException(400, "Pour un profil syndic ou mandataire, la société et la fonction sont obligatoires.")
    if body.statut == StatutUtilisateur.locataire:
        if not body.nom_proprietaire or not body.nom_proprietaire.strip():
            raise HTTPException(400, "Le nom du propriétaire est obligatoire pour un locataire.")
    if body.statut in (StatutUtilisateur.aidant, StatutUtilisateur.mandataire):
        if not body.nom_aide or not body.nom_aide.strip() or not body.prenom_aide or not body.prenom_aide.strip():
            raise HTTPException(400, "Le nom et prénom du copropriétaire aidé sont obligatoires.")
    if not body.consentement_rgpd:
        raise HTTPException(400, "Le consentement RGPD est obligatoire.")
    _check_password_strength(body.password)

    existing = session.exec(select(Utilisateur).where(func.lower(Utilisateur.email) == body.email)).first()
    if existing:
        raise HTTPException(400, "Email déjà utilisé.")

    user = Utilisateur(
        nom=body.nom,
        prenom=body.prenom,
        email=body.email,
        telephone=body.telephone,
        societe=body.societe,
        fonction=body.fonction,
        hashed_password=hash_password(body.password),
        statut=body.statut,
        role=RoleUtilisateur.résident,
        actif=False,  # en attente de validation
        consentement_rgpd=body.consentement_rgpd,
        batiment_id=body.batiment_id,
        etage=body.etage,
        nom_proprietaire=body.nom_proprietaire or None,
        nom_aide=body.nom_aide or None,
        prenom_aide=body.prenom_aide or None,
    )
    # Attribuer les rôles selon le statut
    if body.statut in (StatutUtilisateur.syndic, StatutUtilisateur.mandataire, StatutUtilisateur.aidant):
        user.role = RoleUtilisateur.externe
        user.roles_json = body.statut.value  # "syndic", "mandataire" ou "aidant"
    else:
        _STATUT_ROLES = {
            StatutUtilisateur.copropriétaire_résident: [RoleUtilisateur.propriétaire, RoleUtilisateur.résident],
            StatutUtilisateur.copropriétaire_bailleur: [RoleUtilisateur.propriétaire],
            StatutUtilisateur.locataire: [RoleUtilisateur.résident],
        }
        roles = _STATUT_ROLES.get(body.statut, [RoleUtilisateur.résident])
        _prio = {RoleUtilisateur.propriétaire: 2, RoleUtilisateur.résident: 1}
        user.role = max(roles, key=lambda r: _prio.get(r, 0))
        user.roles_json = ",".join(r.value for r in roles)
    session.add(user)
    session.commit()
    session.refresh(user)

    # ── Token de vérification email ──────────────────────────────
    raw_token = secrets.token_urlsafe(32)
    evt = EmailVerificationToken(
        user_id=user.id,
        token=raw_token,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    session.add(evt)
    session.commit()

    # Envoyer l'email de vérification à l'utilisateur
    cfg_rows = session.exec(
        select(ConfigSite).where(
            ConfigSite.cle.in_(("notify_new_user_created_email", "site_nom", "site_url", "site_manager_user_id", "site_email"))
        )
    ).all()
    cfg = {row.cle: row.valeur for row in cfg_rows}
    site_url = (cfg.get("site_url") or "https://localhost").rstrip("/")
    site_nom = cfg.get("site_nom") or "5Hostachy"

    from app.utils.email import send_email as _send_email
    background_tasks.add_task(
        _send_email,
        code="verification_email",
        to=user.email,
        context={
            "prenom": user.prenom,
            "token": raw_token,
            "lien": f"{site_url}/auth/verifier-email?token={raw_token}",
            "expire_heures": 24,
            "residence": {"nom": site_nom},
            "app": {"url": site_url},
        },
    )

    # Notification au gestionnaire du site
    if cfg.get("notify_new_user_created_email") == "1":
        from app.utils.email import get_site_manager_notification_email

        target_email, site_cfg = get_site_manager_notification_email(session)
        if target_email:
            background_tasks.add_task(
                _send_email,
                code="compte_en_attente",
                to=target_email,
                context={
                    "utilisateur": {
                        "prenom": user.prenom,
                        "nom": user.nom,
                        "email": user.email,
                    },
                    "residence": {
                        "nom": site_cfg.get("site_nom") or cfg.get("site_nom") or "5Hostachy",
                    },
                    "app": {
                        "url": site_cfg.get("site_url") or cfg.get("site_url") or "https://localhost",
                    },
                },
            )

    # Si le compte est actif dès la création (cas admin ou futur flow),
    # lancer l'auto-match immédiatement
    if user.actif:
        from app.utils.auto_match_service import (
            auto_match_pour_utilisateur, notifier_gestionnaire_appariement,
        )
        resultat = auto_match_pour_utilisateur(user, session)
        session.commit()
        # Le résultat était jusqu'ici jeté : des accès pouvaient être créés
        # sans que personne n'en soit informé.
        notifier_gestionnaire_appariement(user, resultat, background_tasks, session)

    return user


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest, response: Response, session: Session = Depends(get_session)):
    user = session.exec(select(Utilisateur).where(func.lower(Utilisateur.email) == body.email)).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect.")
    valid, new_hash = verify_and_rehash(body.password, user.hashed_password)
    if not valid:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect.")
    if not user.actif:
        raise HTTPException(status_code=403, detail="Compte en attente de validation.")
    if not user.email_verifie:
        raise HTTPException(status_code=403, detail="Veuillez vérifier votre adresse e-mail. Consultez votre boîte de réception.")
    if new_hash:
        user.hashed_password = new_hash  # rehash silencieux 12→10 rounds

    user.derniere_connexion = datetime.utcnow()
    session.add(user)

    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})
    rt = RefreshToken(
        user_id=user.id,
        token=refresh,
        expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(rt)
    session.commit()

    response.set_cookie("access_token", access, max_age=settings.access_token_expire_minutes * 60, **COOKIE_OPTS)
    response.set_cookie("refresh_token", refresh, max_age=settings.refresh_token_expire_days * 86400, **COOKIE_OPTS)
    return construire_user_read(user, session)


@router.post("/refresh")
@limiter.limit("10/minute")
def refresh(request: Request, response: Response, refresh_token: str | None = Cookie(default=None), session: Session = Depends(get_session)):
    if not refresh_token:
        raise HTTPException(401, "Refresh token manquant.")
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(401, "Refresh token invalide.")

    stored = session.exec(select(RefreshToken).where(RefreshToken.token == refresh_token)).first()
    if not stored or stored.revoked or stored.expires_at < datetime.utcnow():
        raise HTTPException(401, "Session expirée. Reconnectez-vous.")

    user = session.get(Utilisateur, stored.user_id)
    if not user or not user.actif:
        raise HTTPException(401, "Utilisateur invalide.")

    # Rotation : révoquer l'ancien token, émettre un nouveau
    stored.revoked = True
    session.add(stored)

    new_refresh = create_refresh_token({"sub": str(user.id)})
    rt = RefreshToken(
        user_id=user.id,
        token=new_refresh,
        expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(rt)
    session.commit()

    access = create_access_token({"sub": str(user.id)})
    response.set_cookie("access_token", access, max_age=settings.access_token_expire_minutes * 60, **COOKIE_OPTS)
    response.set_cookie("refresh_token", new_refresh, max_age=settings.refresh_token_expire_days * 86400, **COOKIE_OPTS)
    return {"message": "Token rafraîchi"}


@router.post("/logout")
def logout(response: Response, refresh_token: str | None = Cookie(default=None), session: Session = Depends(get_session)):
    if refresh_token:
        stored = session.exec(select(RefreshToken).where(RefreshToken.token == refresh_token)).first()
        if stored:
            stored.revoked = True
            session.add(stored)
            session.commit()
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Déconnecté"}


@router.get("/verifier-acces", status_code=204)
def verifier_acces(_: Utilisateur = Depends(get_current_user)) -> Response:
    """Réservé au `forward_auth` de Caddy : 204 si la session est valide, 401 sinon.

    Caddy interroge cet endpoint avant de servir un fichier de `/uploads/*`, qui
    était jusqu'ici public. Il ne renvoie **aucun contenu** : seul le code compte,
    et un corps vide évite d'exposer quoi que ce soit sur le porteur du cookie.

    Il s'appuie volontairement sur `get_current_user`, la dépendance d'authentification
    commune, et non sur une vérification allégée maison. Une seconde façon de valider
    une session serait une seconde sémantique à maintenir — et à faire diverger. Le
    coût dominant est le trajet HTTP interne, pas la lecture SQLite qu'elle effectue :
    l'économiser ne rapporterait presque rien et laisserait un compte désactivé
    conserver l'accès jusqu'à l'expiration de son jeton (120 min).
    """
    return Response(status_code=204)


class RenvoiVerificationRequest(BaseModel):
    email: str


@router.get("/verifier-email", status_code=200)
def verify_email(token: str, session: Session = Depends(get_session)):
    """Vérifie l'adresse email via le token reçu par mail."""
    evt = session.exec(
        select(EmailVerificationToken).where(EmailVerificationToken.token == token)
    ).first()

    if not evt or evt.used or evt.expires_at < datetime.utcnow():
        raise HTTPException(400, "Lien de vérification invalide ou expiré.")

    user = session.get(Utilisateur, evt.user_id)
    if not user:
        raise HTTPException(400, "Lien de vérification invalide ou expiré.")

    user.email_verifie = True
    evt.used = True

    session.add(user)
    session.add(evt)
    session.commit()
    return {"message": "Adresse e-mail vérifiée avec succès."}


@router.post("/renvoyer-verification", status_code=204)
@limiter.limit("3/minute")
def resend_verification(
    request: Request,
    body: RenvoiVerificationRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Renvoie un email de vérification (si le compte existe et n'est pas encore vérifié)."""
    user = session.exec(
        select(Utilisateur).where(Utilisateur.email == body.email.strip().lower())
    ).first()

    if user and not user.email_verifie:
        # Invalider les anciens tokens
        old_tokens = session.exec(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used == False,  # noqa: E712
            )
        ).all()
        for t in old_tokens:
            t.used = True
            session.add(t)

        raw_token = secrets.token_urlsafe(32)
        evt = EmailVerificationToken(
            user_id=user.id,
            token=raw_token,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        session.add(evt)
        session.commit()

        cfg_rows = session.exec(
            select(ConfigSite).where(ConfigSite.cle.in_(("site_nom", "site_url")))
        ).all()
        cfg = {row.cle: row.valeur for row in cfg_rows}
        site_url = (cfg.get("site_url") or "https://localhost").rstrip("/")
        site_nom = cfg.get("site_nom") or "5Hostachy"

        from app.utils.email import send_email as _send_email
        background_tasks.add_task(
            _send_email,
            code="verification_email",
            to=user.email,
            context={
                "prenom": user.prenom,
                "token": raw_token,
                "lien": f"{site_url}/auth/verifier-email?token={raw_token}",
                "expire_heures": 24,
                "residence": {"nom": site_nom},
                "app": {"url": site_url},
            },
        )

    # Toujours 204 (pas d'énumération de comptes)
    return None
