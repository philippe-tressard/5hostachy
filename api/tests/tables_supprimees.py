"""Les tables qu'une migration ULTÉRIEURE a supprimées — lues dans ces migrations.

Des tests comparent la liste de tables d'une migration historique (0194 pour
`assiste_ia`, 0221 pour `public_cible`) aux modèles d'aujourd'hui. Une table
supprimée depuis y figure légitimement : la migration a été appliquée quand elle
existait, et une migration appliquée ne se modifie jamais.

La liste n'est pas recopiée ici : elle se lit dans la constante `TABLES` des
migrations de suppression. Une suppression future s'ajoute à `MIGRATIONS`.
"""

from __future__ import annotations

from tests.aides_migrations import charger_migration

#: Les migrations qui suppriment des tables, et leur constante `TABLES`.
MIGRATIONS = ("0238_*.py",)  # `publication`, `publication_evolution` (#1177)


def tables_supprimees() -> set[str]:
    tables: set[str] = set()
    for motif in MIGRATIONS:
        tables |= set(charger_migration(motif).TABLES)
    return tables
