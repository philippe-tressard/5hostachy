"""Router admin — gestion comptes, sauvegardes, configuration."""
import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin, require_cs_or_admin
from app.database import get_session
from sqlalchemy import or_
from app.models.core import (
    Utilisateur, CommandeAcces, StatutCommande,
    HistoriqueSauvegarde, ConfigSauvegarde, StatutSauvegarde,
    Notification, RoleUtilisateur, Batiment,
    DemandeModificationProfil, StatutDemandeProfil, StatutUtilisateur,
    LocationBail, StatutBail, RemiseObjet,
    AgCsInfo, MembreCS, SyndicInfo, MembreSyndic,
    UserLot, Telecommande, Vigik, ConfigSite, Lot,
    RefreshToken, PasswordResetToken,
    TelecommandeImport, VigikImport, LotImport,
    Mandat, VoteSondage, VoteIdee,
    StatutLotImport, StatutImport,
)
from app.schemas import UserRead
from app.utils.backup import run_backup

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_site_manager_user_id(session: Session) -> Optional[int]:
    cfg_site_manager = session.get(ConfigSite, "site_manager_user_id")
    if not cfg_site_manager:
        return None
    valeur = (cfg_site_manager.valeur or "").strip()
    if not valeur.isdigit():
        return None
    return int(valeur)


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

    # Auto-match sur les 3 systèmes d'import dès qu'un compte est validé
    auto_match_result: dict[str, Any] = {}
    if body.action == "valider":
        from app.utils.auto_match_service import auto_match_pour_utilisateur
        auto_match_result = auto_match_pour_utilisateur(user, session)

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
    session.commit()
    return {"statut": cmd.statut}


# ── Sauvegardes ──────────────────────────────────────────────────────────────

