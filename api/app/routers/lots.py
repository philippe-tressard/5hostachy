"""Router lots — consultation et import (staging) des lots."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.utils.batiments import libelle_batiment_ou
from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.utils.etages import (
    ETAGE_HORS_BORNES,
    etage_hors_bornes,
    logement_de_reference,
    type_de_lot,
)
from app.models.core import (
    Lot,
    UserLot,
    Utilisateur,
    RoleUtilisateur,
)


#  `_parse_users` et `_type_lien_from_str` sont PARTIS avec l'atelier d'import
#  (`lots_imports.py`, 09/09/2026) : ils n'y servaient qu'à lui. Les laisser ici
#  aurait fait une copie de plus le jour où l'un des deux fichiers apprend
#  quelque chose sur ce JSON (`standards/02` §1 bis).

router = APIRouter(prefix="/lots", tags=["lots"])


#  Helpers 

#  🔴 Le vocabulaire de la colonne TYPE (tables, `_norm`, `_type_from_raw`,
#  `_etage_from_raw`) vit dans `utils/import_xlsx` depuis #829 : il décrit ce
#  qu'un CLASSEUR contient, pas ce qu'un routeur fait. Il était écrit ici ET
#  dans `auto_match_service`, où la copie s'était logée dans un corps de
#  fonction pour contourner un homonyme.


#  Schémas 

class LotRead(BaseModel):
    id: int
    numero: str
    type: str
    type_appartement: Optional[str] = None
    etage: Optional[int] = None
    superficie: Optional[float] = None
    batiment_id: Optional[int] = None
    batiment_nom: Optional[str] = None
    #: Ce lot est-il celui qui renseigne l'étage où l'on VIT ? La règle — un seul
    #: logement, de type appartement, dont l'étage est connu — vit dans
    #: `utils/etages.py` et le front lit ce booléen. Recalculée dans l'écran, elle
    #: y aurait pris sa deuxième écriture, et la divergence que l'API signale
    #: n'aurait plus été la même que celle que l'écran affiche.
    est_logement_de_reference: bool = False


def _lot_read(lot: Lot) -> LotRead:
    return LotRead(
        id=lot.id,
        numero=lot.numero,
        type=type_de_lot(lot),
        type_appartement=lot.type_appartement,
        etage=lot.etage,
        superficie=lot.superficie,
        batiment_id=lot.batiment_id,
        batiment_nom=libelle_batiment_ou(lot.batiment, None),
    )


#  Endpoints publics 

@router.get("/mes-lots")
def mes_lots(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    # Toujours privilégier les associations explicites UserLot.
    # Évite qu'un profil CS/admin voie "tous les lots" alors qu'il attend ses lots personnels.
    user_lots = session.exec(
        select(UserLot).where(UserLot.user_id == user.id, UserLot.actif == True)
    ).all()
    user_lot_ids = [ul.lot_id for ul in user_lots]

    if user_lot_ids:
        lots = session.exec(select(Lot).where(Lot.id.in_(user_lot_ids))).all()
    elif user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        # Fallback pour comptes d'administration sans association propre.
        lots = session.exec(select(Lot)).all()
    else:
        return []

    #  Le logement de référence est désigné ICI, sur la liste entière : la règle
    #  porte sur l'ENSEMBLE des lots (« un seul logement »), donc elle ne peut pas
    #  se calculer lot par lot dans `_lot_read`.
    reference = logement_de_reference(lots)
    lectures = []
    for lot in lots:
        lecture = _lot_read(lot)
        lecture.est_logement_de_reference = reference is not None and lot.id == reference.id
        lectures.append(lecture)
    return lectures


@router.get("/admin/tous")
def tous_les_lots(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Liste complète de tous les lots (admin/CS)."""
    return [_lot_read(lot) for lot in session.exec(select(Lot)).all()]


def _lot_rattache(user: Utilisateur, lot_id: int) -> bool:
    """Ce lot est-il rattaché à cet utilisateur par une association ACTIVE ?

    La règle était écrite en clair dans `get_lot` ; le second endpoint qui en a
    besoin — celui qui écrit l'étage d'un lot (#835) — l'aurait recopiée. Une
    règle d'accès en deux exemplaires ne diverge pas sur le cas nominal : elle
    diverge le jour où l'un des deux apprend quelque chose (`standards/02` §1 bis).
    """
    return lot_id in [ul.lot_id for ul in user.user_lots if ul.actif]


