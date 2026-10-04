"""La 0263 pose la date d'avertissement et corrige la durée annoncée (#1580).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui
porte la phrase « durée de la relation + 2 ans » telle que la 0029 l'a posée.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.seed.contenus_legaux import CONSERVATION_COMPTES, CONSERVATION_COMPTES_ANCIEN
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration, chemin_migration

POLITIQUE_AVANT = (
    "<h2>5. Durée de conservation</h2><ul><li>"
    + CONSERVATION_COMPTES_ANCIEN
    + "</li><li>Tokens de rafraîchissement\xa0: 7 jours glissants.</li></ul>"
)


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration("0263_purge_comptes_inactifs"), sens)()


def _moteur(politique: str = POLITIQUE_AVANT):
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        conn.execute(text("CREATE TABLE config_site (cle VARCHAR PRIMARY KEY, valeur VARCHAR)"))
        conn.execute(text("CREATE TABLE utilisateur (id INTEGER PRIMARY KEY, email VARCHAR)"))
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


def _colonnes(moteur) -> set[str]:
    with moteur.connect() as conn:
        return {c["name"] for c in sa.inspect(conn).get_columns("utilisateur")}


def test_l_ancienne_phrase_est_celle_que_la_0029_a_posee():
    """La garde ne remplace qu'un texte EXACT : il faut que ce soit le bon."""
    brut = chemin_migration("0029_legal_pages_default").read_text(encoding="utf-8")
    brut = brut.replace("\\u00a0", "\xa0")
    assert CONSERVATION_COMPTES_ANCIEN in brut


def test_la_colonne_est_posee_et_la_phrase_remplacee_une_seule_fois():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    assert "purge_avertie_le" in _colonnes(moteur)
    texte = _politique(moteur)
    assert CONSERVATION_COMPTES_ANCIEN not in texte
    assert texte.count(CONSERVATION_COMPTES) == 1
    assert "Tokens de rafraîchissement" in texte, "le reste du texte ne bouge pas"


def test_un_texte_retouche_a_la_main_n_est_pas_touche():
    retouche = POLITIQUE_AVANT.replace("+ 2 ans", "+ 3 ans")
    moteur = _moteur(retouche)
    _jouer(moteur)
    assert _politique(moteur) == retouche
    assert "purge_avertie_le" in _colonnes(moteur), "la colonne, elle, est posée"


def test_le_retour_arriere_rend_la_phrase_et_retire_la_colonne():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _politique(moteur) == POLITIQUE_AVANT
    assert "purge_avertie_le" not in _colonnes(moteur)
