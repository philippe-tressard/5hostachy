"""La 0275 retire les colonnes de « non relançable » sans toucher à une affaire (#1797).

Exécutée pour de vrai par le contexte d'Alembic, sur une base au schéma d'AVANT :
une table `ticket` qui porte encore les deux colonnes, et des affaires dont l'une
était marquée. Sous `TESTS_BASE_URL`, la même chose sur PostgreSQL — le moteur de
la production.

`start.sh` lance `alembic upgrade head` sous `set -e` : les colonnes PARTENT, les
lignes RESTENT, et la rejouer ne casse rien.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

_MIGRATION = "0275_ticket_sans_non_relancable"
_COLONNES = {"non_relancable", "non_relancable_motif"}


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration(_MIGRATION), sens)()


def _moteur():
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE ticket (id INTEGER PRIMARY KEY, titre VARCHAR NOT NULL, "
                "non_relancable BOOLEAN NOT NULL DEFAULT FALSE, non_relancable_motif TEXT)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO ticket (id, titre, non_relancable, non_relancable_motif) "
                "VALUES (1, 'Fuite', TRUE, 'dossier au tribunal'), (2, 'Porte', FALSE, NULL)"
            )
        )
    return m


def _colonnes(moteur) -> set[str]:
    with moteur.connect() as conn:
        return {c["name"] for c in inspect(conn).get_columns("ticket")}


def _titres(moteur) -> list[str]:
    with moteur.connect() as conn:
        return list(conn.execute(text("SELECT titre FROM ticket ORDER BY id")).scalars())


def test_les_colonnes_partent_et_les_affaires_restent():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    assert not (_COLONNES & _colonnes(moteur))
    assert _titres(moteur) == ["Fuite", "Porte"]


def test_le_retour_arriere_rend_les_colonnes_avec_leur_defaut():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _COLONNES <= _colonnes(moteur)
    with moteur.begin() as conn:
        conn.execute(text("INSERT INTO ticket (id, titre) VALUES (3, 'Ascenseur')"))
        assert conn.execute(text("SELECT non_relancable FROM ticket WHERE id = 3")).scalar() in (
            False,
            0,
        )
