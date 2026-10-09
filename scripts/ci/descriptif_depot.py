#!/usr/bin/env python3
"""Le descriptif que GitHub affiche est-il celui du dépôt ? (#1771)

## Pourquoi

Le descriptif « About » du dépôt est le premier texte public qu'on lit du
projet, et il ne vit pas dans le dépôt : il se règle dans GitHub. Le
09/10/2026, un jour après le passage à l'AGPL-3.0-or-later (#1726), il disait
encore « v1.0.0, Licence 5Hostachy (source-available… + clauses
commerciales) ». Aucun contrôle ne le lisait.

## Ce qu'il mesure

Le TEXTE est versionné dans `.github/descriptif-depot.txt` et jugé hors ligne
par `api/tests/test_gouvernance_depot.py` (licence nommée, aucune autre, aucune
version). Ce script ne juge rien de plus — il confronte deux faits à GitHub :

1. le descriptif affiché est, au caractère près, celui du fichier ;
2. la licence que GitHub détecte dans `LICENSE` est celle que `REUSE.toml`
   accorde (GitHub ne distingue pas `-or-later` : « AGPL-3.0 » pour
   « AGPL-3.0-or-later »).

Un descriptif modifié dans l'interface de GitHub fait donc échouer la PR
suivante, avec la commande qui réaligne : c'est le seul moment où l'écart se
voit, puisque rien dans le dépôt n'a bougé.

## Lecture

L'API publique de GitHub, avec le jeton du job s'il est fourni (`GH_TOKEN`,
lecture seule) — sans lui, la limite est de 60 appels par heure et par adresse.
Sur le poste, le rejeu passe l'expression `${{ … }}` telle quelle : elle est
ignorée, et `gh auth token` la remplace s'il est disponible.

Usage : python scripts/ci/descriptif_depot.py [--selftest]
    0 = GitHub affiche le descriptif et la licence du dépôt
    1 = écart
    2 = INCONNU (GitHub n'a pas répondu, ou le dépôt est illisible)
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from licences_spdx import licence_du_projet  # noqa: E402

RACINE = pathlib.Path(__file__).resolve().parents[2]
DESCRIPTIF = ".github/descriptif-depot.txt"
_SUFFIXES_SPDX = re.compile(r"-(?:only|or-later)$")


class Inconnu(Exception):
    pass


# ── Décision PURE ────────────────────────────────────────────────────────────


def confronter(
    declare: str, affiche: str | None, licence_detectee: str | None, licence_accordee: str
) -> list[str]:
    """Les écarts entre ce que le dépôt déclare et ce que GitHub affiche."""
    ecarts = []
    if (affiche or "").strip() != declare.strip():
        ecarts.append(
            f"GitHub affiche « {affiche or ''} »\n"
            f"    le dépôt déclare « {declare.strip()} » ({DESCRIPTIF})"
        )
    attendue = _SUFFIXES_SPDX.sub("", licence_accordee)
    if licence_detectee not in (licence_accordee, attendue):
        ecarts.append(
            f"GitHub détecte la licence « {licence_detectee or 'aucune'} » dans LICENSE, "
            f"REUSE.toml accorde « {licence_accordee} »"
        )
    return ecarts


# ── Lecture ──────────────────────────────────────────────────────────────────


def _depot() -> str:
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=RACINE,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as erreur:
        raise Inconnu(f"dépôt GitHub introuvable : {erreur}") from erreur
    trouve = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    if not trouve:
        raise Inconnu(f"l'origine « {url} » n'est pas un dépôt GitHub")
    return trouve.group(1)


def jeton_utilisable(valeur: str | None) -> str | None:
    """Le jeton tel quel, ou None s'il est vide ou n'est qu'une expression `${{ … }}` non résolue."""
    valeur = (valeur or "").strip()
    return valeur if valeur and "${{" not in valeur else None


def _jeton() -> str | None:
    jeton = jeton_utilisable(os.environ.get("GH_TOKEN"))
    if jeton:
        return jeton
    #  `gh auth token` RELIT `GH_TOKEN` : sans le retirer, il rendait
    #  l'expression même qu'on vient d'écarter, et GitHub répondait 401.
    env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
    try:
        sortie = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, env=env)
    except OSError:
        return None
    return jeton_utilisable(sortie.stdout) if sortie.returncode == 0 else None


