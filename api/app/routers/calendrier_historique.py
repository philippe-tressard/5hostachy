"""Calendrier — l'HISTORIQUE d'un événement, et le vocabulaire de son suivi.

Extrait de `calendrier.py` le 18/08/2026 : l'ajout du fil l'a porté de 377 à 573
lignes, et le garde-fou de modularité a refusé le lot. Il a fonctionné comme
prévu — on découpe le fichier quand on y touche (`standards/02` §6).

## Le Kanban EST le workflow d'un événement

Demandé ainsi : *« peut-être que le kanban tu le glisses dans Workflow ? »* — et
c'est la bonne lecture. Ses six colonnes (AG · CS · Syndic · Prestataire ·
Terminé · Annulé) répondent exactement à la question de la **section 3** du cadre
#430 : *où en est cet objet ?*. Il n'y avait donc rien à ajouter, seulement à
nommer — et à **tracer**, ce qui manquait vraiment.

⚠️ **Aucun second champ d'état n'a été créé**, et c'est un arbitrage : deux
notions de suivi sur le même objet se contredisent au premier écart, et rien ne
dirait laquelle fait foi.

## La frontière retenue

La même que dans `tickets/` et `publications/` : **la décision d'un côté, le
cycle de vie de l'autre**. Ce module porte ce que le fil raconte ; `calendrier.py`
garde la création, la lecture et la modification d'un événement.
"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Evenement, RoleUtilisateur, Utilisateur
from app.models.evenement import EvenementEvolution
from app.utils.photos import parse_photos, photos_internes

router = APIRouter(prefix="/calendrier", tags=["calendrier"])


class EvolutionEvenementRead(BaseModel):
    id: int
    evenement_id: int
    type: str
    contenu: Optional[str] = None
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    auteur_id: int
    auteur_nom: Optional[str] = None
    cree_le: datetime
    fichiers_urls: list[str] = []

    class Config:
        from_attributes = True


class EvolutionEvenementCreate(BaseModel):
    #  `commentaire` ou `etat` — deux types, comme les tickets et les
    #  publications. Le troisième que l'on serait tenté d'ajouter (« correction »)
    #  n'existe nulle part : une correction est un `commentaire` préfixé.
    type: str = "commentaire"
    contenu: Optional[str] = None
    nouveau_statut: Optional[str] = None
    fichiers_urls: list[str] = []


#: Les libellés des colonnes du Kanban, écrits UNE fois côté serveur : ce sont
#: eux que l'Historique inscrit dans « État : X → Y », et un fil doit rester
#: lisible sans que le client traduise quoi que ce soit.
#: ⚠️ Le pendant est `KANBAN_COLS` dans `calendrier/+page.svelte` — les contextes
#: de build sont `./api` et `./front`, le partage d'un fichier est impossible.
KANBAN_LABELS = {
    "ag": "AG",
    "cs": "CS",
    "syndic": "Syndic",
    "fournisseur": "Prestataire",
    "termine": "Terminé",
    "annule": "Annulé",
}


#: Ce qu'une correction raconte dans l'Historique, et sous quel nom. Les libellés
#: sont ceux des neuf sections du cadre : lire « Périmètre » dans le fil et
#: « Périmètre » dans le formulaire qu'on vient de quitter est la moindre des
#: choses (R3). Les champs ABSENTS sont exclus, pas oubliés : `archivee` est un
#: rangement, `statut_kanban` a sa propre ligne (une transition, pas une
#: correction), et les canaux sont des actes de diffusion.
CHAMPS_CORRIGEABLES = {
    "titre": "Titre",
    "type": "Type",
    "lieu": "Lieu",
    "debut": "Date de début",
    "fin": "Date de fin",
    "epingle": "Épinglage",
    "perimetre": "Périmètre",
    "description": "Description",
    "photos_urls": "Photos",
    "fichiers_urls": "Documents",
    "prestataire_id": "Prestataire",
}


def _evolutions_de(ev_id: int, session: Session) -> list[EvolutionEvenementRead]:
    lignes = session.exec(
        select(EvenementEvolution)
        .where(EvenementEvolution.evenement_id == ev_id)
        .order_by(EvenementEvolution.cree_le)
    ).all()
    sortie = []
    for e in lignes:
        brut = e.model_dump()
        brut["fichiers_urls"] = parse_photos(e.fichiers_urls)
        lue = EvolutionEvenementRead.model_validate(brut)
        auteur = session.get(Utilisateur, e.auteur_id)
        lue.auteur_nom = f"{auteur.prenom} {auteur.nom}" if auteur else "?"
        sortie.append(lue)
    return sortie


@router.post("/{ev_id}/evolutions", response_model=EvolutionEvenementRead, status_code=201)
def add_evolution_evenement(
    ev_id: int,
    body: EvolutionEvenementCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Ajoute une entrée à l'Historique d'un événement.

    Deux gestes, un seul endpoint — comme pour un ticket : un **commentaire**,
    ou une **transition** du Kanban (qui déplace aussi l'événement, sinon le fil
    raconterait un mouvement qui n'a pas eu lieu).
    """
    ev = session.get(Evenement, ev_id)
    if not ev:
        raise HTTPException(404, "Événement introuvable")
    if body.type not in ("commentaire", "etat"):
        raise HTTPException(422, "Type d'évolution inconnu")
    if body.type == "etat":
        if not body.nouveau_statut:
            raise HTTPException(422, "nouveau_statut requis pour un changement d'état")
        if body.nouveau_statut not in KANBAN_LABELS:
            raise HTTPException(422, "Colonne de suivi invalide")

    ancien = ev.statut_kanban if body.type == "etat" else None
    evol = EvenementEvolution(
        evenement_id=ev_id,
        type=body.type,
        contenu=body.contenu,
        ancien_statut=ancien,
        nouveau_statut=body.nouveau_statut if body.type == "etat" else None,
        auteur_id=user.id,
        cree_le=datetime.utcnow(),
        fichiers_urls=json.dumps(photos_internes(body.fichiers_urls), ensure_ascii=False),
    )
    session.add(evol)
    if body.type == "etat":
        ev.statut_kanban = body.nouveau_statut
        ev.mis_a_jour_le = datetime.utcnow()
        if body.nouveau_statut == "termine" and ancien != "termine":
            from app.routers.calendrier import _update_contrat_prochaine_visite

            _update_contrat_prochaine_visite(ev, session)
        session.add(ev)
    session.commit()
    session.refresh(evol)
    return _evolutions_de(ev_id, session)[-1]


@router.patch("/{ev_id}/evolutions/{evol_id}", response_model=EvolutionEvenementRead)
def update_evolution_evenement(
    ev_id: int,
    evol_id: int,
    body: EvolutionEvenementCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Corrige le texte ou les pièces jointes d'une entrée.

    ⚠️ On ne corrige JAMAIS `ancien_statut` / `nouveau_statut` : une transition
    a eu lieu, et réécrire un jalon franchi ferait raconter au fil autre chose
    que ce qui s'est passé.
    """
    evol = session.get(EvenementEvolution, evol_id)
    if not evol or evol.evenement_id != ev_id:
        raise HTTPException(404, "Entrée introuvable")
    if evol.auteur_id != user.id and not user.has_role(RoleUtilisateur.admin):
        raise HTTPException(403, "Accès refusé")
    if body.contenu is not None:
        evol.contenu = body.contenu
    if body.fichiers_urls is not None:
        evol.fichiers_urls = json.dumps(photos_internes(body.fichiers_urls), ensure_ascii=False)
    session.add(evol)
    session.commit()
    session.refresh(evol)
    return next(e for e in _evolutions_de(ev_id, session) if e.id == evol_id)