@router.get("/sauvegardes/config")
def get_backup_config(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    cfg = session.exec(select(ConfigSauvegarde)).first()
    return cfg


@router.put("/sauvegardes/config")
def update_backup_config(
    body: dict,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    cfg = session.exec(select(ConfigSauvegarde)).first()
    if not cfg:
        cfg = ConfigSauvegarde()
    for k, v in body.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    cfg.modifie_par_id = admin.id
    cfg.modifie_le = datetime.utcnow()
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


@router.post("/sauvegardes/maintenant")
def backup_now(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    entry = HistoriqueSauvegarde(declenchee_par="manuelle", declenchee_par_user_id=admin.id)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    background_tasks.add_task(run_backup, entry.id)
    return {"message": "Sauvegarde lancée en arrière-plan", "id": entry.id}


@router.get("/sauvegardes/historique")
def backup_history(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    return session.exec(
        select(HistoriqueSauvegarde).order_by(HistoriqueSauvegarde.cree_le.desc())
    ).all()


# ── Maintenance cron ──────────────────────────────────────────────────────────

from fastapi import Header
from app.models.core import HistoriqueMaintenance
from app.config import get_settings


class RapportMaintenance(BaseModel):
    statut: str = "succes"
    tokens_supprimes: int = 0
    taille_db_octets: Optional[int] = None
    duree_secondes: Optional[int] = None
    erreur: Optional[str] = None
    declenchee_par: str = "cron"
    cree_le: Optional[datetime] = None
    terminee_le: Optional[datetime] = None


@router.post("/maintenance/rapport", status_code=201)
def maintenance_rapport(
    body: RapportMaintenance,
    x_maintenance_key: Optional[str] = Header(default=None, alias="x-maintenance-key"),
    session: Session = Depends(get_session),
):
    settings = get_settings()
    if not settings.maintenance_key:
        raise HTTPException(status_code=503, detail="Maintenance reporting non configuré (MAINTENANCE_KEY vide)")
    if x_maintenance_key != settings.maintenance_key:
        raise HTTPException(status_code=403, detail="Clé maintenance invalide")
    entry = HistoriqueMaintenance(
        declenchee_par=body.declenchee_par,
        statut=body.statut,
        tokens_supprimes=body.tokens_supprimes,
        taille_db_octets=body.taille_db_octets,
        duree_secondes=body.duree_secondes,
        erreur=body.erreur,
        cree_le=body.cree_le or datetime.utcnow(),
        terminee_le=body.terminee_le,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.get("/maintenance/historique")
def maintenance_history(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    return session.exec(
        select(HistoriqueMaintenance).order_by(HistoriqueMaintenance.cree_le.desc()).limit(50)
    ).all()


@router.post("/maintenance/lancer", status_code=202)
def maintenance_now(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    from app.utils.maintenance import run_maintenance
    entry = HistoriqueMaintenance(declenchee_par="manuelle")
    session.add(entry)
    session.commit()
    session.refresh(entry)
    background_tasks.add_task(run_maintenance, entry.id)
    return {"message": "Maintenance lancée en arrière-plan", "id": entry.id}


# ── Modèles e-mail ────────────────────────────────────────────────────────────────────────

from app.models.core import ModeleEmail


@router.get("/modeles-email")
def list_modeles_email(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    return session.exec(select(ModeleEmail).order_by(ModeleEmail.code)).all()


@router.patch("/modeles-email/{modele_id}")
def update_modele_email(
    modele_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    modele = session.get(ModeleEmail, modele_id)
    if not modele:
        raise HTTPException(404, "Modèle introuvable")
    allowed = {"sujet", "corps_html", "corps_texte", "actif"}
    for key, value in payload.items():
        if key in allowed:
            setattr(modele, key, value)
    from datetime import datetime
    modele.modifie_le = datetime.utcnow()
    modele.modifie_par_id = _.id
    session.add(modele)
    session.commit()
    session.refresh(modele)
    return modele


# ── Notifications utilisateur ────────────────────────────────────────────────

@router.get("/notifications")
def mes_notifications(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return session.exec(
        select(Notification)
        .where(Notification.destinataire_id == user.id)
        .order_by(Notification.cree_le.desc())
        .limit(50)
    ).all()


@router.post("/notifications/{notif_id}/lue")
def mark_lue(
    notif_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    notif = session.get(Notification, notif_id)
    if not notif or notif.destinataire_id != user.id:
        raise HTTPException(404, "Notification introuvable")
    notif.lue = True
    session.add(notif)
    session.commit()
    return {"ok": True}


# ── Annuaire public ──────────────────────────────────────────────────────────

@router.get("/annuaire")
def annuaire(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    """Équipe accessible à tous les résidents : membres CS + syndic depuis les tables dédiées."""
    # ── CS ──
    ag = session.exec(select(AgCsInfo)).first()
    membres_cs_raw = session.exec(select(MembreCS)).all()

    def _genre_order(g: str) -> int:
        return 0 if g in ("Mme", "Mlle") else 1

    membres_cs_sorted = sorted(
        membres_cs_raw,
        key=lambda m: (m.batiment_id or 9999, _genre_order(m.genre), m.nom.lower()),
    )

    batiments_cache: dict[int, str] = {}
    def _bat_nom(bid: Optional[int]) -> Optional[str]:
        if bid is None:
            return None
        if bid not in batiments_cache:
            bat = session.get(Batiment, bid)
            batiments_cache[bid] = bat.numero if bat else str(bid)
        return batiments_cache[bid]

    user_photo_cache: dict[int, Optional[str]] = {}
    def _user_photo(uid: Optional[int]) -> Optional[str]:
        if uid is None:
            return None
        if uid not in user_photo_cache:
            u = session.get(Utilisateur, uid)
            user_photo_cache[uid] = u.photo_url if u else None
        return user_photo_cache[uid]

    site_manager_user_id = _get_site_manager_user_id(session)

    cs_out = [
        {
            "id": m.id,
            "genre": m.genre,
            "prenom": m.prenom,
            "nom": m.nom,
            "batiment_nom": _bat_nom(m.batiment_id),
            "etage": m.etage,
            "est_gestionnaire_site": bool(
                m.est_gestionnaire_site or (site_manager_user_id is not None and m.user_id == site_manager_user_id)
            ),
            "est_president": m.est_president,
            "photo_url": _user_photo(m.user_id),
        }
        for m in membres_cs_sorted
    ]

    # ── Syndic ──
    syndic_info = session.exec(select(SyndicInfo)).first()
    membres_syndic_raw = session.exec(select(MembreSyndic)).all()
    membres_syndic_sorted = sorted(
        membres_syndic_raw,
        key=lambda m: m.ordre,
    )
    syndic_membres_out = [
        {
            "id": m.id,
            "genre": m.genre,
            "prenom": m.prenom,
            "nom": m.nom,
            "fonction": m.fonction,
            "email": m.email,
            "telephone": m.telephone,
            "est_principal": m.est_principal,
            "photo_url": _user_photo(m.user_id),
        }
        for m in membres_syndic_sorted
    ]

    return {
        "cs": {
            "ag_annee": ag.ag_annee if ag else None,
            "ag_date": ag.ag_date.isoformat() if (ag and ag.ag_date) else None,
            "membres": cs_out,
        },
        "syndic": {
            "nom_syndic": syndic_info.nom_syndic if syndic_info else "",
            "adresse": syndic_info.adresse if syndic_info else "",
            "membres": syndic_membres_out,
        },
    }


# ── Annuaire CS — gestion (CS + admin) ──────────────────────────────────────

class MembreCSIn(BaseModel):
    genre: str
    prenom: str
    nom: str
    batiment_id: Optional[int] = None
    etage: Optional[int] = None
    est_president: bool = False
    user_id: Optional[int] = None

class CompositionCSIn(BaseModel):
    ag_annee: Optional[int] = None
    ag_date: Optional[str] = None   # ISO "YYYY-MM-DD" ou None
    membres: list[MembreCSIn] = []

@router.get("/annuaire/cs")
def get_composition_cs(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    ag = session.exec(select(AgCsInfo)).first()
    membres = session.exec(select(MembreCS).order_by(MembreCS.ordre)).all()
    site_manager_user_id = _get_site_manager_user_id(session)
    _bat_cache: dict[int, str] = {}
    def _bat_nom_cs(bid: Optional[int]) -> Optional[str]:
        if bid is None:
            return None
        if bid not in _bat_cache:
            bat = session.get(Batiment, bid)
            _bat_cache[bid] = bat.numero if bat else str(bid)
        return _bat_cache[bid]
    return {
        "ag_annee": ag.ag_annee if ag else None,
        "ag_date": ag.ag_date.isoformat() if (ag and ag.ag_date) else None,
        "membres": [
            {
                "id": m.id,
                "genre": m.genre,
                "prenom": m.prenom,
                "nom": m.nom,
                "batiment_id": m.batiment_id,
                "batiment_nom": _bat_nom_cs(m.batiment_id),
                "etage": m.etage,
                "est_gestionnaire_site": bool(
                    m.est_gestionnaire_site or (site_manager_user_id is not None and m.user_id == site_manager_user_id)
                ),
                "est_president": m.est_president,
                "ordre": m.ordre,
                "user_id": m.user_id,
            }
            for m in membres
        ],
    }

@router.put("/annuaire/cs")
def put_composition_cs(
    body: CompositionCSIn,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    # Valider qu'il y a au maximum 1 président
    presidents_count = sum(1 for mb in body.membres if mb.est_president)
    if presidents_count > 1:
        raise HTTPException(status_code=400, detail="Il ne peut y avoir qu'un seul président du Conseil Syndical.")

    # Upsert AgCsInfo
    from datetime import date as date_type
    ag = session.exec(select(AgCsInfo)).first()
    if ag is None:
        ag = AgCsInfo()
        session.add(ag)
    ag.ag_annee = body.ag_annee
    ag.ag_date = date_type.fromisoformat(body.ag_date) if body.ag_date else None

    # Remplacer tous les membres CS
    old = session.exec(select(MembreCS)).all()
    for m in old:
        session.delete(m)
    session.flush()

    for i, mb in enumerate(body.membres):
        session.add(MembreCS(
            genre=mb.genre,
            prenom=mb.prenom,
            nom=mb.nom,
            batiment_id=mb.batiment_id,
            etage=mb.etage,
            est_gestionnaire_site=False,
            est_president=mb.est_president,
            ordre=i,
            user_id=mb.user_id,
        ))

    session.commit()
    return {"ok": True}


# ── Annuaire Syndic — gestion (CS + admin) ──────────────────────────────────

class MembreSyndicIn(BaseModel):
    genre: str
    prenom: str
    nom: str
    fonction: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    est_principal: bool = False
    user_id: Optional[int] = None

class SyndicIn(BaseModel):
    nom_syndic: str = ""
    adresse: str = ""
    membres: list[MembreSyndicIn] = []

@router.get("/annuaire/syndic")
def get_syndic_info(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    syndic = session.exec(select(SyndicInfo)).first()
    membres = session.exec(select(MembreSyndic).order_by(MembreSyndic.ordre)).all()
    return {
        "nom_syndic": syndic.nom_syndic if syndic else "",
        "adresse": syndic.adresse if syndic else "",
        "membres": [
            {
                "id": m.id,
                "genre": m.genre,
                "prenom": m.prenom,
                "nom": m.nom,
                "fonction": m.fonction,
                "email": m.email,
                "telephone": m.telephone,
                "est_principal": m.est_principal,
                "ordre": m.ordre,
                "user_id": m.user_id,
            }
            for m in membres
        ],
    }

@router.put("/annuaire/syndic")
def put_syndic_info(
    body: SyndicIn,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    # Upsert SyndicInfo
    syndic = session.exec(select(SyndicInfo)).first()
    if syndic is None:
        syndic = SyndicInfo()
        session.add(syndic)
    syndic.nom_syndic = body.nom_syndic
    syndic.adresse = body.adresse

    # Remplacer tous les membres syndic
    old = session.exec(select(MembreSyndic)).all()
    for m in old:
        session.delete(m)
    session.flush()

    for i, mb in enumerate(body.membres):
        session.add(MembreSyndic(
            genre=mb.genre,
            prenom=mb.prenom,
            nom=mb.nom,
            fonction=mb.fonction,
            email=mb.email,
            telephone=mb.telephone,
            est_principal=mb.est_principal,
            ordre=i,
            user_id=mb.user_id,
        ))

    session.commit()
    return {"ok": True}


# ── Gestion des utilisateurs (rôles) ────────────────────────────────────────────

@router.get("/utilisateurs")
def list_utilisateurs(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Liste tous les utilisateurs avec leurs rôles cumulés (CS et admin) + tags de liaison."""
    users = session.exec(select(Utilisateur).order_by(Utilisateur.cree_le.desc())).all()

    # Batch : user_ids ayant au moins 1 lot lié
    loti_ids = set(
        session.exec(
            select(UserLot.user_id).where(UserLot.actif == True).distinct()
        ).all()
    )
    # Batch : user_ids ayant au moins 1 télécommande
    tc_ids = set(
        session.exec(
            select(Telecommande.user_id).distinct()
        ).all()
    )
    # Batch : user_ids ayant au moins 1 vigik
    vigik_ids = set(
        session.exec(
            select(Vigik.user_id).distinct()
        ).all()
    )
    # Batch : user_ids liés via un bail (bailleur ou locataire)
    bail_bailleur_ids = set(
        session.exec(
            select(LocationBail.bailleur_id).distinct()
        ).all()
    )
    bail_locataire_ids = set(
        session.exec(
            select(LocationBail.locataire_id).where(LocationBail.locataire_id != None).distinct()
        ).all()
    )
    lie_ids = bail_bailleur_ids | bail_locataire_ids

    result = []
    for u in users:
        d = UserRead.from_orm_with_roles(u).model_dump()
        d["has_lots"] = u.id in loti_ids
        d["has_tc"] = u.id in tc_ids
        d["has_vigik"] = u.id in vigik_ids
        d["has_bail"] = u.id in lie_ids
        result.append(d)
    return result


class RoleAction(BaseModel):
    role: str  # résident | conseil_syndical | admin


@router.post("/utilisateurs/{user_id}/ajouter-role", response_model=UserRead)
def ajouter_role(
    user_id: int,
    body: RoleAction,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Ajouter un rôle à un utilisateur sans retirer les existants."""
    user = session.get(Utilisateur, user_id)
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    if not user.actif:
        raise HTTPException(400, "Impossible de modifier un compte inactif.")
    try:
        role = RoleUtilisateur(body.role)
    except ValueError:
        raise HTTPException(400, f"Rôle invalide : {body.role}")
    user.ajouter_role(role)
    labels = {
        RoleUtilisateur.résident: "Résident",
        RoleUtilisateur.conseil_syndical: "Membre du Conseil Syndical",
        RoleUtilisateur.admin: "Administrateur",
    }
    notif = Notification(
        destinataire_id=user.id,
        type="system",
        titre="Rôle ajouté",
        corps=f"Le rôle {labels.get(role, body.role)} vous a été attribué.",
        lien="/profil",
    )
    session.add(user)
    session.add(notif)
    session.commit()
    session.refresh(user)
    from app.schemas import UserRead
    return UserRead.from_orm_with_roles(user)


@router.post("/utilisateurs/{user_id}/retirer-role", response_model=UserRead)
def retirer_role(
    user_id: int,
    body: RoleAction,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Retirer un rôle d'un utilisateur (le rôle 'résident' ne peut pas être retiré)."""
    if admin.id == user_id and body.role == RoleUtilisateur.admin.value:
        raise HTTPException(400, "Vous ne pouvez pas vous retirer le rôle admin.")
    user = session.get(Utilisateur, user_id)
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    if body.role == RoleUtilisateur.résident.value:
        raise HTTPException(400, "Le rôle 'Résident' est le rôle de base, il ne peut pas être retiré.")
    try:
        role = RoleUtilisateur(body.role)
    except ValueError:
        raise HTTPException(400, f"Rôle invalide : {body.role}")
    user.retirer_role(role)
    labels = {
        RoleUtilisateur.conseil_syndical: "Conseil Syndical",
        RoleUtilisateur.admin: "Administrateur",
    }
    notif = Notification(
        destinataire_id=user.id,
        type="system",
        titre="Rôle retiré",
        corps=f"Le rôle {labels.get(role, body.role)} vous a été retiré.",
        lien="/profil",
    )
    session.add(user)
    session.add(notif)
    session.commit()
    session.refresh(user)
    from app.schemas import UserRead
    return UserRead.from_orm_with_roles(user)


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
        item["utilisateur_nom"] = f"{utilisateur.prenom} {utilisateur.nom}" if utilisateur else "?"
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
class AdminUserUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    societe: Optional[str] = None
    statut: Optional[StatutUtilisateur] = None
    batiment_id: Optional[int] = None
    actif: Optional[bool] = None


@router.patch("/utilisateurs/{user_id}", response_model=UserRead)
def modifier_utilisateur(
    user_id: int,
    body: AdminUserUpdate,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Modifier les informations d'un utilisateur (admin)."""
    user = session.get(Utilisateur, user_id)
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    if body.email and body.email != user.email:
        existing = session.exec(select(Utilisateur).where(Utilisateur.email == body.email)).first()
        if existing:
            raise HTTPException(400, "Cet e-mail est déjà utilisé.")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(user, field, val)
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserRead.from_orm_with_roles(user)


@router.delete("/utilisateurs/{user_id}", status_code=204)
def supprimer_utilisateur(
    user_id: int,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Supprimer définitivement un utilisateur (admin). Impossible de se supprimer soi-même.
    Nettoie toutes les interactions liées : lots, tokens, accès, notifications, votes, baux, etc."""
    if admin.id == user_id:
        raise HTTPException(400, "Vous ne pouvez pas supprimer votre propre compte.")
    user = session.get(Utilisateur, user_id)
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")

    # 1. Tokens d'authentification
    for t in session.exec(select(RefreshToken).where(RefreshToken.user_id == user_id)).all():
        session.delete(t)
    for t in session.exec(select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)).all():
        session.delete(t)

    # 2. UserLot + nettoyage utilisateurs_json dans LotImport + reset statut
    user_lots = session.exec(select(UserLot).where(UserLot.user_id == user_id)).all()
    lot_ids = {ul.lot_id for ul in user_lots}
    for ul in user_lots:
        session.delete(ul)
    if lot_ids:
        for imp in session.exec(select(LotImport).where(LotImport.lot_id.in_(lot_ids))).all():  # type: ignore
            users = json.loads(imp.utilisateurs_json or "[]")
            nouveau = [e for e in users if e.get("user_id") != user_id]
            if len(nouveau) != len(users):
                imp.utilisateurs_json = json.dumps(nouveau, ensure_ascii=False)
                if not nouveau and imp.statut != StatutLotImport.ignore:
                    imp.statut = StatutLotImport.lot_lie if imp.lot_id else StatutLotImport.en_attente
                    imp.resolu_le = None
                session.add(imp)

    # 3. Commandes d'accès
    for c in session.exec(select(CommandeAcces).where(CommandeAcces.user_id == user_id)).all():
        session.delete(c)

    # 4. Notifications
    for n in session.exec(select(Notification).where(Notification.destinataire_id == user_id)).all():
        session.delete(n)

    # 5. Votes
    for v in session.exec(select(VoteSondage).where(VoteSondage.user_id == user_id)).all():
        session.delete(v)
    for v in session.exec(select(VoteIdee).where(VoteIdee.user_id == user_id)).all():
        session.delete(v)

    # 6. Demandes modification profil
    for d in session.exec(select(DemandeModificationProfil).where(DemandeModificationProfil.utilisateur_id == user_id)).all():
        session.delete(d)
    for d in session.exec(select(DemandeModificationProfil).where(DemandeModificationProfil.traite_par_id == user_id)).all():
        d.traite_par_id = None
        session.add(d)

    # 7. Mandats (bailleur ou mandataire)
    for m in session.exec(select(Mandat).where(
        or_(Mandat.bailleur_id == user_id, Mandat.mandataire_id == user_id)
    )).all():
        session.delete(m)

    # 8. Télécommandes et Vigiks (non-nullifiable → suppression)
    deleted_tc_ids = set()
    for tc in session.exec(select(Telecommande).where(Telecommande.user_id == user_id)).all():
        deleted_tc_ids.add(tc.id)
        session.delete(tc)
    deleted_vigik_ids = set()
    for v in session.exec(select(Vigik).where(Vigik.user_id == user_id)).all():
        deleted_vigik_ids.add(v.id)
        session.delete(v)

    # 9. TelecommandeImport / VigikImport — nullifier FK + reset statut
    ti_filter = [TelecommandeImport.user_proprietaire_id == user_id, TelecommandeImport.user_locataire_id == user_id]
    if deleted_tc_ids:
        ti_filter.append(TelecommandeImport.telecommande_id.in_(deleted_tc_ids))  # type: ignore
    for ti in session.exec(select(TelecommandeImport).where(or_(*ti_filter))).all():
        if ti.user_proprietaire_id == user_id:
            ti.user_proprietaire_id = None
        if ti.user_locataire_id == user_id:
            ti.user_locataire_id = None
        if ti.telecommande_id in deleted_tc_ids:
            ti.telecommande_id = None
        if ti.statut != StatutImport.ignore:
            if ti.user_proprietaire_id is None and ti.user_locataire_id is None:
                ti.statut = StatutImport.en_attente
                ti.resolu_le = None
            elif ti.telecommande_id is None:
                ti.statut = StatutImport.proprietaire_lie
                ti.resolu_le = None
        session.add(ti)
    vi_filter = [VigikImport.user_proprietaire_id == user_id, VigikImport.user_locataire_id == user_id]
    if deleted_vigik_ids:
        vi_filter.append(VigikImport.vigik_id.in_(deleted_vigik_ids))  # type: ignore
    for vi in session.exec(select(VigikImport).where(or_(*vi_filter))).all():
        if vi.user_proprietaire_id == user_id:
            vi.user_proprietaire_id = None
        if vi.user_locataire_id == user_id:
            vi.user_locataire_id = None
        if vi.vigik_id in deleted_vigik_ids:
            vi.vigik_id = None
        if vi.statut != StatutImport.ignore:
            if vi.user_proprietaire_id is None and vi.user_locataire_id is None:
                vi.statut = StatutImport.en_attente
                vi.resolu_le = None
            elif vi.vigik_id is None:
                vi.statut = StatutImport.proprietaire_lie
                vi.resolu_le = None
        session.add(vi)

    # 10. LocationBail : locataire → nullifier ; bailleur → supprimer bail + objets remis
    for bail in session.exec(select(LocationBail).where(LocationBail.locataire_id == user_id)).all():
        bail.locataire_id = None
        session.add(bail)
    for bail in session.exec(select(LocationBail).where(LocationBail.bailleur_id == user_id)).all():
        for obj in session.exec(select(RemiseObjet).where(RemiseObjet.bail_id == bail.id)).all():
            session.delete(obj)
        session.delete(bail)

    # 11. HistoriqueSauvegarde — nullifier la référence optionnelle
    for h in session.exec(select(HistoriqueSauvegarde).where(HistoriqueSauvegarde.declenchee_par_user_id == user_id)).all():
        h.declenchee_par_user_id = None
        session.add(h)

    session.delete(user)
    session.commit()


@router.post("/utilisateurs/{user_id}/changer-role", response_model=UserRead)
def changer_role(
    user_id: int,
    body: RoleAction,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Remplace tous les rôles par un seul (compatibilité ascendante)."""
    if admin.id == user_id:
        raise HTTPException(400, "Vous ne pouvez pas changer votre propre rôle.")
    user = session.get(Utilisateur, user_id)
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    if not user.actif:
        raise HTTPException(400, "Impossible de changer le rôle d'un compte inactif.")
    try:
        nouveau_role = RoleUtilisateur(body.role)
    except ValueError:
        raise HTTPException(400, f"Rôle invalide : {body.role}")
    # Réinitialiser à un seul rôle
    user.roles_json = nouveau_role.value
    user.role = nouveau_role
    labels = {
        RoleUtilisateur.résident: "Résident",
        RoleUtilisateur.conseil_syndical: "Membre du Conseil Syndical",
        RoleUtilisateur.admin: "Administrateur",
    }
    notif = Notification(
        destinataire_id=user.id,
        type="system",
        titre="Votre rôle a été mis à jour",
        corps=f"Vos rôles dans l'application : {labels.get(nouveau_role, body.role)}.",
        lien="/profil",
    )
    session.add(user)
    session.add(notif)
    session.commit()
    session.refresh(user)
    from app.schemas import UserRead
    return UserRead.from_orm_with_roles(user)

class AccueilArrivantBody(BaseModel):
    batiment: Optional[str] = None
    ancien_resident: Optional[str] = None
    ancien_resident_inconnu: bool = False


def _declencher_accueil_arrivant(
    user: Utilisateur,
    body: AccueilArrivantBody,
    background_tasks: BackgroundTasks,
    session: Session,
    allow_repeat: bool = False,
):
    """Déclenche les actions d'accueil pour un nouvel arrivant résidentiel."""
    if not user.actif:
        raise HTTPException(400, "Le compte doit être actif pour déclarer un nouvel arrivant")

    statuts_residentiels = {
        StatutUtilisateur.copropriétaire_résident,
        StatutUtilisateur.copropriétaire_bailleur,
        StatutUtilisateur.locataire,
    }
    if user.statut not in statuts_residentiels:
        raise HTTPException(400, "Cette démarche est réservée aux profils résidentiels")

    if not allow_repeat:
        deja_declenche = session.exec(
            select(Notification).where(
                Notification.destinataire_id == user.id,
                Notification.titre == "Bienvenue dans la résidence !",
            )
        ).first()
        if deja_declenche:
            raise HTTPException(409, "La démarche Nouvel Arrivant a déjà été déclarée pour ce compte")

    nom_complet = f"{user.prenom} {user.nom}"
    bat = body.batiment or ""
    ancien = body.ancien_resident or ""
    bat_str = f", {bat}" if bat else ""
    ancien_str = f" (ancien résident : {ancien})" if ancien else ""
    nb_notifs = 0

    # ── A. Notification unique regroupée → arrivant ───────────────────────────
    demarches: list[str] = []

    # Syndic principal (pour l'email BAL)
    syndic_principal: MembreSyndic | None = session.exec(
        select(MembreSyndic).where(
            MembreSyndic.est_principal == True  # noqa: E712
        )
    ).first()
    if syndic_principal:
        demarches.append(
            f"• Demande d'étiquette boîte aux lettres transmise au syndic{bat_str}{ancien_str}."
        )

    # CS du bâtiment + gestionnaire du site (pour les notifs interphone)
    cs_query = select(MembreCS).where(MembreCS.user_id != None)  # noqa: E711
    site_manager_user_id = _get_site_manager_user_id(session)
    if user.batiment_id:
        cs_filters = (MembreCS.batiment_id == user.batiment_id)
        if site_manager_user_id is not None:
            cs_filters = cs_filters | (MembreCS.user_id == site_manager_user_id)
        cs_members = session.exec(cs_query.where(cs_filters)).all()
    else:
        if site_manager_user_id is not None:
            cs_members = session.exec(cs_query.where(MembreCS.user_id == site_manager_user_id)).all()
        else:
            cs_members = []
    # Dédoublonner par user_id
    cs_seen: set[int] = set()
    cs_unique: list[MembreCS] = []
    for mc in cs_members:
        if mc.user_id not in cs_seen:
            cs_seen.add(mc.user_id)
            cs_unique.append(mc)

    if cs_unique:
        demarches.append(
            f"• Demande d'ajout sur l'interphone transmise au Conseil Syndical{bat_str}{ancien_str}."
        )

    demarches_str = ""
    if demarches:
        demarches_str = (
            "\n\n**Démarches initiées en votre nom**\n"
            + "\n".join(demarches)
        )

    session.add(Notification(
        destinataire_id=user.id,
        type="system",
        titre="Bienvenue dans la résidence !",
        corps=(
            f"Bienvenue {user.prenom} ! Nous sommes heureux de vous accueillir "
            "dans notre résidence. Vous trouverez dans cette application toutes "
            "les informations pratiques : actualités, documents, contacts et services."
            "\n\n**Consignes de la copropriété**\n"
            "L'ensemble des consignes de vie en copropriété est disponible dans "
            "l'application : règlement intérieur, consignes de tri, modalités "
            "d'accès et contacts utiles. N'hésitez pas à vous y référer."
            + demarches_str
        ),
        lien="/",
    ))
    nb_notifs += 1

    # ── B. Notification interphone → CS du bâtiment + gestionnaire du site ─────
    for mc in cs_unique:
        session.add(Notification(
            destinataire_id=mc.user_id,
            type="system",
            titre="Accueil — Demande d'ajout sur l'interphone",
            corps=(
                f"Merci d'ajouter le nom **{nom_complet}**{bat_str}{ancien_str} "
                "sur l'interphone du bâtiment concerné."
            ),
        ))
        nb_notifs += 1

    # ── C. E-mail BAL → syndic principal (CC arrivant) ────────────────────────
    if syndic_principal and syndic_principal.email:
        from app.utils.email import send_email

        cc_list = [user.email] if user.email else []
        background_tasks.add_task(
            send_email,
            code="nouvel_arrivant_bal",
            to=syndic_principal.email,
            context={
                "nom_complet": nom_complet,
                "batiment": bat,
                "ancien_resident": ancien,
            },
            session=session,
            cc=cc_list,
        )

    session.commit()
    return {
        "ok": True,
        "notifications_envoyees": nb_notifs,
        "email_syndic": bool(syndic_principal and syndic_principal.email),
    }


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
            "user_nom": f"{user.prenom} {user.nom}" if user else "?",
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


@router.post("/utilisateurs/{user_id}/accueil-arrivant")
def accueil_arrivant(
    user_id: int,
    body: AccueilArrivantBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    """Déclenche les actions d'accueil pour un nouvel arrivant résidentiel (CS/Admin)."""
    user = session.get(Utilisateur, user_id)
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    return _declencher_accueil_arrivant(user, body, background_tasks, session, allow_repeat=True)


@router.post("/me/accueil-arrivant")
def accueil_arrivant_me(
    body: AccueilArrivantBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Self-service : l'utilisateur déclare lui-même son arrivée dans la résidence."""
    ancien = (body.ancien_resident or "").strip()
    if not ancien and not body.ancien_resident_inconnu:
        raise HTTPException(422, "Le nom de l'ancien résident est requis (ou cochez 'Je ne sais pas').")
    if body.ancien_resident_inconnu:
        body.ancien_resident = "Ne sait pas"
    return _declencher_accueil_arrivant(user, body, background_tasks, session, allow_repeat=False)


class BanCommunauteBody(BaseModel):
    interdit: bool


@router.patch("/utilisateurs/{user_id}/ban-communaute", response_model=UserRead)
def ban_communaute(
    user_id: int,
    body: BanCommunauteBody,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Bannir ou débannir un utilisateur de la section Communauté.

    1er ban → probatoire 1 mois. 2e ban → définitif.
    """
    user = session.get(Utilisateur, user_id)
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    if body.interdit and user.has_role(RoleUtilisateur.admin):
        raise HTTPException(400, "Un administrateur ne peut pas être exclu de la communauté")

    if body.interdit:
        from datetime import timedelta
        user.communaute_ban_count = (user.communaute_ban_count or 0) + 1
        if user.communaute_ban_count >= 2:
            # 2e infraction → ban permanent
            user.communaute_interdit = True
            user.communaute_ban_jusqu_au = None
            notif_corps = "Votre accès à la section Communauté a été définitivement suspendu suite à une 2ᵉ infraction."
            notif_titre = "Accès à la Communauté suspendu définitivement"
        else:
            # 1re infraction → ban 1 mois (30 jours)
            user.communaute_ban_jusqu_au = datetime.utcnow() + timedelta(days=30)
            notif_corps = (
                "Votre accès à la section Communauté est suspendu pour une période probatoire d'un mois. "
                "À la 2ᵉ infraction, vous serez banni définitivement."
            )
            notif_titre = "Accès à la Communauté suspendu (1 mois)"
        notif = Notification(
            destinataire_id=user.id, type="system",
            titre=notif_titre, corps=notif_corps, lien="/sondages",
        )
        session.add(notif)
    else:
        # Débannir
        user.communaute_interdit = False
        user.communaute_ban_jusqu_au = None
        # On ne remet PAS ban_count à zéro : l'historique est conservé

    session.add(user)
    session.commit()
    session.refresh(user)
    from app.schemas import UserRead
    return UserRead.from_orm_with_roles(user)


# ── Gestion manuelle des baux locatifs ────────────────────────────────────────

@router.post("/baux/{bail_id}/lier-locataire/{user_id}", response_model=dict)
def lier_locataire_bail(
    bail_id: int,
    user_id: int,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    """Admin : lier manuellement un locataire inscrit à un bail actif."""
    bail = session.get(LocationBail, bail_id)
    if not bail:
        raise HTTPException(404, "Bail introuvable")
    if bail.statut == StatutBail.termine:
        raise HTTPException(400, "Impossible de lier un locataire à un bail terminé")
    locataire = session.get(Utilisateur, user_id)
    if not locataire:
        raise HTTPException(404, "Utilisateur introuvable")
    bail.locataire_id = user_id
    session.add(bail)
    session.commit()
    return {"bail_id": bail.id, "locataire_id": user_id, "ok": True}


@router.get("/baux", response_model=list)
def list_baux(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Admin : liste de tous les baux actifs (pour validation manuelle)."""
    baux = session.exec(
        select(LocationBail).where(LocationBail.statut != StatutBail.termine)
    ).all()
    result = []
    for b in baux:
        locataire = session.get(Utilisateur, b.locataire_id) if b.locataire_id else None
        bailleur = session.get(Utilisateur, b.bailleur_id)
        result.append({
            "id": b.id,
            "lot_id": b.lot_id,
            "statut": b.statut,
            "locataire_email": b.locataire_email,
            "locataire_id": b.locataire_id,
            "locataire_nom": f"{locataire.prenom} {locataire.nom}" if locataire else None,
            "bailleur_id": b.bailleur_id,
            "bailleur_nom": f"{bailleur.prenom} {bailleur.nom}" if bailleur else "?",
            "date_entree": b.date_entree,
            "liaison_manquante": bool(b.locataire_email and not b.locataire_id),
        })
    return result