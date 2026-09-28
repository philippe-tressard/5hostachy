"""La 0232 réserve de nouveau au conseil les maintenances récurrentes du calendrier (#1428).

Signalé le 28/09/2026 : un locataire trouvait, en cherchant « ag » dans
Affaires, les contrats de maintenance de la copropriété. La 0212 n'avait
traduit les destinataires d'un événement que pour ceux devenus actualités ; un
événement suivi (maintenance récurrente, AG) est devenu une affaire sans
destinataires, et l'ouverture de l'affaire datée aux locataires l'a mis sous
leurs yeux.

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire. Ce
que la règle fait ensuite de ces destinataires est tenu par
`lecture_pastille.json` : ici, on vérifie que la migration les POSE, et
seulement là où il faut.
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
    / "0232_destinataires_evenements_migres.py"
)

CS = ["conseil_syndical"]

#: (id, catégorie, confidentiel, public_cible avant, type de l'événement
#:  d'origine ou None) → public_cible attendu après.
CAS = [
    (1, "entretien", 0, None, "maintenance_recurrente", CS),
    (2, "entretien", 0, "[]", "maintenance_recurrente", CS),
    #  Une AG retrouve ses lecteurs (les copropriétaires) par la règle par
    #  défaut, depuis que la date n'ouvre plus rien aux locataires : rien à écrire.
    (3, "etude_travaux", 0, None, "ag", None),
    #  Le conseil a déjà choisi : son choix est plus récent que l'événement.
    (4, "entretien", 0, '["locataires"]', "maintenance_recurrente", ["locataires"]),
    #  Confidentielle : le conseil seul la lit déjà.
    (5, "entretien", 1, None, "maintenance_recurrente", None),
    #  Une actualité a reçu les siens de la 0212.
    (6, "actualite", 0, None, "ag", None),
    #  Un événement que le calendrier montrait à tous : rien à restreindre.
    (7, "etude_travaux", 0, None, "travaux", None),
    (8, "entretien", 0, None, "maintenance", None),
    #  Une affaire née affaire.
    (9, "panne", 0, None, None, None),
]


def _module():
    spec = importlib.util.spec_from_file_location("mig0232", _MIGRATION)
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
                "CREATE TABLE ticket (id INTEGER PRIMARY KEY, categorie TEXT, "
                "confidentiel BOOLEAN, public_cible TEXT, promu_depuis_evenement_id INTEGER)"
            )
        )
        for tid, categorie, confidentiel, avant, type_ev, _ in CAS:
            eid = None
            if type_ev:
                eid = 100 + tid
                conn.execute(
                    text("INSERT INTO evenement (id, type) VALUES (:i, :t)"),
                    {"i": eid, "t": type_ev},
                )
            conn.execute(
                text(
                    "INSERT INTO ticket (id, categorie, confidentiel, public_cible, "
                    "promu_depuis_evenement_id) VALUES (:i, :c, :conf, :p, :e)"
                ),
                {"i": tid, "c": categorie, "conf": confidentiel, "p": avant, "e": eid},
            )
    return m


def _lire(moteur) -> dict:
    with moteur.connect() as conn:
        return dict(conn.execute(text("SELECT id, public_cible FROM ticket")).all())


def test_les_colonnes_lues_sont_celles_du_modele():
    """La migration écrit du SQL brut : un nom de colonne faux passerait ici en silence."""
    from app.models.core import Ticket
    from app.models.evenement import Evenement

    ticket = Ticket.__table__.c
    for colonne in ("categorie", "confidentiel", "public_cible", "promu_depuis_evenement_id"):
        assert colonne in ticket, colonne
    assert "type" in Evenement.__table__.c


def test_les_types_sont_ceux_du_modele():
    from app.models.evenement import TypeEvenement

    assert set(_module().DESTINATAIRES) <= {t.value for t in TypeEvenement}


def test_les_destinataires_de_l_evenement_sont_poses(moteur):
    avant = _lire(moteur)
    _jouer(moteur)
    apres = _lire(moteur)
    for tid, *_, attendu in CAS:
        if attendu is None or attendu == json.loads(avant[tid] or "null"):
            assert apres[tid] == avant[tid], f"affaire {tid} modifiée à tort : {apres[tid]}"
        else:
            assert json.loads(apres[tid]) == attendu, f"affaire {tid} : {apres[tid]}"


def test_la_migration_se_rejoue_sans_rien_changer(moteur):
    _jouer(moteur)
    une_fois = _lire(moteur)
    _jouer(moteur)
    assert _lire(moteur) == une_fois
