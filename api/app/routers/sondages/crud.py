"""Cycle de vie d'un sondage : lister, consulter, créer, modifier, clôturer.

Extrait de `sondages.py` le 17/08/2026 (cf. `__init__.py`). Porte son préfixe
lui-même — `participation`, dont les chemins sont nus, le reçoit du paquet.
"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    CommentaireSondage, MembreSyndic, Notification, OptionSondage, Sondage,
    RoleUtilisateur, Utilisateur, VoteSondage,
)
from app.schemas import liste_depuis_json
from app.utils.reponses import enrich_reponse, tri_reponses
from app.utils.visibility import resultats_sondage_visibles, sondage_accessible, sondage_clos
from app.utils.whatsapp import config_whatsapp, envoyer_whatsapp_avec_log, whatsapp_actif

from .commun import (
    SondageCreate, SondageRead, _deny_communaute_for_statut,
)

router = APIRouter(prefix="/sondages", tags=["sondages"])


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

    cloture = sondage_clos(s, datetime.utcnow())

    #  Le filtrage est ICI, pas côté front : un masquage d'affichage laisse les
    #  décomptes dans la réponse réseau. La règle elle-même vit dans
    #  `utils/visibility.py`, à côté de `sondage_accessible` — et elle y est
    #  testée (tests/test_resultats_sondage.py), point d'appel compris.
    resultats_visibles = resultats_sondage_visibles(s.resultats_publics, cloture)

    options_out = []
    for opt in sorted(options_db, key=lambda o: o.ordre):
        option = {"id": opt.id, "libelle": opt.libelle, "ordre": opt.ordre,
                  "champ_libre": opt.champ_libre}
        if resultats_visibles:
            votes_opt = session.exec(
                select(VoteSondage).where(VoteSondage.option_id == opt.id)
            ).all()
            option["nb_votes"] = len(votes_opt)
            option["reponses_libres"] = [
                v.reponse_libre for v in votes_opt
                if v.reponse_libre and v.reponse_libre.strip()
            ]
        #  Clés ABSENTES et non mises à zéro quand les résultats sont masqués :
        #  « 0 vote » se lirait comme « personne n'a voté », ce qui est une autre
        #  information, et fausse.
        options_out.append(option)

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
        #  Source UNIQUE de la décision d'affichage. Le front recomposait la sienne
        #  à partir de `resultats_publics`, `cloture` et « ai-je voté » — et se
        #  contredisait d'une ligne à l'autre. Il ne la recompose plus : il ne peut
        #  de toute façon plus afficher ce qui n'est pas envoyé.
        "resultats_visibles": resultats_visibles,
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
    if sondage_clos(s, datetime.utcnow()):
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
