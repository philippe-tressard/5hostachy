"""La 0244 rend au standard du 30/09/2026 les affaires qui portaient le défaut d'hier.

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire. Ce
que la règle fait ensuite d'une affaire sans destinataires est tenu par
`lecture_pastille.json` : ici, on vérifie que la migration EFFACE le défaut
d'hier écrit en dur, et lui seul — un choix du conseil tient.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

_MIGRATION = (
    Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0244_lecture_carnet_affaires.py"
)

PANNE_HIER = '["copropriétaires_occupants", "locataires"]'
COPROS = '["copropriétaires_occupants", "bailleurs"]'
CS = '["conseil_syndical"]'

#: (id, catégorie, confidentiel, public_cible avant) → après.
CAS = [
    #  Le défaut d'hier d'une Panne dans un bâtiment : effacé, dans tout ordre.
    (1, "panne", 0, PANNE_HIER, None),
    (2, "panne", 0, '["locataires","copropriétaires_occupants"]', None),
    #  Confidentielle : seule la liste bouge, le drapeau reste et referme.
    (3, "panne", 1, PANNE_HIER, None),
    #  « Tous » sur une Panne : plus large que le standard, c'est un choix.
    (4, "panne", 0, '["résidents"]', '["résidents"]'),
    (5, "panne", 0, '["copropriétaires_occupants"]', '["copropriétaires_occupants"]'),
    #  Un Entretien aux copropriétaires du périmètre : rendu à toute la résidence.
    (6, "entretien", 0, COPROS, None),
    (7, "entretien", 0, '["copropriétaires"]', None),
    #  « Conseil syndical » sur un Entretien : un choix, il tient.
    (8, "entretien", 0, CS, CS),
    #  Une Étude & travaux n'est jamais touchée — un transfert de courriels
    #  compris (« Conseil syndical » choisi), et des copropriétaires choisis.
    (9, "etude_travaux", 0, CS, CS),
    (10, "etude_travaux", 0, COPROS, COPROS),
    #  Une autre catégorie portant la même liste : intouchée.
    (11, "sinistre", 0, PANNE_HIER, PANNE_HIER),
    #  Déjà au défaut, ou illisible : rien à faire.
    (12, "panne", 0, None, None),
    (13, "entretien", 0, "pas du json", "pas du json"),
]


def _module():
    spec = importlib.util.spec_from_file_location("mig0244", _MIGRATION)
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


def test_les_noms_sont_ceux_du_modele():
    """La migration écrit du SQL brut : un nom faux passerait ici en silence."""
    from app.models.core import Ticket
    from app.models.tickets import CategorieTicket

    for colonne in ("categorie", "confidentiel", "public_cible"):
        assert colonne in Ticket.__table__.c, colonne
    assert set(_module().DEFAUTS_D_HIER) <= {c.value for c in CategorieTicket}


def test_seul_le_defaut_d_hier_est_efface(moteur):
    _jouer(moteur)
    apres = _lire(moteur)
    for tid, _cat, confidentiel, _avant, attendu in CAS:
        assert apres[tid] == (attendu, confidentiel), tid


def test_la_migration_est_idempotente(moteur):
    _jouer(moteur)
    une_fois = _lire(moteur)
    _jouer(moteur)
    assert _lire(moteur) == une_fois


def test_apres_migration_la_regle_du_jour_decide():
    """Le NULL posé veut bien dire le standard pour la règle du serveur."""
    from app.models.core import Ticket
    from app.utils.visibility import destinataires_par_defaut, lus_dans_toute_la_residence

    panne = Ticket(categorie="panne", titre="P", description="…", public_cible=None)
    assert set(destinataires_par_defaut(panne)) == {
        "copropriétaires_occupants",
        "bailleurs",
        "locataires",
    }
    assert set(lus_dans_toute_la_residence(panne)) == {"copropriétaires_occupants", "bailleurs"}
    entretien = Ticket(categorie="entretien", titre="E", description="…", public_cible=None)
    assert set(lus_dans_toute_la_residence(entretien)) == {"copropriétaires_occupants", "bailleurs"}
