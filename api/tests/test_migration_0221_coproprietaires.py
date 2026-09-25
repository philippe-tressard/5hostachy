"""La 0221 retire le code « copropriétaires » des publics visés (#1301, lot 2).

Arbitré le 25/09/2026 : la pastille « Copropriétaires » quitte le sélecteur de
Destinataires. Elle faisait double emploi avec « Copropriétaires occupants » et
« Copropriétaires bailleurs », qu'elle couvrait ensemble. Les données qui la
portent passent donc aux DEUX codes. Sans cela, un objet adressé aux
copropriétaires resterait lisible par la règle, mais plus aucun écran ne saurait
le proposer ni le corriger.

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire, dans
les cinq tables qui portent un public visé.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0221_destinataires_sans_coproprietaires.py"
)

#: valeur avant → valeur attendue après (None : ligne inchangée).
CAS = {
    '["copropriétaires"]': ["copropriétaires_occupants", "bailleurs"],
    '["copropriétaires", "locataires"]': ["copropriétaires_occupants", "bailleurs", "locataires"],
    #  Déjà l'un des deux : pas de doublon.
    '["bailleurs", "copropriétaires"]': ["bailleurs", "copropriétaires_occupants"],
    #  L'ancien format CSV, que la règle lit encore.
    "copropriétaires,locataires": ["copropriétaires_occupants", "bailleurs", "locataires"],
    '["copropriétaires_occupants"]': None,
    '["résidents"]': None,
    "[]": None,
}


def _module():
    spec = importlib.util.spec_from_file_location("mig0221", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jouer(moteur) -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            _module().upgrade()


@pytest.fixture()
def moteur():
    m = create_engine("sqlite://")
    with m.begin() as conn:
        for table in _module().TABLES:
            conn.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, public_cible TEXT)"))
            conn.execute(text(f"INSERT INTO {table} (id, public_cible) VALUES (0, NULL)"))
            for i, avant in enumerate(CAS, 1):
                conn.execute(
                    text(f"INSERT INTO {table} (id, public_cible) VALUES (:i, :v)"),
                    {"i": i, "v": avant},
                )
    return m


def _lire(moteur, table: str) -> dict:
    with moteur.connect() as conn:
        return dict(conn.execute(text(f"SELECT id, public_cible FROM {table}")).all())


def test_les_cinq_tables_sont_celles_du_modele():
    """Une table ajoutée au modèle avec un public visé, oubliée ici, garderait le code."""
    import app.models.core  # noqa: F401 — enregistre toutes les tables
    from sqlmodel import SQLModel

    attendu = {t.name for t in SQLModel.metadata.sorted_tables if "public_cible" in t.c}
    assert set(_module().TABLES) == attendu


def test_le_code_est_remplace_par_les_deux_profils(moteur):
    _jouer(moteur)
    for table in _module().TABLES:
        lu = _lire(moteur, table)
        assert lu[0] is None
        for i, (avant, apres) in enumerate(CAS.items(), 1):
            if apres is None:
                assert lu[i] == avant, f"{table} : {avant!r} n'aurait pas dû bouger"
            else:
                assert json.loads(lu[i]) == apres, f"{table} : {avant!r} → {lu[i]!r}"


def test_rejouee_elle_ne_change_rien(moteur):
    _jouer(moteur)
    premier = {t: _lire(moteur, t) for t in _module().TABLES}
    _jouer(moteur)
    assert {t: _lire(moteur, t) for t in _module().TABLES} == premier
