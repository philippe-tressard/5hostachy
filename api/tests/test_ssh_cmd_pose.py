"""Un script qui appelle une fonction SSH des modules pose `SSH_CMD` lui-même (#1781).

`lib-ssh-noeuds.sh` ne pose pas `SSH_CMD` : chaque script l'obtient par
`SSH_CMD=$(ssh_noeud_cmd N)`. `reconstruire-replique.sh` (v2.127.0) appelait
`role_base_pair` sans l'avoir posé — la commande se réduisait à l'adresse du pair, la
base du pair se lisait « illisible », et l'outil refusait toujours. Le contrôle
des variables sous `set -u` ne le voyait pas : la référence vit dans le module.

Ce test calcule, dans `scripts/lib/`, les fonctions qui se servent de `SSH_CMD`
— directement, ou en appelant l'une d'elles —, puis exige que tout script qui
en appelle une pose la variable.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import scripts_shell_versionnes

RACINE = Path(__file__).resolve().parents[2]
_POSE = "SSH_CMD=$(ssh_noeud_cmd"
_UNE_LIGNE = re.compile(r"^([a-z_][a-z0-9_]*)\(\)\s*\{(.*)\}\s*$")
_OUVERTURE = re.compile(r"^([a-z_][a-z0-9_]*)\(\)\s*\{")


def _sans_commentaires(texte: str) -> str:
    return "\n".join(li for li in texte.splitlines() if not li.lstrip().startswith("#"))


def corps_des_fonctions(texte: str) -> dict[str, str]:
    """Les fonctions définies EN DÉBUT DE LIGNE d'un module : nom → corps.

    Une ligne (`f() { …; }`) ou un bloc fermé par `}` seul en colonne 0. Les
    fonctions indentées (celles d'un autotest) ne sont pas des fonctions du module.
    """
    corps: dict[str, str] = {}
    nom, lignes = None, []
    for ligne in texte.splitlines():
        if nom is None:
            if m := _UNE_LIGNE.match(ligne):
                corps[m.group(1)] = m.group(2)
            elif m := _OUVERTURE.match(ligne):
                nom, lignes = m.group(1), []
        elif ligne == "}":
            corps[nom] = "\n".join(lignes)
            nom = None
        else:
            lignes.append(ligne)
    return corps


def fonctions_ssh() -> set[str]:
    corps: dict[str, str] = {}
    modules = [p for p in scripts_shell_versionnes() if p.parent.name == "lib"]
    for module in sorted(m for m in modules if m.name.startswith("lib-")):
        corps |= corps_des_fonctions(_sans_commentaires(module.read_text(encoding="utf-8")))
    ssh = {nom for nom, c in corps.items() if "$SSH_CMD" in c}
    while True:  # fermeture : une fonction qui en appelle une autre en dépend aussi
        plus = {
            nom
            for nom, c in corps.items()
            if nom not in ssh and any(re.search(rf"\b{f}\b", c) for f in ssh)
        }
        if not plus:
            return ssh
        ssh |= plus


def test_le_releve_trouve_les_fonctions_ssh():
    ssh = fonctions_ssh()
    for attendue in (
        "role_base_pair",
        "verrou_poser",
        "phases_base_postgresql",
        "ecrire_database_url_pair",
    ):
        assert attendue in ssh, (
            f"{attendue} devrait dépendre de SSH_CMD — le relevé ne mesure plus rien"
        )
    assert "role_base_locale" not in ssh


def test_tout_appelant_pose_ssh_cmd():
    ssh = fonctions_ssh()
    fautes = []
    for script in scripts_shell_versionnes():
        if "/lib/" in script.as_posix():
            continue
        code = _sans_commentaires(script.read_text(encoding="utf-8"))
        appels = sorted(f for f in ssh if re.search(rf"(^|[\s;&|(]){f}\b", code, re.M))
        if appels and _POSE not in code:
            fautes.append(f"{script.relative_to(RACINE).as_posix()} : {appels}")
    assert not fautes, (
        "ces scripts appellent une fonction SSH des modules sans poser "
        f"`SSH_CMD=$(ssh_noeud_cmd N)` : {fautes}"
    )
