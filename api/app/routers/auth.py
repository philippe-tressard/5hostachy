"""Router auth — inscription, connexion, déconnexion, refresh, réinitialisation mot de passe."""
import re
import secrets
from datetime import date, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, Cookie, Request, status
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select, or_

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_and_rehash,
)
from app.auth.deps import get_current_user
from app.config import get_settings
from app.database import get_session
from app.models.core import (Utilisateur, RefreshToken, PasswordResetToken, EmailVerificationToken, StatutUtilisateur, RoleUtilisateur, Batiment,
    ConfigSite, DemandeModificationProfil, StatutDemandeProfil, TelemetryEvent)
from app.schemas import UserCreate, UserRead, LoginRequest
from app.utils.limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _check_password_strength(password: str) -> None:
    """Vérifie la complexité du mot de passe. Lève HTTPException 400 si les critères ne sont pas satisfaits."""
    errors = []
    if len(password) < 8:
        errors.append("au moins 8 caractères")
    if not re.search(r"[A-Z]", password):
        errors.append("une lettre majuscule")
    if not re.search(r"\d", password):
        errors.append("un chiffre")
    if not re.search(r"[@$!%*?&#._\-+]", password):
        errors.append("un caractère spécial (@$!%*?&#._-+)")
    if errors:
        raise HTTPException(400, "Le mot de passe doit contenir : " + ", ".join(errors) + ".")

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

    existing = session.exec(select(Utilisateur).where(Utilisateur.email == body.email)).first()
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
        consentement_communications=body.consentement_communications,
        batiment_id=body.batiment_id,
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
        from app.utils.auto_match_service import auto_match_pour_utilisateur
        auto_match_pour_utilisateur(user, session)
        session.commit()

    return user


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest, response: Response, session: Session = Depends(get_session)):
    user = session.exec(select(Utilisateur).where(Utilisateur.email == body.email)).first()
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
    return _build_user_read(user, session)


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


def _build_user_read(user: Utilisateur, session: Session) -> UserRead:
    from app.models.core import Delegation, StatutDelegation
    batiment_nom = None
    if user.batiment_id:
        bat = session.get(Batiment, user.batiment_id)
        if bat:
            batiment_nom = f"Bât. {bat.numero}"
    # Charger les délégations actives où l'utilisateur est aidant
    today = date.today()
    deleg_rows = session.exec(
        select(Delegation).where(
            Delegation.aidant_id == user.id,
            Delegation.statut == StatutDelegation.active,
            Delegation.date_debut <= today,
            or_(Delegation.date_fin.is_(None), Delegation.date_fin >= today),
        )
    ).all()
    delegations_aidant = []
    for d in deleg_rows:
        mandant = session.get(Utilisateur, d.mandant_id)
        if mandant:
            delegations_aidant.append({
                "delegation_id": d.id,
                "mandant_id": mandant.id,
                "mandant_nom": f"{mandant.prenom} {mandant.nom}",
            })
    return UserRead.from_orm_with_roles(user, batiment_nom=batiment_nom, delegations_aidant=delegations_aidant)


