"""Le ticket qui SUIT les démarches d'un emménagement (#821).

## 🔴 Pourquoi il existe

Signalé le 07/09/2026, cas concret à l'appui :

> *« Un nouvel arrivant : cocher "Nouvel arrivant" ne devrait-il pas créer un
> ticket pour son suivi ? J'ai l'exemple concret où le syndic n'a rien fait
> depuis deux semaines et le locataire a créé lui-même un ticket. »*

Le parcours d'accueil envoyait **une notification in-app au conseil** (ajout sur
l'interphone) et **un e-mail au syndic** (étiquette de boîte aux lettres). Et
rien d'autre :

* la notification se lit une fois puis quitte la pile ;
* l'e-mail tombe dans une boîte, sans suivi ;
* **le résident n'a aucune trace** — il lit « Démarches initiées en votre nom »
  dans sa notification de bienvenue, et n'entend plus jamais parler de rien ;
* **personne ne voit que ça traîne**, ni au bout d'une semaine ni au bout de
  deux.

C'est la règle du projet enfreinte à l'envers : *vérifier le comportement,
jamais l'artefact* (`standards/04` §14). Le message parti est l'artefact ; la
démarche faite est le fait. Rien ne mesurait le fait.

## Ce que le ticket apporte, que le message n'apportait pas

Un statut qui avance (Ouvert → En cours → Résolu), une place dans la liste du
conseil, la relance, et **la visibilité pour celui qui attend**.

⚠️ `saisi_pour_user_id` : le ticket est ouvert **au nom de** l'arrivant, par le
système. C'est ce qui le fait apparaître dans SES tickets — sans quoi on aurait
reproduit le défaut d'origine sous une autre forme, un objet de suivi que
l'intéressé ne voit pas.

## UN ticket, pas deux

Arbitré le 07/09/2026. Les deux démarches ont deux destinataires — le syndic
pour la boîte aux lettres, le conseil pour l'interphone — et l'on aurait pu en
faire deux tickets. Un seul a été retenu : deux lignes par arrivant encombrent
la liste, et c'est le **fil** qui porte l'avancement de chaque démarche. On clôt
quand les deux sont faites.

⚠️ Les notifications d'origine ne sont PAS supprimées. Elles préviennent ;
le ticket suit. Retirer l'alerte immédiate au profit d'une ligne dans une liste
aurait échangé un défaut contre un autre — c'est justement parce que personne ne
regarde une liste spontanément que l'alerte existe.
"""
from __future__ import annotations

from html import escape

from sqlmodel import Session, select

from app.models.core import Ticket, Utilisateur
from app.routers.tickets.commun import generer_numero

#: Le titre est stable et reconnaissable : c'est lui qui sert de garde contre le
#: doublon, et c'est lui que le conseil cherche dans sa liste.
TITRE = "Démarches d'emménagement"


def ticket_arrivant_existant(session: Session, user_id: int) -> Ticket | None:
    """Le ticket d'emménagement déjà ouvert pour cette personne, s'il y en a un.

    ⚠️ `accueil-arrivant` est rejouable par un membre du conseil
    (`allow_repeat=True`) : sans cette garde, relancer l'accueil de quelqu'un
    créerait un second ticket sans que rien ne le dise, et le premier resterait
    ouvert à côté.
    """
    return session.exec(
        select(Ticket).where(
            Ticket.saisi_pour_user_id == user_id,
            Ticket.titre == TITRE,
        )
    ).first()


def corps_demarches(nom_complet: str, batiment: str, ancien: str, demarches: list[str]) -> str:
    """La description du ticket — les démarches attendues, en toutes lettres.

    ⚠️ `escape` sur chaque valeur venue de l'utilisateur : le nom de l'ancien
    résident est saisi librement dans le formulaire d'accueil, et la description
    d'un ticket est rendue en HTML côté front.
    """
    lieu = f" ({escape(batiment)})" if batiment else ""
    precede = f"<p>Ancien résident : {escape(ancien)}.</p>" if ancien else ""
    items = "".join(f"<li>{escape(d.lstrip('• ').strip())}</li>" for d in demarches)
    return (
        f"<p><strong>{escape(nom_complet)}</strong> vient d'emménager{lieu}.</p>"
        + precede
        + (f"<p>Démarches à effectuer :</p><ul>{items}</ul>" if items else "")
        + "<p>Ce ticket suit ces démarches jusqu'à leur réalisation. "
        "Répondez-y pour dire ce qui est fait ; fermez-le quand tout l'est.</p>"
    )


def creer_ticket_arrivant(
    session: Session,
    user: Utilisateur,
    *,
    nom_complet: str,
    batiment: str,
    ancien: str,
    demarches: list[str],
    vers_syndic: bool,
    vers_cs: bool,
) -> Ticket | None:
    """Ouvre le ticket de suivi. Rend `None` s'il existe déjà.

    ⚠️ Aucun `commit` ici : l'appelant en fait un seul à la fin de l'accueil.
    Committer au milieu laisserait un ticket derrière une démarche qui échoue
    ensuite — un objet de suivi pour quelque chose qui n'a pas eu lieu.
    """
    if ticket_arrivant_existant(session, user.id):
        return None

    ticket = Ticket(
        numero=generer_numero(),
        titre=TITRE,
        description=corps_demarches(nom_complet, batiment, ancien, demarches),
        categorie="acces_accueil",
        statut="ouvert",
        priorite="normale",
        #  🔴 L'AUTEUR est l'arrivant, et `saisi_pour` aussi. Le ticket est ouvert
        #  par le système en son nom : il doit le voir dans ses tickets, sinon on
        #  reproduit le défaut d'origine — un suivi que l'intéressé ne voit pas.
        auteur_id=user.id,
        saisi_pour_user_id=user.id,
        saisi_pour_nom=nom_complet,
        saisi_pour_email=user.email,
        batiment_id=user.batiment_id,
        perimetre_cible='["résidence"]',
        #  Les deux démarches ont deux destinataires : le syndic pose l'étiquette
        #  de boîte aux lettres, le conseil ajoute le nom sur l'interphone. Le
        #  ticket les vise tous les deux — c'est la raison d'en faire UN seul.
        destinataire_syndic=vers_syndic,
        destinataire_cs=vers_cs,
    )
    session.add(ticket)
    return ticket
