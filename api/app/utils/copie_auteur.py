"""À QUI part la copie demandée par la case « Envoyer une copie à … ».

## La règle, arbitrée à l'écran le 31/08/2026

> *« pour éviter l'ambiguïté, c'est bien le propriétaire du ticket, pas celui
> qui fait un commentaire sur le ticket »*

La copie va à **l'auteur de l'OBJET** — le ticket, l'actualité, l'événement — et
jamais à l'auteur du *message* qu'on est en train d'écrire. À la création les
deux coïncident ; ils divergent dès qu'un tiers commente, ce qui est le cas
courant : le conseil syndical reprend un ticket, et c'est le résident qui l'a
signalé qui doit rester informé.

⚠️ **Une première version faisait l'inverse**, et la journée a produit les trois
états successifs qu'il faut connaître pour ne pas y revenir :

1. copie **implicite** à celui qui écrit — le formulaire annonçait trois
   destinataires et en servait quatre ;
2. copie **sur demande** à celui qui écrit — honnête, mais le libellé
   « M'envoyer une copie » ne disait pas qui « m' » désignait, et sur un ticket
   repris par le CS il ne désignait plus la bonne personne ;
3. copie **sur demande à l'auteur de l'objet**, nommé dans le libellé. C'est
   l'état actuel, et c'est le seul où l'écran dit ce que le serveur fait.

## Pourquoi une fonction et pas trois blocs

Elle sert les tickets, les publications et le calendrier. Le bloc a déjà existé
en trois exemplaires : celui des publications faisait un envoi implicite, celui
des tickets un envoi sur demande, et le calendrier n'en faisait aucun — trois
comportements pour une seule case, sur les mêmes écrans.

⚠️ La **déduplication** ne se déduit pas du rôle mais des **adresses réellement
retenues** : un auteur qui est aussi membre du CS ne doit pas recevoir deux
fois. C'est le même fait, dit par ce qui compte.
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlmodel import Session

from app.models.core import Utilisateur


def email_auteur(session: Session, auteur_id: Optional[int]) -> Optional[str]:
    """L'adresse de l'auteur d'un objet, ou `None` s'il n'en a pas d'utilisable.

    Un auteur supprimé, désactivé ou sans adresse ne fait pas échouer l'envoi :
    la copie est simplement impossible, et l'envoi principal doit avoir lieu.
    """
    if not auteur_id:
        return None
    auteur = session.get(Utilisateur, auteur_id)
    if not auteur or not auteur.email:
        return None
    return auteur.email


def copie_demandee(
    session: Session,
    auteur_id: Optional[int],
    deja_servies: Iterable[str],
    *,
    demandee: bool,
) -> Optional[list[str]]:
    """La liste `bcc` à passer à l'envoi — `None` quand il n'y a rien à copier.

    `deja_servies` est l'ensemble des adresses que l'envoi principal touche
    déjà : la copie n'est ajoutée que si l'auteur n'y figure pas.

    ⚠️ Rend `None` et non `[]` : c'est ce que les fonctions d'envoi attendent
    pour « pas de copie cachée », et une liste vide y produirait un en-tête
    `Bcc:` vide chez certains serveurs.
    """
    if not demandee:
        return None
    adresse = email_auteur(session, auteur_id)
    if not adresse:
        return None
    servies = {e.lower() for e in deja_servies if e}
    if adresse.lower() in servies:
        return None
    return [adresse]


def auteur_de(session: Session, modele, objet_id: Optional[int]) -> Optional[int]:
    """L'`auteur_id` d'un objet déjà enregistré, ou `None` s'il n'existe pas.

    Écrit ici et pas dans chaque aperçu : les trois entités posaient la même
    question, et trois `session.get` privés auraient divergé sur le cas de
    l'objet supprimé entre l'ouverture du formulaire et la demande d'aperçu.
    """
    if not objet_id:
        return None
    objet = session.get(modele, objet_id)
    return getattr(objet, "auteur_id", None) if objet else None


def adresse_copie(
    session: Session, auteur_id: Optional[int], redacteur: Utilisateur
) -> Optional[str]:
    """L'adresse que la case copierait — pour l'APERÇU, qui doit l'annoncer.

    ⚠️ Un aperçu se demande **avant** que l'objet existe. À la création, l'auteur
    de l'objet sera donc le rédacteur lui-même ; à l'édition et sur une
    évolution, c'est l'auteur déjà enregistré. Les deux cas sont réels et le
    second est celui qui compte : c'est là que les deux personnes diffèrent.

    🔴 Ne pas remplacer par `email_auteur` seul : l'aperçu d'une création
    n'annoncerait alors aucune copie, et montrerait moins que ce qui part —
    exactement ce qu'on reproche à un envoi implicite.
    """
    return email_auteur(session, auteur_id) or (redacteur.email or None)
