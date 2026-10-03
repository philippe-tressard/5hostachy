"""La 0253 nomme la quatrième fonction tierce et le journal de sécurité (#1585, #1580).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui
porte la politique telle que la 0252 l'a laissée en production.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.seed.contenus_legaux import (
    ACHEMINEMENT_COURRIELS,
    FONCTIONS_TIERS,
    FONCTIONS_TIERS_ANCIEN,
    JOURNAL_SECURITE,
    RECEPTION_COURRIELS,
    TELEMETRIE_PERFORMANCE,
)
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

POLITIQUE_0252 = (
    "<h2>2. Données collectées</h2><ul><li>Données de navigation</li>"
    + TELEMETRIE_PERFORMANCE
    + "<h2>4. Destinataires</h2><p>Services tiers. "
    + FONCTIONS_TIERS_ANCIEN
    + " :</p><ul><li>Diffusion</li>"
    + ACHEMINEMENT_COURRIELS
    + "</ul><h2>5. Durée de conservation</h2>"
)


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration("0253_politique_tiers_journal"), sens)()


def _moteur(politique: str = POLITIQUE_0252):
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


def test_les_trois_passages_sont_poses_une_seule_fois():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    texte = _politique(moteur)
    assert FONCTIONS_TIERS_ANCIEN not in texte
    assert texte.count(FONCTIONS_TIERS) == 1
    assert texte.count(RECEPTION_COURRIELS) == 1
    assert ACHEMINEMENT_COURRIELS + RECEPTION_COURRIELS + "</ul>" in texte
    assert texte.count(JOURNAL_SECURITE) == 1
    assert TELEMETRIE_PERFORMANCE + JOURNAL_SECURITE in texte


def test_un_texte_reformule_a_la_main_n_est_pas_touche():
    reformule = "<p>Notre politique, réécrite par l'administrateur.</p>"
    moteur = _moteur(reformule)
    _jouer(moteur)
    assert _politique(moteur) == reformule


def test_le_retour_arriere_defait_les_trois():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _politique(moteur) == POLITIQUE_0252
