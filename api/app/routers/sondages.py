"""Router sondages — création, vote, résultats."""
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.schemas import ListeJson, liste_depuis_json
from app.models.core import (
    CommentaireSondage, MembreSyndic, Notification, OptionSondage, Sondage, Utilisateur, VoteSondage, RoleUtilisateur, StatutUtilisateur
)
from app.utils.whatsapp import envoyer_whatsapp_avec_log
from app.utils.visibility import sondage_accessible
from app.utils.reponses import (
    auteur_meta, enrich_reponse, notifier_nouvelle_reponse, tri_reponses,
)

router = APIRouter(prefix="/sondages", tags=["sondages"])

from app.utils.whatsapp import config_whatsapp, whatsapp_actif


# ── helpers ──────────────────────────────────────────────────────────────────

def _deny_communaute_for_statut(user: Utilisateur) -> None:
    if user.statut in (StatutUtilisateur.syndic, StatutUtilisateur.mandataire):
        raise HTTPException(403, "La rubrique Communauté n'est pas accessible à votre profil")
    if user.communaute_interdit:
        raise HTTPException(403, "Votre accès à la Communauté a été définitivement suspendu.")
    if user.communaute_ban_jusqu_au and user.communaute_ban_jusqu_au > datetime.utcnow():
        raise HTTPException(403, "Votre accès à la Communauté est suspendu pour une période probatoire d\u2019un mois. À la 2\u1d49 infraction, vous serez banni définitivement.")


# ── schémas ──────────────────────────────────────────────────────────────────

class OptionCreate(BaseModel):
    libelle: str
    ordre: int = 0
    champ_libre: bool = False


class SondageCreate(BaseModel):
    question: str
    description: Optional[str] = None
    cloture_le: Optional[datetime] = None
    resultats_publics: bool = True
    options: list[OptionCreate]
    #  MÊMES deux champs que les publications : codes de périmètre et codes de
    #  public. `None`/vide = aucune restriction, des deux côtés.
    perimetre_cible: Optional[List[str]] = None
    public_cible: Optional[List[str]] = None
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False


class SondageRead(BaseModel):
    id: int
    question: str
    description: Optional[str] = None
    cloture_le: Optional[datetime] = None
    cloture_forcee: bool = False
    resultats_publics: bool
    auteur_id: int
    cree_le: datetime
    #  Exposés en LISTES, comme les publications et les tickets : la colonne est
    #  du texte JSON, mais aucun appelant ne doit avoir à le savoir. La page des
    #  sondages découpait la chaîne à la main et affichait les codes bruts.
    perimetre_cible: ListeJson = []
    public_cible: ListeJson = []
    nb_votants: int = 0

    class Config:
        from_attributes = True


class OptionRead(BaseModel):
    id: int
    libelle: str
    ordre: int
    nb_votes: int = 0
    champ_libre: bool = False

    class Config:
        from_attributes = True


class SondageDetail(SondageRead):
    options: list[OptionRead] = []
    mon_vote: Optional[int] = None
    cloture: bool = False


# ── endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[SondageRead])
def list_sondages(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    all_s = session.exec(select(Sondage).order_by(Sondage.cree_le.desc())).all()
    accessible = [s for s in all_s if sondage_accessible(s, user)]
    if not accessible:
        return []
    # Compter les votants distincts par sondage en une seule requête
    ids = [s.id for s in accessible]
    counts = session.exec(
        select(VoteSondage.sondage_id, func.count(func.distinct(VoteSondage.user_id)))
        .where(VoteSondage.sondage_id.in_(ids))
        .group_by(VoteSondage.sondage_id)
    ).all()
    count_map = {row[0]: row[1] for row in counts}
    result = []
    for s in accessible:
        d = SondageRead.model_validate(s)
        d.nb_votants = count_map.get(s.id, 0)
        result.append(d)
    return result


@router.get("/{sondage_id}")
def get_sondage(
    sondage_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    s = session.get(Sondage, sondage_id)
    if not s:
        raise HTTPException(404, "Sondage introuvable")
    if not sondage_accessible(s, user):
        raise HTTPException(403, "Vous n'êtes pas autorisé à accéder à ce sondage")

    options_db = session.exec(
        select(OptionSondage).where(OptionSondage.sondage_id == sondage_id)
    ).all()

    mon_vote = session.exec(
        select(VoteSondage).where(
            VoteSondage.sondage_id == sondage_id,
            VoteSondage.user_id == user.id,
        )
    ).first()

    cloture = s.cloture_forcee or (s.cloture_le is not None and s.cloture_le < datetime.utcnow())
    options_out = []
    for opt in sorted(options_db, key=lambda o: o.ordre):
        votes_opt = session.exec(
            select(VoteSondage).where(VoteSondage.option_id == opt.id)
        ).all()
        reponses = [v.reponse_libre for v in votes_opt if v.reponse_libre and v.reponse_libre.strip()]
        options_out.append({
            "id": opt.id, "libelle": opt.libelle, "ordre": opt.ordre,
            "nb_votes": len(votes_opt), "champ_libre": opt.champ_libre,
            "reponses_libres": reponses,
        })

    # Enrichissement partagé (nom + bâtiment + rôle, CS mis en avant) — même helper
    # que idées/annonces pour une UX cohérente. CS/admin d'abord, puis chronologique.
    commentaires_db = session.exec(
        select(CommentaireSondage).where(CommentaireSondage.sondage_id == sondage_id)
    ).all()
    commentaires_out = tri_reponses([enrich_reponse(c, session) for c in commentaires_db])

    return {
        "id": s.id, "question": s.question, "description": s.description,
        "cloture_le": s.cloture_le, "resultats_publics": s.resultats_publics,
        "auteur_id": s.auteur_id, "cree_le": s.cree_le,
        #  Cette réponse est construite à la main (pas de `response_model`) : la
        #  conversion JSON → liste ne se fait donc pas toute seule. Même règle
        #  que `ListeJson`, appelée et non recopiée.
        "perimetre_cible": liste_depuis_json(s.perimetre_cible),
        "public_cible": liste_depuis_json(s.public_cible),
        "options": options_out, "mon_vote": mon_vote.option_id if mon_vote else None,
        "cloture": cloture, "cloture_forcee": s.cloture_forcee, "commentaires": commentaires_out,
    }


@router.post("", status_code=201)
def create_sondage(
    body: SondageCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    #  Sérialisation JSON, comme les publications. `None` quand la liste est vide :
    #  un `"[]"` et un `None` répondraient à la même question de deux façons.
    perimetre_json = json.dumps(body.perimetre_cible, ensure_ascii=False) if body.perimetre_cible else None
    public_json = json.dumps(body.public_cible, ensure_ascii=False) if body.public_cible else None

    s = Sondage(
        question=body.question,
        description=body.description,
        cloture_le=body.cloture_le,
        resultats_publics=body.resultats_publics,
        auteur_id=user.id,
        perimetre_cible=perimetre_json,
        public_cible=public_json,
        partager_whatsapp=body.partager_whatsapp,
        envoyer_syndic=body.envoyer_syndic,
        envoyer_cs=body.envoyer_cs,
    )
    session.add(s)
    session.flush()

    for opt in body.options:
        session.add(OptionSondage(sondage_id=s.id, **opt.model_dump()))

    #  Notifier exactement ceux qui PEUVENT le voir. Cette boucle réappliquait à
    #  la main les deux filtres de ciblage — une seconde écriture de la règle
    #  d'accès, qui ne connaissait donc ni les périmètres transverses ni le CS.
    #  `sondage_accessible` est désormais la seule à en décider.
    q = select(Utilisateur).where(Utilisateur.actif == True, Utilisateur.id != user.id)
    residents = session.exec(q).all()
    for r in residents:
        if not sondage_accessible(s, r):
            continue
        session.add(Notification(
            destinataire_id=r.id,
            type="sondage",
            titre=f"📊 Nouveau sondage : {s.question[:60]}",
            corps="Votre avis compte — participez au sondage.",
            lien=f"/sondages/{s.id}",
        ))

    session.commit()
    session.refresh(s)

    # ── Notifications WhatsApp / syndic / CS optionnelles ──────────────────
    if body.partager_whatsapp or body.envoyer_syndic or body.envoyer_cs:
        cfg_map = config_whatsapp(session, "reference_copro", "site_nom")

        if body.partager_whatsapp:
            if whatsapp_actif(cfg_map):
                background_tasks.add_task(
                    envoyer_whatsapp_avec_log,
                    f"📊 Nouveau sondage : {s.question}", s.description or "", False, None, None, cfg_map,
                )

        if body.envoyer_syndic or body.envoyer_cs:
            from app.utils.email import send_email_group
            destinataires: list[tuple[int | None, str]] = []
            seen_emails: set[str] = set()

            if body.envoyer_syndic:
                syndic_principal = session.exec(
                    select(MembreSyndic).where(MembreSyndic.est_principal == True)
                ).first()
                if syndic_principal and syndic_principal.email:
                    destinataires.append((syndic_principal.user_id, syndic_principal.email))
                    seen_emails.add(syndic_principal.email.lower())

            if body.envoyer_cs:
                cs_users = session.exec(
                    select(Utilisateur.id, Utilisateur.email)
                    .where(
                        Utilisateur.actif == True,
                        Utilisateur.email.isnot(None),
                        Utilisateur.roles_json.contains("conseil_syndical"),
                    )
                ).all()
                for uid, email in cs_users:
                    if email and email.lower() not in seen_emails:
                        destinataires.append((uid, email))
                        seen_emails.add(email.lower())

            # Le template `publication_syndic` déréférence `publication.titre`,
            # `publication.contenu` et `publication.id` : avec la clé `ticket`
            # reprise du mail de ticket, l'envoi échouait à tous les coups en
            # `'publication' is undefined`. Bug LATENT — invisible dans
            # `historique_email` faute d'un sondage créé avec « envoyer au CS »
            # depuis sa mise en place ; trouvé le 01/08/2026 par
            # `tests/test_email_contexte_appel.py`, pas par le pré-check.
            ctx = {
                "publication": {
                    "id": s.id,
                    "titre": s.question,
                    "contenu": s.description or "",
                },
                "auteur": {"prenom": user.prenom, "nom": user.nom},
                "residence": {"nom": cfg_map.get("site_nom", "5Hostachy")},
                "app": {"url": cfg_map.get("site_url", "https://localhost")},
                "reference_copro": cfg_map.get("reference_copro", ""),
                # Un sondage n'a pas de pièce jointe, mais le modèle
                # `publication_syndic` teste `fichiers` : Jinja évalue un
                # indéfini à faux sans rien dire, donc le rendu était correct
                # par chance. La clé manquante est précisément ce que
                # `test_email_contexte_appel.py` cherche — on la fournit.
                "fichiers": False,
            }
            if destinataires:
                background_tasks.add_task(
                    send_email_group, code="publication_syndic",
                    to_recipients=destinataires, context=ctx,
                    session=session,
                )

    return s


class VoteBody(BaseModel):
    option_id: int
    commentaire: Optional[str] = None
    reponse_libre: Optional[str] = None


@router.post("/{sondage_id}/voter", status_code=201)
def voter(
    sondage_id: int,
    body: VoteBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    if user.has_role(RoleUtilisateur.externe) and not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        raise HTTPException(403, "Les utilisateurs externes ne peuvent pas voter")
    s = session.get(Sondage, sondage_id)
    if not s:
        raise HTTPException(404, "Sondage introuvable")
    if not sondage_accessible(s, user):
        raise HTTPException(403, "Vous n'\u00eates pas autoris\u00e9 \u00e0 participer \u00e0 ce sondage")
    if s.cloture_forcee or (s.cloture_le and s.cloture_le < datetime.utcnow()):
        raise HTTPException(400, "Ce sondage est clôturé")

    existant = session.exec(
        select(VoteSondage).where(
            VoteSondage.sondage_id == sondage_id,
            VoteSondage.user_id == user.id,
        )
    ).first()
    if existant:
        raise HTTPException(400, "Vous avez déjà voté")

    opt = session.get(OptionSondage, body.option_id)
    if not opt or opt.sondage_id != sondage_id:
        raise HTTPException(400, "Option invalide")

    reponse_libre_val = body.reponse_libre.strip() if body.reponse_libre else None
    session.add(VoteSondage(
        sondage_id=sondage_id, option_id=body.option_id, user_id=user.id,
        reponse_libre=reponse_libre_val,
    ))

    if body.commentaire and body.commentaire.strip():
        contenu = body.commentaire.strip()
        session.add(CommentaireSondage(
            sondage_id=sondage_id,
            auteur_id=user.id,
            contenu=contenu,
        ))
        notifier_nouvelle_reponse(
            session, background_tasks,
            createur_id=s.auteur_id, auteur=user,
            rubrique_label="votre sondage", sujet=s.question,
            extrait=contenu, lien_path=f"/sondages/{sondage_id}",
        )

    session.commit()
    return {"message": "Vote enregistré"}


class CommentaireBody(BaseModel):
    contenu: str


@router.post("/{sondage_id}/commenter", status_code=201)
def commenter(
    sondage_id: int,
    body: CommentaireBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    s = session.get(Sondage, sondage_id)
    if not s:
        raise HTTPException(404, "Sondage introuvable")
    if not sondage_accessible(s, user):
        raise HTTPException(403, "Accès refusé")
    if not body.contenu.strip():
        raise HTTPException(400, "Le commentaire ne peut pas être vide")
    contenu = body.contenu.strip()
    c = CommentaireSondage(sondage_id=sondage_id, auteur_id=user.id, contenu=contenu)
    session.add(c)
    notifier_nouvelle_reponse(
        session, background_tasks,
        createur_id=s.auteur_id, auteur=user,
        rubrique_label="votre sondage", sujet=s.question,
        extrait=contenu, lien_path=f"/sondages/{sondage_id}",
    )
    session.commit()
    session.refresh(c)
    return {"id": c.id, "contenu": c.contenu, "cree_le": c.cree_le,
            "auteur_id": c.auteur_id, **auteur_meta(user, session)}


@router.delete("/{sondage_id}/commentaires/{commentaire_id}", status_code=204)
def supprimer_commentaire(
    sondage_id: int,
    commentaire_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    c = session.get(CommentaireSondage, commentaire_id)
    if not c or c.sondage_id != sondage_id:
        raise HTTPException(404, "Commentaire introuvable")
    # Seuls l'auteur, le CS et l'admin peuvent supprimer
    est_moderateur = user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)
    if c.auteur_id != user.id and not est_moderateur:
        raise HTTPException(403, "Non autorisé")
    session.delete(c)
    session.commit()


# ── Édition / suppression / clôture anticipée ──────────────────────────────

class SondageUpdate(BaseModel):
    question: Optional[str] = None
    description: Optional[str] = None
    cloture_le: Optional[datetime] = None
    resultats_publics: Optional[bool] = None


@router.patch("/{sondage_id}")
def modifier_sondage(
    sondage_id: int,
    body: SondageUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Modifier un sondage (auteur ou admin)."""
    s = session.get(Sondage, sondage_id)
    if not s:
        raise HTTPException(404, "Sondage introuvable")
    est_admin = user.has_role(RoleUtilisateur.admin)
    if s.auteur_id != user.id and not est_admin:
        raise HTTPException(403, "Seul l'auteur ou un admin peut modifier ce sondage")
    if s.cloture_forcee or (s.cloture_le and s.cloture_le < datetime.utcnow()):
        raise HTTPException(400, "Ce sondage est clôturé et ne peut plus être modifié")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(s, field, val)
    session.add(s)
    session.commit()
    session.refresh(s)
    return {"id": s.id, "question": s.question, "description": s.description,
            "cloture_le": s.cloture_le, "resultats_publics": s.resultats_publics}


@router.delete("/{sondage_id}", status_code=204)
def supprimer_sondage(
    sondage_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Supprimer un sondage et toutes ses données (auteur ou admin)."""
    s = session.get(Sondage, sondage_id)
    if not s:
        raise HTTPException(404, "Sondage introuvable")
    est_admin = user.has_role(RoleUtilisateur.admin)
    if s.auteur_id != user.id and not est_admin:
        raise HTTPException(403, "Seul l'auteur ou un admin peut supprimer ce sondage")
    # Suppression en cascade
    for c in session.exec(select(CommentaireSondage).where(CommentaireSondage.sondage_id == sondage_id)).all():
        session.delete(c)
    for v in session.exec(select(VoteSondage).where(VoteSondage.sondage_id == sondage_id)).all():
        session.delete(v)
    for o in session.exec(select(OptionSondage).where(OptionSondage.sondage_id == sondage_id)).all():
        session.delete(o)
    session.delete(s)
    session.commit()


@router.patch("/{sondage_id}/cloturer", status_code=200)
def cloturer_sondage(
    sondage_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Stopper un sondage immédiatement (auteur ou admin)."""
    s = session.get(Sondage, sondage_id)
    if not s:
        raise HTTPException(404, "Sondage introuvable")
    est_admin = user.has_role(RoleUtilisateur.admin)
    if s.auteur_id != user.id and not est_admin:
        raise HTTPException(403, "Seul l'auteur ou un admin peut clôturer ce sondage")
    s.cloture_forcee = True
    session.add(s)
    session.commit()
    return {"message": "Sondage clôturé"}
