"""La synthèse assistée d'un contrat d'entretien — un seul endpoint.

Sorti de `prestataires.py` dès l'écriture : ce fichier est à 440 lignes et le
contrôle de modularité (rang 1) refuse qu'il grossisse encore. La coupe suit le
SUJET — un appel à un service externe, sa configuration et ses refus n'ont rien
à voir avec le CRUD des contrats — et elle suit la couture déjà ouverte par
`compteurs.py` le 29/08/2026.

⚠️ Le préfixe d'URL reste `/prestataires` : c'est le même écran, et déplacer le
chemin casserait le client TypeScript pour un gain nul. C'est le RANGEMENT du
code qui change, pas l'API.

🔴 **Cet endpoint n'écrit RIEN.** Il rend une proposition ; l'écran la place dans
le formulaire du contrat, et c'est le conseil syndical qui enregistre. Le
raisonnement est en tête de `app/utils/synthese_contrat.py` — écrire directement
dans `notes` écraserait sans filet une synthèse rédigée à la main.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import ContratEntretien, Utilisateur
from app.utils.synthese_contrat import (
    MAX_DOCUMENTS,
    SyntheseIndisponible,
    documents_transmissibles,
    generer_synthese,
    synthese_active,
)

router = APIRouter(prefix="/prestataires", tags=["prestataires"])


class SyntheseProposee(BaseModel):
    """Ce que l'écran reçoit : du HTML à relire, et de quoi il a été tiré.

    ⚠️ `documents` n'est pas décoratif. La synthèse porte sur les PDF réellement
    transmis — au plus `MAX_DOCUMENTS`, les plus récents — et pas forcément sur
    tout ce que la fiche affiche. Le taire ferait croire que l'avenant de 2019 a
    été lu alors qu'il ne l'a pas été.
    """

    synthese: str
    documents: list[str]


class SyntheseDisponible(BaseModel):
    active: bool


@router.get("/contrats/synthese-disponible", response_model=SyntheseDisponible)
def synthese_disponible(_: Utilisateur = Depends(require_cs_or_admin)):
    """La génération est-elle installée sur ce serveur ?

    🔴 **L'écran doit dire ce que le serveur fait, ni plus ni moins**
    (`ux-patterns` §15). Sans cette réponse, le bouton s'afficherait sur une
    copropriété sans clé et répondrait 501 à qui le presse : une capacité
    introuvable est un défaut, une capacité qui échoue en est un autre.

    ⚠️ Elle ne dit PAS quelle clé, ni laquelle est posée — seulement qu'il y en
    a une. Un booléen n'est pas un secret ; la valeur, elle, ne sort jamais.
    """
    return SyntheseDisponible(active=synthese_active())


@router.post("/contrats/{c_id}/synthese", response_model=SyntheseProposee)
def proposer_synthese(
    c_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    contrat = session.get(ContratEntretien, c_id)
    if not contrat:
        raise HTTPException(404, "Contrat introuvable")
    if not synthese_active():
        #  501 et non 500 : ce n'est pas une panne, c'est une capacité non
        #  installée. L'écran ne devrait d'ailleurs pas proposer le bouton —
        #  cette garde couvre l'appel direct, pas le geste normal.
        raise HTTPException(501, "La génération de synthèse n'est pas configurée sur ce serveur.")

    noms = [d.fichier_nom for d in documents_transmissibles(session, c_id)][:MAX_DOCUMENTS]
    try:
        html = generer_synthese(session, contrat)
    except SyntheseIndisponible as e:
        #  🔴 502, et le message part TEL QUEL vers l'écran. `SyntheseIndisponible`
        #  ne porte que des phrases écrites pour être lues par le conseil syndical
        #  et qui nomment le geste suivant — les remplacer par « Erreur » ici
        #  annulerait le seul travail que fait cette exception.
        raise HTTPException(502, str(e)) from None
    return SyntheseProposee(synthese=html, documents=noms)