@router.get("/me", response_model=UserRead)
def me(
    user: Utilisateur = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return _build_user_read(user, session)


class MeUpdate(BaseModel):
    prenom: str | None = None
    nom: str | None = None
    email: str | None = None
    telephone: str | None = None
    societe: str | None = None
    fonction: str | None = None
    last_seen_actualites: str | None = None
    preferences_notifications: str | None = None
    demarche_arrivant: str | None = None

    @field_validator("nom", mode="before")
    @classmethod
    def uppercase_nom(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else v

    @field_validator("prenom", mode="before")
    @classmethod
    def titlecase_prenom(cls, v: str | None) -> str | None:
        return v.strip().title() if v else v


@router.patch("/me", response_model=UserRead)
def update_me(
    body: MeUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    if body.prenom is not None:
        user.prenom = body.prenom
    if body.nom is not None:
        user.nom = body.nom
    if body.email is not None:
        new_email = body.email.strip().lower()
        if new_email != user.email.lower():
            existing = session.exec(select(Utilisateur).where(Utilisateur.email == new_email)).first()
            if existing:
                raise HTTPException(400, "Cette adresse e-mail est déjà utilisée")
            user.email = new_email
    if body.telephone is not None:
        user.telephone = body.telephone
    if body.societe is not None:
        user.societe = body.societe
    if body.fonction is not None:
        user.fonction = body.fonction
    if body.last_seen_actualites is not None:
        user.last_seen_actualites = datetime.fromisoformat(body.last_seen_actualites.replace("Z", "+00:00"))
    if body.preferences_notifications is not None:
        user.preferences_notifications = body.preferences_notifications
    if body.demarche_arrivant is not None:
        if body.demarche_arrivant not in ("nouvel_arrivant", "deja_resident"):
            raise HTTPException(400, "Valeur invalide pour demarche_arrivant")
        user.demarche_arrivant = body.demarche_arrivant
    session.add(user)
    session.commit()
    session.refresh(user)
    return _build_user_read(user, session)


# ── Demandes de modification de profil (statut / bâtiment) ───────────────────

class DemandeModifCreate(BaseModel):
    statut_souhaite: str | None = None
    batiment_id_souhaite: int | None = None
    motif: str | None = None


@router.post("/me/demande-modification", status_code=201)
def creer_demande_modif(
    body: DemandeModifCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Soumet une demande de changement de type de résident et/ou de bâtiment, soumise à validation CS."""
    if not body.statut_souhaite and not body.batiment_id_souhaite:
        raise HTTPException(400, "Au moins un champ à modifier (statut ou bâtiment) est requis.")

    # Valider le statut si fourni
    if body.statut_souhaite:
        try:
            StatutUtilisateur(body.statut_souhaite)
        except ValueError:
            raise HTTPException(400, f"Statut invalide : {body.statut_souhaite}")

    # Vérifier qu'il n'y a pas déjà une demande en attente
    existante = session.exec(
        select(DemandeModificationProfil).where(
            DemandeModificationProfil.utilisateur_id == user.id,
            DemandeModificationProfil.statut_demande == StatutDemandeProfil.en_attente,
        )
    ).first()
    if existante:
        raise HTTPException(409, "Une demande est déjà en cours. Attendez qu'elle soit traitée.")

    demande = DemandeModificationProfil(
        utilisateur_id=user.id,
        statut_souhaite=body.statut_souhaite,
        batiment_id_souhaite=body.batiment_id_souhaite,
        motif=body.motif,
    )
    session.add(demande)
    session.commit()
    session.refresh(demande)
    return demande


@router.get("/me/demandes-modification")
def mes_demandes_modif(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Retourne les demandes de modification de profil de l'utilisateur connecté."""
    demandes = session.exec(
        select(DemandeModificationProfil)
        .where(DemandeModificationProfil.utilisateur_id == user.id)
        .order_by(DemandeModificationProfil.cree_le.desc())
        .limit(10)
    ).all()
    # Enrichir avec nom bâtiment souhaité
    result = []
    for d in demandes:
        item = d.model_dump()
        if d.batiment_id_souhaite:
            bat = session.get(Batiment, d.batiment_id_souhaite)
            item["batiment_nom_souhaite"] = f"Bât. {bat.numero}" if bat else None
        else:
            item["batiment_nom_souhaite"] = None
        result.append(item)
    return result


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
    session: Session = Depends(get_session),
):
    """
    Génère un token de réinitialisation et envoie un e-mail si le compte existe.
    Retourne toujours 204 pour éviter l'enumération d'adresses e-mail.
    """
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

        import asyncio
        from app.utils.email import send_email
        asyncio.create_task(
            send_email(
                code="reinitialisation_mdp",
                to=user.email,
                context={
                    "prenom": user.prenom,
                    "token": raw_token,
                    "expire_heures": 1,
                },
                session=session,
            )
        ) if asyncio.get_event_loop().is_running() else None

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


# ──────────────────────────────────────────────
#  Vérification email
# ──────────────────────────────────────────────

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


# ── RGPD — Données de télémétrie ─────────────────────────────────────────────


@router.get("/me/telemetrie")
@limiter.limit("5/minute")
def export_telemetrie(
    request: Request,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Exporter ses données de télémétrie (RGPD art. 15 + 20 — droit d'accès et portabilité)."""
    events = session.exec(
        select(TelemetryEvent)
        .where(TelemetryEvent.user_id == user.id)
        .order_by(TelemetryEvent.cree_le.desc())  # type: ignore
    ).all()
    return [
        {
            "page": ev.page,
            "action": ev.action,
            "detail": ev.detail,
            "date": ev.cree_le.isoformat() if ev.cree_le else None,
        }
        for ev in events
    ]


@router.delete("/me/telemetrie", status_code=204)
@limiter.limit("5/minute")
def effacer_telemetrie(
    request: Request,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Effacer ses données de télémétrie (RGPD art. 17 — droit à l'effacement)."""
    events = session.exec(
        select(TelemetryEvent).where(TelemetryEvent.user_id == user.id)
    ).all()
    for ev in events:
        session.delete(ev)
    session.commit()


class OptOutTelemetrieBody(BaseModel):
    opt_out_telemetrie: bool


@router.patch("/me/opt-out-telemetrie", status_code=204)
@limiter.limit("10/minute")
def toggle_opt_out_telemetrie(
    request: Request,
    body: OptOutTelemetrieBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Activer/désactiver la collecte de télémétrie (RGPD art. 21 — droit d'opposition)."""
    user.opt_out_telemetrie = body.opt_out_telemetrie
    session.add(user)
    session.commit()
