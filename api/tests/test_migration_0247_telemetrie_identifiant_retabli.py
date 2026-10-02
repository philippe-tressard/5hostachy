"""La 0247 rétablit l'identifiant de la mesure d'audience et les textes servis.

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui
porte la table et les textes tels que la 0246 les a laissés en production.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration


def _module():
    return charger_migration("0247_telemetrie_identifiant_retabli")


def _jouer(moteur) -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            _module().upgrade()


def _politique_0246() -> str:
    m = _module()
    return (
        "<h2>2. Données collectées</h2><ul><li>Données de navigation "
        + m.NAVIGATION_0246
        + "</li>"
        + m.COLLECTE_0246
        + "<h2>3. Finalités et bases légales</h2><ul><li>E-mails</li>"
        + m.BASE_LEGALE_0246
        + "</ul><h2>4. Destinataires</h2><h2>5. Durée de conservation</h2><ul><li>"
        + m.DUREE_0246
        + "</li>"
        + m.CONSERVATION_0246
        + "</ul><h2>6. Vos droits</h2><p>"
        + m.DROITS_0246
        + "</p>"
    )


def _mentions_0246() -> str:
    return "<p>… détaillés dans la " + _module().MENTIONS_ANCRE + "</p>"


def _moteur():
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE telemetry_event (id INTEGER PRIMARY KEY, page VARCHAR NOT NULL, "
                "action VARCHAR NOT NULL DEFAULT 'view', detail VARCHAR, cree_le DATETIME NOT NULL)"
            )
        )
        conn.execute(text("CREATE TABLE config_site (cle VARCHAR PRIMARY KEY, valeur VARCHAR)"))
        conn.execute(
            text("INSERT INTO config_site (cle, valeur) VALUES (:c, :v)"),
            [
                {"c": "politique_confidentialite", "v": _politique_0246()},
                {"c": "mentions_legales", "v": _mentions_0246()},
            ],
        )
    return m


def _texte(moteur, cle: str) -> str:
    with moteur.connect() as conn:
        return conn.execute(
            text("SELECT valeur FROM config_site WHERE cle = :c"), {"c": cle}
        ).scalar()


def test_la_colonne_revient_sans_cle_etrangere():
    moteur = _moteur()
    _jouer(moteur)
    inspecteur = inspect(moteur)
    assert "user_id" in {c["name"] for c in inspecteur.get_columns("telemetry_event")}
    assert inspecteur.get_foreign_keys("telemetry_event") == []


def test_les_textes_servis_rattachent_de_nouveau_la_mesure_au_compte():
    from app.seed.contenus_legaux import (
        DROITS_DEPUIS_LE_PROFIL,
        TELEMETRIE_BASE_LEGALE,
        TELEMETRIE_COLLECTE,
        TELEMETRIE_CONSERVATION,
    )

    moteur = _moteur()
    _jouer(moteur)
    politique = _texte(moteur, "politique_confidentialite")
    assert "sans identifiant" not in politique
    assert "rattachées à votre compte" in politique
    assert "(avec identifiant)" in politique
    for retabli in (
        TELEMETRIE_COLLECTE,
        TELEMETRIE_BASE_LEGALE,
        TELEMETRIE_CONSERVATION,
        DROITS_DEPUIS_LE_PROFIL,
    ):
        assert politique.count(retabli) == 1, retabli[:60]
    assert _texte(moteur, "mentions_legales").count("exporter et effacer") == 1


def test_la_migration_est_idempotente():
    moteur = _moteur()
    _jouer(moteur)
    une_fois = (_texte(moteur, "politique_confidentialite"), _texte(moteur, "mentions_legales"))
    _jouer(moteur)
    assert (_texte(moteur, "politique_confidentialite"), _texte(moteur, "mentions_legales")) == (
        une_fois
    )


def test_un_texte_reecrit_a_la_main_n_est_pas_touche():
    moteur = _moteur()
    with moteur.begin() as conn:
        conn.execute(
            text("UPDATE config_site SET valeur = :v WHERE cle = 'politique_confidentialite'"),
            {"v": "<p>Notre politique, rédigée par le conseil.</p>"},
        )
    _jouer(moteur)
    assert _texte(moteur, "politique_confidentialite") == (
        "<p>Notre politique, rédigée par le conseil.</p>"
    )
