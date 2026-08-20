"""Retirer une entrée d'un fil de suivi — **le geste, écrit une seule fois** (#512).

## Pourquoi ce module

Trois objets du site portent un fil d'évolutions : le **ticket**
(`TicketEvolution`), l'**actualité** (`PublicationEvolution`) et l'**événement**
(`EvenementEvolution`). Le geste de suppression n'existait que pour le premier.

Le recopier deux fois aurait été le réflexe évident — et exactement la faute que
`standards/02` interdit. Ce n'est pas une question de lignes : les trois copies
auraient porté chacune leur liste de types effaçables et leur message d'erreur,
et la première divergence serait passée inaperçue, parce qu'un administrateur ne
compare pas le refus d'un écran à celui d'un autre.

⚠️ Le ticket #512 le disait déjà : *« les nouveaux endpoints doivent dire **la
même chose** que lui, ni plus ni moins »*. La seule façon de le garantir est
qu'ils appellent le même code.

## Les deux arbitrages, tranchés le 18/08/2026 et NON rouverts

**Qui** — `require_admin`, jamais `require_cs_or_admin`. Corriger sa propre
entrée (`PATCH`) est un geste ordinaire ; **effacer** fait disparaître une trace
que d'autres ont pu lire et sur laquelle ils ont pu agir. C'est la frontière de
« archiver n'est pas supprimer » : l'irréversible reste à l'administrateur. La
dépendance est posée par chaque endpoint, pas ici — c'est le routeur qui déclare
qui il laisse entrer.

**Quoi** — `commentaire` et `etat` seulement. Une **réponse** appartient à son
auteur, souvent un résident : l'effacer supprimerait la parole de quelqu'un
d'autre, ce qui n'est pas la même chose que retirer une ligne écrite par le
système ou par soi-même.

⚠️ Supprimer une entrée d'état **ne change pas** le statut de l'objet : celui-ci
vit dans sa propre colonne, le fil n'en est que le récit. Le coût est une perte
de traçabilité — on ne saura plus quand l'objet est passé « En cours » —, pas une
incohérence de données. C'est un coût réel : le fil sert de preuve au conseil
syndical face au syndic, et une transition effacée ne se retrouve pas.
"""
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

#: Les types d'entrée qu'un administrateur peut retirer.
#:
#: ⚠️ Le front en tient le pendant dans `RubriqueHistorique.svelte`
#: (`TYPES_EFFACABLES`) : les contextes de build sont `./api` et `./front`, rien
#: de la racine n'entre dans les images — seule la copie est possible. Le test
#: `test_evolutions_suppression.py` échoue si les deux listes divergent.
TYPES_EFFACABLES: tuple[str, ...] = ("commentaire", "etat")

#: Un seul message pour les trois fils. Deux formulations différentes pour le
#: même refus laisseraient croire à deux règles différentes.
REFUS_TYPE = "Cette entrée ne peut pas être supprimée : une réponse appartient à son auteur."


def supprimer_evolution(
    session: Session,
    modele: type,
    evol_id: int,
    *,
    champ_parent: str,
    parent_id: int,
) -> None:
    """Retire une entrée de fil, ou lève l'exception qui explique pourquoi non.

    `champ_parent` est le nom de la clé étrangère (`ticket_id`,
    `publication_id`, `evenement_id`) : c'est la seule chose qui distingue les
    trois fils. La vérifier n'est pas une formalité — sans elle, un identifiant
    d'entrée valide permettrait d'effacer l'entrée d'un AUTRE objet que celui
    dont on a l'adresse, et le contrôle d'accès de l'URL ne servirait à rien.
    """
    evol: Any = session.get(modele, evol_id)
    if not evol or getattr(evol, champ_parent, None) != parent_id:
        raise HTTPException(404, "Entrée introuvable")
    if getattr(evol, "type", None) not in TYPES_EFFACABLES:
        raise HTTPException(422, REFUS_TYPE)
    session.delete(evol)
    session.commit()
