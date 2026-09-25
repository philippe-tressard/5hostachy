"""Uvicorn ne tient PAS de journal d'accès (#1300, arbitré le 25/09/2026).

Uvicorn écrit une ligne par requête, avec l'adresse du client. Aujourd'hui elle vaut
celle de Caddy (`172.18.0.5`) : la ligne ne sert à rien. Le jour où l'API lira
l'adresse réelle (`--proxy-headers`, le reste de #1300), chaque ligne porterait
l'adresse IP d'un résident — une donnée personnelle, conservée dans les journaux
Docker (`CLAUDE.md` : « jamais de donnée personnelle dans une ligne de journal »).

Les erreurs restent journalisées : une exception non gérée passe par
`uvicorn.error`, que le point 6 du pré-check compte (`MOTIF_ERREURS_API`).
"""

from __future__ import annotations

import pathlib

_START = pathlib.Path(__file__).resolve().parents[1] / "start.sh"


def _lancement() -> str:
    lignes = [
        ligne
        for ligne in _START.read_text(encoding="utf-8").splitlines()
        if "uvicorn " in ligne and ligne.strip().startswith("exec")
    ]
    assert len(lignes) == 1, f"lancement d'uvicorn introuvable ou multiple dans start.sh : {lignes}"
    return lignes[0]


def test_uvicorn_est_lance_sans_journal_d_acces():
    assert "--no-access-log" in _lancement().split(), (
        "uvicorn tiendrait un journal d'accès : une ligne par requête, avec l'adresse du "
        "client — une donnée personnelle dès que l'API lira l'adresse réelle (#1300)."
    )
