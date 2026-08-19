"""Tickets — **voir ce qui partira, avant de confirmer la diffusion**.

## Pourquoi cet endpoint existe (#498, 19/08/2026)

Demandé à l'écran :

> *« avant la diffusion il faudrait voir le mail (aperçu) avant de confirmer son
> envoi »*, puis *« cela est à intégrer partout où l'objet diffusion par mail est
> concerné »*, puis *« l'aperçu peut-il aussi englober WhatsApp ? »*

Jusqu'ici on cochait « envoyer au syndic » ou « partager sur le groupe » et on
découvrait le résultat en le recevant — quand on faisait partie des destinataires.

## 🔴 Un aperçu qui ment est pire que pas d'aperçu

C'est la règle du projet (`standards/04` §14 : observer la chose, pas son
enregistrement). Un aperçu reconstruit « à peu près » deviendrait faux à la
première évolution d'un gabarit, et **personne ne s'en apercevrait** — puisque
c'est justement l'aperçu qu'on regarderait pour le vérifier.

Cet endpoint ne recompose donc **rien** :

| Ce qu'il montre | Fonction employée | Employée aussi par |
|---|---|---|
| l'e-mail | `contexte_ticket_syndic` + `composer_email` | `envoyer_email_syndic_cs` |
| le message WhatsApp | `construire_message` | `envoyer_whatsapp` |
| les destinataires | `destinataires_syndic_cs` | l'envoi réel |

`api/tests/test_apercu_diffusion.py` échoue si l'un des deux chemins s'en écarte.

## Ce qu'il ne peut pas savoir, et qu'il DIT

L'aperçu est demandé **avant** que le ticket existe (arbitrage du 19/08 : « si
l'aperçu est correct alors envoi, sinon annulation ou retour au formulaire »).
Deux champs sont donc attribués plus tard, et l'écran les marque comme tels
plutôt que d'inventer une valeur :

  * le **numéro** du ticket (`TK-……`) ;
  * le **lien permanent**, qui en dépend.

⚠️ Un troisième cas n'est pas connaissable du tout, et l'écran doit le dire : si
une photo existe mais que son encodage pour le bridge échoue, le message WhatsApp
reçoit en plus « 📷 Photos à voir sur le site ». Cela se décide à l'envoi.
L'aperçu montre donc *le message tel qu'il sera composé*, pas *ce que le groupe
recevra à coup sûr* — la nuance est petite et réelle.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, peut_commenter
from app.database import get_session
from app.models.core import ModeleEmail, Ticket, TicketEvolution, Utilisateur
from app.utils.fichiers import est_image
from app.utils.photos import photos_internes

from .courriels import contexte_ticket_syndic, destinataires_syndic_cs

router = APIRouter()


class BrouillonTicket(BaseModel):
    """Ce que l'écran a sous la main au moment où l'on demande l'aperçu.

    Volontairement **plat et permissif** : c'est un brouillon, pas un ticket. Le
    valider comme une création refuserait l'aperçu à qui veut justement vérifier
    avant de compléter.
    """

    #  🔴 Renseigné quand on commente un ticket EXISTANT (#498, 19/08/2026).
    #
    #  L'aperçu ne couvrait que la création, et l'utilisateur l'a découvert en
    #  commentant : il avait coché « envoyer au syndic », rien ne s'est ouvert.
    #  Une fonctionnalité livrée à moitié ne se lit pas comme « la suite arrive »,
    #  elle se lit comme cassée — et c'est la lecture juste, du côté de l'écran.
    #
    #  Le fil est le cas où l'aperçu sert le PLUS : à la création on relit ce
    #  qu'on vient d'écrire, alors qu'un commentaire part avec l'historique du
    #  ticket derrière lui, que personne ne relit avant l'envoi.
    ticket_id: Optional[int] = None
    commentaire: str = ""
    titre: str = ""
    description: str = ""
    categorie: str = ""
    perimetre_cible: Optional[list[str]] = None
    photos_urls: list[str] = []
    fichiers_urls: list[str] = []
    destinataire_syndic: bool = False
    destinataire_cs: bool = False
    partager_whatsapp: bool = False


class ApercuCanal(BaseModel):
    """Un canal, tel qu'il partira — ou la raison pour laquelle il ne partira pas."""

    canal: str                       # 'email' | 'whatsapp'
    actif: bool
    #  🔴 `inactif_motif` est ce qui distingue cet aperçu d'une maquette : si le
    #  bridge est éteint ou qu'aucun destinataire n'est joignable, l'écran doit
    #  le dire AVANT l'envoi, pas laisser croire à une diffusion qui n'aura pas
    #  lieu. C'est le défaut que #480 décrit sur l'annonce de hall.
    inactif_motif: Optional[str] = None
    destinataires: list[str] = []
    sujet: Optional[str] = None
    corps_html: Optional[str] = None
    texte: Optional[str] = None
    #  Vrai quand le message est réduit à « avertissement + périmètre + lien ».
    ampute: bool = False
    avec_photo: bool = False


