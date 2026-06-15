"""Garde-fou préventif : intégrité de la chaîne de migrations Alembic.

Une migration avec un mauvais `down_revision` crée plusieurs *heads* : en prod,
`start.sh` lance `alembic upgrade head` avec `set -e` → le conteneur reste
bloqué au démarrage. Ce test attrape ces erreurs structurelles avant la MEP
(la cause des fix « migration 0094/0105 » de l'historique).

Note : on ne teste pas `upgrade head` depuis une base vierge car le schéma de
base est créé par `SQLModel.create_all` puis ajusté par des migrations
incrémentales (non rejouables seules sur une base vide / déjà au schéma final).
La validation porte donc sur la cohérence du graphe de révisions.
"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_API_DIR = Path(__file__).resolve().parents[1]


def _script_dir() -> ScriptDirectory:
    cfg = Config(str(_API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_DIR / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_un_seul_head():
    """Pas de divergence : un unique head (sinon upgrade head échoue en prod)."""
    heads = _script_dir().get_heads()
    assert len(heads) == 1, f"Plusieurs heads de migration : {heads} (down_revision incorrect ?)"


def test_une_seule_base():
    """Un unique point de départ dans le graphe de migrations."""
    bases = _script_dir().get_bases()
    assert len(bases) == 1, f"Plusieurs bases de migration : {bases}"


def test_revisions_uniques():
    """Aucun identifiant de révision dupliqué."""
    revs = [s.revision for s in _script_dir().walk_revisions()]
    doublons = sorted({r for r in revs if revs.count(r) > 1})
    assert not doublons, f"Identifiants de révision dupliqués : {doublons}"
