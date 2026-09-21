"""**Une actualité devient une affaire** — sans rien ressaisir (#1094).

## Pourquoi un module à part

`crud.py` était à 486 lignes ; ces deux routes l'auraient porté à 643, au-dessus
du plafond de 500. Le découpage suit la règle du paquet — *un domaine, un
module* — et celui-ci en est un : la **conversion** d'un objet en un autre n'est
ni un cycle de vie, ni un fil de suivi, ni un envoi.

⚠️ C'est un **découpage**, pas une factorisation : rien n'est dédupliqué ici,
un fichier trop long est seulement coupé selon sa nature (`standards/02` §6).

## Le gain, et il est pour l'utilisateur

Une actualité qui dérape — « attention, fuite au 3e » — obligeait à rouvrir une
affaire et **tout retaper**. Ici, titre, description, pièces jointes et
périmètre suivent ; on ajoute un statut.

## L'arbitrage du 21/09/2026 : la publication DISPARAÎT

Trois voies étaient possibles — convertir, coexister, archiver. La conversion a
été retenue : *un seul objet à la fois, jamais de doublon*. C'est ce que « le
suivi devient une propriété » veut dire à l'écran.

🔴 **Ce que la conversion coûtait, et ce qui le paie.** Une actualité publiée a
déjà été envoyée par courriel, avec son adresse. `promu_depuis_publication_id`
garde le numéro de la publication disparue, et `GET /publications/{id}` rend
**410** avec l'affaire née d'elle — sans quoi chacun de ces courriels serait un
lien mort. Le chantier refuse de renommer les identifiants `TK-xxxx` pour
exactement cette raison.

Verrouillé par `api/tests/test_promotion_actualite.py`.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.annonce_hall import AnnonceHall
from app.models.core import Publication, StatutTicket, Ticket, Utilisateur
from app.models.documents import Document
from app.routers.tickets.commun import generer_numero, ticket_read
from app.schemas import PublicationRead, TicketRead
from app.utils.courriel_entrant import nouveau_jeton
from app.utils.perimetres import parse_json_perimetres
from app.utils.recuperer import ou_404
from app.utils.visibility import publication_visible

from .commun import _pub_to_read

router = APIRouter(prefix="/publications", tags=["publications"])


def _affaire_nee_de(session: Session, pub_id: int) -> Optional[Ticket]:
    """L'affaire née de cette publication, s'il y en a une.

    C'est la seule lecture de `promu_depuis_publication_id`, et elle sert les
    deux chemins : la redirection de l'ancienne adresse, et le refus d'une
    seconde promotion.
    """
    return session.exec(
        select(Ticket).where(Ticket.promu_depuis_publication_id == pub_id)
    ).first()


@router.get("/{pub_id}", response_model=PublicationRead)
def lire_publication(
    pub_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Une actualité — ou **où elle est allée**, si elle a été promue.

    🔴 Cette route existe d'abord pour le second cas (#1094). Une actualité
    publiée a déjà été envoyée par courriel, avec son adresse : la promotion la
    supprime, et sans cette route chacun de ces courriels deviendrait un lien
    mort. Le dépôt refuse de renommer les identifiants `TK-xxxx` pour
    exactement la même raison.

    ⚠️ **410 et non 404**, et la nuance porte tout l'usage : 404 dit « ça n'a
    jamais existé » et ne laisse nulle part où aller ; 410 dit « ça a existé,
    voici où c'est parti ». Un identifiant réellement inconnu, lui, reste un
    404 — sinon on annoncerait une affaire qui n'existe pas.
    """
    pub = session.get(Publication, pub_id)
    if pub is None:
        affaire = _affaire_nee_de(session, pub_id)
        if affaire is not None:
            raise HTTPException(
                status_code=410,
                detail={
                    "message": "Cette actualité est devenue une affaire.",
                    "promu_en_affaire": affaire.id,
                    "numero": affaire.numero,
                },
            )
        #  Le 404 passe par la porte commune : les quatre-vingt-dix messages du
        #  produit disent la même chose de la même façon (`utils/recuperer`).
        return ou_404(session, Publication, pub_id, "Publication")
    #  La règle de visibilité est celle du site, jamais réécrite ici. Un objet
    #  qu'on n'a pas le droit de voir se dit INTROUVABLE et non « interdit » :
    #  un 403 confirmerait son existence.
    if not publication_visible(session, pub, user):
        return ou_404(session, Publication, None, "Publication")
    return _pub_to_read(pub, session)