class ApercuDiffusion(BaseModel):
    canaux: list[ApercuCanal]
    #  Champs qui n'existeront qu'après la création — l'écran les nomme.
    attribues_a_la_creation: list[str] = []


def _ticket_previsionnel(brouillon: BrouillonTicket, auteur: Utilisateur) -> Ticket:
    """Un `Ticket` **non persisté**, tel qu'il serait créé.

    Il n'est jamais ajouté à la session : `composer_email` et `construire_message`
    ne lisent que des attributs, et un objet en mémoire suffit. C'est ce qui
    permet l'aperçu avant création sans laisser d'objet fantôme en base.
    """
    import json

    return Ticket(
        numero="",                      # attribué à la création
        titre=brouillon.titre,
        description=brouillon.description,
        categorie=brouillon.categorie or "question",
        statut="ouvert",
        auteur_id=auteur.id,
        perimetre_cible=json.dumps(brouillon.perimetre_cible or ["résidence"], ensure_ascii=False),
        photos_urls=json.dumps(photos_internes(brouillon.photos_urls), ensure_ascii=False),
        fichiers_urls=json.dumps(photos_internes(brouillon.fichiers_urls), ensure_ascii=False),
        destinataire_syndic=brouillon.destinataire_syndic,
        destinataire_cs=brouillon.destinataire_cs,
    )


