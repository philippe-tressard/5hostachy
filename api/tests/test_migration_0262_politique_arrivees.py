"""La 0262 dit dans la politique servie que le lien d'une notification porte son canal (#1634).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui
porte la politique telle que la 0261 l'a laissée.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.seed.contenus_legaux import (
    TELEMETRIE_ARRIVEES,
    TELEMETRIE_GESTES,
    TELEMETRIE_PERFORMANCE,
)
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

POLITIQUE_0261 = (
    "<h2>2. Données collectées</h2><ul>"
    + TELEMETRIE_PERFORMANCE
    + TELEMETRIE_GESTES
    + "</ul><h2>3. Finalités et bases légales</h2>"
)


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration("0262_politique_arrivees"), sens)()


def _moteur(politique: str = POLITIQUE_0261):
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        conn.execute(text("CREATE TABLE config_site (cle VARCHAR PRIMARY KEY, valeur VARCHAR)"))
        conn.execute(
            text("INSERT INTO config_site (cle, valeur) VALUES ('politique_confidentialite', :v)"),
            {"v": politique},
        )
    return m


def _politique(moteur) -> str:
    with moteur.connect() as conn:
        return conn.execute(
            text("SELECT valeur FROM config_site WHERE cle = 'politique_confidentialite'")
        ).scalar()


def test_le_paragraphe_suit_celui_des_durees_une_seule_fois():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    texte = _politique(moteur)
    assert texte.count(TELEMETRIE_ARRIVEES) == 1
    #  L'ordre du gabarit : durées, arrivées, gestes.
    assert TELEMETRIE_PERFORMANCE + TELEMETRIE_ARRIVEES + TELEMETRIE_GESTES in texte


def test_un_texte_reformule_a_la_main_n_est_pas_touche():
    reformule = "<p>Notre politique, réécrite par l'administrateur.</p>"
    moteur = _moteur(reformule)
    _jouer(moteur)
    assert _politique(moteur) == reformule


def test_le_retour_arriere_retire_le_paragraphe():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _politique(moteur) == POLITIQUE_0261
