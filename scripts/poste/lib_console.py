#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe Tressard
# SPDX-License-Identifier: MIT
"""Sortie console UTF-8 — la console de ce poste est en cp1252.

🔴 **Sans cela, un contrôle PLANTE en affichant son propre verdict** : un « ✓ »
suffit. Il tournerait en CI (UTF-8) et échouerait là où il sert, dans le hook
pre-commit du poste Windows. Trouvé au premier lancement du self-test de
`verifier-fins-de-ligne.py` : la décision était juste, le tuyau cassé.

Ces cinq lignes étaient sur le point d'exister en **deux** exemplaires
(06/09/2026, `verifier-variables-shell.py`). Une règle recopiée ne se durcit
pas : elle vit ici, et nulle part ailleurs (`standards/02`).

Usage, avant tout `print` :

    from lib_console import console_utf8
    console_utf8()
"""
from __future__ import annotations

import sys


def console_utf8() -> None:
    """Force stdout/stderr en UTF-8, sans échouer si le flux ne le permet pas."""
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # flux redirigé, Python ancien
            pass
