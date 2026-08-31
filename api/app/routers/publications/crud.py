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
    Publication, PublicationEvolution, RoleUtilisateur, Utilisateur,
)
from app.schemas import PublicationCreate, PublicationRead, PublicationUpdate
from app.models.annonce_hall import AnnonceHall
from app.utils.photos import photos_json, premiere_photo
from app.utils.suppression_liee import flush_si_necessaire, supprimer_documents_de
from app.utils.visibility import publication_visible
from app.utils.whatsapp import config_whatsapp, envoyer_whatsapp_avec_log, whatsapp_actif

from app.utils.archivage import seuil_archivage_jours

from .commun import (
    STATUT_LABELS,
    appliquer_confidentialite, _generer_annonce_hall, _is_annule_expired,
    _is_archived, _pub_to_read,
)
from .courriels import (
    _envoyer_email_externe_publication, _envoyer_email_syndic_publication,
)
from app.utils.corrections import contenu_correction

router = APIRouter(prefix="/publications", tags=["publications"])

#  Ce qu'une correction RACONTE dans l'Historique, et sous quel nom à l'écran.
#  Les libellés sont ceux des neuf sections du cadre (`SECTIONS_LIBELLE` côté
#  front) : lire « Périmètre » dans le fil et « Périmètre » dans le formulaire
#  qu'on vient de quitter est la moindre des choses (R3).
#
#  ⚠️ Les champs ABSENTS de cette table ne sont pas oubliés, ils sont exclus :
#  `archivee` est un rangement, `batiment_id` une donnée dérivée, et les canaux
#  (`partager_whatsapp`, `envoyer_syndic`, `envoyer_cs`, `annonce_hall`) sont des
#  ACTES : cocher l'un d'eux fait PARTIR un message — ce n'est pas une correction
#  de contenu, et l'inscrire comme telle mêlerait deux natures dans le même fil.
#  ⚠️ Ce commentaire disait « section 9, absente en édition, motif geste » : c'est
#  faux depuis le 18/08/2026, la Diffusion y est rouverte. Un commentaire qui
#  survit à ce qu'il décrit est pire qu'absent.
CHAMPS_CORRIGEABLES = {
    'titre': 'Titre',
    'epingle': 'Épinglage',
    'urgente': 'Urgence',
    'brouillon': 'Brouillon',
    'confidentiel': 'Confidentiel',
    'perimetre_cible': 'Périmètre',
    'public_cible': 'Destinataires',
    'contenu': 'Description',
    'photos_urls': 'Photos',
}


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

    seuil_jours = seuil_archivage_jours(session)

    #  ⚠️ La purge garde SON délai, en heures, et il n'est pas réglable par
    #  l'écran d'administration : elle SUPPRIME. Le réglage unique gouverne
    #  l'archivage, pas la destruction (cf. `PURGE_ANNULE_HEURES`).
    to_delete = [p for p in pubs if _is_annule_expired(p)]
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
        arch = _is_archived(pub, seuil_jours)
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
    session.flush()
    appliquer_confidentialite(pub, session)
    session.commit()
    session.refresh(pub)
    if pub.partager_whatsapp and not pub.brouillon:
        wa_config = config_whatsapp(session)
        if whatsapp_actif(wa_config):
            background_tasks.add_task(
                envoyer_whatsapp_avec_log, pub.titre, pub.contenu, pub.urgente, pub.perimetre_cible, premiere_photo(pub.photos_urls), wa_config,
                pub.public_cible, pub.id, pub.confidentiel,
            )
    #  🔴 UN SEUL ENVOI, pas deux. `destinataires_syndic_cs` fusionne et
    #  dédoublonne les deux listes — c'est ce pour quoi elle existe (#668).
    #  L'appeler deux fois envoyait DEUX courriels quand les deux cases étaient
    #  cochées, et le syndic qui siège au CS les recevait tous les deux.
    #
    #  L'aperçu, lui, annonçait déjà **une** liste fusionnée : l'écran et l'envoi
    #  se contredisaient, et c'est l'écran qui avait raison (31/08/2026).
    if (pub.envoyer_syndic or pub.envoyer_cs) and not pub.brouillon:
        _envoyer_email_syndic_publication(
            pub, user, background_tasks, session,
            syndic=pub.envoyer_syndic, cs=pub.envoyer_cs,
            auteur=bool(getattr(body, "envoyer_auteur", False)),
        )
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

    #  L'état d'AVANT, relevé avant la boucle d'affectation : c'est lui qui dit
    #  ce qui a réellement changé. Sans ce relevé, « corriger » une valeur en la
    #  réenregistrant identique s'inscrirait quand même dans l'Historique.
    avant = {champ: getattr(pub, champ, None) for champ in data}
    #  L'état des CANAUX avant modification. La Diffusion est rouverte à
    #  l'édition depuis le 18/08/2026 : sans les boutons de renvoi, retirés de la
    #  carte le matin même, plus aucun chemin ne permettait de prévenir le syndic
    #  d'une actualité déjà publiée.
    canaux_avant = {
        'partager_whatsapp': pub.partager_whatsapp,
        'envoyer_syndic': pub.envoyer_syndic,
        'envoyer_cs': pub.envoyer_cs,
        'annonce_hall': pub.annonce_hall,
    }

    for k, v in data.items():
        setattr(pub, k, v)
    pub.mis_a_jour_le = datetime.utcnow()

    #  🔴 UNE ÉDITION ÉCRIT UNE CORRECTION, PAS UNE TRANSITION (cadre #430, #433)
    #
    #  Ce bloc écrivait une `PublicationEvolution(type="etat")` dès que le statut
    #  changeait — la même forme, au même endroit du fil, que le changement d'état
    #  volontaire du conseil syndical. Tant que l'édition ne rouvrait pas le
    #  workflow, cela ne se voyait pas ; le cadre l'y rouvre (*l'édition corrige, et
    #  l'état s'y corrige comme les autres champs*), et corriger un état mal saisi
    #  apparaîtrait alors comme une ÉTAPE : la publication aurait « été » en cours
    #  alors qu'elle n'y est jamais passée.
    #
    #  Correction identique à celle des tickets (`tickets/crud.py`, #431) — même
    #  défaut, même remède, même forme de ligne : rien ne devient muet, mais ce
    #  qui s'écrit se présente pour ce qu'il est. La vraie transition, elle, garde
    #  son chemin : `POST /publications/{id}/evolutions` (`evolutions.py`), avec
    #  sa date, son auteur et ses canaux.
    if nouveau_statut and nouveau_statut != ancien_statut:
        pub.statut_change_le = datetime.utcnow()

    corrections = [
        libelle
        for champ, libelle in CHAMPS_CORRIGEABLES.items()
        if champ in data and data[champ] != avant.get(champ)
    ]
    if nouveau_statut and nouveau_statut != ancien_statut:
        corrections.insert(
            0,
            f"État : {STATUT_LABELS.get(ancien_statut or '', 'Aucun')} → "
            f"{STATUT_LABELS.get(nouveau_statut, nouveau_statut)}",
        )
    if corrections:
        session.add(PublicationEvolution(
            publication_id=pub.id,
            type="commentaire",
            contenu=contenu_correction(corrections),
            auteur_id=user.id,
            cree_le=datetime.utcnow(),
        ))

    # Publication du brouillon → date de publication
    was_brouillon_published = 'brouillon' in data and not data['brouillon'] and pub.publiee_le is None
    if was_brouillon_published:
        pub.publiee_le = datetime.utcnow()

    #  Après l'affectation des champs, pas avant : la case « Confidentiel » reste
    #  modifiable après publication (arbitrage #347), et c'est précisément ce
    #  changement-là qui doit retirer l'actualité de l'affiche de hall.
    appliquer_confidentialite(pub, session)

    session.add(pub)
    session.commit()
    session.refresh(pub)

    #  🔴 L'ENVOI SUR TRANSITION — décoché → coché, et rien d'autre.
    #
    #  Une case déjà cochée ne repart pas à chaque enregistrement : corriger une
    #  faute de frappe reste silencieux, et l'incident du triple envoi WhatsApp du
    #  14/08/2026 ne peut pas se rejouer par ce chemin. C'est ce qui distingue
    #  « je décide d'envoyer » de « je corrige ».
    #
    #  ⚠️ Exclu quand le brouillon vient d'être publié : ce cas envoie déjà TOUS
    #  les canaux retenus, juste en dessous. Sans cette garde, une publication
    #  passant de brouillon à publique avec une case fraîchement cochée partirait
    #  deux fois.
    #
    #  Sans ce bloc, rouvrir la section serait PIRE que la fermer : la case
    #  cocherait un drapeau que rien ne consommerait, et l'écran promettrait un
    #  envoi qui n'aurait pas lieu — le défaut de `non_relancable` (#435).
    def _vient_d_etre_coche(champ: str) -> bool:
        return bool(getattr(pub, champ)) and not canaux_avant[champ] and not pub.brouillon

    if not was_brouillon_published:
        if _vient_d_etre_coche('partager_whatsapp'):
            wa_config = config_whatsapp(session)
            if whatsapp_actif(wa_config):
                background_tasks.add_task(
                    envoyer_whatsapp_avec_log, pub.titre, pub.contenu, pub.urgente,
                    pub.perimetre_cible, premiere_photo(pub.photos_urls), wa_config,
                    pub.public_cible, pub.id, pub.confidentiel,
                )
        #  Un seul envoi — voir la création. Seuls les canaux qui VIENNENT
        #  d'être cochés partent : un canal déjà coché ne repart pas à chaque
        #  enregistrement, c'est ce qui rend l'édition sûre (cadre, 18/08).
        _neuf_syndic = _vient_d_etre_coche('envoyer_syndic')
        _neuf_cs = _vient_d_etre_coche('envoyer_cs')
        if _neuf_syndic or _neuf_cs:
            _envoyer_email_syndic_publication(
                pub, user, background_tasks, session,
                syndic=_neuf_syndic, cs=_neuf_cs,
                auteur=bool(getattr(body, "envoyer_auteur", False)),
            )
        if _vient_d_etre_coche('annonce_hall'):
            _generer_annonce_hall(pub, user, background_tasks, session)

    # Envoi WhatsApp si brouillon publié + flag activé
    if was_brouillon_published and pub.partager_whatsapp:
        wa_config = config_whatsapp(session)
        if whatsapp_actif(wa_config):
            background_tasks.add_task(
                envoyer_whatsapp_avec_log, pub.titre, pub.contenu, pub.urgente, pub.perimetre_cible, premiere_photo(pub.photos_urls), wa_config,
                pub.public_cible, pub.id, pub.confidentiel,
            )
    # Envoi email syndic si brouillon publié + flag activé
    if was_brouillon_published and (pub.envoyer_syndic or pub.envoyer_cs):
        _envoyer_email_syndic_publication(
            pub, user, background_tasks, session,
            syndic=pub.envoyer_syndic, cs=pub.envoyer_cs,
            auteur=bool(getattr(body, "envoyer_auteur", False)),
        )
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
    if pub.envoyer_syndic or pub.envoyer_cs:
        #  Un seul envoi, comme à la création. Pas de copie à l'auteur : ce
        #  renvoi est un geste d'ADMINISTRATION, pas une diffusion voulue par
        #  l'auteur — le lui copier lui annoncerait un envoi qu'il n'a pas
        #  demandé.
        _envoyer_email_syndic_publication(
            pub, user, background_tasks, session,
            syndic=pub.envoyer_syndic, cs=pub.envoyer_cs,
        )
    else:
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
        premiere_photo(pub.photos_urls), wa_config, pub.public_cible, pub.id, pub.confidentiel,
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
    #  🔴 IL MANQUAIT LES DOCUMENTS ET LES AFFICHES (#546). Trois tables
    #  référencent une publication ; seules les évolutions étaient traitées.
    #
    #    • `document.publication_id` : une pièce jointe n'existe que par sa
    #      publication — elle part avec, fichier compris ;
    #    • `annonce_hall.publication_id` : l'affiche, elle, RESTE et se délie.
    #      Une affiche a été imprimée et posée dans le hall : supprimer la
    #      publication d'origine n'annule pas ce qui est au mur.
    docs = supprimer_documents_de(session, "publication_id", pub_id)
    affiches = session.exec(
        select(AnnonceHall).where(AnnonceHall.publication_id == pub_id)
    ).all()
    for affiche in affiches:
        affiche.publication_id = None
        session.add(affiche)
    #  ⚠️ Le `flush()` ordonne les DELETE — mais ICI, le retirer ne fait PAS
    #  échouer le test : mesuré, pas supposé. L'ordre tombe juste par accident
    #  d'implémentation, `Document` n'ayant aucune `Relationship` vers
    #  `Publication` pour le garantir (cf. `utils/suppression_liee.py`, où le
    #  même geste est, lui, indispensable pour le ticket et l'événement).
    #  Il reste : une ligne qui coûte un aller-retour vaut mieux qu'un ordre dont
    #  rien ne dit qu'il tiendra à la prochaine version de SQLAlchemy.
    flush_si_necessaire(session, docs)
    session.delete(pub)
    session.commit()
