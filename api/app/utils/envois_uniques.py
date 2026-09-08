"""**Un fait, un courriel par personne** — la déduplication ENTRE deux envois (#850).

## La consigne, et le défaut qu'elle nomme

Philippe, le 08/09/2026, en recevant deux fois « 🎫 Nouveau ticket » :

> *« Pour les notifications par mail : éviter le doublon quand la notification
> comprend les destinataires qui sont inclus dans la diffusion du ticket ou de
> l'actualité. Ce point est important pour éviter de recevoir deux fois le même
> mail. »*

À la création d'un ticket, **deux** envois partent, décidés à deux endroits qui
ne se connaissent pas :

=========================  =====================  ===============================
Envoi                      Destinataires          Décidé par
=========================  =====================  ===============================
``ticket_nouveau_cs``      CS du **périmètre**    automatique, toujours
``ticket_syndic``          syndic + CS            la case « diffuser au CS »
=========================  =====================  ===============================

Un conseiller rattaché au bâtiment visé, sur un ticket dont l'auteur a coché
« CS », est dans **les deux listes**.

## 🔴 Pourquoi aucun contrôle ne pouvait le voir

Les deux envois sont **chacun corrects**. Chaque fonction a la bonne liste, la
bonne portée, la bonne préférence — et une docstring qui explique pourquoi. Ce
qui manque n'est dans **aucune des deux** : c'est leur **intersection**, et
personne ne lit deux fonctions à la fois.

La déduplication par adresse existait déjà — `membres_cs_notifiables` dédoublonne
sa propre liste, `copie_auteur` retire l'auteur des destinataires du groupe. Elle
s'appliquait **à l'intérieur** d'un envoi. Ce module la fait **entre** deux.

## Qui gagne le doublon : LE PLUS DISANT

Ce n'est pas un choix de commodité. Entre deux messages qui parlent du même fait,
on garde celui qui porte **le plus d'information**, et l'autre cède :

* ``ticket_syndic`` porte l'adresse de réponse à jeton, les pièces jointes et
  l'historique — ``ticket_nouveau_cs`` ne porte que le titre et l'auteur ;
* ``ticket_bug_admin`` nomme le bogue et le gestionnaire du site à qui il revient
  — plus précis que « nouveau ticket » ;
* ``annonce_hall`` porte le **PDF à imprimer** — la publication ne porte qu'un
  lien.

C'est `standards/02` §4 bis : entre deux implémentations, on retient la plus
disante, jamais un compromis. Ici la « plus disante » n'est pas une
implémentation mais un message, et la règle vaut de la même façon.

⚠️ **La conséquence est que l'ordre d'exécution compte.** L'envoi qui cède doit
être calculé APRÈS celui qui gagne, ou recevoir ses adresses. C'est le seul point
délicat de ce module, et c'est pourquoi les appelants passent explicitement
`deja_servies` plutôt que de compter sur un état partagé.

## Ce que ce module NE fait pas

Les notifications **dans l'application** ne sont pas concernées : elles ont
volontairement une portée plus large que les courriels — *« ce qui est tolérable
dans une liste qu'on parcourt ne l'est pas dans une boîte aux lettres »*
(`tickets/courriels.py`). Deux notifications in-app pour le même fait sont deux
lignes dans une liste ; deux courriels sont deux dérangements.
"""
from __future__ import annotations

from typing import Iterable, Optional

#: Un destinataire tel que le portent `send_email_group` et ses appelants.
Destinataire = tuple[Optional[int], str]


def normaliser(adresse: Optional[str]) -> str:
    """La forme sur laquelle deux adresses se comparent.

    ⚠️ Minuscules et espaces retirés, **et rien de plus**. Pas de retrait des
    points ni de la partie après `+` : `jean.dupont@` et `jeandupont@` sont deux
    adresses distinctes pour la plupart des serveurs, et les « normaliser »
    ensemble supprimerait un destinataire légitime. Une déduplication trop zélée
    fait disparaître du courrier — c'est le mauvais côté de l'erreur.
    """
    return (adresse or "").strip().lower()


def adresses(destinataires: Iterable[Destinataire]) -> set[str]:
    """Les adresses normalisées d'une liste de destinataires."""
    return {normaliser(email) for _, email in destinataires if normaliser(email)}


def sans_les_deja_servies(
    destinataires: Iterable[Destinataire], deja_servies: Iterable[str]
) -> list[Destinataire]:
    """La liste, privée de ceux qui ont déjà reçu un courriel pour le même fait.

    L'ordre d'origine est conservé : il porte une décision ailleurs (`syndic_puis`
    fait passer le syndic en premier pour qu'il gagne le doublon interne, #480).

    ⚠️ Rendre une liste **vide** est un résultat normal, pas une erreur : cela
    signifie que tout le monde a déjà été servi par l'envoi le plus disant.
    L'appelant doit alors ne rien envoyer — pas envoyer à personne, ce qui
    laisserait une trace d'envoi sans destinataire dans `historique_email`.
    """
    servies = {normaliser(a) for a in deja_servies if normaliser(a)}
    return [
        (uid, email)
        for uid, email in destinataires
        if normaliser(email) not in servies
    ]


__all__ = ["Destinataire", "adresses", "normaliser", "sans_les_deja_servies"]
