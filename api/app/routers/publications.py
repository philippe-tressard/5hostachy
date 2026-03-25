"""Router publications — actualités, annonces."""
import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import ConfigSite, Publication, PublicationEvolution, Utilisateur, RoleUtilisateur
from app.schemas import PublicationCreate, PublicationRead, PublicationUpdate, EvolutionCreate, EvolutionRead
from app.utils.whatsapp import envoyer_whatsapp_avec_log

router = APIRouter(prefix="/publications", tags=["publications"])

ARCHIVAGE_DELAI_HEURES = 48
_WA_KEYS = {'whatsapp_enabled', 'whatsapp_api_url', 'whatsapp_api_key', 'whatsapp_group_jid'}  # délai avant archivage automatique après résolu/annulé


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
        ))
    data = PublicationRead.model_validate(pub)
    auteur_pub = session.get(Utilisateur, pub.auteur_id)
    data.auteur_nom = f"{auteur_pub.prenom} {auteur_pub.nom}" if auteur_pub else "?"
    data.evolutions = evol_reads
    return data


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
        result.append(_pub_to_read(pub, session))
    return result


@router.post("", response_model=PublicationRead, status_code=201)
def create_publication(
    body: PublicationCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    data = body.model_dump()
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
                envoyer_whatsapp_avec_log, pub.titre, pub.contenu, pub.urgente, pub.perimetre_cible, pub.image_url, wa_config
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
                envoyer_whatsapp_avec_log, pub.titre, pub.contenu, pub.urgente, pub.perimetre_cible, pub.image_url, wa_config
            )

    return _pub_to_read(pub, session)


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


@router.post("/{pub_id}/evolutions", response_model=EvolutionRead, status_code=201)
def add_evolution(
    pub_id: int,
    body: EvolutionCreate,
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
    )
    session.add(evol)

    if body.type == "etat":
        pub.statut = body.nouveau_statut
        pub.statut_change_le = datetime.utcnow()
        pub.mis_a_jour_le = datetime.utcnow()
        session.add(pub)

    session.commit()
    session.refresh(evol)

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
    )

