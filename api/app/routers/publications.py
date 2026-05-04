"""Router publications — actualités, annonces."""
import json
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import ConfigSite, Document, MembreSyndic, Publication, PublicationEvolution, Utilisateur, RoleUtilisateur
from app.schemas import PublicationCreate, PublicationRead, PublicationUpdate, EvolutionCreate, EvolutionRead, PublicationEvolutionUpdate
from app.utils.visibility import publication_visible
from app.utils.whatsapp import envoyer_whatsapp_avec_log

router = APIRouter(prefix="/publications", tags=["publications"])

ARCHIVAGE_DELAI_HEURES = 48
_WA_KEYS = {'whatsapp_enabled', 'whatsapp_api_url', 'whatsapp_api_key', 'whatsapp_group_jid', 'whatsapp_footer', 'site_url'}


def _pub_to_read(pub: Publication, session: Session) -> PublicationRead:
    """Construit un PublicationRead avec les évolutions et le nom auteur."""
    evols = session.exec(
        select(PublicationEvolution)
        .where(PublicationEvolution.publication_id == pub.id)
        .order_by(PublicationEvolution.cree_le)
    ).all()
    evol_reads = []
    for e in evols:
        auteur = session.get(Utilisateur, e.auteur_id)
        nom = f"{auteur.prenom} {auteur.nom}" if auteur else "?"
        fichiers_list = json.loads(e.fichiers_urls) if e.fichiers_urls else []
        evol_reads.append(EvolutionRead(
            id=e.id,
            publication_id=e.publication_id,
            type=e.type,
            contenu=e.contenu,
            ancien_statut=e.ancien_statut,
            nouveau_statut=e.nouveau_statut,
            auteur_id=e.auteur_id,
            auteur_nom=nom,
            cree_le=e.cree_le,
            fichiers_urls=fichiers_list,
        ))
    data = PublicationRead.model_validate(pub)
    auteur_pub = session.get(Utilisateur, pub.auteur_id)
    data.auteur_nom = f"{auteur_pub.prenom} {auteur_pub.nom}" if auteur_pub else "?"
    data.evolutions = evol_reads
    return data


def _envoyer_email_syndic_publication(
    pub: Publication, user: Utilisateur, background_tasks: BackgroundTasks, session: Session,
    *, syndic: bool = True, cs: bool = False,
    commentaire: str | None = None, fichiers_urls: list[str] | None = None,
):
    """Envoie un email au syndic et/ou CS avec la publication en corps."""
    from app.utils.email import send_email_group
    from zoneinfo import ZoneInfo

    def _fmt_paris(dt: datetime) -> str:
        return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Paris")).strftime("%-d %B %Y à %H:%M")

    destinataires: list[tuple[int | None, str]] = []
    seen_emails: set[str] = set()

    if syndic:
        syndic_principal = session.exec(
            select(MembreSyndic).where(MembreSyndic.est_principal == True)
        ).first()
        if syndic_principal and syndic_principal.email:
            destinataires.append((syndic_principal.user_id, syndic_principal.email))
            seen_emails.add(syndic_principal.email.lower())

    if cs:
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

    if not destinataires:
        return

    cfg_rows = session.exec(
        select(ConfigSite).where(ConfigSite.cle.in_(("reference_copro", "site_nom", "site_url")))
    ).all()
    cfg = {r.cle: r.valeur for r in cfg_rows}

    # Historique des évolutions (pour les commentaires)
    evols_ctx = []
    is_commentaire = commentaire is not None
    if is_commentaire:
        evols = session.exec(
            select(PublicationEvolution)
            .where(PublicationEvolution.publication_id == pub.id)
            .order_by(PublicationEvolution.cree_le)
        ).all()
        for e in evols[:-1]:  # Exclure le dernier (= le commentaire en cours)
            if not e.contenu:
                continue
            auteur_e = session.get(Utilisateur, e.auteur_id)
            evols_ctx.append({
                "auteur_nom": f"{auteur_e.prenom} {auteur_e.nom}" if auteur_e else "?",
                "date": _fmt_paris(e.cree_le),
                "contenu": e.contenu,
            })

    ctx = {
        "publication": {"id": pub.id, "titre": pub.titre, "contenu": pub.contenu or ""},
        "auteur": {"prenom": user.prenom, "nom": user.nom},
        "residence": {"nom": cfg.get("site_nom", "5Hostachy")},
        "app": {"url": (cfg.get("site_url") or "https://localhost").rstrip("/")},
        "reference_copro": cfg.get("reference_copro", ""),
        "is_commentaire": is_commentaire,
        "commentaire": commentaire or "",
        "date_commentaire": _fmt_paris(datetime.utcnow()),
        "date_publication": _fmt_paris(pub.cree_le),
        "evolutions": evols_ctx,
        "fichiers": bool(fichiers_urls),
    }

    # Photo jointe (image de la publication)
    all_attachments: list[str] = []
    if pub.image_url:
        fname = os.path.basename(pub.image_url)
        fpath = os.path.join("/app/uploads", "publications", fname)
        if os.path.isfile(fpath):
            all_attachments.append(fpath)

    # Fichiers joints (documents liés à la publication)
    docs = session.exec(select(Document).where(Document.publication_id == pub.id)).all()
    for doc in docs:
        if doc.fichier_chemin and os.path.isfile(doc.fichier_chemin):
            all_attachments.append(doc.fichier_chemin)

    # Fichiers joints au commentaire
    if fichiers_urls:
        all_attachments.extend(_resolve_fichiers_attachments(fichiers_urls))

    if destinataires:
        background_tasks.add_task(
            send_email_group,
            code="publication_syndic",
            to_recipients=destinataires,
            context=ctx,
            session=session,
            attachments=all_attachments or None,
        )


