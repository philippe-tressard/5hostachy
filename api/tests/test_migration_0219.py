"""La 0219 retire de `pages_order` les pages disparues, et elles seules (#1114).

Rejouée sur une vraie base SQLite, comme la 0218.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

VERSIONS = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _jouer(moteur):
    spec = importlib.util.spec_from_file_location("m0219", next(VERSIONS.glob("0219_*.py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with moteur.begin() as c, Operations.context(MigrationContext.configure(c)):
        module.upgrade()


@pytest.fixture(name="base")
def base_fixture():
    moteur = create_engine("sqlite://")
    with moteur.begin() as c:
        c.execute(text("CREATE TABLE config_site (cle TEXT PRIMARY KEY, valeur TEXT)"))
    return moteur


def _ordre(moteur, valeur):
    with moteur.begin() as c:
        c.execute(text("INSERT INTO config_site VALUES ('pages_order', :v)"), {"v": valeur})
    _jouer(moteur)
    with moteur.connect() as c:
        return c.execute(text("SELECT valeur FROM config_site WHERE cle = 'pages_order'")).scalar()


def test_les_trois_fantomes_partent_l_ordre_du_reste_est_garde(base):
    servi = [
        "tableau-de-bord",
        "residence",
        "actualites",
        "mes-demandes",
        "calendrier",
        "mon-lot",
        "acces-badges",
        "annuaire",
    ]
    assert json.loads(_ordre(base, json.dumps(servi))) == [
        "tableau-de-bord",
        "residence",
        "mes-demandes",
        "mon-lot",
        "annuaire",
    ]


def test_une_valeur_illisible_n_est_pas_reparee_a_l_aveugle(base):
    assert _ordre(base, "pas du json") == "pas du json"


def test_sans_ordre_enregistre_rien_n_est_ecrit(base):
    _jouer(base)
    with base.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM config_site")).scalar() == 0
