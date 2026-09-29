"""La 0236 ramène au conseil seul les Études & travaux aux destinataires choisis (29/09/2026).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire. Ce
que la règle fait ensuite d'une Étude & travaux sans destinataires (le conseil
seul) est tenu par `lecture_pastille.json` : ici, on vérifie que la migration
EFFACE le choix, et seulement là où il faut.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0236_etude_travaux_au_conseil.py"
)

COPRO = '["copropriétaires_occupants", "bailleurs"]'

#: (id, catégorie, confidentiel, public_cible avant) → public_cible attendu après.
CAS = [
    #  Le choix du conseil est effacé : la catégorie décide, donc le conseil seul.
    (1, "etude_travaux", 0, COPRO, None),
    (2, "etude_travaux", 0, '["locataires"]', None),
    (3, "etude_travaux", 0, "[]", None),
    #  Déjà au défaut : rien à faire.
    (4, "etude_travaux", 0, None, None),
    #  Confidentielle : seul `public_cible` bouge, le drapeau reste.
    (5, "etude_travaux", 1, COPRO, None),
    #  Une autre catégorie, une actualité : intouchées.
    (6, "entretien", 0, COPRO, COPRO),
    (7, "panne", 0, '["locataires"]', '["locataires"]'),
    (8, "actualite", 0, '["résidents"]', '["résidents"]'),
]


def _module():
    spec = importlib.util.spec_from_file_location("mig0236", _MIGRATION)
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
        conn.execute(
            text(
                "CREATE TABLE ticket (id INTEGER PRIMARY KEY, categorie TEXT, "
                "confidentiel BOOLEAN, public_cible TEXT)"
            )
        )
        for tid, categorie, confidentiel, avant, _ in CAS:
            conn.execute(
                text(
                    "INSERT INTO ticket (id, categorie, confidentiel, public_cible) "
                    "VALUES (:i, :c, :conf, :p)"
                ),
                {"i": tid, "c": categorie, "conf": confidentiel, "p": avant},
            )
    return m


def _lire(moteur) -> dict:
    with moteur.connect() as conn:
        return {
            i: (p, c)
            for i, p, c in conn.execute(text("SELECT id, public_cible, confidentiel FROM ticket"))
        }


def test_les_colonnes_et_la_categorie_sont_celles_du_modele():
    """La migration écrit du SQL brut : un nom faux passerait ici en silence."""
    from app.models.core import Ticket
    from app.models.tickets import CategorieTicket

    for colonne in ("categorie", "confidentiel", "public_cible"):
        assert colonne in Ticket.__table__.c, colonne
    assert _module().CATEGORIE in {c.value for c in CategorieTicket}


def test_seules_les_etudes_perdent_leurs_destinataires(moteur):
    _jouer(moteur)
    apres = _lire(moteur)
    for tid, _cat, confidentiel, _avant, attendu in CAS:
        assert apres[tid] == (attendu, confidentiel), tid


def test_la_migration_est_idempotente(moteur):
    _jouer(moteur)
    une_fois = _lire(moteur)
    _jouer(moteur)
    assert _lire(moteur) == une_fois


def test_apres_migration_une_etude_est_lue_du_seul_conseil():
    """Le NULL posé veut bien dire « conseil seul » pour la règle du serveur."""
    from app.models.core import Ticket
    from app.utils.visibility import destinataires_par_defaut, reservee_au_conseil

    t = Ticket(categorie="etude_travaux", titre="É", description="…", public_cible=None)
    assert destinataires_par_defaut(t) == ["conseil_syndical"]
    assert reservee_au_conseil(t)
