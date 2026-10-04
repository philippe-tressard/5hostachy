"""La 0257 dit à la politique que la synthèse nomme d'autres affaires (#1647).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui
porte la phrase de la synthèse telle que la 0255 l'a posée en production.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.seed.contenus_legaux import SYNTHESE_AFFAIRE_CLOSE, SYNTHESE_RECIDIVE
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

#: La phrase d'avant : celle de la 0255, sans la clause.
PHRASE_0255 = SYNTHESE_AFFAIRE_CLOSE.replace(SYNTHESE_RECIDIVE, "")
POLITIQUE_0256 = "<h2>4. Destinataires</h2><ul><li>Assistant." + PHRASE_0255 + "</li></ul>"


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration("0257_politique_recidive_equipement"), sens)()


def _moteur(politique: str = POLITIQUE_0256):
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


def test_la_phrase_d_avant_est_bien_celle_de_la_0255():
    assert PHRASE_0255 != SYNTHESE_AFFAIRE_CLOSE
    assert "les personnes désignées par leur rôle, sont transmis" in PHRASE_0255


def test_la_clause_est_posee_une_seule_fois():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    texte = _politique(moteur)
    assert texte.count(SYNTHESE_RECIDIVE) == 1
    assert SYNTHESE_AFFAIRE_CLOSE in texte
    assert "jamais leur contenu" in texte


def test_une_base_neuve_a_deja_la_clause_et_ne_la_double_pas():
    moteur = _moteur("<ul><li>Assistant." + SYNTHESE_AFFAIRE_CLOSE + "</li></ul>")
    _jouer(moteur)
    assert _politique(moteur).count(SYNTHESE_RECIDIVE) == 1


def test_un_texte_reformule_a_la_main_n_est_pas_touche():
    reformule = "<p>Notre politique, réécrite par l'administrateur.</p>"
    moteur = _moteur(reformule)
    _jouer(moteur)
    assert _politique(moteur) == reformule


def test_le_retour_arriere_retire_la_clause():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _politique(moteur) == POLITIQUE_0256
