"""Le PATRIMOINE physique de la copropriété — ses bâtiments et ses lots.

Extrait de `routers/copropriete.py` le 22/09/2026, au fil de l'eau : le fichier
faisait 513 lignes et le garde-fou de modularité (rang 1) a refusé qu'il
grossisse en recevant le nom du propriétaire dans la liste des lots (#1154).

🔴 Ce bloc, et pas un autre : les deux routes qui restent là-bas décrivent la
FICHE de la copropriété — son assurance, son syndic, les contrats qui les
portent — et partagent pour cela six fonctions de lecture de contrat. Ces
deux-ci ne partagent rien avec elles : elles listent des objets physiques.

⚠️ Le préfixe reste `/copropriete` : les URL publiques ne bougent pas. FastAPI
additionne les routeurs, et `main.py` inclut les deux — c'est la même forme que
`auth_profil` ou `calendrier_historique`, sortis pour la même raison.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Batiment, Lot, TypeLien, UserLot, Utilisateur
from app.utils.noms import nom_affiche

from .copropriete import BatimentRead, LotRead

router = APIRouter(prefix="/copropriete", tags=["copropriété"])

@router.get("/batiments", response_model=list[BatimentRead])
def get_batiments(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    return session.exec(select(Batiment)).all()


@router.get("/lots")
def get_lots(
    batiment_id: Optional[int] = None,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    stmt = select(Lot)
    if batiment_id:
        stmt = stmt.where(Lot.batiment_id == batiment_id)
    lots = session.exec(stmt).all()

    #  🔴 Les propriétaires en UNE requête, pas une par lot (#1154).
    #
    #  La copropriété compte plusieurs centaines de lots : un `session.get` par
    #  ligne ferait autant d'allers-retours, sur une route qu'un écran
    #  d'administration appelle à chaque ouverture. C'est le motif N+1 que
    #  l'audit du 19/09 relevait ailleurs (#1048).
    liens = session.exec(
        select(UserLot, Utilisateur)
        .join(Utilisateur, Utilisateur.id == UserLot.user_id)
        .where(UserLot.type_lien == TypeLien.propriétaire, UserLot.actif.is_(True))
    ).all()
    #  ⚠️ Un lot peut avoir PLUSIEURS propriétaires (indivision) : on garde le
    #  premier plutôt que de les concaténer — le libellé sert à RECONNAÎTRE un
    #  lot dans une liste déroulante, pas à dresser son état civil.
    proprietaire_par_lot: dict[int, str] = {}
    for lien, utilisateur in liens:
        proprietaire_par_lot.setdefault(
            lien.lot_id, nom_affiche(utilisateur.prenom, utilisateur.nom)
        )

    result = []
    for lot in lots:
        bat = session.get(Batiment, lot.batiment_id) if lot.batiment_id else None
        d = LotRead.model_validate(lot)
        d.batiment_nom = bat.numero if bat else None
        d.proprietaire_nom = proprietaire_par_lot.get(lot.id)
        result.append(d)
    return result
