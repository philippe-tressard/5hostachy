"""La 0260 crée le jour de la dernière visite, le remplit de ce que la base sait, et la politique le dit (#1629).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui
porte les tables qu'elle lit et la politique telle que la 0254 l'a laissée.
"""

from __future__ import annotations

from datetime import timedelta

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from app.seed.contenus_legaux import TELEMETRIE_CONSERVATION, TELEMETRIE_DERNIERE_VISITE
from app.utils import horloge
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

POLITIQUE_0254 = "<h2>5. Durée de conservation</h2><ul>" + TELEMETRIE_CONSERVATION + "</ul>"


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration("0260_derniere_visite"), sens)()


def _moteur(politique: str = POLITIQUE_0254):
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        conn.execute(text("CREATE TABLE config_site (cle VARCHAR PRIMARY KEY, valeur VARCHAR)"))
        conn.execute(
            text("INSERT INTO config_site (cle, valeur) VALUES ('politique_confidentialite', :v)"),
            {"v": politique},
        )
        conn.execute(
            text("CREATE TABLE utilisateur (id INTEGER PRIMARY KEY, opt_out_telemetrie BOOLEAN)")
        )
        conn.execute(
            text(
                "CREATE TABLE telemetry_event (id INTEGER PRIMARY KEY, user_id INTEGER, "
                "page VARCHAR, action VARCHAR, detail VARCHAR, cree_le DATETIME)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE presence_mensuelle (id INTEGER PRIMARY KEY, mois VARCHAR, user_id INTEGER)"
            )
        )
    return m


def _politique(moteur) -> str:
    with moteur.connect() as conn:
        return conn.execute(
            text("SELECT valeur FROM config_site WHERE cle = 'politique_confidentialite'")
        ).scalar()


def _visites(moteur) -> dict[int, str]:
    with moteur.connect() as conn:
        return dict(conn.execute(text("SELECT user_id, jour FROM derniere_visite")).all())


def test_la_table_ne_porte_qu_un_compte_et_un_jour():
    moteur = _moteur()
    _jouer(moteur)
    colonnes = {c["name"] for c in inspect(moteur).get_columns("derniere_visite")}
    assert colonnes == {"user_id", "jour"}


def test_le_remplissage_lit_les_evenements_puis_la_presence_jamais_un_refus():
    moteur = _moteur()
    il_y_a_40_jours = horloge.aujourd_hui() - timedelta(days=40)
    with moteur.begin() as conn:
        for ident, refus in [(1, 0), (2, 0), (3, 1), (4, 0)]:
            conn.execute(
                text("INSERT INTO utilisateur (id, opt_out_telemetrie) VALUES (:i, :r)"),
                {"i": ident, "r": refus},
            )
        #  1 : deux évènements, le plus récent l'emporte.
        for quand in ("2026-09-20 10:00:00", "2026-09-28 18:30:00"):
            conn.execute(
                text("INSERT INTO telemetry_event (user_id, page, cree_le) VALUES (1, '/', :q)"),
                {"q": quand},
            )
        #  3 a refusé : rien.
        conn.execute(
            text(
                "INSERT INTO telemetry_event (user_id, page, cree_le) VALUES (3, '/', '2026-09-28')"
            )
        )
        #  2 n'a plus que sa présence, il y a plus d'un mois : le dernier jour de ce mois-là.
        conn.execute(
            text("INSERT INTO presence_mensuelle (mois, user_id) VALUES (:m, 2)"),
            {"m": il_y_a_40_jours.strftime("%Y-%m")},
        )
        #  1 a aussi une présence : les évènements, plus précis, priment.
        conn.execute(text("INSERT INTO presence_mensuelle (mois, user_id) VALUES ('2026-09', 1)"))
    _jouer(moteur)
    visites = _visites(moteur)
    assert set(visites) == {1, 2}
    assert visites[1] == "2026-09-28"
    #  Une borne HAUTE (fin du mois), jamais au-delà de la veille des 30 jours d'évènements :
    #  un compte n'est jamais dit dormant à tort.
    assert visites[2] <= (horloge.aujourd_hui() - timedelta(days=31)).isoformat()
    assert visites[2].startswith(il_y_a_40_jours.strftime("%Y-%m"))


def test_le_paragraphe_suit_la_conservation_une_seule_fois():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    texte = _politique(moteur)
    assert texte.count(TELEMETRIE_DERNIERE_VISITE) == 1
    assert TELEMETRIE_CONSERVATION + TELEMETRIE_DERNIERE_VISITE in texte


def test_un_texte_reformule_a_la_main_n_est_pas_touche():
    reformule = "<p>Notre politique, réécrite par l'administrateur.</p>"
    moteur = _moteur(reformule)
    _jouer(moteur)
    assert _politique(moteur) == reformule


def test_le_retour_arriere_defait_les_deux():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _politique(moteur) == POLITIQUE_0254
    assert "derniere_visite" not in inspect(moteur).get_table_names()
