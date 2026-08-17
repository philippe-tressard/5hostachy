"""Publications — notions partagées par les quatre sous-domaines.

Extrait de `publications.py` (682 lignes) le 11/08/2026. Voir `__init__.py` pour
la règle de découpage.
"""
import json
import logging
from datetime import datetime, timedelta

from fastapi import BackgroundTasks
from sqlmodel import Session, select

from app.models.core import (
    AnnonceHall, Publication, PublicationEvolution, Utilisateur,
)
from app.schemas import EvolutionRead, PublicationRead
from app.utils.perimetres import a_portee_globale

#  `_generer_annonce_hall` journalise l'échec de génération sans le propager :
#  sans ce logger, l'`except` du module d'origine levait un `NameError` et
#  faisait échouer la publication qu'il devait justement protéger. Trouvé par
#  ruff au découpage, jamais par un test — aucun n'emprunte ce chemin.
logger = logging.getLogger("publications")

ARCHIVAGE_DELAI_HEURES = 48
PUBLIE_VISIBILITE_JOURS = 30  # une publication « publié » reste visible 1 mois puis est archivée

#  ── Le WORKFLOW d'une publication, écrit UNE fois (#433) ────────────────────
#
#  La liste des états et leurs libellés vivaient en trois exemplaires : le tuple
#  de validation d'`evolutions.py`, un dictionnaire en clair dans le `PATCH` de
#  `crud.py`, et un `_STATUT_LABELS` **amputé de `publie`** dans
#  `flux/publications.py`. C'est la panne des statuts de ticket à l'identique
#  (#415, quatre copies) : deux listes d'accord entre elles ne prouvent rien, et
#  la copie la plus consultée est celle qui trompe le plus longtemps.
#
#  ⚠️ Le front en tient le pendant dans `front/src/lib/publications.ts`
#  (`STATUT_LABELS`, `STATUT_BADGE`) : les contextes de build sont `./api` et
#  `./front`, rien de la racine n'entre dans les images — le partage d'un fichier
#  entre les deux est impossible, seule la copie l'est. Toute modification ici en
#  appelle une là-bas.
STATUTS_PUBLICATION = ("publie", "en_cours", "resolu", "annule")

STATUT_LABELS = {
    "publie": "Publié",
    "en_cours": "En cours",
    "resolu": "Résolu",
    "annule": "Annulé",
}


def _pub_to_read(pub: Publication, session: Session) -> PublicationRead:
    """Construit un PublicationRead avec les évolutions et le nom auteur."""
    evols = session.exec(
        select(PublicationEvolution)
        .where(PublicationEvolution.publication_id == pub.id)
        .order_by(PublicationEvolution.cree_le)
    ).all()
    evol_reads = [evolution_read(e, session) for e in evols]
    data = PublicationRead.model_validate(pub)
    auteur_pub = session.get(Utilisateur, pub.auteur_id)
    data.auteur_nom = f"{auteur_pub.prenom} {auteur_pub.nom}" if auteur_pub else "?"
    data.evolutions = evol_reads
    return data


def appliquer_confidentialite(pub: Publication, session: Session) -> None:
    """Fait tenir les deux invariants de la confidentialité, à chaque écriture.

    ## 1. Confidentiel n'a de sens que sur un périmètre qui restreint vraiment

    `perimetre_visible` rend `True` pour tout le monde dès qu'un nœud cité — ou
    l'un de ses ancêtres — porte `portee_globale` : « Copropriété entière », mais
    aussi « Parking » ou « Caves » sur l'arbre livré. Cocher « Confidentiel »
    là-dessus ne retirerait la publication à personne, et le cadenas affiché
    promettrait une protection inexistante. Le drapeau est donc **décoché** dans
    ce cas, plutôt que conservé et menteur (`standards/04` : vérifier le fait).

    L'interface grise déjà la case ; ce contrôle-ci est celui qui vaut, parce
    qu'il est le seul que l'API ne délègue pas au formulaire.

    ## 2. Confidentiel ⇒ pas d'affiche de hall

    Une affiche est punaisée dans un hall et lue par n'importe qui : il n'y a
    aucun contrôle d'accès derrière, contrairement à WhatsApp où le lien renvoie
    vers l'application. La symétrie compte — cocher « Confidentiel » sur une
    actualité **déjà retenue** pour le hall doit l'en retirer (arbitrage #347),
    et l'affiche déjà générée est **archivée**, pas supprimée : le PDF a été
    envoyé au CS, il fait foi (archiver ≠ supprimer, `standards/11`).
    """
    if pub.confidentiel:
        try:
            codes = json.loads(pub.perimetre_cible or "[]")
        except Exception:
            #  Ciblage illisible : on ne RETIRE pas une protection sur la foi
            #  d'une donnée qu'on n'a pas su lire. `publication_visible` refuse
            #  déjà cette publication à tout le monde sauf au CS, qui pourra la
            #  corriger.
            codes = None
        if isinstance(codes, (list, tuple)) and (
            not codes or a_portee_globale([str(c) for c in codes])
        ):
            pub.confidentiel = False

    if not pub.confidentiel:
        return

    pub.annonce_hall = False
    for annonce in session.exec(
        select(AnnonceHall).where(
            AnnonceHall.publication_id == pub.id, AnnonceHall.archivee == False,  # noqa: E712
        )
    ).all():
        annonce.archivee = True
        session.add(annonce)


