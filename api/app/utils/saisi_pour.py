"""« SAISI POUR » — au nom de qui un objet est déposé, et comment ça s'affiche.

## La notion

Un membre du conseil syndical dépose parfois **au nom de quelqu'un d'autre** :
un résident qui a appelé, un voisin sans compte, une personne extérieure. Trois
colonnes portent cette information, et elles voyagent toujours ensemble :

| | |
|---|---|
| `saisi_pour_user_id` | un résident INSCRIT — c'est lui qui gagne le droit de corriger |
| `saisi_pour_nom` | une personne extérieure, dont on n'a que le nom |
| `saisi_pour_email` | son adresse, quand on la connaît |

Portée par `Ticket` depuis l'origine, par `Publication` et `Evenement` depuis le
15/09/2026.

## 🔴 Pourquoi ce module existe

Le libellé affiché — *« lequel de ces trois champs montre-t-on, et sous quelle
forme ? »* — était sur le point d'être écrit une **troisième** fois. Les tickets
le composaient chez eux ; les actualités et le calendrier allaient le recopier.

Trois écritures d'une même règle divergent au premier ajout : c'est le motif que
ce dépôt connaît le mieux (les destinataires CS en ont compté **quatre**, dont
un qui affirmait être le seul). La règle monte donc d'un cran avant la copie,
pas après.

## ⚠️ Ce que ce module ne fait PAS

**Il ne décide pas des droits.** `auth/deps.py::est_auteur` lit
`saisi_pour_user_id` par `getattr`, sur n'importe quel objet qui en porte un :
poser la colonne suffit à ce que la personne nommée puisse corriger ce qui parle
d'elle. C'est voulu (`ux-patterns` §15), c'est écrit là-bas, et le redire ici en
ferait une seconde source de vérité.

**Il ne lit pas la PRÉSENCE d'un champ.** Effacer « Saisi pour » — revenir à
« En mon nom » — suppose que le serveur distingue *« champ absent »* de *« champ
remis à vide »*. Les trois routeurs concernés le font déjà, chacun par son
chemin : `exclude_unset=True` pour les actualités et le calendrier,
`model_fields_set` pour les tickets (`tickets/correction.py::_envoye`, dont la
forme est imposée par un `PATCH` qui n'affecte pas en boucle). Deux mécaniques,
une seule règle — et aucune n'avait besoin d'être déplacée.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from app.models.core import Utilisateur
from app.utils.noms import nom_affiche

#: Les trois colonnes, dans l'ordre. Écrites une fois : un routeur qui n'en
#: réécrirait que deux laisserait le nom d'un ancien destinataire survivre au
#: résident inscrit désigné depuis.
CHAMPS = ("saisi_pour_user_id", "saisi_pour_nom", "saisi_pour_email")


def affichage(session: Session, objet) -> Optional[str]:
    """Le nom à montrer, ou `None` quand l'objet est déposé en son nom propre.

    ⚠️ **`None` et non chaîne vide** : l'écran teste la présence pour décider
    d'afficher la mention. Une chaîne vide est *présente* — elle afficherait
    « Saisi pour » suivi de rien.

    Le résident inscrit prime sur le nom libre : quand les deux sont posés, c'est
    le compte qui fait foi, puisque c'est lui qui porte le droit de correction.
    """
    uid = getattr(objet, "saisi_pour_user_id", None)
    if uid:
        personne = session.get(Utilisateur, uid)
        if personne:
            return nom_affiche(personne.prenom, personne.nom)
    nom = (getattr(objet, "saisi_pour_nom", None) or "").strip()
    return nom or None
