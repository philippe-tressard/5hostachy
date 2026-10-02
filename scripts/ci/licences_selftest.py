"""Autotest des fonctions de décision de `licences_tierces.py` (`--selftest`).

Chaque cas est choisi pour échouer si la ligne qu'il éprouve disparaissait
(`standards/04` §46) : le OR qui offre un choix, le AND qui cumule, l'exception
qui ne couvre qu'une licence PRÉCISE, celle qui ne sert plus, et le cas zéro.
"""

from __future__ import annotations

import json
import pathlib
import tempfile

from licences_inventaire import Inconnu, paquets_npm
from licences_spdx import admise, identifiants, licence_python

ADMISES = frozenset({"MIT", "Apache-2.0", "BSD-3-Clause"})
EXC = (
    {"source": "bridge", "paquets": ("libsignal",), "licences": ("GPL-3.0",)},
    {"source": "bridge", "paquets": ("@img/sharp-*",), "licences": ("LGPL-3.0-or-later",)},
)


def lancer(confronter, exceptions_inutiles) -> int:
    cas: list[tuple[str, object, object]] = []

    def t(nom: str, obtenu, attendu) -> None:
        cas.append((nom, obtenu, attendu))

    t("admise — identifiant simple", admise("MIT", ADMISES), True)
    t("admise — copyleft refusé", admise("GPL-3.0", ADMISES), False)
    t("admise — OR : un choix suffit", admise("(MPL-2.0 OR Apache-2.0)", ADMISES), True)
    t("admise — AND : tout est exigé", admise("Apache-2.0 AND LGPL-3.0-or-later", ADMISES), False)
    t("admise — AND admis", admise("MIT AND BSD-3-Clause", ADMISES), True)
    t("admise — priorité AND sur OR", admise("GPL-3.0 AND MIT OR Apache-2.0", ADMISES), True)
    t("admise — WITH jamais d'office", admise("Apache-2.0 WITH LLVM-exception", ADMISES), False)
    t("admise — illisible refusé", admise("MIT | GPL (classifieurs multiples)", ADMISES), False)
    t("admise — parenthèse ouverte", admise("(MIT OR Apache-2.0", ADMISES), False)
    t("admise — vide refusé", admise("", ADMISES), False)
    t(
        "identifiants — sans opérateur ni WITH",
        sorted(identifiants("(ISC AND MIT) OR Apache-2.0 WITH LLVM-exception")),
        ["Apache-2.0", "ISC", "MIT"],
    )
    t(
        "python — License-Expression prime",
        licence_python("MIT", "BSD", []),
        ("MIT", "License-Expression"),
    )
    t(
        "python — champ court, alias",
        licence_python(None, "Apache License, Version 2.0", [])[0],
        "Apache-2.0",
    )
    t(
        "python — texte intégral ignoré",
        licence_python(
            None,
            "Copyright (c) X\nPermission is hereby granted",
            ["License :: OSI Approved :: MIT License"],
        )[0],
        "MIT",
    )
    t(
        "python — classifieurs multiples jamais admis",
        admise(licence_python(None, "", ["License :: A", "License :: B"])[0], ADMISES),
        False,
    )
    t("python — rien de lisible", licence_python(None, None, [])[0], "NON DÉTERMINÉE")

    gpl = [{"nom": "libsignal", "licence": "GPL-3.0"}, {"nom": "express", "licence": "MIT"}]
    e, tol, s = confronter("bridge", gpl, (), ADMISES)
    t("confronter — copyleft sans exception échoue", len(e), 1)
    e, tol, s = confronter("bridge", gpl, EXC, ADMISES)
    t("confronter — exception nominative couvre", (len(e), len(tol)), (0, 1))
    e, _, _ = confronter("bridge", [{"nom": "libsignal", "licence": "AGPL-3.0"}], EXC, ADMISES)
    t("confronter — licence changée : l'exception ne couvre plus", len(e), 1)
    e, _, _ = confronter("front", gpl, EXC, ADMISES)
    t("confronter — exception d'une autre source ne couvre pas", len(e), 1)
    e, _, s2 = confronter(
        "bridge", [{"nom": "@img/sharp-libvips-x", "licence": "LGPL-3.0-or-later"}], EXC, ADMISES
    )
    t("confronter — motif *", len(e), 0)
    t("inutiles — tout sert", exceptions_inutiles(EXC, s | s2, {"bridge"}), [])
    t(
        "inutiles — une exception qui ne sert plus échoue",
        len(exceptions_inutiles(EXC, s, {"bridge"})),
        1,
    )
    t("inutiles — source INCONNUE : rien conclu", exceptions_inutiles(EXC, set(), set()), [])
    _, _, s0 = confronter("bridge", [], EXC, ADMISES)
    t(
        "cas zéro — inventaire vide : toutes les exceptions sont inutiles",
        len(exceptions_inutiles(EXC, s0, {"bridge"})),
        2,
    )

    with tempfile.TemporaryDirectory() as d:
        verrou = pathlib.Path(d) / "package-lock.json"
        verrou.write_text(
            json.dumps({"lockfileVersion": 3, "packages": {"": {}}}), encoding="utf-8"
        )
        t("cas zéro — verrou sans paquet rend une liste vide", paquets_npm(verrou), [])
        verrou.write_text(json.dumps({"lockfileVersion": 1, "dependencies": {}}), encoding="utf-8")
        try:
            paquets_npm(verrou)
            t("verrou v1 — INCONNU", "aucune exception", "Inconnu")
        except Inconnu:
            t("verrou v1 — INCONNU", "Inconnu", "Inconnu")
        verrou.write_text(
            json.dumps({"lockfileVersion": 3, "packages": {"node_modules/a": {"version": "1"}}}),
            encoding="utf-8",
        )
        t(
            "verrou — licence absente déclarée comme telle",
            paquets_npm(verrou)[0]["licence"],
            "NON DÉCLARÉE",
        )

    ko = [(n, o, a) for n, o, a in cas if o != a]
    for n, o, a in ko:
        print(f"✗ {n} : obtenu {o!r}, attendu {a!r}")
    signe = "✗" if ko else "✓"
    print(f"{signe} autotest des licences tierces — {len(cas) - len(ko)}/{len(cas)} cas.")
    return 1 if ko else 0
