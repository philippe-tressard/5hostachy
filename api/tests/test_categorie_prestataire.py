"""La catégorie d'un prestataire dit son MÉTIER, jamais le cadre (#1444).

« Contrat récurrent » et « Dépannage » ont été fondues en « Maintenance &
dépannage » : le cadre — sous contrat ou non — appartient à chaque
intervention, et se déduit des contrats de la fiche. Ces tests tiennent trois
choses que rien d'autre ne verrait :

- les anciennes valeurs ne reviennent pas dans l'énumération ;
- la migration convertit chacune vers une valeur RÉELLE — une valeur inventée
  passerait l'`UPDATE` et serait refusée à la lecture, des semaines plus tard ;
- une fiche créée sans catégorie reçoit la nouvelle valeur par défaut.
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import sqlalchemy as sa

from app.models.prestataires import Prestataire, TypePrestataire
from app.routers.prestataires_schemas import PrestataireCreate

_MIGRATION = (
    Path(__file__).parent.parent / "alembic" / "versions" / "0233_categorie_prestataire_metier.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("migration_0233", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_le_cadre_n_est_plus_une_categorie():
    valeurs = {t.value for t in TypePrestataire}
    assert "contrat_recurrent" not in valeurs
    assert "ponctuel" not in valeurs
    assert "maintenance_depannage" in valeurs


def test_la_migration_convertit_vers_une_valeur_reelle():
    correspondance = _migration().CORRESPONDANCE
    assert set(correspondance) == {"contrat_recurrent", "ponctuel"}
    for nouvelle in correspondance.values():
        assert TypePrestataire(nouvelle)


def test_la_migration_reecrit_les_fiches_et_seulement_elles(monkeypatch):
    moteur = sa.create_engine("sqlite://")
    with moteur.begin() as c:
        c.execute(sa.text("CREATE TABLE prestataire (id INTEGER, type_prestataire TEXT)"))
        c.execute(
            sa.text(
                "INSERT INTO prestataire VALUES "
                "(1, 'contrat_recurrent'), (2, 'ponctuel'), (3, 'travaux'), (4, 'gestion')"
            )
        )
        migration = _migration()
        monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: c))
        migration.upgrade()
        lus = dict(c.execute(sa.text("SELECT id, type_prestataire FROM prestataire")).all())
    assert lus == {
        1: "maintenance_depannage",
        2: "maintenance_depannage",
        3: "travaux",
        4: "gestion",
    }


def test_le_defaut_est_la_nouvelle_categorie():
    assert Prestataire(nom="x", specialite="ascenseur").type_prestataire == (
        TypePrestataire.maintenance_depannage
    )
    assert PrestataireCreate(nom="x", specialite="ascenseur").type_prestataire == (
        TypePrestataire.maintenance_depannage
    )
