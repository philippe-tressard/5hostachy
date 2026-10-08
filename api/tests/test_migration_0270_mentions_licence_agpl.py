"""La 0270 remplace, dans les mentions en base, la Licence 5Hostachy par l'AGPL (#1726).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui
porte les mentions telles que la 0180 les a laissées.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.seed.contenus_legaux import DEFAULT_LEGAL, PARAGRAPHE_LICENCE
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

MIGRATION = charger_migration("0270_mentions_licence_agpl")
#: Ce que la 0180 a posé en base — la seule source de vérité sur le texte servi.
POSE_PAR_0180 = charger_migration("0180_licence_5hostachy").NOUVEAU
#: Une page réelle : un éditeur saisi en administration, le passage de la 0180.
PAGE = "<h2>Éditeur</h2><p>Syndicat des copropriétaires.</p>" + POSE_PAR_0180


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(MIGRATION, sens)()


def _moteur(valeur: str):
    m = moteur_memoire()
    with m.begin() as conn:
        conn.execute(
            text("INSERT INTO config_site (cle, valeur) VALUES ('mentions_legales', :v)"),
            {"v": valeur},
        )
    return m


def _mentions(moteur) -> str:
    with moteur.connect() as conn:
        return conn.execute(
            text("SELECT valeur FROM config_site WHERE cle = 'mentions_legales'")
        ).scalar()


def test_l_ancien_passage_est_celui_que_la_0180_a_pose():
    """Recopié au caractère près — sinon la migration ne trouverait rien, en silence."""
    assert MIGRATION.ANCIEN in POSE_PAR_0180


def test_une_base_neuve_et_une_base_migree_disent_la_meme_licence():
    assert PARAGRAPHE_LICENCE in DEFAULT_LEGAL["mentions_legales"]
    assert "clause" not in DEFAULT_LEGAL["mentions_legales"].casefold()


def test_la_licence_est_remplacee_une_seule_fois_et_le_reste_garde():
    moteur = _moteur(PAGE)
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    mentions = _mentions(moteur)
    assert PARAGRAPHE_LICENCE in mentions
    assert mentions.count(PARAGRAPHE_LICENCE) == 1
    assert "Licence 5Hostachy" not in mentions
    assert "Syndicat des copropriétaires" in mentions, "l'éditeur saisi a été effacé"
    assert "restent la propriété de leurs auteurs" in mentions


def test_une_page_reecrite_a_la_main_n_est_pas_touchee():
    reecrite = "<p>Texte rédigé depuis Admin › Légal, sans le passage d'origine.</p>"
    moteur = _moteur(reecrite)
    _jouer(moteur)
    assert _mentions(moteur) == reecrite


def test_le_retour_arriere_remet_l_ancien_texte():
    moteur = _moteur(PAGE)
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _mentions(moteur) == PAGE
