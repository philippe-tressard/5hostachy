"""La 0268 renomme la rubrique « logiciel » de la FAQ comme le seed la nomme (#1725).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.seed.faq import CATEGORIE_APPLICATION
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

MIGRATION = charger_migration("0268_faq_categorie_application")


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(MIGRATION, sens)()


def _moteur(categories: list[str]):
    m = moteur_memoire()
    with m.begin() as conn:
        for ordre, categorie in enumerate(categories):
            conn.execute(
                text(
                    "INSERT INTO faq_item (categorie, question, reponse, ordre, actif, "
                    "cree_le, mis_a_jour_le) VALUES (:c, :q, 'r', :o, 1, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"c": categorie, "q": f"question {ordre}", "o": ordre},
            )
    return m


def _categories(moteur) -> list[str]:
    with moteur.connect() as conn:
        return [c for (c,) in conn.execute(text("SELECT categorie FROM faq_item ORDER BY ordre"))]


def test_la_nouvelle_rubrique_est_celle_du_seed():
    """Une base neuve et une base migrée rangent les questions au même endroit."""
    assert MIGRATION.NOUVELLE == CATEGORIE_APPLICATION


def test_seule_l_ancienne_rubrique_est_renommee_une_seule_fois():
    moteur = _moteur([MIGRATION.ANCIENNE, "Tri des déchets", MIGRATION.ANCIENNE])
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    assert _categories(moteur) == [
        CATEGORIE_APPLICATION,
        "Tri des déchets",
        CATEGORIE_APPLICATION,
    ]


def test_le_retour_arriere_remet_l_ancien_nom():
    moteur = _moteur([MIGRATION.ANCIENNE])
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _categories(moteur) == [MIGRATION.ANCIENNE]
