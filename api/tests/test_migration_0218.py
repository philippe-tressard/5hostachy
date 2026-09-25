"""La 0218 corrige deux phrases fausses du texte SERVI, et rien d'autre (#1073, #1070).

Rejouée sur une vraie base SQLite : une migration de texte juridique se juge
sur ce qu'elle laisse dans la table, pas sur son code. Trois cas :
1. le texte posé par la 0199 et la 0170 est corrigé ;
2. un texte réécrit depuis l'administration n'est PAS touché ;
3. le downgrade rend la phrase de conservation, mais jamais le lien en 404.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

VERSIONS = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _migration():
    chemin = next(VERSIONS.glob("0218_*.py"))
    spec = importlib.util.spec_from_file_location("m0218", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="base")
def base_fixture():
    moteur = create_engine("sqlite://")
    with moteur.begin() as c:
        c.execute(text("CREATE TABLE config_site (cle TEXT PRIMARY KEY, valeur TEXT)"))
    return moteur


def _poser(moteur, cle, valeur):
    with moteur.begin() as c:
        c.execute(text("INSERT INTO config_site VALUES (:c, :v)"), {"c": cle, "v": valeur})


def _lire(moteur, cle):
    with moteur.connect() as c:
        return c.execute(text("SELECT valeur FROM config_site WHERE cle = :c"), {"c": cle}).scalar()


def _jouer(moteur, sens):
    m = _migration()
    with moteur.begin() as c:
        with Operations.context(MigrationContext.configure(c)):
            getattr(m, sens)()
    return m


def test_les_deux_phrases_fausses_sont_corrigees(base):
    m = _migration()
    _poser(base, "politique_confidentialite", f"<ul>{m.ANCIENNE_CONSERVATION}</li></ul>")
    _poser(base, "mentions_legales", f"<p>Voir la <a {m.LIEN_MORT}>politique</a>.</p>")
    _jouer(base, "upgrade")
    politique = _lire(base, "politique_confidentialite")
    assert "Aucune purge automatique" not in politique
    assert m._nouvelle_conservation() in politique
    assert _lire(base, "mentions_legales") == f"<p>Voir la <a {m.LIEN_JUSTE}>politique</a>.</p>"


def test_un_texte_reecrit_a_la_main_n_est_pas_touche(base):
    _poser(base, "politique_confidentialite", "<p>Rédigé depuis l'administration.</p>")
    _jouer(base, "upgrade")
    assert _lire(base, "politique_confidentialite") == "<p>Rédigé depuis l'administration.</p>"


def test_le_downgrade_rend_la_phrase_mais_pas_la_404(base):
    m = _migration()
    _poser(base, "politique_confidentialite", f"<ul>{m.ANCIENNE_CONSERVATION}</li></ul>")
    _poser(base, "mentions_legales", f"<a {m.LIEN_MORT}>x</a>")
    _jouer(base, "upgrade")
    _jouer(base, "downgrade")
    assert _lire(base, "politique_confidentialite") == f"<ul>{m.ANCIENNE_CONSERVATION}</li></ul>"
    assert m.LIEN_MORT not in _lire(base, "mentions_legales")
