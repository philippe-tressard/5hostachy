"""Chaque action GitHub de la CI est épinglée par son SHA (#1584, 04/10/2026).

POURQUOI — `uses: actions/checkout@v7` désigne un TAG, que son propriétaire peut
déplacer : la CI d'aujourd'hui n'est pas celle d'hier, et une action compromise
est exécutée avec les droits du workflow sans qu'aucun commit du dépôt ne change.
Un SHA ne se déplace pas. Dependabot (`github-actions`, `dependabot.yml`) suit les
actions épinglées par SHA tant que la version est écrite en commentaire : c'est ce
qui rend l'épinglage tenable.

FORME ATTENDUE : `uses: <propriétaire>/<dépôt>[/<chemin>]@<sha de 40 hexadécimaux>  # vX[.Y.Z]`.
Une action locale (`./.github/actions/…`) n'a pas de version et n'est pas jugée.
Le commentaire de version est exigé : un SHA seul ne se relit pas, et Dependabot
y lit la version qu'il met à jour.

Une exception se NOMME dans `EXCEPTIONS` avec sa raison, et une exception qui ne
sert plus fait échouer le test (même règle que `test_ci_installations_epinglees`).
"""

import re

from tests.conftest import racine_depot

RACINE = racine_depot()
WORKFLOWS = sorted((RACINE / ".github" / "workflows").glob("*.yml"))

#: `uses:` non épinglés tolérés : clé = la valeur de `uses:`, valeur = la raison.
#: Vide, et c'est voulu : elle ne fait que baisser.
EXCEPTIONS: dict[str, str] = {}

_USES = re.compile(r"^\s*-?\s*uses:\s*(?P<ref>\S+)(?P<reste>.*)$")
_EPINGLE = re.compile(r"^[\w.\-]+/[\w.\-]+(/[\w.\-/]+)?@[0-9a-f]{40}$")
_VERSION = re.compile(r"^\s*#\s*v\d+(\.\d+){0,2}\b")


def _usages():
    """(fichier, numéro, ref, reste de ligne) de chaque `uses:` hors commentaire entier."""
    for chemin in WORKFLOWS:
        for numero, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1):
            if ligne.strip().startswith("#"):
                continue
            m = _USES.match(ligne)
            if m:
                yield chemin.name, numero, m["ref"], m["reste"]


def test_les_workflows_sont_lus():
    """Cas zéro : un contrôle qui ne lit rien rend vert sans avoir regardé."""
    assert WORKFLOWS, "aucun workflow sous .github/workflows"
    assert len(list(_usages())) >= 8, "moins de huit `uses:` lus : le motif ne voit plus rien"


def test_chaque_action_est_epinglee_par_son_sha():
    fautifs = []
    for fichier, numero, ref, reste in _usages():
        if ref.startswith("./") or ref in EXCEPTIONS:
            continue
        if not _EPINGLE.match(ref):
            fautifs.append(f"{fichier}:{numero} `{ref}` — tag ou branche mobile, pas un SHA")
        elif not _VERSION.match(reste):
            fautifs.append(f"{fichier}:{numero} `{ref}` — SHA sans commentaire `# vX` (Dependabot)")
    assert not fautifs, "action(s) non épinglée(s) (#1584) :\n  " + "\n  ".join(fautifs)


def test_les_exceptions_servent_encore():
    refs = {ref for _, _, ref, _ in _usages()}
    inutiles = sorted(set(EXCEPTIONS) - refs)
    assert not inutiles, f"exception(s) sur un `uses:` qui n'existe plus : {inutiles}"
