"""Actualités — **voir ce qui partira, avant de confirmer la diffusion**.

## Pourquoi cet endpoint existe (#498, et l'incident du 31/08/2026)

Demandé le 19/08/2026 : *« avant la diffusion il faudrait voir le mail (aperçu)
avant de confirmer son envoi »*, puis *« cela est à intégrer partout où l'objet
diffusion par mail est concerné »*.

**Seuls les tickets l'avaient.** Le 31/08, l'utilisateur a publié une actualité
avec « envoyer au conseil syndical » coché : le message est parti aux
destinataires **sans qu'il ait rien pu voir ni annuler**. Il l'a signalé comme
une régression ; ce n'en était pas une — c'était la moitié jamais construite. La
distinction ne change rien pour qui reçoit le mail.

⚠️ Ce qui rendait cet endpoint impossible jusqu'ici n'était pas l'endpoint :
c'était que `_envoyer_email_syndic_publication` construisait son contexte **dans
son propre corps**. Un aperçu aurait dû le recopier — et un aperçu recomposé
devient faux à la première évolution du gabarit, sans que personne le voie,
puisque c'est l'aperçu qu'on regarde pour vérifier. Le contexte a donc été
extrait d'abord (`contexte_publication_syndic`), et les deux chemins l'appellent.

## Ce qu'il ne recompose PAS

| Ce qu'il montre | Fonction employée | Employée aussi par |
|---|---|---|
| l'e-mail | `contexte_publication_syndic` + `apercu_email` | `_envoyer_email_syndic_publication` |
| le message WhatsApp | `apercu_whatsapp` → `construire_message` | `envoyer_whatsapp_avec_log` |
| les destinataires | `destinataires_syndic_cs` | l'envoi réel |

## Ce qu'il ne peut pas savoir, et qu'il DIT

L'aperçu est demandé **avant** que la publication existe : son identifiant, et
donc le lien permanent, sont attribués à la création. L'écran les nomme plutôt
que d'inventer une valeur.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Publication, Utilisateur
from app.utils.copie_auteur import adresse_copie, auteur_de
from app.utils.apercu_diffusion import ApercuCanal, ApercuDiffusion, apercu_email, apercu_whatsapp
from app.utils.destinataires import destinataires_syndic_cs
from app.utils.fichiers import est_image
from app.utils.photos import photos_internes

from .courriels import contexte_publication_syndic

router = APIRouter()


class BrouillonPublication(BaseModel):
    """Ce que l'écran a sous la main au moment où l'on demande l'aperçu.

    Volontairement **plat et permissif** : c'est un brouillon, pas une
    publication. Le valider comme une création refuserait l'aperçu à qui veut
    justement vérifier avant de compléter.
    """

    #  Renseigné quand on commente une publication EXISTANTE. Le fil est le cas
    #  où l'aperçu sert le PLUS : à la création on relit ce qu'on vient d'écrire,
    #  alors qu'un commentaire part avec l'historique derrière lui, que personne
    #  ne relit avant l'envoi.
    publication_id: Optional[int] = None
    commentaire: str = ""
    titre: str = ""
    contenu: str = ""
    urgente: bool = False
    perimetre_cible: Optional[list[str]] = None
    photos_urls: list[str] = []
    fichiers_urls: list[str] = []
    envoyer_syndic: bool = False
    envoyer_cs: bool = False
    partager_whatsapp: bool = False
    #  « Envoyer une copie à … » — la 4e case de la Diffusion. L'aperçu doit la
    #  montrer : taire un destinataire ferait mentir l'aperçu par omission.
    envoyer_auteur: bool = False


def _publication_previsionnelle(b: BrouillonPublication, auteur: Utilisateur) -> Publication:
    """Une `Publication` **non persistée**, telle qu'elle serait créée.

    Elle n'est jamais ajoutée à la session : les fonctions de composition ne
    lisent que des attributs. C'est ce qui permet l'aperçu avant création sans
    laisser d'objet fantôme en base — `test_apercu_publication` le vérifie en
    comptant les lignes avant et après.
    """
    import json
    from datetime import datetime

    return Publication(
        titre=b.titre,
        contenu=b.contenu,
        auteur_id=auteur.id,
        urgente=b.urgente,
        perimetre_cible=json.dumps(b.perimetre_cible or ["résidence"], ensure_ascii=False),
        photos_urls=json.dumps(photos_internes(b.photos_urls), ensure_ascii=False),
        cree_le=datetime.utcnow(),
    )


@router.post("/apercu-diffusion", response_model=ApercuDiffusion)
def apercu_diffusion(
    brouillon: BrouillonPublication,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Ce que chaque canal coché enverra — composé par les fonctions d'envoi.

    ⚠️ `get_current_user` et non `require_cs_or_admin` : le droit de **diffuser
    sur le groupe** est vérifié par `apercu_whatsapp`, qui rend le canal inactif
    avec son motif plutôt que de montrer un message qui ne partira pas. Refuser
    l'endpoint entier priverait d'aperçu ceux qui n'ont coché que l'e-mail.
    """
    if brouillon.publication_id is not None:
        pub = session.get(Publication, brouillon.publication_id)
        if not pub:
            raise HTTPException(404, "Publication introuvable")
    else:
        pub = _publication_previsionnelle(brouillon, user)

    canaux: list[ApercuCanal] = []

    # ── E-mail syndic / conseil syndical ────────────────────────────────────
    if brouillon.envoyer_syndic or brouillon.envoyer_cs:
        contexte, pieces = contexte_publication_syndic(
            pub,
            user,
            session,
            commentaire=brouillon.commentaire or None,
            fichiers_urls=photos_internes(brouillon.fichiers_urls) or None,
        )
        canaux.append(
            apercu_email(
                session,
                code_modele="publication_syndic",
                contexte=contexte,
                destinataires=destinataires_syndic_cs(
                    session, syndic=brouillon.envoyer_syndic, cs=brouillon.envoyer_cs
                ),
                pieces_jointes=pieces,
                #  La copie va à l'auteur de la PUBLICATION — voir
                #  `app/utils/copie_auteur.py`. L'aperçu doit l'annoncer :
                #  taire un destinataire ferait mentir l'aperçu par omission.
                copie_auteur=(
                    adresse_copie(session, auteur_de(session, Publication, brouillon.publication_id), user)
                    if brouillon.envoyer_auteur
                    else None
                ),
            )
        )

    # ── Groupe WhatsApp ─────────────────────────────────────────────────────
    if brouillon.partager_whatsapp:
        canaux.append(
            apercu_whatsapp(
                session,
                user,
                titre=pub.titre,
                contenu=pub.contenu or "",
                urgent=pub.urgente,
                perimetre=pub.perimetre_cible,
                photo=next(
                    (u for u in photos_internes(brouillon.photos_urls) if est_image(u)), None
                ),
            )
        )

    #  Sur une publication EXISTANTE, rien n'est attribué plus tard.
    a_attribuer = [] if brouillon.publication_id is not None else ["lien permanent"]
    return ApercuDiffusion(
        canaux=canaux,
        attribues_a_la_creation=a_attribuer if canaux else [],
    )