@router.post("/apercu-diffusion", response_model=ApercuDiffusion)
def apercu_diffusion(
    brouillon: BrouillonTicket,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Ce que chaque canal coché enverra — composé par les fonctions d'envoi.

    ⚠️ `get_current_user` et non `require_cs_or_admin` : n'importe quel résident
    ouvre un ticket et peut cocher « prévenir le syndic ». Le droit de **diffuser
    sur le groupe** est vérifié à la création (`body.partager_whatsapp and est_cs`)
    — l'aperçu le reflète en marquant le canal inactif, plutôt que de montrer un
    message qui ne partira pas.
    """
    from app.utils.email import composer_email
    from app.utils.email import _contexte_rendu  # même rendu que l'envoi
    from app.utils.whatsapp import (
        config_whatsapp,
        construire_message,
        message_sans_contenu,
        whatsapp_actif,
    )

    #  Deux gestes, un seul endpoint : créer un ticket, ou commenter un ticket
    #  existant. Le second lit l'objet RÉEL en base — son numéro, son titre et son
    #  fil sont déjà attribués, donc rien n'est prévisionnel de ce côté-là.
    evolutions = None
    if brouillon.ticket_id is not None:
        ticket = session.get(Ticket, brouillon.ticket_id)
        if not ticket:
            raise HTTPException(404, "Ticket introuvable")
        #  ⚠️ Le droit de commenter, pas seulement de lire : l'aperçu montre le
        #  contenu du ticket et son historique. Le refuser ici évite d'en faire
        #  une voie de lecture détournée.
        if not peut_commenter(ticket, user):
            raise HTTPException(403, "Accès refusé")
        #  L'historique part AVEC le message, et c'est précisément ce que
        #  personne ne relit avant d'envoyer.
        evolutions = session.exec(
            select(TicketEvolution)
            .where(TicketEvolution.ticket_id == ticket.id)
            .order_by(TicketEvolution.cree_le)
        ).all()
    else:
        ticket = _ticket_previsionnel(brouillon, user)

    canaux: list[ApercuCanal] = []
    pieces = photos_internes(brouillon.photos_urls) + photos_internes(brouillon.fichiers_urls)

    # ── E-mail syndic / conseil syndical ────────────────────────────────────
    if brouillon.destinataire_syndic or brouillon.destinataire_cs:
        destinataires = destinataires_syndic_cs(
            session, syndic=brouillon.destinataire_syndic, cs=brouillon.destinataire_cs
        )
        if not destinataires:
            canaux.append(ApercuCanal(
                canal="email", actif=False,
                inactif_motif="Aucun destinataire joignable : le syndic ou le conseil "
                              "syndical n'a pas d'adresse renseignée.",
            ))
        else:
            modele = session.exec(
                __import__("sqlmodel").select(ModeleEmail).where(ModeleEmail.code == "ticket_syndic")
            ).first()
            if not modele or not modele.actif:
                canaux.append(ApercuCanal(
                    canal="email", actif=False,
                    inactif_motif="Le modèle d'e-mail « ticket_syndic » est inactif ou absent.",
                ))
            else:
                ctx_metier = contexte_ticket_syndic(
                    ticket, user, session, pieces_jointes=pieces,
                    commentaire=brouillon.commentaire or None,
                    evolutions=evolutions,
                )
                ctx, site_nom, site_url, footer = _contexte_rendu(session, ctx_metier)
                sujet, html = composer_email(
                    modele, ctx, site_nom=site_nom, site_url=site_url,
                    email_footer=footer, attachments=pieces or None,
                )
                canaux.append(ApercuCanal(
                    canal="email", actif=True,
                    destinataires=[e for _, e in destinataires],
                    sujet=sujet, corps_html=html,
                ))

    # ── Groupe WhatsApp ─────────────────────────────────────────────────────
    if brouillon.partager_whatsapp:
        est_cs = user.has_role(*_ROLES_DIFFUSION)
        wa_config = config_whatsapp(session)
        if not est_cs:
            canaux.append(ApercuCanal(
                canal="whatsapp", actif=False,
                inactif_motif="Le partage sur le groupe est réservé au conseil syndical.",
            ))
        elif not whatsapp_actif(wa_config):
            canaux.append(ApercuCanal(
                canal="whatsapp", actif=False,
                inactif_motif="Le groupe WhatsApp n'est pas connecté : rien ne partira.",
            ))
        else:
            texte = construire_message(
                f"\U0001f3ab {ticket.titre}",
                ticket.description,
                ticket.categorie == "urgence",
                ticket.perimetre_cible,
                wa_config,
            )
            photo = next((u for u in photos_internes(brouillon.photos_urls) if est_image(u)), None)
            ampute = message_sans_contenu(None, False)
            canaux.append(ApercuCanal(
                canal="whatsapp", actif=True,
                destinataires=["Groupe de la copropriété"],
                texte=texte, ampute=ampute,
                #  La photo ne part QU'AVEC le message complet — même règle que
                #  l'envoi : sur un message amputé, l'image dirait au groupe ce
                #  que le texte s'abstient de dire.
                avec_photo=bool(photo) and not ampute,
            ))

    #  Sur un ticket EXISTANT, rien n'est attribué plus tard : le numéro et le
    #  lien sont déjà là. Annoncer le contraire ferait douter d'un aperçu exact.
    a_attribuer = [] if brouillon.ticket_id is not None else ["numéro du ticket", "lien permanent"]
    return ApercuDiffusion(
        canaux=canaux,
        attribues_a_la_creation=a_attribuer if canaux else [],
    )


#  Les rôles autorisés à diffuser sur le groupe — lus par `has_role`, jamais
#  comparés à une chaîne (`standards/03` §1, et l'audit du 26/07/2026).
def _roles_diffusion():
    from app.models.core import RoleUtilisateur

    return (RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)


_ROLES_DIFFUSION = _roles_diffusion()
