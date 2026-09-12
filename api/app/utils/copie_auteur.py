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
from app.utils.noms import nom_affiche


def proprietaire(session: Session, objet) -> tuple[Optional[str], Optional[str]]:
    """**À qui cet objet appartient-il ?** — son nom, et son adresse.

    ## Pourquoi ce n'est pas toujours l'auteur (12/09/2026)

    Un ticket porte un champ « Saisi pour » : le conseil syndical enregistre le
    signalement d'un résident qui a téléphoné, ou d'un intervenant extérieur.
    L'auteur est alors celui qui a *tapé*, et le propriétaire celui qui *a le
    problème*.

    Demandé à l'écran :

    > *« Pour un ticket dont le "Saisi pour" possède un résident inscrit ou une
    > personne extérieure, ce dernier se substitue à l'auteur. »*

    🔴 C'est le prolongement exact de l'arbitrage du 31/08 qui a créé ce module —
    *« c'est bien le propriétaire du ticket, pas celui qui fait un commentaire »*.
    La question était déjà la bonne ; la réponse s'arrêtait à l'auteur parce que
    rien d'autre n'existait alors.

    ## Trois cas, dans cet ordre

    1. **`saisi_pour_user_id`** — un résident INSCRIT : son nom et son adresse de
       compte, qui sont à jour et vérifiés.
    2. **`saisi_pour_nom` / `saisi_pour_email`** — une personne EXTÉRIEURE : ce
       que le rédacteur a saisi. L'adresse peut manquer ; le nom, non.
    3. **l'auteur** — le cas courant, et le seul que connaissent les publications,
       les événements et les annonces de hall.

    ⚠️ **Générique volontairement.** Les objets sans « Saisi pour » traversent
    cette fonction sans rien changer (`getattr` rend `None`), et gardent leur
    auteur. Écrire une variante pour les tickets aurait donné deux règles de
    copie, ce que ce module existe précisément pour empêcher.

    ⚠️ Le nom peut exister sans l'adresse — une personne extérieure dont on ne
    connaît que le nom. L'écran doit alors ANNONCER le bon nom et n'envoyer
    aucune copie : ce sont deux questions distinctes, et les confondre ferait
    soit taire le nom, soit promettre un envoi qui n'a pas lieu.
    """
    sp_id = getattr(objet, "saisi_pour_user_id", None)
    if sp_id:
        u = session.get(Utilisateur, sp_id)
        if u:
            return nom_affiche(u.prenom, u.nom), (u.email or None)
    sp_nom = getattr(objet, "saisi_pour_nom", None)
    if sp_nom:
        return sp_nom, (getattr(objet, "saisi_pour_email", None) or None)
    auteur_id = getattr(objet, "auteur_id", None)
    if auteur_id:
        a = session.get(Utilisateur, auteur_id)
        if a:
            return nom_affiche(a.prenom, a.nom), (a.email or None)
    return None, None


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
    objet,
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
    #  🔴 Le PROPRIÉTAIRE, pas l'auteur : sur un ticket « saisi pour » quelqu'un,
    #  c'est lui qui doit recevoir la copie (12/09/2026). Les autres objets n'ont
    #  pas ce champ et retombent sur leur auteur, sans condition écrite ici.
    _, adresse = proprietaire(session, objet)
    if not adresse:
        return None
    servies = {e.lower() for e in deja_servies if e}
    if adresse.lower() in servies:
        return None
    return [adresse]


def objet_de(session: Session, modele, objet_id: Optional[int]):
    """L'objet déjà enregistré, ou `None` s'il n'existe pas.

    🔴 Rendait l'`auteur_id` jusqu'au 12/09/2026. Elle rend l'objet depuis que la
    copie va au PROPRIÉTAIRE : un identifiant d'auteur ne peut pas porter un
    « Saisi pour », et le faire remonter aurait demandé un second appel — donc
    deux endroits où oublier la règle.

    Écrit ici et pas dans chaque aperçu : les trois entités posaient la même
    question, et trois `session.get` privés auraient divergé sur le cas de
    l'objet supprimé entre l'ouverture du formulaire et la demande d'aperçu.
    """
    if not objet_id:
        return None
    return session.get(modele, objet_id)


def adresse_copie(
    session: Session, objet, redacteur: Utilisateur
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
    return proprietaire(session, objet)[1] or (redacteur.email or None)
