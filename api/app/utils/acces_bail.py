"""Les badges qu'un bail fait passer du bailleur au locataire — écrit une fois (#1194).

## Un seul sens de « chez le locataire »

Jusqu'au 23/09/2026, la même case disait deux choses opposées :

| Chemin | `chez_locataire` | `user_id` (en main) |
|---|---|---|
| l'import du syndic | vrai | le **locataire** |
| la remise par le bail | vrai | le **bailleur** — resté tel quel |

Elle ne dit plus qu'une chose : **le badge est chez le locataire du lot**, et
`user_id` est celui qui l'a en main — le locataire du bail, ou personne de
connu s'il n'a pas de compte. Ses porteurs, eux, se lisent sur le lot
(`utils/porteurs_acces`) : le bailleur ne perd pas de vue ce qu'il a confié.

## 🔴 Ce que ce module remplace

Le retour au bailleur était écrit **deux fois** — à la récupération et à la fin
du bail —, chacune en deux jumeaux vigik/télécommande, et toutes quatre filtraient
sur `user_id == bailleur` : un badge remis par l'import, dont le détenteur était
le locataire, ne revenait jamais.
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from app.utils.types_acces import TYPES_ACCES


def confies(session: Session, bail_id: int) -> list[tuple[str, object]]:
    """Les badges confiés au locataire par CE bail, avec la clé de leur type."""
    return [
        (t.cle, o)
        for t in TYPES_ACCES.values()
        for o in session.exec(
            select(t.modele).where(
                t.modele.bail_id == bail_id,
                t.modele.chez_locataire == True,  # noqa: E712
            )
        ).all()
    ]


def remettre(objet, bail) -> None:
    """Le bailleur remet ce badge au locataire du bail."""
    objet.chez_locataire = True
    objet.bail_id = bail.id
    objet.user_id = bail.locataire_id


def rendre_au_bailleur(
    session: Session,
    bail,
    choix: Optional[dict[str, list[int]]] = None,
) -> list[tuple[str, object]]:
    """Les badges du bail reviennent au bailleur — tous, ou ceux de `choix`.

    `choix` : `{clé du type: identifiants}` ; un type absent n'en rend aucun.
    Sans `commit` : l'appelant décide de sa transaction.
    """
    rendus = []
    for t in TYPES_ACCES.values():
        q = select(t.modele).where(t.modele.bail_id == bail.id)
        if choix is not None:
            q = q.where(t.modele.id.in_(choix.get(t.cle) or [-1]))  # type: ignore[attr-defined]
        for o in session.exec(q).all():
            o.chez_locataire = False
            o.bail_id = None
            o.user_id = bail.bailleur_id
            session.add(o)
            rendus.append((t.cle, o))
    return rendus


__all__ = ["confies", "remettre", "rendre_au_bailleur"]
