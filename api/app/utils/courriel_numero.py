"""« Vouliez-vous TK-E00066 ? » — l'aide donnée à un numéro d'affaire mal tapé.

## Pourquoi (05/10/2026)

Un transfert a été refusé : l'objet portait `TK-E000066`, l'affaire est
`TK-E00066`. Le refus était juste — et le message qu'il laissait, « l'affaire
TK-E000066 n'existe pas », laissait chercher l'erreur à l'œil.

## Ce que ça ne fait PAS

Jamais de rattachement automatique : un message versé dans la mauvaise affaire
est pire qu'un message refusé. La proposition s'écrit dans le MOTIF, le conseil
retransfère avec le bon numéro.

Une proposition n'est faite que s'il n'y en a **qu'une** : à égalité, deviner
serait tirer au sort.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.core import Ticket


def a_une_faute_pres(a: str, b: str) -> bool:
    """Vrai si `a` et `b` (déjà en minuscules) diffèrent d'UN seul caractère —
    ajouté, retiré ou remplacé. Deux chaînes égales ne sont pas « voisines ».

    >>> a_une_faute_pres("tk-e000066", "tk-e00066")
    True
    >>> a_une_faute_pres("tk-e00066", "tk-e00067")
    True
    >>> a_une_faute_pres("tk-e00066", "tk-e00066")
    False
    >>> a_une_faute_pres("tk-e00066", "tk-e00099")
    False
    """
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    court, long = (a, b) if len(a) < len(b) else (b, a)
    i = 0
    while i < len(court) and court[i] == long[i]:
        i += 1
    return court[i:] == long[i + 1 :]


def voisins(numero: str, existants: list[str]) -> list[str]:
    """Les numéros existants à une faute de frappe de `numero`."""
    cible = numero.lower()
    return [n for n in existants if a_une_faute_pres(cible, n.lower())]


def aide_au_numero(session: Session, numero: str) -> str:
    """La phrase à ajouter à « n'existe pas » — vide s'il n'y a pas UN seul candidat."""
    existants = list(session.exec(select(Ticket.numero)).all())
    trouves = voisins(numero, existants)
    return f" — vouliez-vous {trouves[0]} ?" if len(trouves) == 1 else ""
