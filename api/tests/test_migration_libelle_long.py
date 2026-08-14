"""La migration `0143` ne doit jamais écraser un bâtiment renommé à la main.

Pourquoi celle-ci est testée alors qu'aucune autre ne l'est : `0141` (les icônes)
ne remplissait que des champs **vides**, donc son pire cas était de ne rien faire.
`0143` réécrit une donnée **déjà affichée** — le nom d'un bâtiment, visible sur le
site, dans les e-mails et sur le document remis aux arrivants. Si sa condition de
non-écrasement était fausse, une copropriété ayant nommé ses bâtiments « Le Cèdre »
et « Les Tilleuls » les retrouverait « Bâtiment 1 » et « Bâtiment 2 » au prochain
déploiement, sans que rien ne le signale et sans retour en arrière possible.

La décision est isolée en fonction pure (`decider`) précisément pour être
vérifiable ici : elle ne l'est pas à travers `op.get_bind()`.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

CHEMIN = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "0143_libelle_long_des_batiments.py"
)


def _module():
    """Charge la migration par son chemin — son nom commence par un chiffre."""
    if not CHEMIN.is_file():
        pytest.fail(f"Migration introuvable : {CHEMIN.name}")
    spec = importlib.util.spec_from_file_location("migration_0143", CHEMIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_un_libelle_jamais_touche_passe_en_nom_long():
    long, court = _module().decider("Bât. 3", "Bât. 3", 3)
    assert long == "Bâtiment 3"
    assert court == "Bât. 3", "l'abrégé reste court — c'est lui que lisent les badges"


def test_un_batiment_renomme_n_est_jamais_reecrit():
    """Le cas qui justifie ce fichier."""
    for renomme in ("Le Cèdre", "Bâtiment A", "Bât 3", "bât. 3", "Bâtiment 3"):
        assert _module().decider(renomme, "Bât. 3", 3) is None, renomme


def test_un_abrege_saisi_par_l_administrateur_est_conserve():
    long, court = _module().decider("Bât. 2", "B2", 2)
    assert long == "Bâtiment 2"
    assert court == "B2", "l'abrégé choisi dans l'administration doit survivre"


def test_un_abrege_vide_est_rempli():
    for vide in (None, ""):
        long, court = _module().decider("Bât. 5", vide, 5)
        assert (long, court) == ("Bâtiment 5", "Bât. 5")


def test_la_migration_est_rejouable():
    """Deuxième passage : le libellé vaut déjà le nom long, donc plus rien à faire."""
    module = _module()
    long, court = module.decider("Bât. 7", "Bât. 7", 7)
    assert module.decider(long, court, 7) is None