def _generer_annonce_hall(
    pub: Publication, user: Utilisateur, background_tasks: BackgroundTasks, session: Session,
) -> None:
    """Génère l'affiche de hall d'une publication (option « Annonce Hall »).

    Idempotent : une publication ne produit qu'une seule annonce. L'échec de la
    génération ne doit jamais faire échouer la publication elle-même — il est
    journalisé, la publication reste créée.
    """
    from app.routers.annonces_hall import creer_annonce_hall, images_de_publication

    #  Garde-fou de dernier recours : `appliquer_confidentialite` a déjà décoché
    #  `annonce_hall`, donc aucun appelant ne devrait arriver ici. On ne génère
    #  pas l'affiche pour autant — un contrôle placé au seul endroit qui produit
    #  le PDF est le seul qu'un futur chemin d'appel ne pourra pas contourner.
    if pub.confidentiel:
        logger.warning(
            "Affiche de hall refusée : la publication %s est confidentielle", pub.id,
        )
        return

    deja = session.exec(
        select(AnnonceHall).where(AnnonceHall.publication_id == pub.id)
    ).first()
    if deja:
        return

    try:
        creer_annonce_hall(
            session=session,
            user=user,
            background_tasks=background_tasks,
            titre=pub.titre,
            message=pub.contenu,
            perimetre_cible=json.loads(pub.perimetre_cible or '["résidence"]'),
            images=images_de_publication(pub, session),
            publication_id=pub.id,
        )
    except Exception as exc:
        logger.error("Annonce de hall non générée pour la publication %s : %s", pub.id, exc)


def _is_archived(
    pub: Publication,
    delai_heures: int = ARCHIVAGE_DELAI_HEURES,
    publie_jours: int = PUBLIE_VISIBILITE_JOURS,
) -> bool:
    """True si la publication doit être considérée comme archivée."""
    if pub.archivee:
        # L'archivage explicite prime sur tout : c'est une décision humaine.
        return True
    if pub.epingle:
        # Épinglé = « garder en vue » ; s'auto-archiver au bout de 30 jours
        # contredirait le marqueur. Décision du 01/08/2026, prise avec le
        # bandeau « Épinglé » du fil d'activité. Pour retirer la publication,
        # on la dépingle (ou on l'archive à la main) — l'action reste explicite.
        # Volontairement ici et non côté fil : /actualités et le tableau de bord
        # doivent trancher pareil, sous peine de voir un élément dans une vue et
        # pas dans l'autre (bug du 17/07/2026).
        return False
    if pub.statut == "resolu" and pub.statut_change_le:
        delta = datetime.utcnow() - pub.statut_change_le
        return delta >= timedelta(hours=delai_heures)
    # État « publié » (défaut, hors workflow) : visible publie_jours puis archivé.
    # Les brouillons (non encore publiés) ne sont jamais concernés.
    if pub.statut in ("publie", None) and not pub.brouillon:
        ref = pub.statut_change_le or pub.publiee_le or pub.cree_le
        if ref:
            return (datetime.utcnow() - ref) >= timedelta(days=publie_jours)
    return False


def _is_annule_expired(pub: Publication, delai_heures: int = ARCHIVAGE_DELAI_HEURES) -> bool:
    """True si la publication annulée a dépassé le délai et doit être supprimée."""
    if pub.statut == "annule" and pub.statut_change_le:
        return (datetime.utcnow() - pub.statut_change_le) >= timedelta(hours=delai_heures)
    return False


def evolution_read(evol: PublicationEvolution, session: Session) -> EvolutionRead:
    """Sérialisation d'une évolution — écrite trois fois avant le découpage.

    `update_evolution`, `add_evolution` et `_pub_to_read` construisaient chacun
    ce même `EvolutionRead` de dix champs, avec la même résolution de l'auteur et
    le même `json.loads` défensif sur `fichiers_urls`. Trois copies d'une
    sérialisation divergent au premier champ ajouté — celui-ci n'aurait été mis à
    jour qu'à deux endroits sur trois, et rien ne l'aurait signalé.
    """
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
