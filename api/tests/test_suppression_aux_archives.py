"""Supprimer définitivement ne s'offre qu'aux ARCHIVES (24/09/2026).

Question de l'utilisateur, devant la boîte « Supprimer définitivement » ouverte
depuis la liste des affaires : « c'est une suppression ou pas ? ». Ça l'était —
l'actualité entière, sans retour. `ux-patterns` §8 le disait déjà : archiver
dans la vue principale, supprimer depuis les Archives seulement. Les deux
rangées d'icônes ne le respectaient pas.

Le contrôle lit la condition qui ouvre le bloc du bouton : elle doit exiger
`archive`, jamais `!archive`.
"""
from __future__ import annotations

import pathlib
import re

import pytest

_COMPOSANTS = pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "components"


@pytest.mark.parametrize("fichier", ["ActionsTicket.svelte", "ActionsActualite.svelte"])
def test_la_corbeille_n_est_offerte_qu_aux_archives(fichier):
    source = (_COMPOSANTS / fichier).read_text(encoding="utf-8")
    i = source.find("Supprimer définitivement")
    assert i > 0, f"{fichier} : le bouton de suppression a disparu — ce contrôle ne mesure plus rien"
    conditions = re.findall(r"\{(?:#if|:else if) ([^}]*)\}", source[:i])
    assert conditions, f"{fichier} : la corbeille n'est gardée par aucune condition"
    derniere = conditions[-1]
    assert re.search(r"(?<!!)\barchive\b", derniere) and "!archive" not in derniere, (
        f"{fichier} : la corbeille s'offre hors des Archives (condition « {derniere} »)"
    )


@pytest.mark.parametrize("fichier", ["ActionsTicket.svelte", "ActionsActualite.svelte"])
def test_la_liste_offre_l_archivage(fichier):
    source = (_COMPOSANTS / fichier).read_text(encoding="utf-8")
    assert 'aria-label="Archiver"' in source, f"{fichier} : plus de 📦 dans la liste"
