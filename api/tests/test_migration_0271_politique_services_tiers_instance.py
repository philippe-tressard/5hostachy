"""La 0271 nomme les services tiers de l'instance — seulement ce que la config prouve (#1585).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui
porte la politique du gabarit et la configuration d'une instance.
"""

from __future__ import annotations

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.seed.contenus_legaux import DEFAULT_LEGAL
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

MIGRATION = charger_migration("0271_politique_services_tiers_instance")
GABARIT = DEFAULT_LEGAL["politique_confidentialite"]
PASSAGES = ("DIFFUSION", "MODELE", "ENVOI", "RECEPTION")
#: Le gabarit porte d'autres « À RENSEIGNER » (éditeur, hébergeur…), que la 0170 a
#: remplis en production : on compte par rapport à lui, jamais en absolu.
AVANT = GABARIT.count("RENSEIGNER")

#: La configuration relevée sur l'instance : tous les faits prouvés.
INSTANCE = {
    "whatsapp_enabled": "1",
    "llm_fournisseur": "openai",
    "smtp_server": "ssl0.ovh.net",
    "imap_server": "ssl0.ovh.net",
}


def _moteur(page: str, cfg: dict[str, str]):
    m = moteur_memoire()
    with m.begin() as conn:
        for cle, valeur in {"politique_confidentialite": page, **cfg}.items():
            conn.execute(
                text("INSERT INTO config_site (cle, valeur) VALUES (:c, :v)"),
                {"c": cle, "v": valeur},
            )
    return m


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(MIGRATION, sens)()


def _politique(moteur) -> str:
    with moteur.connect() as conn:
        return conn.execute(
            text("SELECT valeur FROM config_site WHERE cle = 'politique_confidentialite'")
        ).scalar()


@pytest.mark.parametrize("nom", PASSAGES)
def test_chaque_passage_figure_une_fois_dans_le_gabarit(nom):
    """Au caractère près — sinon la migration ne trouverait rien, en silence."""
    assert GABARIT.count(getattr(MIGRATION, nom)) == 1


def test_une_instance_qui_prouve_tout_remplit_les_quatre_passages():
    moteur = _moteur(GABARIT, INSTANCE)
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    politique = _politique(moteur)
    assert politique.count("RENSEIGNER") == AVANT - 4
    for nom in ("DIFFUSION_ACTIVE", "MODELE_OPENAI", "ENVOI_OVH", "RECEPTION_OVH"):
        assert politique.count(getattr(MIGRATION, nom)) == 1


@pytest.mark.parametrize(
    ("cle", "valeur", "passage"),
    [
        ("whatsapp_enabled", "0", "DIFFUSION"),
        ("llm_fournisseur", "anthropic", "MODELE"),
        ("smtp_server", "smtp.exemple.fr", "ENVOI"),
        ("imap_server", "", "RECEPTION"),
    ],
)
def test_un_fait_que_la_config_ne_prouve_pas_reste_a_renseigner(cle, valeur, passage):
    moteur = _moteur(GABARIT, {**INSTANCE, cle: valeur})
    _jouer(moteur)
    politique = _politique(moteur)
    assert getattr(MIGRATION, passage) in politique
    assert politique.count("RENSEIGNER") == AVANT - 3


def test_sans_aucune_cle_seul_le_fournisseur_par_defaut_est_nomme():
    """Le défaut de l'application est OpenAI : c'est le seul fait qu'une base vide prouve."""
    moteur = _moteur(GABARIT, {})
    _jouer(moteur)
    politique = _politique(moteur)
    assert MIGRATION.MODELE_OPENAI in politique
    assert politique.count("RENSEIGNER") == AVANT - 1


def test_le_retour_arriere_rend_le_gabarit():
    moteur = _moteur(GABARIT, INSTANCE)
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _politique(moteur) == GABARIT


def test_une_page_reecrite_a_la_main_n_est_pas_touchee():
    reecrite = "<p>Texte rédigé depuis Admin › Légal, sans les passages d'origine.</p>"
    moteur = _moteur(reecrite, INSTANCE)
    _jouer(moteur)
    assert _politique(moteur) == reecrite
