"""L'assistant IA dans l'administration — les trois points d'accès de l'onglet.

Sortis de `config.py` le 17/09/2026 (modularité, rang 1) : le fichier franchissait
500 lignes en recevant la liste des usages (#984). Même préfixe `/config` : FastAPI
additionne les routers, les URL publiques ne changent pas — le geste de
`auth_mot_de_passe`.

Tout est réservé à l'administrateur, comme l'onglet. Rien de la clé ne sort :
elle s'emploie côté serveur, et `config.py` la masque à la lecture (`_SECRETS`).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.auth.deps import require_admin
from app.database import get_session
from app.models.core import Utilisateur

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/llm-usages")
def llm_usages(
    user: Utilisateur = Depends(require_admin),
):
    """Les usages de l'assistant, leurs clés et leurs valeurs d'origine.

    🔴 C'est la SEULE liste : l'écran d'administration rend un bloc par entrée
    (#984). Une liste recopiée côté front divergerait au premier usage ajouté.
    Les valeurs courantes, elles, viennent de `GET /config/admin`.
    """
    from app.utils.llm_usages import decrire

    return decrire()


@router.post("/llm-test")
async def llm_test(
    usage: str,
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Interroge vraiment le modèle configuré pour cet USAGE et rend sa réponse.

    🔴 Le FAIT, pas le réglage. Un écran qui annonce « configuré » parce que
    trois champs sont remplis ne prouve rien : une clé se révoque, un modèle se
    renomme, un point d'accès se ferme. Ce test envoie une question et attend une
    réponse (`standards/04` — vérifier le comportement, jamais l'artefact).

    Un test PAR usage (17/09/2026) : chacun a son modèle, et c'est lui qu'on
    éprouve. Un usage inconnu est une erreur de l'écran, pas du service.

    ⚠️ Le message d'erreur vient de `ErreurLLM`, jamais du fournisseur : sa
    réponse peut contenir la requête, donc ce qu'on vient de lui envoyer.
    """
    from app.utils.llm import ErreurLLM, tester
    from app.utils.llm_usages import USAGES

    if usage not in USAGES:
        raise HTTPException(422, f"Usage inconnu : « {usage} ».")
    try:
        return await tester(session, usage)
    except ErreurLLM as exc:
        raise HTTPException(400, str(exc))


@router.get("/llm-modeles")
async def llm_modeles(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Les modèles que la clé enregistrée peut réellement appeler.

    ⚠️ Ce point d'accès n'expose rien de la clé : il l'emploie côté serveur et
    ne rend que des identifiants publics de modèles. Il reste réservé à
    l'administrateur, comme tout l'onglet Assistant IA.

    Une liste indisponible n'est pas une erreur — voir `modeles_disponibles`.
    Seule une configuration inexploitable (aucune clé) lève.
    """
    from app.utils.llm import ErreurLLM, modeles_disponibles

    try:
        return await modeles_disponibles(session)
    except ErreurLLM as exc:
        raise HTTPException(400, str(exc))