def lire_github(depot: str) -> tuple[str | None, str | None]:
    """(descriptif, identifiant SPDX de la licence détectée) du dépôt."""
    requete = urllib.request.Request(
        f"https://api.github.com/repos/{depot}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "descriptif-depot"},
    )
    jeton = _jeton()
    if jeton:
        requete.add_header("Authorization", f"Bearer {jeton}")
    try:
        with urllib.request.urlopen(requete, timeout=20) as reponse:
            donnees = json.load(reponse)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erreur:
        raise Inconnu(f"GitHub n'a pas répondu pour {depot} : {erreur}") from erreur
    return donnees.get("description"), (donnees.get("license") or {}).get("spdx_id")


# ── Autotest ─────────────────────────────────────────────────────────────────


def selftest() -> int:
    echecs = 0

    def t(nom, obtenu, attendu):
        nonlocal echecs
        ok = obtenu == attendu
        echecs += not ok
        print(f"  {'OK ' if ok else 'KO '} {nom}" + ("" if ok else f" — {obtenu!r} ≠ {attendu!r}"))

    texte, agpl = "CoproConnect — sous AGPL-3.0-or-later.", "AGPL-3.0-or-later"
    t("identique : aucun écart", confronter(texte, texte, "AGPL-3.0", agpl), [])
    t("espaces de fin ignorés", confronter(texte + "\n", texte, "AGPL-3.0", agpl), [])
    t("descriptif modifié dans GitHub", len(confronter(texte, "v1.0.0", "AGPL-3.0", agpl)), 1)
    t("descriptif vide : un écart", len(confronter(texte, None, "AGPL-3.0", agpl)), 1)
    t("licence non détectée", len(confronter(texte, texte, None, agpl)), 1)
    t("NOASSERTION n'est pas une licence", len(confronter(texte, texte, "NOASSERTION", agpl)), 1)
    t("autre licence détectée", len(confronter(texte, texte, "MIT", agpl)), 1)
    t("GPL n'est pas AGPL", len(confronter(texte, texte, "GPL-3.0", agpl)), 1)
    t("identifiant exact accepté", confronter(texte, texte, "MIT", "MIT"), [])

    t("jeton fourni : gardé", jeton_utilisable(" abc "), "abc")
    t("jeton vide : aucun", jeton_utilisable(""), None)
    t("expression non résolue (rejeu) : aucun", jeton_utilisable("${{ github.token }}"), None)

    reuse = '[[annotations]]\npath = "**"\nSPDX-License-Identifier = "AGPL-3.0-or-later"\n'
    t("REUSE : motif racine lu", licence_du_projet(reuse), agpl)
    autre = '[[annotations]]\npath = ["a.json"]\nSPDX-License-Identifier = "MIT"\n'
    t(
        "REUSE : un autre motif n'est pas la licence du projet",
        licence_du_projet(autre + reuse),
        agpl,
    )
    for nom, illisible in (("sans motif racine", autre), ("vide", ""), ("TOML cassé", "[[")):
        try:
            licence_du_projet(illisible)
            t(f"REUSE {nom} : illisible", "lu", "ValueError")
        except ValueError:
            t(f"REUSE {nom} : illisible", "ValueError", "ValueError")

    print(f"{'TOUS OK' if not echecs else f'{echecs} ÉCHEC(S)'}")
    return 1 if echecs else 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    try:
        declare = (RACINE / DESCRIPTIF).read_text(encoding="utf-8")
        licence = licence_du_projet((RACINE / "REUSE.toml").read_text(encoding="utf-8"))
        depot = _depot()
        affiche, detectee = lire_github(depot)
    except (OSError, ValueError, Inconnu) as erreur:
        print(f"INCONNU — {erreur}")
        return 2

    ecarts = confronter(declare, affiche, detectee, licence)
    if not ecarts:
        print(f"OK — {depot} affiche le descriptif du dépôt, sous {detectee}")
        return 0
    print(f"ÉCART — ce que GitHub montre de {depot} n'est pas ce que le dépôt déclare :")
    for ecart in ecarts:
        print(f"  • {ecart}")
    print(
        "\nSi le fichier a raison, réaligner GitHub :\n"
        f'  gh repo edit {depot} --description "$(cat {DESCRIPTIF})"\n'
        f"Si le texte doit changer, le changer dans {DESCRIPTIF} (jugé par "
        "test_gouvernance_depot.py), puis réaligner."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
