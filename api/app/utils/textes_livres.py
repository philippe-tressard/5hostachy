"""Remplacer en base un texte LIVRÉ par le produit — seulement s'il est intact.

La FAQ et les modèles d'e-mail vivent en base : le seed ne pose que les
instances neuves, et le conseil syndical peut les reformuler. Corriger un texte
livré demande donc une migration, et elle ne doit toucher que ce que personne
n'a retouché — d'où la garde : on remplace si, et seulement si, chaque colonne
porte encore le texte d'avant.

## Pourquoi ici (24/09/2026)

`_remplacer` était recopié dans QUINZE migrations (0121 → 0203), chacune avec
sa requête SQL écrite à la main. Une migration appliquée ne se modifie jamais :
les quinze restent, figées — `test_migrations.py` refuse la seizième.

Le SQL est composé par SQLAlchemy, jamais par une chaîne : le nom de la table et
des colonnes vient de l'appelant, et une f-string SQL est refusée (Ruff S608).
"""

from __future__ import annotations

import sqlalchemy as sa


def remplacer_si_intact(conn, table: str, avant: dict[str, str], apres: dict[str, str]) -> int:
    """Pose `apres` sur les lignes qui portent EXACTEMENT `avant` ; rend leur nombre.

    Une ligne reformulée depuis n'est pas touchée — en silence, c'est le
    compromis : la migration ne sait pas mieux que le conseil ce qu'il a écrit.
    """
    colonnes = sorted(set(avant) | set(apres))
    t = sa.table(table, *(sa.column(c) for c in colonnes))
    requete = sa.update(t).where(sa.and_(*(t.c[c] == v for c, v in avant.items()))).values(**apres)
    return conn.execute(requete).rowcount or 0


def remplacer_passage(
    conn, table: str, cle: dict[str, str], colonne: str, avant: str, apres: str
) -> int:
    """Remplace un PASSAGE d'un texte long, s'il y figure tel quel ; rend 0 ou 1.

    Le cas que `remplacer_si_intact` ne couvre pas (#1073, 24/09/2026) : une
    phrase fausse au milieu d'un texte juridique dont la migration ne connaît
    pas — et ne doit pas recopier — le reste. Même garde, à l'échelle de la
    phrase : si elle a été reformulée depuis l'administration, rien ne change.
    """
    t = sa.table(table, *(sa.column(c) for c in sorted({*cle, colonne})))
    filtre = sa.and_(*(t.c[c] == v for c, v in cle.items()))
    actuel = conn.execute(sa.select(t.c[colonne]).where(filtre)).scalar()
    if not actuel or avant not in actuel:
        return 0
    conn.execute(sa.update(t).where(filtre).values({colonne: actuel.replace(avant, apres)}))
    return 1


__all__ = ["remplacer_si_intact", "remplacer_passage"]
