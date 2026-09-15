"""Proposer la synthèse d'un contrat — le seul point d'entrée PAYANT du dépôt.

Sorti de `prestataires.py` le 15/09/2026. Deux raisons, et la seconde est la
vraie :

1. `prestataires.py` était à 498 lignes ; y poser la limite de débit l'aurait
   fait franchir le plafond de modularité (rang 1), qui répond alors
   « découper avant d'ajouter ». La coupe suit le SUJET — un appel externe,
   asynchrone et facturé n'a rien à voir avec le CRUD des prestataires et des
   contrats — et elle suit la couture déjà ouverte par `compteurs.py` le
   29/08/2026.
2. **Cet endpoint n'a pas la même nature que ses voisins.** Partout ailleurs
   dans ce dépôt, un appel en trop coûte du CPU. Ici il coûte de l'argent. Le
   loger avec quarante routes gratuites laisse croire qu'il leur ressemble —
   c'est précisément ce qui a fait qu'il est resté sans frein.

⚠️ Le préfixe d'URL reste `/prestataires` : c'est le même écran et le même
geste, et déplacer le chemin casserait le client TypeScript pour un gain nul.
C'est le RANGEMENT du code qui change, pas l'API.

🔴 **Ce qu'il fait n'a pas bougé d'une ligne** — le corps, ses refus et sa
documentation sont ceux écrits le 11/09/2026 (#901 à #905). Seuls s'ajoutent le
décorateur de limite et le paramètre `request` qu'il exige.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import ContratEntretien, Utilisateur
from app.utils.limiter import limiter

router = APIRouter(prefix="/prestataires", tags=["prestataires"])

#: 🔴 LE SEUL ENDPOINT DE CE DÉPÔT QUI DÉPENSE DE L'ARGENT À CHAQUE APPEL.
#:
#: Une boucle — double-clic, tempête de réessais, onglet resté ouvert sur un
#: écran qui se recharge — facturerait chaque tour. Les autres points d'entrée
#: sensibles sont bornés depuis toujours (`/auth/*`, `/csp`, `/telemetry`) ;
#: celui-ci ne l'était pas, alors qu'il est le seul dont l'abus se lit sur une
#: facture.
#:
#: ⚠️ **C'est un garde-BOUCLE, PAS un plafond de dépense.** Le seul endroit qui
#: puisse réellement arrêter la dépense est le compte du fournisseur (plafond
#: mensuel dans sa console) : une limite posée ici ne connaît ni le prix d'un
#: appel, ni le solde restant. Écrire qu'elle protège le budget serait une
#: consigne fausse, et ce dépôt les tient pour pires qu'absentes.
#:
#: ⚠️ **Le seau est GLOBAL, pas par utilisateur.** `get_remote_address` lit
#: `request.client.host`, or `start.sh` lance uvicorn SANS `--proxy-headers` :
#: derrière Caddy, toutes les requêtes portent l'adresse du conteneur proxy.
#: C'est vrai de TOUTES les limites de ce dépôt, `/auth/login` compris — ce
#: n'est donc pas propre à cet endpoint, et le corriger changerait la sémantique
#: des sept autres. Signalé, pas traité ici.
#:
#: Le chiffre tient compte de ce partage : une synthèse demande au modèle de
#: lire un contrat entier, soit une à plusieurs minutes. Dix par minute est hors
#: d'atteinte d'un usage légitime, même à plusieurs — seule une boucle y arrive.
LIMITE_GENERATION = "10/minute"


@router.post("/contrats/{c_id}/synthese",
             summary="Proposer la synthèse d'un contrat (CS/Admin)")
@limiter.limit(LIMITE_GENERATION)
async def proposer_synthese(
    #  ⚠️ `request` est EXIGÉ par slowapi, qui le lit pour trouver l'appelant.
    #  Son absence ne casse rien au montage : le décorateur lève au PREMIER
    #  clic, pas au démarrage. D'où le contrôle qui appelle vraiment la route.
    request: Request,
    c_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Rend une synthèse PROPOSÉE. N'enregistre rien.

    🔴 Le geste est manuel et il le reste : rien n'appelle ce point d'entrée
    sinon l'icône ✨ d'une carte de contrat, cliquée par un membre du conseil
    syndical. Aucune tâche planifiée, aucun appel à la création d'un contrat —
    chaque synthèse est facturée, et chacune doit être voulue.

    ⚠️ Le texte rendu remplit le champ « Synthèse » du formulaire d'édition, que
    le CS relit et enregistre lui-même. Écrire directement en base ferait du
    modèle l'auteur d'un document réglementaire (décret n° 2001-477).
    """
    from app.utils.synthese_contrat import ErreurLLM, synthese_disponible, synthetiser

    contrat = session.get(ContratEntretien, c_id)
    if not contrat:
        raise HTTPException(404, "Contrat introuvable")
    if not synthese_disponible(session, contrat):
        raise HTTPException(
            400,
            "L'assistant n'est pas configuré, ou ce contrat n'a pas de document joint.",
        )
    try:
        return {"synthese": await synthetiser(session, contrat)}
    except ErreurLLM as exc:
        raise HTTPException(400, str(exc))
