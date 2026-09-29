"""La reprise de la 0235 : l'affaire apprend sous quel contrat elle a eu lieu (#1445).

Deux sources, dans l'ordre : le contrat de l'événement d'origine (que la 0212
n'avait pas recopié), puis la règle d'AVANT — celle qu'`apres_cloture`
appliquait à chaque clôture, le libellé du contrat dans le titre. Ces tests
exécutent la vraie migration sur une base jetable.
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import sqlalchemy as sa

_MIGRATION = Path(__file__).parent.parent / "alembic" / "versions" / "0235_affaire_sous_contrat.py"


def _migration():
    spec = importlib.util.spec_from_file_location("migration_0235", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base(c):
    c.execute(
        sa.text(
            "CREATE TABLE contrat_entretien (id INTEGER PRIMARY KEY, prestataire_id INTEGER, "
            "libelle TEXT, frequence_type TEXT, type_equipement TEXT, actif INTEGER)"
        )
    )
    c.execute(sa.text("CREATE TABLE evenement (id INTEGER PRIMARY KEY, contrat_id INTEGER)"))
    c.execute(
        sa.text(
            "CREATE TABLE ticket (id INTEGER PRIMARY KEY, prestataire_id INTEGER, titre TEXT, "
            "categorie TEXT, frequence_type TEXT, frequence_valeur INTEGER, "
            "promu_depuis_evenement_id INTEGER)"
        )
    )
    c.execute(
        sa.text(
            "INSERT INTO contrat_entretien VALUES "
            "(10, 1, 'Ascenseur', 'mois', 'ascenseur', 1), "
            "(11, 1, 'Portail', 'ans', 'porte_parking', 1), "
            "(20, 2, 'Extincteurs', 'ans', 'extincteurs', 1), "
            "(30, 3, 'Multirisque', 'ans', 'assurance', 1)"
        )
    )
    c.execute(sa.text("INSERT INTO evenement VALUES (500, 11)"))
    c.execute(
        sa.text(
            "INSERT INTO ticket VALUES "
            #  1 : l'événement d'origine désigne le contrat « Portail ».
            "(1, 1, 'Visite', 'entretien', 'ans', 1, 500), "
            #  2 : le titre cite « Ascenseur ».
            "(2, 1, 'Otis — Ascenseur (1/4)', 'entretien', 'mois', 3, NULL), "
            #  3 : Sicli n'a qu'un contrat.
            "(3, 2, 'Contrôle annuel', 'entretien', 'ans', 1, NULL), "
            #  4 : Otis en a deux, et le titre n'en cite aucun — rien n'est deviné.
            "(4, 1, 'Visite', 'entretien', 'mois', 1, NULL), "
            #  5 : une panne n'est pas une visite de contrat.
            "(5, 2, 'Extincteurs — fuite', 'panne', NULL, NULL, NULL), "
            #  6 : une assurance ne cadre pas une intervention.
            "(6, 3, 'Multirisque', 'entretien', 'ans', 1, NULL)"
        )
    )


def test_la_reprise_rattache_ce_qui_se_prouve_et_rien_d_autre(monkeypatch):
    moteur = sa.create_engine("sqlite://")
    migration = _migration()
    with moteur.begin() as c:
        _base(c)

        def add_column(table, colonne):
            c.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {colonne.name} INTEGER"))

        monkeypatch.setattr(
            migration, "op", SimpleNamespace(get_bind=lambda: c, add_column=add_column)
        )
        migration.upgrade()
        migration.upgrade()  # idempotente
        lus = {
            r[0]: (r[1], r[2])
            for r in c.execute(sa.text("SELECT id, contrat_id, frequence_type FROM ticket")).all()
        }
    assert lus == {
        1: (11, None),
        2: (10, None),
        3: (20, None),
        4: (None, "mois"),
        5: (None, None),
        6: (None, "ans"),
    }