def _resolve_fichiers_attachments(fichiers_urls: list[str]) -> list[str]:
    """Convertit des URLs /uploads/fichiers/... en chemins locaux /app/uploads/fichiers/..."""
    paths = []
    for url in fichiers_urls:
        if url.startswith("/uploads/"):
            path = "/app" + url
        else:
            path = url
        if os.path.isfile(path):
            paths.append(path)
    return paths


def _envoyer_email_externe_publication(
    pub: Publication,
    user: Utilisateur,
    email_externe: str,
    background_tasks: BackgroundTasks,
    session: Session,
    *,
    is_commentaire: bool = True,
    commentaire: str | None = None,
    fichiers_urls: list[str] | None = None,
):
    """Envoie un email vers une adresse externe (non-utilisateur) avec l'historique de la publication."""
    from app.utils.email import send_email
    from zoneinfo import ZoneInfo

    def _fmt_paris(dt: datetime) -> str:
        return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Paris")).strftime("%-d %B %Y à %H:%M")

    cfg_rows = session.exec(
        select(ConfigSite).where(ConfigSite.cle.in_(("site_nom", "site_url")))
    ).all()
    cfg = {r.cle: r.valeur for r in cfg_rows}

    # Historique des évolutions (du plus ancien au plus récent, sauf la dernière si commentaire)
    evols = session.exec(
        select(PublicationEvolution)
        .where(PublicationEvolution.publication_id == pub.id)
        .order_by(PublicationEvolution.cree_le)
    ).all()
    evols_for_history = evols[:-1] if (is_commentaire and evols) else evols
    evol_ctx = []
    for e in evols_for_history:
        if not e.contenu:
            continue
        auteur_e = session.get(Utilisateur, e.auteur_id)
        evol_ctx.append({
            "auteur_nom": f"{auteur_e.prenom} {auteur_e.nom}" if auteur_e else "?",
            "date": _fmt_paris(e.cree_le),
            "contenu": e.contenu,
        })

    attachments = _resolve_fichiers_attachments(fichiers_urls or [])

    ctx = {
        "publication": {"id": pub.id, "titre": pub.titre, "contenu": pub.contenu or ""},
        "auteur": {"prenom": user.prenom, "nom": user.nom},
        "date_publication": _fmt_paris(pub.cree_le),
        "date_commentaire": _fmt_paris(datetime.utcnow()),
        "residence": {"nom": cfg.get("site_nom", "5Hostachy")},
        "app": {"url": (cfg.get("site_url") or "https://localhost").rstrip("/")},
        "is_commentaire": is_commentaire,
        "commentaire": commentaire or "",
        "evolutions": evol_ctx,
        "fichiers": bool(attachments),
    }

    background_tasks.add_task(
        send_email,
        code="publication_externe",
        to=email_externe,
        context=ctx,
        attachments=attachments or None,
    )


