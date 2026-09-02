"""Publications — le fil de suivi : changements d'état et commentaires.

Extrait de `publications.py` le 11/08/2026. Voir `__init__.py`.

Chemins nus : le préfixe `/publications` est appliqué au montage.
"""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.deps import peut_editer, require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Publication, PublicationEvolution, Utilisateur,
)
from app.schemas import EvolutionCreate, EvolutionRead, PublicationEvolutionUpdate
from app.utils.evolutions import supprimer_evolution
from app.utils.photos import photos_json
from app.utils.whatsapp import config_whatsapp, envoyer_whatsapp_avec_log, whatsapp_actif

from .commun import STATUTS_PUBLICATION, evolution_read
from .courriels import (
    _envoyer_email_externe_publication, _envoyer_email_syndic_publication,
)

router = APIRouter(tags=["publications"])


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
    if evol.type not in ("commentaire", "etat"):
        raise HTTPException(422, "Ce type d'évolution ne peut pas être modifié")
    #  L'auteur ou un admin — `peut_editer`, du module central.
    if not peut_editer(evol, user):
        raise HTTPException(403, "Accès refusé")
    if body.contenu is not None:
        evol.contenu = body.contenu
    if body.fichiers_urls is not None:
        evol.fichiers_urls = photos_json(body.fichiers_urls)
    session.add(evol)
    session.commit()
    session.refresh(evol)
    return evolution_read(evol, session)


@router.delete("/{pub_id}/evolutions/{evol_id}", status_code=204)
def delete_evolution(
    pub_id: int,
    evol_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    """Retirer une entrée du fil d'une actualité — **administrateur seulement**.

    Le bouton 🗑️ existait à l'écran depuis longtemps ; la route, non. Un
    administrateur cliquait, et **rien ne se passait** — pas d'action, pas
    d'erreur, pas de trace (#505 puis #512). L'écran a été corrigé d'abord (le
    bouton a disparu là où il ne pouvait rien), parce qu'un geste proposé et non
    consommé est pire qu'un geste absent. Voici le geste.

    Le contrat est celui des tickets, **littéralement** : même code, même liste
    de types effaçables, même message de refus — voir `app/utils/evolutions.py`.
    """
    supprimer_evolution(
        session, PublicationEvolution, evol_id,
        champ_parent="publication_id", parent_id=pub_id,
    )
    return None


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
    if body.type == "etat" and body.nouveau_statut not in STATUTS_PUBLICATION:
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
        fichiers_urls=photos_json(body.fichiers_urls),
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
        wa_config = config_whatsapp(session)
        if whatsapp_actif(wa_config):
            # Commentaires précédents (hors celui qui vient d'être créé)
            evols_precedents = [
                e for e in session.exec(
                    select(PublicationEvolution).where(
                        PublicationEvolution.publication_id == pub.id,
                        PublicationEvolution.id != evol.id,
                    )
                ).all()
                if e.contenu
            ]
            #  Sur une actualité confidentielle, le commentaire ne part PAS dans
            #  le groupe : `envoyer_whatsapp_avec_log` réduit alors le message à
            #  l'avertissement + le périmètre + le lien. Le contenu ci-dessous
            #  n'est donc pas diffusé — il reste construit pour le cas normal.
            wa_contenu = body.contenu
            if evols_precedents:
                site_url = (wa_config.get('site_url') or '').rstrip('/')
                nb = len(evols_precedents)
                wa_contenu += (
                    f"\n\n📜 Cet échange comporte {nb} commentaire(s) précédent(s).\n"
                    f"Consultez l'historique complet sur l'application :\n"
                    f"👉 {site_url}/actualites#pub-{pub.id}"
                )
            background_tasks.add_task(
                envoyer_whatsapp_avec_log,
                f"{pub.titre} (suite)",
                wa_contenu,
                pub.urgente,
                pub.perimetre_cible,
                None,
                wa_config,
                pub.public_cible,
                pub.id,
                pub.confidentiel,
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

    return evolution_read(evol, session)
