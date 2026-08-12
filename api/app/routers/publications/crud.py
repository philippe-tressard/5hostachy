"""Publications — cycle de vie : lister, créer, modifier, supprimer, renvoyer.

Extrait de `publications.py` le 11/08/2026. Voir `__init__.py`.

Ce module déclare son propre préfixe : ses deux routes de collection ont un
chemin **vide** (`GET /publications`, `POST /publications`), et FastAPI refuse un
chemin vide sur un router sans préfixe — même contrainte que `tickets/crud.py`.
"""
import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    ConfigSite, Publication, PublicationEvolution, RoleUtilisateur, Utilisateur,
)
from app.schemas import PublicationCreate, PublicationRead, PublicationUpdate
from app.utils.photos import photos_json, premiere_photo
from app.utils.visibility import publication_visible
from app.utils.whatsapp import config_whatsapp, envoyer_whatsapp_avec_log, whatsapp_actif

from .commun import (
    ARCHIVAGE_DELAI_HEURES, PUBLIE_VISIBILITE_JOURS,
    _generer_annonce_hall, _is_annule_expired, _is_archived, _pub_to_read,
)
from .courriels import (
    _envoyer_email_externe_publication, _envoyer_email_syndic_publication,
)

router = APIRouter(prefix="/publications", tags=["publications"])


@router.get("", response_model=list[PublicationRead])
def list_publications(
    archived: bool = Query(False),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    pubs = session.exec(
        select(Publication).order_by(
            Publication.epingle.desc(),
            func.coalesce(Publication.mis_a_jour_le, Publication.cree_le).desc(),
        )
    ).all()

    is_cs = user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)

    delai_row = session.get(ConfigSite, 'archivage_delai_heures')
    delai_heures = int(delai_row.valeur) if delai_row and delai_row.valeur.isdigit() else ARCHIVAGE_DELAI_HEURES

    publie_row = session.get(ConfigSite, 'publie_visibilite_jours')
    publie_jours = int(publie_row.valeur) if publie_row and publie_row.valeur.isdigit() else PUBLIE_VISIBILITE_JOURS

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
        arch = _is_archived(pub, delai_heures, publie_jours)
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
    data['perimetre_cible'] = json.dumps(data.get('perimetre_cible', ["résidence"]), ensure_ascii=False)
    data['public_cible'] = json.dumps(data.get('public_cible', ["résidents"]), ensure_ascii=False)
    data['photos_urls'] = photos_json(data.get('photos_urls'))
    pub = Publication(
        **data,
        auteur_id=user.id,
        publiee_le=datetime.utcnow() if not data.get('brouillon') else None,
    )
    session.add(pub)
    session.commit()
    session.refresh(pub)
    if pub.partager_whatsapp and not pub.brouillon:
        wa_config = config_whatsapp(session)
        if whatsapp_actif(wa_config):
            background_tasks.add_task(
                envoyer_whatsapp_avec_log, pub.titre, pub.contenu, pub.urgente, pub.perimetre_cible, premiere_photo(pub.photos_urls), wa_config,
                pub.public_cible, pub.id,
            )
    if pub.envoyer_syndic and not pub.brouillon:
        _envoyer_email_syndic_publication(pub, user, background_tasks, session, syndic=True, cs=False)
    if pub.envoyer_cs and not pub.brouillon:
        _envoyer_email_syndic_publication(pub, user, background_tasks, session, syndic=False, cs=True)
    if pub.annonce_hall and not pub.brouillon:
        _generer_annonce_hall(pub, user, background_tasks, session)
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
    for champ in ('perimetre_cible', 'public_cible'):
        if champ in data:
            data[champ] = json.dumps(data[champ], ensure_ascii=False)
    if 'photos_urls' in data:
        data['photos_urls'] = photos_json(data['photos_urls'])

    ancien_statut = pub.statut
    nouveau_statut = data.get('statut')

    for k, v in data.items():
        setattr(pub, k, v)
    pub.mis_a_jour_le = datetime.utcnow()

    # Changement de statut → enregistrer date + évolution auto
    if nouveau_statut and nouveau_statut != ancien_statut:
        pub.statut_change_le = datetime.utcnow()
        labels = {"publie": "Publié", "en_cours": "En cours", "resolu": "Résolu", "annule": "Annulé"}
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
        wa_config = config_whatsapp(session)
        if whatsapp_actif(wa_config):
            background_tasks.add_task(
                envoyer_whatsapp_avec_log, pub.titre, pub.contenu, pub.urgente, pub.perimetre_cible, premiere_photo(pub.photos_urls), wa_config,
                pub.public_cible, pub.id,
            )
    # Envoi email syndic si brouillon publié + flag activé
    if was_brouillon_published and pub.envoyer_syndic:
        _envoyer_email_syndic_publication(pub, user, background_tasks, session, syndic=True, cs=False)
    if was_brouillon_published and pub.envoyer_cs:
        _envoyer_email_syndic_publication(pub, user, background_tasks, session, syndic=False, cs=True)
    if was_brouillon_published and pub.annonce_hall:
        _generer_annonce_hall(pub, user, background_tasks, session)

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


@router.post("/{pub_id}/renvoyer-whatsapp", status_code=204)
def renvoyer_whatsapp_publication(
    pub_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    """Renvoie l'annonce sur le groupe WhatsApp (admin uniquement).

    Pendant exact de `renvoyer-email`, qui existait seul. L'asymétrie s'est vue
    le 10/08/2026 : un envoi WhatsApp a échoué en production et il n'existait
    AUCUN moyen de le rejouer — republier ne déclenche rien (le déclencheur exige
    `publiee_le is None`, donc il ne vaut qu'une fois), et ajouter un commentaire
    aurait envoyé le commentaire, pas l'annonce. Le seul recours aurait été de
    supprimer la publication et de la recréer.
    """
    pub = session.get(Publication, pub_id)
    if not pub:
        raise HTTPException(404, "Publication introuvable")
    if pub.brouillon:
        raise HTTPException(422, "Impossible de renvoyer un brouillon")
    wa_config = config_whatsapp(session)
    if not whatsapp_actif(wa_config):
        raise HTTPException(422, "Le partage WhatsApp n'est pas actif")
    background_tasks.add_task(
        envoyer_whatsapp_avec_log, pub.titre, pub.contenu, pub.urgente, pub.perimetre_cible,
        premiere_photo(pub.photos_urls), wa_config, pub.public_cible, pub.id,
    )


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
