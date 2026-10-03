"""La 0252 crée la table des durées d'affichage et le dit dans la politique servie (#1632).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui
porte la politique telle que la 0251 l'a laissée en production.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from app.seed.contenus_legaux import TELEMETRIE_ERREURS, TELEMETRIE_PERFORMANCE
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

POLITIQUE_0251 = (
    "<h2>2. Données collectées</h2><ul><li>Données de navigation</li>"
    + TELEMETRIE_ERREURS
    + "<h2>3. Finalités et bases légales</h2>"
)


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration("0252_mesures_affichage"), sens)()


def _moteur(politique: str = POLITIQUE_0251):
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


def test_la_table_est_creee_sans_identifiant_de_compte():
    moteur = _moteur()
    _jouer(moteur)
    colonnes = {c["name"] for c in inspect(moteur).get_columns("mesure_affichage")}
    assert colonnes == {"id", "jour", "page", "indicateur", "duree_ms"}


def test_le_paragraphe_suit_celui_des_erreurs_une_seule_fois():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    texte = _politique(moteur)
    assert texte.count(TELEMETRIE_PERFORMANCE) == 1
    assert TELEMETRIE_ERREURS + TELEMETRIE_PERFORMANCE in texte


def test_un_texte_reformule_a_la_main_n_est_pas_touche():
    reformule = "<p>Notre politique, réécrite par l'administrateur.</p>"
    moteur = _moteur(reformule)
    _jouer(moteur)
    assert _politique(moteur) == reformule


def test_le_retour_arriere_defait_les_deux():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _politique(moteur) == POLITIQUE_0251
    assert "mesure_affichage" not in inspect(moteur).get_table_names()
