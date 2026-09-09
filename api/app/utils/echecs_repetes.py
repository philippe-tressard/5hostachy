"""Passager ou persistant : le niveau d'alerte d'un échec qui se répète (#858).

## Le défaut que ce module corrige

Une relève IMAP a échoué une fois, le 09/09/2026 à 10:20, sur un
`[UNAVAILABLE] Account is temporarily unavailable` du fournisseur de messagerie.
Le cycle suivant, dix minutes plus tard, a réussi. Rien n'était perdu : la boîte
n'est pas touchée quand la connexion échoue, et les messages sont relus.

Mais l'échec était journalisé en `ERROR` **dès la première occurrence**. Il a donc
fait échouer le point 6 du pré-check pendant une heure et aurait déclenché
l'alerte quotidienne — sur un système parfaitement sain, pour une secousse déjà
résolue au moment où on la lit.

🔴 **La bonne règle était déjà écrite, dans le fichier même qui l'enfreignait** :

> *« un message qui échouerait indéfiniment se signale au lieu de tourner en
> silence. Une erreur qui se répète est un appel, pas du bruit. »*

Écrite, et pas appliquée : rien ne distinguait le passager du persistant. C'est
`standards/04` §18 — un seuil se règle sur le **régime** de ce qu'on surveille —
et §7 : une alerte qui crie sur du normal finit ignorée, et c'est ainsi qu'un
contrôle meurt.

## Ce que ce module n'est pas

Ce n'est pas une temporisation ni une politique de reprise : rien n'est réessayé
ici, et le geste qui a échoué a déjà échoué. C'est **le niveau auquel on en
parle**, et lui seul.

## L'état vit en mémoire du PROCESS, délibérément

Un compteur d'échecs consécutifs décrit la surveillance, pas la copropriété : il
n'a rien à faire en base. Un redémarrage a le droit de le remettre à zéro — après
un redémarrage, la première tentative est effectivement la première, et rien ne
prouve encore que la panne dure.

⚠️ Conséquence assumée : une panne qui traverse un redéploiement recommence son
décompte. Elle se signalera au bout de `SEUIL` cycles de plus, soit une demi-heure
sur une relève à dix minutes. C'est le prix d'un état qui ne ment pas sur ce qu'il
a réellement observé.
"""
from __future__ import annotations

import logging

#: Nombre d'échecs CONSÉCUTIFS à partir duquel on parle d'incident.
#:
#: Trois, sur une relève à dix minutes, veut dire « une demi-heure d'affilée ».
#: Une secousse du fournisseur ne réveille personne ; un compte fermé, un mot de
#: passe changé ou un IMAP coupé franchissent le seuil dans la demi-heure et se
#: signalent. Le seuil est réglé sur le régime de la panne qu'on cherche, pas sur
#: la fréquence du travail.
SEUIL = 3


def niveau(consecutifs: int, seuil: int = SEUIL) -> int:
    """Le niveau de journalisation pour le `consecutifs`-ième échec d'affilée.

    Fonction PURE : c'est la décision, et elle s'éprouve sans horloge, sans
    réseau et sans journal. `consecutifs` vaut 1 au premier échec.
    """
    if consecutifs <= 0:
        return logging.INFO
    return logging.ERROR if consecutifs >= seuil else logging.WARNING


class CompteurEchecs:
    """Combien d'échecs d'affilée, par tâche — en mémoire du process.

    Une instance par tâche surveillée, posée au niveau du module qui la porte :
    l'état est ainsi aussi visible que la tâche elle-même, et ne survit pas plus
    longtemps qu'elle.
    """

    def __init__(self, libelle: str, seuil: int = SEUIL):
        self.libelle = libelle
        self.seuil = seuil
        self.consecutifs = 0

    def succes(self) -> None:
        """Remet le décompte à zéro. À appeler à CHAQUE passage réussi.

        ⚠️ Oublier cet appel transforme un compteur d'échecs consécutifs en
        compteur d'échecs tout court : trois secousses en trois semaines
        finiraient par crier. C'est le seul défaut possible de ce module, et il
        est silencieux — d'où le test qui l'exige.
        """
        self.consecutifs = 0

    def echec(self, journal: logging.Logger, message: str, *args) -> int:
        """Journalise l'échec au bon niveau et rend le nombre d'échecs d'affilée.

        Le message est **complété** par le décompte : lire « 3ᵉ échec consécutif »
        dans un journal évite d'avoir à compter les lignes soi-même, et c'est
        cette information-là qui distingue l'incident de la secousse.
        """
        self.consecutifs += 1
        suffixe = f" (échec consécutif n°{self.consecutifs} pour « {self.libelle} »)"
        journal.log(niveau(self.consecutifs, self.seuil), message + suffixe, *args)
        return self.consecutifs


__all__ = ["SEUIL", "CompteurEchecs", "niveau"]
