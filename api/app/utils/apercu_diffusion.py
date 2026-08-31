"""Voir ce qui partira, avant de confirmer la diffusion — pour TOUTE entité.

## Pourquoi cet objet existe (#498, demandé le 19/08/2026)

> *« avant la diffusion il faudrait voir le mail (aperçu) avant de confirmer son
> envoi »*, puis *« cela est à intégrer partout où l'objet diffusion par mail est
> concerné »*, puis, le 31/08 : *« c'est une fonctionnalité critique »*.

Jusqu'ici, **seuls les tickets** l'avaient. On cochait « envoyer au syndic » sur
une actualité ou un événement, et l'on découvrait le résultat en le recevant —
quand on faisait partie des destinataires. C'est ce que l'utilisateur a constaté
le 31/08 sur une publication : le message est parti sans qu'il ait rien pu voir.

## 🔴 Un aperçu qui ment est pire que pas d'aperçu

`standards/04` §14 : observer la chose, pas son enregistrement. Un aperçu
reconstruit « à peu près » deviendrait faux à la première évolution d'un
gabarit, et **personne ne s'en apercevrait** — puisque c'est justement l'aperçu
qu'on regarderait pour le vérifier.

Ce module ne recompose donc **rien** : il appelle les fonctions de l'envoi.

| Ce qu'il montre | Fonction employée | Employée aussi par |
|---|---|---|
| l'e-mail | `_contexte_rendu` + `composer_email` | `send_email` / `send_email_group` |
| le message WhatsApp | `construire_message` | `envoyer_whatsapp` |
| les destinataires | `destinataires_syndic_cs` | l'envoi réel |

## Ce que l'appelant fournit, et pourquoi c'est LUI qui le fournit

Chaque entité a son gabarit, son contexte métier et sa façon de se raconter sur
WhatsApp. Ce module porte ce qui est **commun à toutes** : la forme de la
réponse, les motifs d'inactivité, et l'ordre dans lequel on décide.

⚠️ Il ne devine jamais le code du modèle d'e-mail : l'appelant le passe, comme il
le passe à `send_email`. Une entité qui se tromperait de gabarit se tromperait
des deux côtés — donc l'aperçu montrerait exactement l'erreur qui partira, ce qui
est le comportement voulu.

## Ce qu'il ne peut pas savoir, et qu'il DIT

L'aperçu est demandé **avant** que l'objet existe. Les champs attribués plus tard
— numéro, lien permanent — sont nommés dans `attribues_a_la_creation` plutôt
qu'inventés.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel
from sqlmodel import Session, select

from app.models.core import ModeleEmail


class ApercuCanal(BaseModel):
    """Un canal, tel qu'il partira — ou la raison pour laquelle il ne partira pas."""

    canal: str  # 'email' | 'whatsapp'
    actif: bool
    #  🔴 `inactif_motif` est ce qui distingue cet aperçu d'une maquette : si le
    #  bridge est éteint ou qu'aucun destinataire n'est joignable, l'écran doit le
    #  dire AVANT l'envoi, pas laisser croire à une diffusion qui n'aura pas lieu.
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


def roles_diffusion():
    """Les rôles autorisés à diffuser sur le groupe.

    Lus par `has_role`, jamais comparés à une chaîne (`standards/03` §1, et
    l'audit du 26/07/2026 qui avait trouvé deux comparaisons littérales).
    """
    from app.models.core import RoleUtilisateur

    return (RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)


