"""La 0251 crée le compteur des erreurs du navigateur et le dit dans la politique servie.

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui
porte la politique telle que la 0247 l'a laissée en production.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from app.seed.contenus_legaux import TELEMETRIE_COLLECTE, TELEMETRIE_ERREURS
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

POLITIQUE_0247 = (
    "<h2>2. Données collectées</h2><ul><li>Données de navigation</li>"
    + TELEMETRIE_COLLECTE
    + "<h2>3. Finalités et bases légales</h2>"
)


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration("0251_erreurs_navigateur"), sens)()


def _moteur(politique: str = POLITIQUE_0247):
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
    colonnes = {c["name"] for c in inspect(moteur).get_columns("erreur_navigateur")}
    assert colonnes == {"id", "jour", "page", "code", "total", "premiere_le", "derniere_le"}


def test_le_paragraphe_suit_celui_de_la_mesure_d_audience_une_seule_fois():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    texte = _politique(moteur)
    assert texte.count(TELEMETRIE_ERREURS) == 1
    assert TELEMETRIE_COLLECTE + TELEMETRIE_ERREURS in texte


def test_un_texte_reformule_a_la_main_n_est_pas_touche():
    reformule = "<p>Notre politique, réécrite par l'administrateur.</p>"
    moteur = _moteur(reformule)
    _jouer(moteur)
    assert _politique(moteur) == reformule


def test_le_retour_arriere_defait_les_deux():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _politique(moteur) == POLITIQUE_0247
    assert "erreur_navigateur" not in inspect(moteur).get_table_names()
