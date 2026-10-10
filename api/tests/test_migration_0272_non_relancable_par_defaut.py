"""La 0272 pose un défaut sur `ticket.non_relancable` (#1797).

Exécutée pour de vrai par le contexte d'Alembic, sur une base qui porte la
colonne telle que `create_all` la pose — `NOT NULL`, sans défaut —, puis sur une
base migrée par la 0104, qui en porte déjà un. Sous `TESTS_BASE_URL`, la même
chose sur PostgreSQL : c'est le cas de la production.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration


def _jouer(moteur) -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            charger_migration("0272_non_relancable_par_defaut").upgrade()


def _moteur(defaut: str = ""):
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE ticket (id INTEGER PRIMARY KEY, titre VARCHAR NOT NULL, "
                f"non_relancable BOOLEAN NOT NULL {defaut})"
            )
        )
    return m


def _inserer_sans_la_colonne(moteur) -> bool:
    """Ce que fait l'application dès que le modèle ne déclare plus la colonne."""
    with moteur.begin() as conn:
        conn.execute(text("INSERT INTO ticket (id, titre) VALUES (1, 'Fuite')"))
        return conn.execute(text("SELECT non_relancable FROM ticket")).scalar()


def test_sans_defaut_l_insertion_echoue_donc_le_test_mesure_quelque_chose():
    """Le cas fautif : la base née de `create_all`, avant la migration."""
    moteur = _moteur()
    try:
        _inserer_sans_la_colonne(moteur)
    except Exception:  # noqa: BLE001 — l'erreur du moteur, quel qu'il soit
        return
    raise AssertionError("une colonne NOT NULL sans défaut a accepté une ligne sans valeur")


def test_le_defaut_est_pose_et_la_migration_rejouable():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    assert not _inserer_sans_la_colonne(moteur), "le défaut vaut « relançable »"


def test_une_base_qui_porte_deja_un_defaut_n_est_pas_touchee():
    moteur = _moteur("DEFAULT FALSE")
    _jouer(moteur)
    assert not _inserer_sans_la_colonne(moteur)
