"""La 0243 rend aux copropriétaires les Entretiens que la 0232 avait fermés au conseil (30/09/2026).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire. Ce
que la règle fait ensuite d'un Entretien sans destinataires (les
copropriétaires) est tenu par `lecture_pastille.json` : ici, on vérifie que la
migration EFFACE le « Conseil syndical » de la 0232, et lui seul — un choix du
conseil tient.
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
    / "0243_entretien_aux_coproprietaires.py"
)

CS = '["conseil_syndical"]'
#: L'événement 1 est une maintenance récurrente, le 2 une AG.
MAINTENANCE, AG = 1, 2

#: (id, catégorie, confidentiel, événement d'origine, public_cible avant) → après.
CAS = [
    #  Le « Conseil syndical » de la 0232 : effacé, la catégorie décide.
    (1, "entretien", 0, MAINTENANCE, CS, None),
    #  Même liste, autres espaces : reconnue quand même.
    (2, "entretien", 0, MAINTENANCE, '[ "conseil_syndical" ]', None),
    #  Confidentielle : seul `public_cible` bouge, le drapeau reste et referme.
    (3, "entretien", 1, MAINTENANCE, CS, None),
    #  Un choix du conseil, plus large ou plus étroit : il tient.
    (4, "entretien", 0, MAINTENANCE, '["locataires"]', '["locataires"]'),
    (
        5,
        "entretien",
        0,
        MAINTENANCE,
        '["conseil_syndical", "bailleurs"]',
        '["conseil_syndical", "bailleurs"]',
    ),
    #  « Conseil syndical » posé à la main, hors de la 0232 : il tient.
    (6, "entretien", 0, None, CS, CS),
    (7, "entretien", 0, AG, CS, CS),
    #  Une autre catégorie : intouchée.
    (8, "etude_travaux", 0, MAINTENANCE, CS, CS),
    #  Déjà au défaut, ou illisible : rien à faire.
    (9, "entretien", 0, MAINTENANCE, None, None),
    (10, "entretien", 0, MAINTENANCE, "pas du json", "pas du json"),
]


def _module():
    spec = importlib.util.spec_from_file_location("mig0243", _MIGRATION)
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
        conn.execute(text("CREATE TABLE evenement (id INTEGER PRIMARY KEY, type TEXT)"))
        conn.execute(
            text(
                "INSERT INTO evenement (id, type) VALUES (:m, 'maintenance_recurrente'), (:a, 'ag')"
            ),
            {"m": MAINTENANCE, "a": AG},
        )
        conn.execute(
            text(
                "CREATE TABLE ticket (id INTEGER PRIMARY KEY, categorie TEXT, "
                "confidentiel BOOLEAN, promu_depuis_evenement_id INTEGER, public_cible TEXT)"
            )
        )
        for tid, categorie, confidentiel, evenement, avant, _ in CAS:
            conn.execute(
                text(
                    "INSERT INTO ticket (id, categorie, confidentiel, promu_depuis_evenement_id, "
                    "public_cible) VALUES (:i, :c, :conf, :e, :p)"
                ),
                {"i": tid, "c": categorie, "conf": confidentiel, "e": evenement, "p": avant},
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
    from app.models.evenement import Evenement
    from app.models.tickets import CategorieTicket

    for colonne in ("categorie", "confidentiel", "public_cible", "promu_depuis_evenement_id"):
        assert colonne in Ticket.__table__.c, colonne
    assert "type" in Evenement.__table__.c
    assert _module().CATEGORIE in {c.value for c in CategorieTicket}


def test_la_0232_est_bien_celle_que_l_on_defait():
    """Le type et la liste sont ceux que la 0232 a écrits — pas une recopie approximative."""
    chemin = _MIGRATION.with_name("0232_destinataires_evenements_migres.py")
    spec = importlib.util.spec_from_file_location("mig0232", chemin)
    m0232 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m0232)
    assert m0232.DESTINATAIRES == {_module().TYPE_EVENEMENT: _module().CONSEIL_SEUL}


def test_seuls_les_entretiens_de_la_0232_perdent_leurs_destinataires(moteur):
    _jouer(moteur)
    apres = _lire(moteur)
    for tid, _cat, confidentiel, _evt, _avant, attendu in CAS:
        assert apres[tid] == (attendu, confidentiel), tid


def test_la_migration_est_idempotente(moteur):
    _jouer(moteur)
    une_fois = _lire(moteur)
    _jouer(moteur)
    assert _lire(moteur) == une_fois


def test_apres_migration_un_entretien_est_lu_des_coproprietaires():
    """Le NULL posé veut bien dire « les copropriétaires » pour la règle du serveur."""
    from app.models.core import Ticket
    from app.utils.visibility import destinataires_par_defaut, reservee_au_conseil

    t = Ticket(categorie="entretien", titre="E", description="…", public_cible=None)
    assert destinataires_par_defaut(t) == ["copropriétaires_occupants", "bailleurs"]
    assert not reservee_au_conseil(t)