def _is_archived(pub: Publication, delai_heures: int = ARCHIVAGE_DELAI_HEURES) -> bool:
    """True si la publication doit être considérée comme archivée."""
    if pub.archivee:
        return True
    if pub.statut == "resolu" and pub.statut_change_le:
        delta = datetime.utcnow() - pub.statut_change_le
        return delta >= timedelta(hours=delai_heures)
    return False


def _is_annule_expired(pub: Publication, delai_heures: int = ARCHIVAGE_DELAI_HEURES) -> bool:
    """True si la publication annulée a dépassé le délai et doit être supprimée."""
    if pub.statut == "annule" and pub.statut_change_le:
        return (datetime.utcnow() - pub.statut_change_le) >= timedelta(hours=delai_heures)
    return False



@router.get("", response_model=list[PublicationRead])
def list_publications(
    archived: bool = Query(False),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    pubs = session.exec(
        select(Publication).order_by(Publication.epingle.desc(), Publication.cree_le.desc())
    ).all()

    is_cs = user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)

    delai_row = session.get(ConfigSite, 'archivage_delai_heures')
    delai_heures = int(delai_row.valeur) if delai_row and delai_row.valeur.isdigit() else ARCHIVAGE_DELAI_HEURES

    # Purge automatique : supprimer les publications annulées depuis > 48h
    to_delete = [p for p in pubs if _is_annule_expired(p, delai_heures)]
    for pub in to_delete:
        evols = session.exec(
            select(PublicationEvolution).where(PublicationEvolution.publication_id == pub.id)
        ).all()
        for e in evols:
            session.delete(e)
        session.delete(pub)
    if to_delete:
        session.commit()
        pubs = [p for p in pubs if p not in to_delete]

    result = []
    for pub in pubs:
        arch = _is_archived(pub, delai_heures)
        if archived and not arch:
            continue
        if not archived and arch:
            continue
        # Les brouillons ne sont visibles que par le CS/admin
        if pub.brouillon and not is_cs:
            continue
        # Filtre périmètre + public cible (non-CS/admin uniquement)
        if not is_cs and not publication_visible(pub, user):
            continue
        result.append(_pub_to_read(pub, session))
    return result


