"""📦 Archiver et ressortir un prestataire ou un contrat — un geste, un mot (#1538).

## Pourquoi ce module

Le geste avait TROIS noms : l'icône était une corbeille (« supprimer »), la boîte
disait « Archiver ce prestataire ? », la route était un `DELETE` nommé
`archive_prestataire`. Et rien ne le défaisait : l'objet rangé n'avait plus
d'écran, archiver revenait à supprimer sans le dire (`standards/11` §14).

Il n'y a plus qu'un mot, **archivage**, et un seul geste qui range ET ressort :
`PATCH …/archivage {"archivee": true|false}` — la forme de `ux-patterns` §8.
Ce qui est rangé se lit à part, `GET …/archives` : les listes courantes ne
changent pas, et leurs autres lecteurs (formulaire d'affaire, reporting, relevés)
ne voient pas surgir une entreprise qu'on a rangée.

⚠️ Il écrit la colonne héritée `actif`, que `utils/archivage.REGLES` déclare
(`champ_actif`) : c'est la règle qui dit ce qu'est un objet archivé, ce module
ne fait que poser la décision.

Sorti de `prestataires.py`, qui approchait les 500 lignes (modularité, rang 1).
Même préfixe : l'URL dit l'objet, le fichier dit le geste — comme `compteurs.py`.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import ContratEntretien, Prestataire, Utilisateur
from app.routers.prestataires import ContratRead, lister_contrats, lister_prestataires
from app.routers.prestataires_schemas import PrestataireRead
from app.utils.recuperer import ou_404

router = APIRouter(prefix="/prestataires", tags=["prestataires"])


class Archivage(BaseModel):
    """`true` range l'objet dans les Archives, `false` l'en ressort."""

    archivee: bool


def _poser(session: Session, objet, corps: Archivage) -> None:
    objet.actif = not corps.archivee
    session.add(objet)
    session.commit()


@router.get("/archives", response_model=list[PrestataireRead])
def list_prestataires_archives(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return lister_prestataires(session, archivees=True)


@router.get("/contrats/archives", response_model=list[ContratRead])
def list_contrats_archives(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return lister_contrats(session, archivees=True)


#  ⚠️ Le contrat AVANT le prestataire : FastAPI retient la première route qui
#  correspond (#1151). Les deux chemins n'ont pas le même nombre de segments, mais
#  l'ordre fixe-puis-paramètre ne coûte rien et ne dépend pas de ce hasard.
@router.patch("/contrats/{c_id}/archivage", status_code=204)
def archiver_contrat(
    c_id: int,
    corps: Archivage,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    _poser(session, ou_404(session, ContratEntretien, c_id, "Contrat"), corps)


@router.patch("/{p_id}/archivage", status_code=204)
def archiver_prestataire(
    p_id: int,
    corps: Archivage,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    _poser(session, ou_404(session, Prestataire, p_id, "Prestataire"), corps)
