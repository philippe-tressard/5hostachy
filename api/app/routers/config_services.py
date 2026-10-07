"""Les services de la copropriété dans l'administration (#1718).

À part de `config.py`, qui approche des 500 lignes ; même préfixe `/config`, comme
`config_llm`. Réservé à l'administrateur, comme l'onglet.

L'écran n'a ni liste ni règle à lui : il rend ce que décrit `utils/services`, et
un interrupteur écrit la clé d'activation par `PUT /config`, qui la normalise.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth.deps import require_admin
from app.database import get_session
from app.models.core import Utilisateur

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/services")
def services(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Chaque service, son état (`actif`, `coupe`, `incomplet`) et ce qui lui manque.

    🔴 C'est la SEULE liste : l'onglet « Services » rend une carte par entrée.
    Les secrets ne sortent pas — seulement le fait qu'un réglage manque.
    """
    from app.utils.services import decrire

    return decrire(session)
