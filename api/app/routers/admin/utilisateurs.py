"""Admin — Cycle de vie d'un utilisateur existant : rôles, modification, suppression, bannissement.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select
from sqlalchemy import func, or_
from app.auth.deps import require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    CommandeAcces,
    DemandeModificationProfil,
    HistoriqueSauvegarde,
    LocationBail,
    LotImport,
    Mandat,
    Notification,
    PasswordResetToken,
    RefreshToken,
    RemiseObjet,
    RoleUtilisateur,
    StatutImport,
    StatutLotImport,
    StatutUtilisateur,
    Telecommande,
    TelecommandeImport,
    TelemetryEvent,
    UserLot,
    UserTelecommande,
    UserVigik,
    Utilisateur,
    Vigik,
    VigikImport,
    VoteIdee,
    VoteSondage,
)
from app.schemas import UserRead
from app.utils.comptes import marquer_decide
from app.utils.purge_referentielle import purger
from datetime import datetime
from typing import Optional
from app.utils.communaute import notification_de_ban

router = APIRouter()


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
    # Batch : user_ids ayant au moins 1 télécommande (directe ou via M2M)
    tc_ids = set(
        session.exec(
            select(Telecommande.user_id).distinct()
        ).all()
    )
    tc_ids |= set(
        session.exec(
            select(UserTelecommande.user_id).distinct()
        ).all()
    )
    # Batch : user_ids ayant au moins 1 vigik (direct ou via M2M)
    vigik_ids = set(
        session.exec(
            select(Vigik.user_id).distinct()
        ).all()
    )
    vigik_ids |= set(
        session.exec(
            select(UserVigik.user_id).distinct()
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
class AdminUserUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    societe: Optional[str] = None
    statut: Optional[StatutUtilisateur] = None
    batiment_id: Optional[int] = None
    actif: Optional[bool] = None

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str | None) -> str | None:
        return v.strip().lower() if v else v


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
    if body.email and body.email != user.email.lower():
        existing = session.exec(select(Utilisateur).where(func.lower(Utilisateur.email) == body.email)).first()
        if existing:
            raise HTTPException(400, "Cet e-mail est déjà utilisé.")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(user, field, val)
    #  Basculer `actif` — dans un sens comme dans l'autre — EST une décision de
    #  l'administration sur ce compte. Sans cette ligne, désactiver un résident
    #  qui déménage le renvoyait dans la file des comptes à valider, où plus rien
    #  ne le distinguait d'une inscription du jour (#399).
    if body.actif is not None:
        marquer_decide(user)
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

    # 0. Télémétrie (RGPD art. 17 — droit à l'effacement)
    for ev in session.exec(select(TelemetryEvent).where(TelemetryEvent.user_id == user_id)).all():
        session.delete(ev)

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

    #  🔴 Le reste — et « le reste » est la majorité (#546, 28/08/2026).
    #
    #  Les onze étapes ci-dessus portent des règles MÉTIER : remettre un statut
    #  d'import, retirer une entrée d'un `..._json`, choisir entre délier et
    #  supprimer un bail. Elles restent, et elles passent en premier.
    #
    #  Mais le modèle compte CINQUANTE-SIX références à `utilisateur`, dont
    #  trente-sept obligatoires. Vingt-six tables n'étaient nettoyées nulle part —
    #  publications, tickets, messages, idées, sondages, signalements… La
    #  suppression réussissait quand même, parce que SQLite tournait avec
    #  `foreign_keys=OFF`, et laissait en base des lignes pointant vers un compte
    #  disparu.
    #
    #  ⚠️ Une liste tenue à la main ne peut pas suivre : c'est bien ce qui s'est
    #  passé. `purger` LIT les métadonnées au lieu de les réciter.
    session.flush()
    purger(session, "utilisateur", user_id)
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

class BanCommunauteBody(BaseModel):
    interdit: bool


@router.patch("/utilisateurs/{user_id}/ban-communaute", response_model=UserRead)
def ban_communaute(
    user_id: int,
    body: BanCommunauteBody,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Bannir ou débannir un utilisateur de la rubrique Communauté.

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
            notif_titre, notif_corps = notification_de_ban(definitif=True)
        else:
            # 1re infraction → ban 1 mois (30 jours)
            user.communaute_ban_jusqu_au = datetime.utcnow() + timedelta(days=30)
            notif_titre, notif_corps = notification_de_ban(definitif=False)
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
