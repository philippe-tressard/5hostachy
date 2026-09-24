"""Les liens `/api/…` du manuel mènent à une route MONTÉE de l'API (#1070).

Le volet front des liens du manuel est mesuré dans un navigateur
(`front/e2e/liens-manuel.spec.ts`) ; celui-ci confronte les liens vers l'API à
la liste des routes que FastAPI sert réellement — pas à un grep des routeurs,
qui trouverait aussi une route jamais incluse (`test_routeurs_montes.py`).

⚠️ Les routes se lisent dans le schéma OpenAPI, jamais dans `app.routes` : cette
version de FastAPI y garde des nœuds de routeurs opaques, sans `path` — la
première version de ce test n'y voyait AUCUNE route (`test_demarrage.py`).
Caddy retire le préfixe `/api` : `/api/manuel/pdf` est la route `/manuel/pdf`.
"""

from __future__ import annotations

import pathlib
import re

from app.main import app

MANUEL = pathlib.Path(__file__).resolve().parents[2] / "docs" / "manuel-utilisateur.html"


def test_chaque_lien_api_du_manuel_est_une_route_montee():
    liens = set(re.findall(r'href="/api(/[^"#?]*)', MANUEL.read_text(encoding="utf-8")))
    #  Cas zéro : le manuel propose le PDF à trois endroits.
    assert liens, "aucun lien /api/ lu dans le manuel — le motif ne lit plus rien"
    montees = set(app.openapi().get("paths", {}))
    assert len(montees) > 180, "schéma OpenAPI incomplet — la comparaison ne mesurerait rien"
    manquantes = sorted(liens - montees)
    assert not manquantes, f"lien(s) du manuel vers une route API absente : {manquantes}"
