"""Hygiène du dépôt public — ce que l'audit du 02/10/2026 a trouvé, et qui revient seul.

Trois écarts de la même famille : un fichier que tout le monde lit et que rien ne
vérifie (#1582, #1601, #1607).

- `SECURITY.md` annonçait « 1.x suivie » pour un produit en 2.91 : la page que
  lit d'abord qui veut signaler une faille disait une version que personne ne
  sert. Il ne cite plus de version ; s'il en recite une, ce sera la majeure
  servie (`front/package.json`).
- `front/svelte_errors.txt`, un vidage d'erreurs en UTF-16, était versionné
  depuis le premier commit public. Les sorties d'outils se rangent hors du
  dépôt (`.gitignore`), jamais à la racine de `front/`.
- Les `.py` de `scripts/poste/` s'appellent par `python …` (ci.yml) : deux
  étaient en 100755, deux en 100644. Un mode se lit dans l'index, pas sur le
  poste — Windows avale `chmod` (`standards/08` §3).
- Un script exécutable sans `set -u` tait une variable vide : il continue avec
  un chemin tronqué. Les exceptions sont NOMMÉES, et la liste ne fait que
  baisser ; une exception qui ne sert plus fait échouer le test.
"""

import json
import re
import subprocess

from tests.conftest import racine_depot

RACINE = racine_depot()

#: Exécutables sans `set -u`, chacun avec sa raison. Ne fait que baisser.
SANS_SET_U = {
    "boot-role-guard.sh": "relais pur : une seule ligne, `exec` du vrai script",
    "api/start.sh": "démarrage du conteneur de production — à durcir dans un lot "
    "qui le redémarre en conditions réelles, pas en passant",
    "scripts/exploitation/MaJ-Hostachy.sh": "reprise en main manuelle — à durcir "
    "avec une répétition sur le standby",
    "scripts/installation/install-cloudflared.sh": "installation ponctuelle d'un nœud",
    ".claude/cloud/garde-git.sh": "hook de session cloud — lit des variables "
    "d'environnement facultatives",
}


def _index(*motifs: str) -> list[tuple[str, str]]:
    """(mode, chemin) des fichiers SUIVIS — l'index, pas le disque du poste."""
    sortie = subprocess.run(
        ["git", "ls-files", "-s", "--", *motifs],
        cwd=RACINE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [(ligne.split()[0], ligne.split("\t")[1]) for ligne in sortie.splitlines()]


def test_security_md_ne_cite_que_la_majeure_servie():
    version = json.loads((RACINE / "front" / "package.json").read_text(encoding="utf-8"))
    majeure = version["version"].split(".")[0]
    assert majeure.isdigit(), "version de front/package.json illisible — cas zéro"
    texte = (RACINE / "SECURITY.md").read_text(encoding="utf-8")
    citees = set(re.findall(r"\b(\d+)\.x\b", texte))
    assert citees <= {majeure}, (
        f"SECURITY.md cite la ou les versions {sorted(citees)}.x, le produit est en "
        f"{majeure}.x — ne pas recopier de version, ou citer celle qui est servie"
    )


def test_aucune_sortie_d_outil_versionnee_a_la_racine_du_front():
    fichiers = [c for _, c in _index("front/*.txt", "front/*.log") if c.count("/") == 1]
    assert not fichiers, (
        f"Sortie d'outil versionnée à la racine de front/ : {fichiers} — la retirer "
        "et l'ajouter au .gitignore"
    )


def test_les_py_de_poste_ne_sont_pas_executables():
    fichiers = _index("scripts/poste/*.py")
    assert len(fichiers) >= 3, "aucun .py de poste lu — le motif ne voit plus rien"
    executables = [c for mode, c in fichiers if mode != "100644"]
    assert not executables, (
        f"{executables} : un .py de poste s'appelle par `python …` — "
        "`git update-index --chmod=-x <fichier>`"
    )


def test_tout_executable_porte_set_u_ou_se_declare():
    executables = [c for mode, c in _index("*.sh") if mode == "100755"]
    assert len(executables) >= 10, "trop peu d'exécutables lus — cas zéro"
    sans = {
        c
        for c in executables
        if not re.search(r"^\s*set -[a-z]*u", (RACINE / c).read_text(encoding="utf-8"), re.M)
    }
    assert sans <= SANS_SET_U.keys(), (
        f"Exécutable sans `set -u` : {sorted(sans - SANS_SET_U.keys())} — "
        "ajouter `set -uo pipefail`, ou le déclarer dans SANS_SET_U avec sa raison"
    )
    perimees = SANS_SET_U.keys() - sans
    assert not perimees, f"Exception qui ne sert plus, à retirer de SANS_SET_U : {perimees}"
