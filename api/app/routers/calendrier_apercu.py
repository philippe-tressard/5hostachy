"""Calendrier — **voir ce qui partira, avant de confirmer la diffusion**.

## Pourquoi cet endpoint existe (#498, et l'incident du 31/08/2026)

Demandé le 19/08/2026, puis rappelé comme **fonctionnalité critique** le 31/08 :

> *« quand une notification est demandée, il n'y a plus une prévisualisation
> avant envoi (possibilité d'annulation si visuel du mail non conforme) »*

Seuls les tickets l'avaient. On cochait « envoyer au syndic » sur un événement et
l'on découvrait le résultat en le recevant — quand on faisait partie des
destinataires.

⚠️ Ce qui rendait cet endpoint impossible n'était pas l'endpoint : c'était que
`notifier_canaux` construisait son contexte, ses pièces jointes et son message
WhatsApp **dans son propre corps**. Un aperçu aurait dû les recopier — et un
aperçu recomposé devient faux à la première évolution d'un gabarit, sans que
personne le voie. Le tout a donc été extrait dans `contexte_evenement_canaux`,
que les deux chemins appellent.

## Ce qu'il ne recompose PAS

| Ce qu'il montre | Fonction employée | Employée aussi par |
|---|---|---|
| l'e-mail | `contexte_evenement_canaux` + `apercu_email` | `notifier_canaux` |
| le message WhatsApp | `contexte_evenement_canaux` + `apercu_whatsapp` | `notifier_canaux` |
| les destinataires | `destinataires_syndic_cs` | `notifier_canaux` |

## 🔴 Le code du modèle est un ternaire de deux littéraux, ICI AUSSI

`calendrier_evenement_suivi` ou `calendrier_evenement_cree`, selon qu'on décrit
une entrée d'Historique ou la création. Écrit tel quel — et non reçu en argument
— parce que `test_email_contexte_appel` lit l'arbre syntaxique : un code opaque
sortirait l'appel du garde-fou, et c'est ainsi que trois `'X' is undefined` sont
partis en production.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Evenement, Utilisateur
from app.utils.apercu_diffusion import ApercuCanal, ApercuDiffusion, apercu_email, apercu_whatsapp
from app.utils.destinataires import destinataires_syndic_cs

from .calendrier_courriels import contexte_evenement_canaux

router = APIRouter(prefix="/calendrier", tags=["calendrier"])


class BrouillonEvenement(BaseModel):
    """Ce que l'écran a sous la main au moment où l'on demande l'aperçu.

    Volontairement **plat et permissif** : c'est un brouillon, pas un événement.
    Le valider comme une création refuserait l'aperçu à qui veut justement
    vérifier avant de compléter.
    """

    #  Renseigné quand on ajoute une entrée à l'Historique d'un événement
    #  EXISTANT. C'est le cas où l'aperçu sert le plus : le message part avec
    #  l'objet derrière lui, que personne ne relit avant d'envoyer.
    evenement_id: Optional[int] = None
    #  L'entrée d'Historique en cours de saisie, s'il y en a une. Sa présence
    #  bascule le gabarit ET le contenu du message : une entrée parle d'ELLE,
    #  pas de l'événement.
    suivi: Optional[dict] = None
    fichiers_suivi: list[str] = []
    titre: str = ""
    description: str = ""
    type: str = ""
    debut: Optional[str] = None
    perimetre: Optional[str] = None
    photos_urls: list[str] = []
    fichiers_urls: list[str] = []
    envoyer_syndic: bool = False
    envoyer_cs: bool = False
    partager_whatsapp: bool = False


def _evenement_previsionnel(b: BrouillonEvenement, auteur: Utilisateur) -> Evenement:
    """Un `Evenement` **non persisté**, tel qu'il serait créé.

    Il n'est jamais ajouté à la session : les fonctions de composition ne lisent
    que des attributs. C'est ce qui permet l'aperçu avant création sans laisser
    d'objet fantôme en base.
    """
    import json
    from datetime import datetime

    from app.models.core import TypeEvenement

    #  ⚠️ Un type inconnu ne fait pas échouer l'aperçu : le brouillon peut être
    #  incomplet, c'est même la raison d'être d'un aperçu. On retombe sur
    #  « autre », qui est ce que le formulaire propose par défaut.
    try:
        type_ev = TypeEvenement(b.type) if b.type else TypeEvenement.autre
    except ValueError:
        type_ev = TypeEvenement.autre

    debut = None
    if b.debut:
        try:
            debut = datetime.fromisoformat(b.debut)
        except ValueError:
            debut = None

    return Evenement(
        titre=b.titre,
        description=b.description,
        type=type_ev,
        debut=debut,
        auteur_id=auteur.id,
        perimetre=b.perimetre or "résidence",
        photos_urls=json.dumps(b.photos_urls, ensure_ascii=False),
        fichiers_urls=json.dumps(b.fichiers_urls, ensure_ascii=False),
    )


@router.post("/apercu-diffusion", response_model=ApercuDiffusion)
def apercu_diffusion(
    brouillon: BrouillonEvenement,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Ce que chaque canal coché enverra — composé par les fonctions d'envoi.

    ⚠️ `get_current_user` et non `require_cs_or_admin` : le droit de diffuser sur
    le groupe est vérifié par `apercu_whatsapp`, qui rend le canal inactif avec
    son motif plutôt que de montrer un message qui ne partira pas.
    """
    if brouillon.evenement_id is not None:
        ev = session.get(Evenement, brouillon.evenement_id)
        if not ev:
            raise HTTPException(404, "Événement introuvable")
    else:
        ev = _evenement_previsionnel(brouillon, user)

    ctx, pieces, wa = contexte_evenement_canaux(
        ev,
        user,
        session,
        suivi=brouillon.suivi,
        fichiers_suivi=brouillon.fichiers_suivi or None,
    )
    #  Le ternaire de deux littéraux — voir l'en-tête du module.
    code = "calendrier_evenement_suivi" if brouillon.suivi else "calendrier_evenement_cree"

    canaux: list[ApercuCanal] = []

    if brouillon.envoyer_syndic or brouillon.envoyer_cs:
        canaux.append(
            apercu_email(
                session,
                code_modele=code,
                contexte=ctx,
                destinataires=destinataires_syndic_cs(
                    session, syndic=brouillon.envoyer_syndic, cs=brouillon.envoyer_cs
                ),
                pieces_jointes=pieces,
            )
        )

    if brouillon.partager_whatsapp:
        canaux.append(
            apercu_whatsapp(
                session,
                user,
                titre=wa["titre"],
                contenu=wa["contenu"],
                #  `urgent=False` : le calendrier n'a pas de notion d'urgence, et
                #  l'envoi passe la même valeur. Un aperçu qui la déduirait du
                #  type d'événement montrerait un bandeau que le groupe ne verra
                #  pas.
                urgent=False,
                perimetre=ev.perimetre,
                photo=wa["photo"],
            )
        )

    a_attribuer = [] if brouillon.evenement_id is not None else ["lien permanent"]
    return ApercuDiffusion(
        canaux=canaux,
        attribues_a_la_creation=a_attribuer if canaux else [],
    )
