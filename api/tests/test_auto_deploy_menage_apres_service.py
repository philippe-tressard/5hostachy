"""Rien ne se tient entre le marqueur d'images et le service (#1527).

Le 01/10/2026, l'actif a construit les images de v2.90.3, posé le marqueur
`.images-construites`, puis son auto-deploy est mort dans la purge du cache de
build — placée ENTRE le marqueur et `docker compose up -d`. Le marqueur disant
les images à jour, aucun passage suivant n'a relancé les conteneurs : v2.90.2
est restée servie, sans un mot, jusqu'à une reprise à la main.

Ce qui ne sert pas à servir — le ménage du cache — vient APRÈS la ligne datée
qui clôt le chemin (« Déployé », « Aligné », « Images reconstruites »).
"""

from __future__ import annotations

import pathlib
import re

AUTO_DEPLOY = pathlib.Path(__file__).resolve().parents[2] / "scripts/exploitation/auto-deploy.sh"

MARQUEUR = re.compile(r"^\s*marquer_images_construites\b")
#  La ligne datée s'écrit par `log` depuis #1587 (datée à l'écriture, et non
#  plus par `$LOG_DATE`, figé au démarrage).
CLOTURE = re.compile(r'\blog "(Déployé|Aligné|Images reconstruites):')
MENAGE = re.compile(r"^\s*borner_cache_build\s*$")


def _lignes() -> list[str]:
    return AUTO_DEPLOY.read_text(encoding="utf-8").splitlines()


def _ecarts(lignes: list[str]) -> list[str]:
    """Le ménage appelé entre un marqueur et la ligne qui clôt son chemin."""
    ecarts = []
    for i, ligne in enumerate(lignes):
        if not MARQUEUR.match(ligne):
            continue
        for j in range(i + 1, len(lignes)):
            if CLOTURE.search(lignes[j]):
                break
            if MENAGE.match(lignes[j]):
                ecarts.append(f"l. {j + 1}, après le marqueur de la l. {i + 1}")
        else:
            ecarts.append(f"marqueur de la l. {i + 1} sans ligne de clôture")
    return ecarts


def test_le_menage_vient_apres_le_service():
    lignes = _lignes()
    assert sum(bool(MARQUEUR.match(ligne)) for ligne in lignes) == 3, (
        "trois chemins posent le marqueur : rattrapage, déploiement, alignement"
    )
    assert sum(bool(MENAGE.match(ligne)) for ligne in lignes) == 3, (
        "chaque chemin qui construit borne aussi le cache"
    )
    assert _ecarts(lignes) == []


def test_le_controle_voit_l_ordre_du_01_10():
    """Cas zéro : l'ordre fautif, tel qu'il était en v2.90.3, est refusé."""
    fautif = [
        '    marquer_images_construites "$REPO" "$GIT_HASH"',
        "    borner_cache_build",
        "    docker compose up -d",
        '    log "Déployé: $GIT_HASH"',
    ]
    assert _ecarts(fautif) == ["l. 2, après le marqueur de la l. 1"]
