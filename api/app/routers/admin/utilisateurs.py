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
from app.utils.journal_securite import journaliser_securite
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
    TelemetryEvent,
    UserLot,
    Utilisateur,
    VoteIdee,
    VoteSondage,
)
from app.schemas import UserRead
from app.utils.comptes import marquer_decide
from app.utils.porteurs_acces import ids_detenteurs
from app.utils.etiquettes_compte import etiquettes
from app.models.copropriete import Lot
from app.utils.valeurs import valeur
from app.utils.purge_referentielle import purger
from app.utils.types_acces import TELECOMMANDE, TYPES_ACCES, VIGIK
from app.utils.roles_libelles import libelle_role
from app.utils import horloge
from typing import Optional
from app.utils.communaute import notification_de_ban
from app.utils.recuperer import ou_404
from app.utils.etages import ETAGE_HORS_BORNES, etage_hors_bornes
from app.schemas_communs import NomMajuscules
from app.utils.cloche import sonner_systeme

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
            select(UserLot.user_id).where(UserLot.actif == True).distinct()  # noqa: E712
        ).all()
    )
    #  « A un badge » : UNE définition, `utils/porteurs_acces` (#1194). Celle
    #  d'ici comptait aussi les badges perdus et ignorait le conjoint.
    tc_ids = ids_detenteurs(session, TELECOMMANDE)
    vigik_ids = ids_detenteurs(session, VIGIK)
    # Batch : user_ids liés via un bail (bailleur ou locataire)
    bail_bailleur_ids = set(session.exec(select(LocationBail.bailleur_id).distinct()).all())
    bail_locataire_ids = set(
        session.exec(
            select(LocationBail.locataire_id).where(LocationBail.locataire_id != None).distinct()  # noqa: E711
        ).all()
    )
    lie_ids = bail_bailleur_ids | bail_locataire_ids
    #  Les TYPES de lot de chaque compte : ce qui rend une étiquette « sans objet »
    #  (`utils/etiquettes_compte`) — pas de parking, pas de télécommande à porter.
    types_lots: dict[int, set[str]] = {}
    for user_id, type_lot in session.exec(
        select(UserLot.user_id, Lot.type)
        .join(Lot, Lot.id == UserLot.lot_id)
        .where(UserLot.actif == True)  # noqa: E712
    ).all():
        types_lots.setdefault(user_id, set()).add(valeur(type_lot))

    result = []
    for u in users:
        d = UserRead.from_orm_with_roles(u).model_dump()
        d["has_lots"] = u.id in loti_ids
        d["has_tc"] = u.id in tc_ids
        d["has_vigik"] = u.id in vigik_ids
        d["has_bail"] = u.id in lie_ids
        d["etiquettes"] = etiquettes(
            a_lot=d["has_lots"],
            a_tc=d["has_tc"],
            a_vigik=d["has_vigik"],
            a_bail=d["has_bail"],
            types_lots=types_lots.get(u.id, set()),
            statut=valeur(u.statut),
            types_tc=TELECOMMANDE.types_lot,
            types_vigik=VIGIK.types_lot,
        )
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
    user = ou_404(session, Utilisateur, user_id, "Utilisateur")
    if not user.actif:
        raise HTTPException(400, "Impossible de modifier un compte inactif.")
    try:
        role = RoleUtilisateur(body.role)
    except ValueError:
        raise HTTPException(400, f"Rôle invalide : {body.role}")
    user.ajouter_role(role)
    #  🔴 En WARNING : c'est le geste qui donne des droits. La `Notification` part
    #  au concerné et ne dit pas QUI a agi — le journal, lui, nomme l'admin.
    journaliser_securite("role_ajoute", acteur_id=admin.id, cible_id=user.id, detail=role.value)
    sonner_systeme(
        session,
        "compte",
        destinataire_id=user.id,
        type="system",
        titre="Rôle ajouté",
        corps=f"Le rôle {libelle_role(role)} vous a été attribué.",
        lien="/profil",
    )
    session.add(user)
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
    user = ou_404(session, Utilisateur, user_id, "Utilisateur")
    if body.role == RoleUtilisateur.résident.value:
        raise HTTPException(
            400, "Le rôle 'Résident' est le rôle de base, il ne peut pas être retiré."
        )
    try:
        role = RoleUtilisateur(body.role)
    except ValueError:
        raise HTTPException(400, f"Rôle invalide : {body.role}")
    user.retirer_role(role)
    journaliser_securite("role_retire", acteur_id=admin.id, cible_id=user.id, detail=role.value)
    sonner_systeme(
        session,
        "compte",
        destinataire_id=user.id,
        type="system",
        titre="Rôle retiré",
        corps=f"Le rôle {libelle_role(role)} vous a été retiré.",
        lien="/profil",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    from app.schemas import UserRead

    return UserRead.from_orm_with_roles(user)


class AdminUserUpdate(BaseModel):
    nom: NomMajuscules = None
    prenom: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    societe: Optional[str] = None
    statut: Optional[StatutUtilisateur] = None
    batiment_id: Optional[int] = None
    actif: Optional[bool] = None
    #  Corriger une saisie de l'inscription (#1155) : où la personne habite, et,
    #  pour un locataire, le nom de son bailleur — ce qui sert à la rapprocher
    #  de son lot. Mêmes règles qu'à l'inscription : bornes, capitales.
    etage: Optional[int] = None
    nom_proprietaire: NomMajuscules = None

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
    user = ou_404(session, Utilisateur, user_id, "Utilisateur")
    if body.email and body.email != user.email.lower():
        existing = session.exec(
            select(Utilisateur).where(func.lower(Utilisateur.email) == body.email)
        ).first()
        if existing:
            raise HTTPException(400, "Cet e-mail est déjà utilisé.")
    if body.etage is not None and etage_hors_bornes(body.etage):
        raise HTTPException(400, ETAGE_HORS_BORNES)
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
    ou_404(session, Utilisateur, user_id, "Utilisateur")

    # 0. Télémétrie (RGPD art. 17 — droit à l'effacement)
    for ev in session.exec(select(TelemetryEvent).where(TelemetryEvent.user_id == user_id)).all():
        session.delete(ev)

    # 1. Tokens d'authentification
    for t in session.exec(select(RefreshToken).where(RefreshToken.user_id == user_id)).all():
        session.delete(t)
    for t in session.exec(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
    ).all():
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
                    imp.statut = (
                        StatutLotImport.lot_lie if imp.lot_id else StatutLotImport.en_attente
                    )
                    imp.resolu_le = None
                session.add(imp)

    # 3. Commandes d'accès
    for c in session.exec(select(CommandeAcces).where(CommandeAcces.user_id == user_id)).all():
        session.delete(c)

    # 4. Notifications
    for n in session.exec(
        select(Notification).where(Notification.destinataire_id == user_id)
    ).all():
        session.delete(n)

    # 5. Votes
    for v in session.exec(select(VoteSondage).where(VoteSondage.user_id == user_id)).all():
        session.delete(v)
    for v in session.exec(select(VoteIdee).where(VoteIdee.user_id == user_id)).all():
        session.delete(v)

    # 6. Demandes modification profil
    for d in session.exec(
        select(DemandeModificationProfil).where(DemandeModificationProfil.utilisateur_id == user_id)
    ).all():
        session.delete(d)
    for d in session.exec(
        select(DemandeModificationProfil).where(DemandeModificationProfil.traite_par_id == user_id)
    ).all():
        d.traite_par_id = None
        session.add(d)

    # 7. Mandats (bailleur ou mandataire)
    for m in session.exec(
        select(Mandat).where(or_(Mandat.bailleur_id == user_id, Mandat.mandataire_id == user_id))
    ).all():
        session.delete(m)

    #  8. Les badges RESTENT sur leur lot (arbitrage du 23/09/2026, #1194) : la
    #  purge délie `user_id`, désormais facultatif. Ils étaient supprimés, et
    #  avec eux la trace d'objets physiques toujours en circulation.
    #  9. Les lignes d'import perdent ce compte ; une ligne résolue le reste —
    #  son badge existe toujours.
    for type_acces in TYPES_ACCES.values():
        modele = type_acces.modele_import
        for ligne in session.exec(
            select(modele).where(
                or_(
                    modele.user_proprietaire_id == user_id,
                    modele.user_locataire_id == user_id,
                )
            )
        ).all():
            if ligne.user_proprietaire_id == user_id:
                ligne.user_proprietaire_id = None
            if ligne.user_locataire_id == user_id:
                ligne.user_locataire_id = None
            if ligne.statut == StatutImport.proprietaire_lie and not ligne.user_proprietaire_id:
                ligne.statut = StatutImport.en_attente
            session.add(ligne)

    # 10. LocationBail : locataire → nullifier ; bailleur → supprimer bail + objets remis
    for bail in session.exec(
        select(LocationBail).where(LocationBail.locataire_id == user_id)
    ).all():
        bail.locataire_id = None
        session.add(bail)
    for bail in session.exec(select(LocationBail).where(LocationBail.bailleur_id == user_id)).all():
        for obj in session.exec(select(RemiseObjet).where(RemiseObjet.bail_id == bail.id)).all():
            session.delete(obj)
        session.delete(bail)

    # 11. HistoriqueSauvegarde — nullifier la référence optionnelle
    for h in session.exec(
        select(HistoriqueSauvegarde).where(HistoriqueSauvegarde.declenchee_par_user_id == user_id)
    ).all():
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


#  🔴 `POST /utilisateurs/{user_id}/changer-role` A ÉTÉ SUPPRIMÉ le 06/09/2026
#  (#801). Il « remplaçait tous les rôles par un seul », et sa docstring le
#  donnait pour de la « compatibilité ascendante » — avec rien : aucun écran,
#  aucun script, aucun test ne l'appelait, et son client TypeScript figurait au
#  relevé des méthodes sans appelant. Le produit a des rôles MULTIPLES depuis
#  longtemps ; `ajouter-role` et `retirer-role`, juste au-dessus, sont les deux
#  gestes réels.
#
#  ⚠️ Il portait la TROISIÈME copie de la table des libellés de rôles, et un
#  passe-droit que les deux autres n'ont pas : il écrivait `user.role` et
#  `user.roles_json` directement au lieu de passer par `ajouter_role()` /
#  `retirer_role()` du modèle. Un endpoint sans appelant n'est pas seulement du
#  code mort — c'est du code qui n'est plus corrigé quand la règle bouge.


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
    user = ou_404(session, Utilisateur, user_id, "Utilisateur")
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
            user.communaute_ban_jusqu_au = horloge.maintenant() + timedelta(days=30)
            notif_titre, notif_corps = notification_de_ban(definitif=False)
        journaliser_securite(
            "ban_communaute",
            acteur_id=admin.id,
            cible_id=user.id,
            detail=f"infraction {user.communaute_ban_count}",
        )
        sonner_systeme(
            session,
            "compte",
            destinataire_id=user.id,
            type="system",
            titre=notif_titre,
            corps=notif_corps,
            lien="/sondages",
        )
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