def apercu_email(
    session: Session,
    *,
    code_modele: str,
    contexte: dict[str, Any],
    destinataires: list[tuple[int | None, str]],
    pieces_jointes: Optional[list[str]] = None,
    copie_auteur: Optional[str] = None,
) -> ApercuCanal:
    """L'e-mail tel qu'il sera composé — ou pourquoi il ne partira pas.

    ⚠️ Les deux causes d'inactivité sont vérifiées dans cet ordre, et il compte :
    sans destinataire, le gabarit n'a aucune importance. Annoncer « modèle
    inactif » à quelqu'un dont le vrai problème est l'absence d'adresse
    l'enverrait corriger la mauvaise chose.
    """
    if not destinataires:
        return ApercuCanal(
            canal="email",
            actif=False,
            inactif_motif="Aucun destinataire joignable : le syndic ou le conseil "
            "syndical n'a pas d'adresse renseignée.",
        )

    modele = session.exec(select(ModeleEmail).where(ModeleEmail.code == code_modele)).first()
    if not modele or not modele.actif:
        return ApercuCanal(
            canal="email",
            actif=False,
            inactif_motif=f"Le modèle d'e-mail « {code_modele} » est inactif ou absent.",
        )

    #  🔴 Les DEUX fonctions de l'envoi, et rien d'autre. `_contexte_rendu` ajoute
    #  le nom du site, son URL et le pied — un aperçu qui les reconstruirait
    #  divergerait au premier changement de configuration.
    from app.utils.email import _contexte_rendu, composer_email

    ctx, site_nom, site_url, footer = _contexte_rendu(session, contexte)
    sujet, html = composer_email(
        modele,
        ctx,
        site_nom=site_nom,
        site_url=site_url,
        email_footer=footer,
        attachments=pieces_jointes or None,
    )
    #  🔴 La copie à l'auteur est ANNONCÉE, pas seulement envoyée. Un aperçu qui
    #  tairait un destinataire montrerait moins que ce qui part — et c'est
    #  exactement ce qu'on reproche à un envoi implicite (31/08/2026).
    #
    #  ⚠️ Nommée « (copie) » : elle part en copie CACHÉE, donc les autres
    #  destinataires ne la verront pas. L'auteur, lui, doit savoir qu'il l'a
    #  demandée.
    adresses = [e for _, e in destinataires]
    if copie_auteur and copie_auteur.lower() not in {e.lower() for e in adresses}:
        adresses.append(f"{copie_auteur} (copie)")

    return ApercuCanal(
        canal="email",
        actif=True,
        destinataires=adresses,
        sujet=sujet,
        corps_html=html,
    )


def apercu_whatsapp(
    session: Session,
    auteur,
    *,
    titre: str,
    contenu: str,
    urgent: bool = False,
    perimetre: Optional[str] = None,
    photo: Optional[str] = None,
) -> ApercuCanal:
    """Le message du groupe tel qu'il sera composé — ou pourquoi il ne partira pas.

    ⚠️ Ce que l'aperçu montre est *le message tel qu'il sera composé*, pas *ce que
    le groupe recevra à coup sûr* : si une photo existe mais que son encodage pour
    le bridge échoue, le message reçoit en plus « 📷 Photos à voir sur le site ».
    Cela se décide à l'envoi. La nuance est petite et réelle.
    """
    from app.utils.whatsapp import (
        config_whatsapp,
        construire_message,
        message_sans_contenu,
        whatsapp_actif,
    )

    if not auteur.has_role(*roles_diffusion()):
        return ApercuCanal(
            canal="whatsapp",
            actif=False,
            inactif_motif="Le partage sur le groupe est réservé au conseil syndical.",
        )
    cfg = config_whatsapp(session)
    if not whatsapp_actif(cfg):
        return ApercuCanal(
            canal="whatsapp",
            actif=False,
            inactif_motif="Le groupe WhatsApp n'est pas connecté : rien ne partira.",
        )

    texte = construire_message(titre, contenu, urgent, perimetre, cfg)
    ampute = message_sans_contenu(None, False)
    return ApercuCanal(
        canal="whatsapp",
        actif=True,
        destinataires=["Groupe de la copropriété"],
        texte=texte,
        ampute=ampute,
        #  La photo ne part QU'AVEC le message complet — même règle que l'envoi :
        #  sur un message amputé, l'image dirait au groupe ce que le texte
        #  s'abstient de dire.
        avec_photo=bool(photo) and not ampute,
    )
