"""Ce que les scripts d'exploitation ENVOIENT est-il ACCEPTÉ par l'endpoint ?

C'est la seule question qui vaille sur un rapport de maintenance, et personne ne
la posait. Deux moitiés existaient, et aucune ne se parlait :

| Contrôle | Ce qu'il vérifie |
|---|---|
| `lib-rapport.sh --selftest` | la charge utile est **bien construite** |
| `test_migrations.py`, la CI | l'endpoint **existe** et le schéma est valide |

Aucun ne confronte l'un à l'autre. Résultat, le **16/08/2026** :

    ⚠ Rapport applicative non enregistré sur http://localhost (HTTP 422)

Un caractère non échappé dans `details` produisait un JSON invalide. Le script
l'a signalé dans son journal, personne ne lisait ce journal, et l'écran
d'administration a affiché « Aucun rapport reçu » pendant **deux jours** sur une
maintenance qui avait parfaitement tourné (#301).

## Ce que ce fichier fait

Il APPELLE la vraie fonction bash `rapport_payload`, prend sa sortie, et la
valide contre le schéma Pydantic que l'endpoint emploie. Rien n'est recopié : le
script est la source pour la charge utile, le schéma est la source pour ce qui
est accepté.

⚠️ Il ne teste pas l'ENVOI — le réseau, la clé, le nœud actif. Cela reste
`standards/04` §11 : un autotest couvre la construction, jamais le tuyau. Mais
la construction est justement ce qui a cassé, et deux fois.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest
from pydantic import ValidationError

from app.routers.admin.rapports_scripts import RapportMaintenance

_RACINE = pathlib.Path(__file__).resolve().parents[2]
LIB = _RACINE / "scripts" / "lib" / "lib-rapport.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="bash absent : la construction ne peut pas être mesurée"
)


def _payload(*args: str) -> dict:
    """Appelle la VRAIE fonction bash et rend son JSON."""
    arguments = " ".join(f"'{a}'" for a in args)
    script = f"source '{LIB.as_posix()}'\nrapport_payload {arguments}\n"
    res = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    assert res.returncode == 0, f"`rapport_payload` a échoué : {res.stderr}"
    #  🔴 Un JSON illisible EST le défaut du 16/08 : on le dit ici, pas ailleurs.
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"la charge utile construite n'est pas un JSON valide : {exc}\n{res.stdout[:300]}"
        ) from exc


def test_la_bibliotheque_existe():
    """Cas zéro : sans elle, tout ce fichier passerait au vert sans rien mesurer."""
    assert LIB.is_file(), f"{LIB} introuvable — ce fichier ne mesure plus rien."


def test_un_rapport_NOMINAL_est_accepte():
    """Le cas de tous les dimanches. S'il casse, la maintenance devient muette."""
    charge = _payload(
        "maintenance", "rpi1", "applicative", "succes", "42",
        '{"images":"3","lignes_rotees":12}', "", "2026-08-16T03:00:00",
        "2026-08-16T03:02:14", "5", "1234",
    )
    RapportMaintenance(**charge)


def test_des_DÉTAILS_avec_guillemets_et_accents_passent():
    """🔴 Le défaut RÉEL du 16/08 : un caractère non échappé cassait le JSON.

    Le remède est `rapport_echapper`, et ce test l'exerce par le chemin qui a
    cassé — un texte qui contient ce qu'un journal d'exploitation contient
    vraiment : des guillemets, des accents, une barre oblique inverse.
    """
    script = (
        f"source '{LIB.as_posix()}'\n"
        'details=$(printf \'{"images":"%s"}\' "$(rapport_echapper "3 \\"images\\" purgées C:\\\\tmp")")\n'
        'rapport_payload maintenance rpi1 applicative succes 1 "$details" "" '
        '"2026-08-16T03:00:00" "2026-08-16T03:02:14"\n'
    )
    res = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    assert res.returncode == 0, res.stderr
    charge = json.loads(res.stdout)  # lève si l'échappement a manqué
    RapportMaintenance(**charge)


def test_une_ERREUR_multiligne_ne_casse_pas_la_charge():
    """Une erreur d'exploitation tient rarement sur une ligne.

    `rapport_echapper` remplace les sauts de ligne par des espaces : sans cela,
    un message d'erreur réel produirait un JSON invalide — et le rapport qui
    signale l'incident serait perdu **précisément** le jour de l'incident.
    """
    script = (
        f"source '{LIB.as_posix()}'\n"
        'msg=$(printf "ligne une\\nligne deux\\ttabulée")\n'
        'rapport_payload maintenance rpi2 applicative echec 3 null "$(rapport_echapper "$msg")" '
        '"2026-08-16T03:00:00" "2026-08-16T03:02:14"\n'
    )
    res = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    assert res.returncode == 0, res.stderr
    charge = json.loads(res.stdout)
    lu = RapportMaintenance(**charge)
    assert "\n" not in (lu.erreur or ""), "un saut de ligne a survécu à l'échappement"


def test_une_DATE_VIDE_est_refusee_et_c_est_su():
    """⚠️ Fragilité LATENTE du contrat, nommée plutôt que subie.

    `rapport_payload` interpole ses dates sans les tester : appelée avec des
    dates vides, elle produit `"cree_le":""`, et Pydantic répond **422** —

        Input should be a valid datetime or date, input is too short

    Les trois appelants (`maintenance.sh`, `bascule.sh`, `export-hors-site.sh`)
    renseignent tous leurs dates : le cas n'est **pas atteignable aujourd'hui**,
    vérifié. Ce test existe pour que le jour où un quatrième appelant apparaît,
    le contrat soit déjà écrit — et non découvert par un rapport perdu.

    Même famille que le document sans profil d'accès (#547) : un invariant tenu
    à un endroit et supposé à un autre, sans rien qui relie les deux.
    """
    charge = _payload("maintenance", "rpi1", "applicative", "succes", "1", "null", "", "", "")
    with pytest.raises(ValidationError):
        RapportMaintenance(**charge)