@router.post("/{pub_id}/promouvoir", response_model=TicketRead, status_code=201)
def promouvoir_en_affaire(
    pub_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """**Cette information demande un suivi** — l'actualité devient une affaire.

    ## Le gain, et il est pour l'utilisateur (#1094)

    Une actualité qui dérape — « attention, fuite au 3e » — obligeait à rouvrir
    une affaire et **tout retaper**. Ici, titre, description, pièces jointes et
    périmètre suivent ; on ajoute un statut.

    ## L'arbitrage du 21/09/2026 : la publication DISPARAÎT

    Trois voies étaient possibles — convertir, coexister, archiver. La
    conversion a été retenue : *un seul objet à la fois, jamais de doublon*.
    C'est ce que « le suivi devient une propriété » veut dire à l'écran.

    ## Ce qui suit, ce qui se délie, ce qui part

    | | |
    |---|---|
    | titre, contenu → description, photos, périmètre, bâtiment, dates, confidentiel, épinglé | **suit** |
    | les `Document` rattachés | **suivent** — repointés vers l'affaire, pas supprimés : « rien n'est ressaisi » vaut aussi pour eux |
    | l'affiche de hall | **se délie** — elle a été imprimée et posée, la convertir n'annule pas ce qui est au mur (même règle que la suppression, #546) |
    | les évolutions de la publication | **partent** — une suite dont l'objet n'existe plus n'est lisible par personne |

    ⚠️ Le geste est réservé au conseil syndical : il change la nature d'un objet
    déjà publié et lui donne un statut de suivi. Même règle que les champs de
    commandement à la création d'une affaire (`routers/tickets/crud.py`).
    """
    pub = session.get(Publication, pub_id)
    if pub is None:
        affaire = _affaire_nee_de(session, pub_id)
        if affaire is not None:
            raise HTTPException(
                status_code=410,
                detail={
                    "message": "Cette actualité est déjà devenue une affaire.",
                    "promu_en_affaire": affaire.id,
                },
            )
        return ou_404(session, Publication, pub_id, "Publication")

    affaire = Ticket(
        numero=generer_numero(),
        #  L'adresse de réponse se fixe à la naissance, comme pour toute affaire
        #  (#703) : une affaire sans jeton part avec un courriel sans `Reply-To`,
        #  et la réponse du syndic retombe dans une boîte muette.
        jeton_courriel=nouveau_jeton(),
        promu_depuis_publication_id=pub.id,
        titre=pub.titre,
        #  🔴 Le CONTENU d'une actualité devient la DESCRIPTION d'une affaire :
        #  deux noms pour la même chose, et cette ligne est le seul endroit où
        #  la correspondance s'écrit.
        description=pub.contenu,
        debut=pub.debut,
        fin=pub.fin,
        #  Une affaire naît OUVERTE : elle n'a pas encore été regardée. Reprendre
        #  le `statut` de la publication n'aurait aucun sens — ce sont deux
        #  vocabulaires (`publie`/`resolu` d'un côté, le workflow de l'autre).
        statut=StatutTicket.ouvert,
        auteur_id=pub.auteur_id,
        batiment_id=pub.batiment_id,
        #  Le périmètre SUIT tel quel. Pas de défaut écrit ici : il est une
        #  DONNÉE (`code_par_defaut()`), et une copropriété qui renomme son nœud
        #  racine ne doit pas voir un badge mentir. `parse_json_perimetres`
        #  porte ce repli, et `Ticket.perimetre_cible` son propre défaut.
        perimetre_cible=pub.perimetre_cible
        or json.dumps(parse_json_perimetres(None), ensure_ascii=False),
        photos_urls=pub.photos_urls,
        confidentiel=pub.confidentiel,
        epingle=pub.epingle,
        #  « Saisi pour » suit : l'affaire appartient à la même personne que
        #  l'actualité dont elle naît (#1104).
        saisi_pour_user_id=pub.saisi_pour_user_id,
        saisi_pour_nom=pub.saisi_pour_nom,
        saisi_pour_email=pub.saisi_pour_email,
    )
    session.add(affaire)
    session.flush()

    #  Les pièces jointes SUIVENT — c'est « rien n'est ressaisi » appliqué aux
    #  documents, que `photos_urls` seul ne couvre pas (autre table).
    for doc in session.exec(select(Document).where(Document.publication_id == pub_id)).all():
        doc.publication_id = None
        doc.ticket_id = affaire.id
        session.add(doc)

    #  L'affiche de hall se DÉLIE et reste : elle a été imprimée et posée.
    for affiche in session.exec(
        select(AnnonceHall).where(AnnonceHall.publication_id == pub_id)
    ).all():
        affiche.publication_id = None
        session.add(affiche)

    for evol in list(pub.evolutions):
        session.delete(evol)
    session.flush()
    session.delete(pub)
    session.commit()
    session.refresh(affaire)
    return ticket_read(affaire, session)