@router.post("", response_model=PublicationRead, status_code=201)
def create_publication(
    body: PublicationCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    email_externe = body.email_externe  # adresse externe (pas dans le modèle)
    data = body.model_dump(exclude={"email_externe"})
    perimetre_cible_raw = json.dumps(data.get('perimetre_cible', ["résidence"]), ensure_ascii=False)
    data['perimetre_cible'] = perimetre_cible_raw
    data['public_cible'] = json.dumps(data.get('public_cible', ["résidents"]), ensure_ascii=False)
    pub = Publication(
        **data,
        auteur_id=user.id,
        publiee_le=datetime.utcnow() if not data.get('brouillon') else None,
    )
    session.add(pub)
    session.commit()
    session.refresh(pub)
    if pub.partager_whatsapp and not pub.brouillon:
        wa_config = {r.cle: r.valeur for r in session.exec(select(ConfigSite).where(ConfigSite.cle.in_(_WA_KEYS))).all()}
        if wa_config.get('whatsapp_enabled') == '1':
            background_tasks.add_task(
                envoyer_whatsapp_avec_log, pub.titre, pub.contenu, pub.urgente, pub.perimetre_cible, pub.image_url, wa_config,
                pub.public_cible, pub.id,
            )
    if pub.envoyer_syndic and not pub.brouillon:
        _envoyer_email_syndic_publication(pub, user, background_tasks, session, syndic=True, cs=False)
    if pub.envoyer_cs and not pub.brouillon:
        _envoyer_email_syndic_publication(pub, user, background_tasks, session, syndic=False, cs=True)
    if email_externe and email_externe.strip() and not pub.brouillon:
        _envoyer_email_externe_publication(
            pub, user, email_externe.strip(), background_tasks, session,
            is_commentaire=False,
        )
    return _pub_to_read(pub, session)


@router.patch("/{pub_id}", response_model=PublicationRead)
def update_publication(
    pub_id: int,
    body: PublicationUpdate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    pub = session.get(Publication, pub_id)
    if not pub:
        raise HTTPException(404, "Publication introuvable")
    data = body.model_dump(exclude_unset=True)
    if data.get('archivee') is True and pub.statut != "resolu":
        raise HTTPException(422, "Seules les publications résolues peuvent être archivées")
    if 'perimetre_cible' in data:
        data['perimetre_cible'] = json.dumps(data['perimetre_cible'], ensure_ascii=False)
    if 'public_cible' in data:
        data['public_cible'] = json.dumps(data['public_cible'], ensure_ascii=False)

    ancien_statut = pub.statut
    nouveau_statut = data.get('statut')

    for k, v in data.items():
        setattr(pub, k, v)
    pub.mis_a_jour_le = datetime.utcnow()

    # Changement de statut → enregistrer date + évolution auto
    if nouveau_statut and nouveau_statut != ancien_statut:
        pub.statut_change_le = datetime.utcnow()
        labels = {"en_cours": "En cours", "resolu": "Résolu", "annule": "Annulé"}
        evol = PublicationEvolution(
            publication_id=pub.id,
            type="etat",
            contenu=f"Statut changé : {labels.get(ancien_statut or '', 'Aucun')} → {labels.get(nouveau_statut, nouveau_statut)}",
            ancien_statut=ancien_statut,
            nouveau_statut=nouveau_statut,
            auteur_id=user.id,
            cree_le=datetime.utcnow(),
        )
        session.add(evol)

    # Publication du brouillon → date de publication
    was_brouillon_published = 'brouillon' in data and not data['brouillon'] and pub.publiee_le is None
    if was_brouillon_published:
        pub.publiee_le = datetime.utcnow()

    session.add(pub)
    session.commit()
    session.refresh(pub)

    # Envoi WhatsApp si brouillon publié + flag activé
    if was_brouillon_published and pub.partager_whatsapp:
        wa_config = {r.cle: r.valeur for r in session.exec(select(ConfigSite).where(ConfigSite.cle.in_(_WA_KEYS))).all()}
        if wa_config.get('whatsapp_enabled') == '1':
            background_tasks.add_task(
                envoyer_whatsapp_avec_log, pub.titre, pub.contenu, pub.urgente, pub.perimetre_cible, pub.image_url, wa_config,
                pub.public_cible, pub.id,
            )
    # Envoi email syndic si brouillon publié + flag activé
    if was_brouillon_published and pub.envoyer_syndic:
        _envoyer_email_syndic_publication(pub, user, background_tasks, session, syndic=True, cs=False)
    if was_brouillon_published and pub.envoyer_cs:
        _envoyer_email_syndic_publication(pub, user, background_tasks, session, syndic=False, cs=True)

    return _pub_to_read(pub, session)


@router.post("/{pub_id}/renvoyer-email", status_code=204)
def renvoyer_email_publication(
    pub_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    """Renvoie l'email de la publication au syndic et/ou CS (admin uniquement)."""
    pub = session.get(Publication, pub_id)
    if not pub:
        raise HTTPException(404, "Publication introuvable")
    if pub.brouillon:
        raise HTTPException(422, "Impossible de renvoyer un brouillon")
    if pub.envoyer_syndic:
        _envoyer_email_syndic_publication(pub, user, background_tasks, session, syndic=True, cs=False)
    if pub.envoyer_cs:
        _envoyer_email_syndic_publication(pub, user, background_tasks, session, syndic=False, cs=True)
    if not pub.envoyer_syndic and not pub.envoyer_cs:
        raise HTTPException(422, "Cette publication n'a pas de destinataires email configurés")


@router.delete("/{pub_id}", status_code=204)
def delete_publication(
    pub_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    pub = session.get(Publication, pub_id)
    if not pub:
        raise HTTPException(404, "Publication introuvable")
    # Supprimer les évolutions liées avant la publication (pas de CASCADE en SQLite)
    for evol in list(pub.evolutions):
        session.delete(evol)
    session.delete(pub)
    session.commit()


@router.patch("/{pub_id}/evolutions/{evol_id}", response_model=EvolutionRead)
def update_evolution(
    pub_id: int,
    evol_id: int,
    body: PublicationEvolutionUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    evol = session.get(PublicationEvolution, evol_id)
    if not evol or evol.publication_id != pub_id:
        raise HTTPException(404, "Évolution introuvable")
    if evol.type != "commentaire":
        raise HTTPException(422, "Seuls les commentaires peuvent être modifiés")
    if evol.auteur_id != user.id and not user.has_role(RoleUtilisateur.admin):
        raise HTTPException(403, "Accès refusé")
    if body.contenu is not None:
        evol.contenu = body.contenu
    if body.fichiers_urls is not None:
        evol.fichiers_urls = json.dumps(body.fichiers_urls)
    session.add(evol)
    session.commit()
    session.refresh(evol)
    auteur = session.get(Utilisateur, evol.auteur_id)
    fichiers_list = json.loads(evol.fichiers_urls) if evol.fichiers_urls else []
    return EvolutionRead(
        id=evol.id,
        publication_id=evol.publication_id,
        type=evol.type,
        contenu=evol.contenu,
        ancien_statut=evol.ancien_statut,
        nouveau_statut=evol.nouveau_statut,
        auteur_id=evol.auteur_id,
        auteur_nom=f"{auteur.prenom} {auteur.nom}" if auteur else "?",
        cree_le=evol.cree_le,
        fichiers_urls=fichiers_list,
    )


@router.post("/{pub_id}/evolutions", response_model=EvolutionRead, status_code=201)
def add_evolution(
    pub_id: int,
    body: EvolutionCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    pub = session.get(Publication, pub_id)
    if not pub:
        raise HTTPException(404, "Publication introuvable")
    if body.type == "etat" and not body.nouveau_statut:
        raise HTTPException(422, "nouveau_statut requis pour un changement d'état")
    if body.type == "etat" and body.nouveau_statut not in ("en_cours", "resolu", "annule"):
        raise HTTPException(422, "statut invalide")

    ancien_statut = pub.statut if body.type == "etat" else None
    evol = PublicationEvolution(
        publication_id=pub_id,
        type=body.type,
        contenu=body.contenu,
        ancien_statut=ancien_statut,
        nouveau_statut=body.nouveau_statut if body.type == "etat" else None,
        auteur_id=user.id,
        cree_le=datetime.utcnow(),
        fichiers_urls=json.dumps(body.fichiers_urls, ensure_ascii=False),
    )
    session.add(evol)

    if body.type == "etat":
        pub.statut = body.nouveau_statut
        pub.statut_change_le = datetime.utcnow()
        pub.mis_a_jour_le = datetime.utcnow()
        session.add(pub)

    session.commit()
    session.refresh(evol)

    # Envoi WhatsApp pour le commentaire si demandé
    share_wa = body.partager_whatsapp if body.partager_whatsapp is not None else pub.partager_whatsapp
    if share_wa and body.contenu and body.contenu.strip():
        wa_config = {r.cle: r.valeur for r in session.exec(select(ConfigSite).where(ConfigSite.cle.in_(_WA_KEYS))).all()}
        if wa_config.get('whatsapp_enabled') == '1':
            background_tasks.add_task(
                envoyer_whatsapp_avec_log,
                f"{pub.titre} (suite)",
                body.contenu,
                pub.urgente,
                pub.perimetre_cible,
                None,
                wa_config,
                pub.public_cible,
                pub.id,
            )

    # Envoi email syndic pour le commentaire si demandé
    share_syndic = body.envoyer_syndic if body.envoyer_syndic is not None else pub.envoyer_syndic
    if share_syndic and body.contenu and body.contenu.strip():
        _envoyer_email_syndic_publication(
            pub, user, background_tasks, session, syndic=True, cs=False,
            commentaire=body.contenu, fichiers_urls=body.fichiers_urls,
        )

    # Envoi email CS pour le commentaire si demandé
    share_cs = body.envoyer_cs if body.envoyer_cs is not None else pub.envoyer_cs
    if share_cs and body.contenu and body.contenu.strip():
        _envoyer_email_syndic_publication(
            pub, user, background_tasks, session, syndic=False, cs=True,
            commentaire=body.contenu, fichiers_urls=body.fichiers_urls,
        )

    # Envoi email externe si adresse fournie
    if body.email_externe and body.email_externe.strip():
        _envoyer_email_externe_publication(
            pub, user, body.email_externe.strip(), background_tasks, session,
            is_commentaire=True,
            commentaire=body.contenu,
            fichiers_urls=body.fichiers_urls,
        )

    auteur = session.get(Utilisateur, evol.auteur_id)
    return EvolutionRead(
        id=evol.id,
        publication_id=evol.publication_id,
        type=evol.type,
        contenu=evol.contenu,
        ancien_statut=evol.ancien_statut,
        nouveau_statut=evol.nouveau_statut,
        auteur_id=evol.auteur_id,
        auteur_nom=f"{auteur.prenom} {auteur.nom}" if auteur else "?",
        cree_le=evol.cree_le,
        fichiers_urls=json.loads(evol.fichiers_urls) if evol.fichiers_urls else [],
    )

