"""La 0246 retire l'identifiant de la mesure d'audience et corrige les textes servis (#1545).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui
porte la table et les textes tels que les migrations d'avant les ont laissés.
"""

from __future__ import annotations

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration


def _module():
    return charger_migration("0246_telemetrie_sans_identifiant")


def _jouer(moteur) -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            _module().upgrade()


def _politique_d_avant(avec_base_0088: bool) -> str:
    """Un texte d'instance qui porte chaque passage visé, à sa place."""
    m = _module()
    base_0088 = (
        "<li><strong>Télémétrie d'usage</strong> — base\xa0: intérêt légitime.</li>"
        if avec_base_0088
        else ""
    )
    return (
        "<h2>2. Données collectées</h2><ul><li>Données de navigation "
        + m.NAVIGATION_AVANT
        + "</li>"
        + m.COLLECTE_AVANT
        + "<h2>3. Finalités et bases légales</h2><ul>"
        + base_0088
        + "<li>E-mails</li>"
        + m.ANCRE_BASES
        + "<p>…</p><h2>5. Durée de conservation</h2><ul><li>"
        + m.DUREE_AVANT
        + "</li>"
        + m.CONSERVATION_AVANT
        + "</ul><h2>6. Vos droits</h2><p>"
        + m.DROITS_AVANT
        + "</p>"
    )


MENTIONS_D_AVANT = (
    "<p>… détaillés dans la politique de confidentialité."
    + " Chaque compte peut exporter et effacer ses propres données depuis son profil."
    + "</p>"
)


def _moteur(avec_base_0088: bool = False):
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        conn.execute(text("CREATE TABLE utilisateur (id INTEGER PRIMARY KEY)"))
        conn.execute(
            text(
                "CREATE TABLE telemetry_event (id INTEGER PRIMARY KEY, "
                "user_id INTEGER REFERENCES utilisateur(id), page VARCHAR NOT NULL, "
                "action VARCHAR NOT NULL DEFAULT 'view', detail VARCHAR, cree_le DATETIME NOT NULL)"
            )
        )
        conn.execute(text("CREATE INDEX ix_telemetry_event_page ON telemetry_event (page)"))
        conn.execute(text("CREATE TABLE config_site (cle VARCHAR PRIMARY KEY, valeur VARCHAR)"))
        conn.execute(text("INSERT INTO utilisateur (id) VALUES (7)"))
        conn.execute(
            text(
                "INSERT INTO telemetry_event (user_id, page, action, cree_le) VALUES "
                "(7, '/actualites', 'view', '2026-10-01 10:37:12.123456'), "
                "(NULL, '/tickets', 'view', '2026-10-01 11:02:59.000000')"
            )
        )
        conn.execute(
            text("INSERT INTO config_site (cle, valeur) VALUES (:c, :v)"),
            [
                {"c": "politique_confidentialite", "v": _politique_d_avant(avec_base_0088)},
                {"c": "mentions_legales", "v": MENTIONS_D_AVANT},
            ],
        )
    return m


def _texte(moteur, cle: str) -> str:
    with moteur.connect() as conn:
        return conn.execute(
            text("SELECT valeur FROM config_site WHERE cle = :c"), {"c": cle}
        ).scalar()


def test_la_colonne_d_identite_disparait_et_les_vues_restent():
    moteur = _moteur()
    _jouer(moteur)
    inspecteur = inspect(moteur)
    assert "user_id" not in {c["name"] for c in inspecteur.get_columns("telemetry_event")}
    assert inspecteur.get_foreign_keys("telemetry_event") == []
    assert "ix_telemetry_event_page" in {
        i["name"] for i in inspecteur.get_indexes("telemetry_event")
    }
    with moteur.connect() as conn:
        lignes = conn.execute(text("SELECT page, cree_le FROM telemetry_event ORDER BY page")).all()
    assert [(p, str(c)[:19]) for p, c in lignes] == [
        ("/actualites", "2026-10-01 10:00:00"),
        ("/tickets", "2026-10-01 11:00:00"),
    ]


def test_les_textes_servis_cessent_de_rattacher_la_mesure_au_compte():
    from app.seed.contenus_legaux import (
        DROITS_DEPUIS_LE_PROFIL,
        TELEMETRIE_BASE_LEGALE,
        TELEMETRIE_COLLECTE,
        TELEMETRIE_CONSERVATION,
    )

    moteur = _moteur()
    _jouer(moteur)
    politique = _texte(moteur, "politique_confidentialite")
    m = _module()
    for ancien in (m.COLLECTE_AVANT, m.CONSERVATION_AVANT, m.DROITS_AVANT, m.NAVIGATION_AVANT):
        assert ancien not in politique, ancien[:60]
    assert "(avec identifiant)" not in politique
    for nouveau in (
        TELEMETRIE_COLLECTE,
        TELEMETRIE_CONSERVATION,
        DROITS_DEPUIS_LE_PROFIL,
        TELEMETRIE_BASE_LEGALE + m.ANCRE_BASES,
    ):
        assert politique.count(nouveau) == 1, nouveau[:60]
    assert "exporter et effacer" not in _texte(moteur, "mentions_legales")


def test_une_base_legale_deja_posee_par_la_0088_n_est_pas_doublee():
    from app.seed.contenus_legaux import TELEMETRIE_BASE_LEGALE

    moteur = _moteur(avec_base_0088=True)
    _jouer(moteur)
    assert TELEMETRIE_BASE_LEGALE not in _texte(moteur, "politique_confidentialite")


@pytest.mark.parametrize("avec_base_0088", [False, True])
def test_la_migration_est_idempotente(avec_base_0088):
    moteur = _moteur(avec_base_0088)
    _jouer(moteur)
    une_fois = (_texte(moteur, "politique_confidentialite"), _texte(moteur, "mentions_legales"))
    _jouer(moteur)
    assert (_texte(moteur, "politique_confidentialite"), _texte(moteur, "mentions_legales")) == (
        une_fois
    )


def test_un_texte_reecrit_a_la_main_n_est_pas_touche():
    """Rien de reconnu : la page de l'instance garde la sienne, base légale comprise."""
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