@router.get("/{lot_id}")
def get_lot(
    lot_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    lot = session.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Lot introuvable")
    if not user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        if not _lot_rattache(user, lot_id):
            raise HTTPException(403, "Accès refusé")
    return _lot_read(lot)


class EtageLotUpdate(BaseModel):
    """L'étage d'un lot, seul champ que son occupant peut écrire."""

    etage: Optional[int] = None


@router.patch("/{lot_id}/etage")
def maj_etage_de_mon_lot(
    lot_id: int,
    body: EtageLotUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """L'étage d'UN de MES lots, modifiable depuis le profil (#835).

    ## Ce que cet endpoint écrit, et ce qu'il n'écrit pas

    `Lot.etage` seul. Le lot porte le reste du patrimoine — numéro, superficie,
    tantièmes, bâtiment — et rien de tout cela ne s'ouvre ici : la liste blanche
    est le schéma lui-même, à un champ.

    ## Pourquoi l'association ACTIVE, et pas le repli par rôle

    `get_lot` laisse un admin ou un conseiller lire n'importe quel lot. Ce repli
    n'a pas sa place sur une **écriture** : ils ont déjà l'écran du patrimoine,
    avec ses contrôles, et un conseiller qui modifierait depuis son profil un lot
    qui n'est pas le sien écrirait une donnée partagée par un chemin prévu pour
    la sienne. L'endpoint exige donc un `UserLot` actif — pour tout le monde.

    ## ⚠️ Ce que ce choix accepte, dit une fois

    `Lot.etage` est une donnée de **patrimoine** : elle sert aux imports, aux
    fiches et aux affiches. Deux écrans l'écrivent désormais, avec deux niveaux
    de contrôle — celui-ci et l'administration. Arbitré par Philippe le
    09/09/2026, après que l'alternative (lecture seule + signalement) a été
    posée : c'est l'occupant qui sait à quel étage il vit, et le faire passer par
    un ticket pour corriger un chiffre était la friction de trop.
    """
    lot = session.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Lot introuvable")
    if not _lot_rattache(user, lot_id):
        raise HTTPException(403, "Accès refusé")
    if body.etage is not None and etage_hors_bornes(body.etage):
        raise HTTPException(400, ETAGE_HORS_BORNES)
    #  `None` EFFACE l'étage, et c'est voulu : un champ qu'on vide doit pouvoir
    #  se vider. Il n'y a pas d'ambiguïté ici, contrairement au PATCH du profil
    #  où `None` signifie « ce champ n'est pas dans la requête » — la charge
    #  utile ne porte que lui.
    lot.etage = body.etage
    session.add(lot)
    session.commit()
    session.refresh(lot)
    return _lot_read(lot)


#  🔴 « COMMANDER UN ACCÈS » N'EXISTE QU'UNE FOIS — ici, il n'existe plus
#  (12/09/2026).
#
#  Ce fichier portait `GET /lots/commandes-acces/mes-commandes` et
#  `POST /lots/commandes-acces`, qui créaient le MÊME `CommandeAcces` que
#  `routers/acces/resident.py`. Deux chemins pour un geste, et — c'est le point —
#  **deux règles d'autorisation différentes** :
#
#    * `acces/resident.py` exige un lien `UserLot` avec le lot, et prévient le
#      conseil syndical par courriel ;
#    * la copie d'ici laissait passer admin et conseil syndical sans lien,
#      bornait la quantité à 10, et **ne prévenait personne**.
#
#  Aucun écran n'appelait la copie : ses deux méthodes du client étaient
#  masquées dans `lint:client-appele` par leurs homonymes de `acces` (le
#  contrôle cherche `.<nom>` sans savoir de quel objet il s'agit — c'est la
#  limite relevée le 12/09/2026). Une surface d'écriture sans appelant et avec
#  sa propre règle d'accès est exactement ce que `standards/03` §1 refuse :
#  l'autorisation se décide à UN endroit.

#  L'atelier d'import vit dans `lots_imports.py` depuis le 09/09/2026 (#835) :
#  ce fichier avait franchi les 500 lignes, et la règle de modularité est « au
#  fil de l'eau ». Inclus ICI, à la fin, pour que les chemins et leur ordre de
#  déclaration restent exactement ce qu'ils étaient.
from app.routers.lots_imports import router as _router_imports  # noqa: E402

router.include_router(_router_imports)
