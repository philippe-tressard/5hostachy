"""La 0261 crée le compteur des gestes aboutis et le dit dans la politique servie (#1633).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui
porte la politique telle que la 0252 l'a laissée.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from app.seed.contenus_legaux import TELEMETRIE_GESTES, TELEMETRIE_PERFORMANCE
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

POLITIQUE_0252 = (
    "<h2>2. Données collectées</h2><ul>"
    + TELEMETRIE_PERFORMANCE
    + "</ul><h2>3. Finalités et bases légales</h2>"
)


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration("0261_gestes_formulaire"), sens)()


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


def test_la_table_est_creee_sans_identifiant_de_compte():
    moteur = _moteur()
    _jouer(moteur)
    colonnes = {c["name"] for c in inspect(moteur).get_columns("geste_formulaire")}
    assert colonnes == {"id", "jour", "geste", "ouvertures", "envois"}


def test_le_paragraphe_suit_celui_des_durees_une_seule_fois():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    texte = _politique(moteur)
    assert texte.count(TELEMETRIE_GESTES) == 1
    assert TELEMETRIE_PERFORMANCE + TELEMETRIE_GESTES in texte


def test_un_texte_reformule_a_la_main_n_est_pas_touche():
    reformule = "<p>Notre politique, réécrite par l'administrateur.</p>"
    moteur = _moteur(reformule)
    _jouer(moteur)
    assert _politique(moteur) == reformule


def test_le_retour_arriere_defait_les_deux():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _politique(moteur) == POLITIQUE_0252
    assert "geste_formulaire" not in inspect(moteur).get_table_names()
