"""Le plafond de clones Python tient, et son outil sait VRAIMENT en voir un (#1564).

Deux choses se vérifient ici, parce qu'un contrôle vert peut mentir :

1. **la décision** (`verdict`) — pure, sans outil : au-dessus du plafond, en
   dessous, égal, inconnu ;
2. **le cas zéro** (`standards/04` §2) — jscpd compte bien un clone planté.
   Sans lui, un `jscpd` qui ne lirait rien rendrait « 0 clone » et le plafond
   n'échouerait jamais : c'est la forme silencieuse du faux vert.

La mesure du dépôt lui-même est faite par le job `lint-backend`
(`python scripts/ci/clones_python.py`), pas ici : elle dépend d'un Node que les
tests unitaires n'ont pas à exiger.
"""

import pathlib
import shutil
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "scripts" / "ci"))
import clones_python as clones  # noqa: E402


def test_au_dessus_du_plafond_echoue():
    code, message = clones.verdict(clones.PLAFOND_CLONES + 1)
    assert code == 1 and "AJOUTÉE" in message


def test_en_dessous_du_plafond_echoue_aussi():
    """Sinon la marge libérée par une factorisation resservirait à un nouveau clone."""
    code, message = clones.verdict(clones.PLAFOND_CLONES - 1)
    assert code == 1 and "baisser PLAFOND_CLONES" in message


def test_egal_au_plafond_passe():
    assert clones.verdict(clones.PLAFOND_CLONES)[0] == 0


def test_mesure_impossible_est_inconnue_jamais_ok():
    code, message = clones.verdict(None)
    assert code == 2 and "INCONNU" in message


@pytest.mark.skipif(
    shutil.which("npx") is None, reason="Node absent : le cas zéro n'est pas mesurable"
)
def test_cas_zero_jscpd_voit_un_clone_plante(tmp_path):
    """Deux fichiers qui recopient la même fonction : l'outil DOIT en compter un."""
    corps = "\n".join(
        f"    resultat_{i} = valeur_{i} * coefficient_{i} + decalage_{i}" for i in range(12)
    )
    for nom in ("a.py", "b.py"):
        (tmp_path / nom).write_text(
            f"def calcul(valeur_0, coefficient_0):\n{corps}\n    return 1\n", "utf-8"
        )
    assert clones.mesurer(".", tmp_path) == 1
    #  Et un dossier sans clone en compte zéro : l'outil ne répond pas « 1 » à tout.
    (tmp_path / "b.py").write_text("def autre():\n    return 'rien de commun'\n", "utf-8")
    assert clones.mesurer(".", tmp_path) == 0
