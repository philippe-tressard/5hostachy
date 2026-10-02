"""Aucun module de `app/routers/` n'échappe à tous les tests — par leur NOM (#1569).

## Pourquoi

L'audit du 02/10/2026 (axe 5) relevait seize modules de `app/` qu'aucun fichier de
`tests/` ne nomme, dont deux routeurs, `annonces_hall_sources` et `tickets/suite_groupe` :
montés (`test_routeurs_montes`), jamais exercés. La passe de #1569 a ramené ce relevé à
ZÉRO ; ce contrôle empêche qu'il remonte en silence pour la partie qui expose des URL.

Un routeur est ce qu'un test oublie le plus facilement : l'import réussit, l'application
démarre, et les droits qu'il applique (401, 403, 404) ne sont vérifiés par personne.

## Ce que ce contrôle mesure — et ne mesure pas

Il mesure l'absence de **nom** : le nom du module (`crud`, `liees`…) doit paraître comme
mot entier dans au moins un fichier de `tests/`. C'est exactement la méthode du ticket
(`grep -rlw <nom> api/tests`).

⚠️ Il ne mesure PAS l'exécution : un module peut être nommé sans être exercé, ou exercé
par un autre routeur sans être nommé. Un plancher de couverture le dirait — `coverage`
n'est pas dans `requirements-dev.txt`, et l'ajouter est hors de ce lot. Ce contrôle est un
filet à grosses mailles, pas une mesure.

## Une exception se déclare

`EXCEPTIONS` : chemin relatif → raison. Une exception non écrite est un oubli qui ressemble
à une décision ; une exception qui cesse de servir (le module est nommé, ou a disparu) fait
ÉCHOUER le contrôle : la liste ne fait que baisser. Elle est vide aujourd'hui, et le reste
doit se tenir.
"""

from __future__ import annotations

import pathlib
import re

from tests.aides_sources import modules_app

TESTS = pathlib.Path(__file__).resolve().parent
CE_FICHIER = pathlib.Path(__file__).name

#: Les modules de `app/routers/` qu'aucun test ne nomme, et pourquoi on l'accepte.
#: Vide au 02/10/2026 — ne s'allonge pas : on écrit le test du routeur neuf.
EXCEPTIONS: dict[str, str] = {}

#: Sous ce nombre de fichiers de tests lus, la portée est cassée : le contrôle ne
#: mesurerait plus rien (cas zéro).
PLANCHER_TESTS = 100
PLANCHER_ROUTEURS = 50


def _corpus() -> str:
    """Tous les fichiers de tests — SAUF celui-ci, qui ne doit pas se nommer lui-même."""
    fichiers = [
        p
        for p in sorted(TESTS.glob("*.py"))
        if p.name != CE_FICHIER and "__pycache__" not in p.parts
    ]
    assert len(fichiers) >= PLANCHER_TESTS, (
        f"`tests/` ne rend que {len(fichiers)} fichier(s) (plancher {PLANCHER_TESTS}) : "
        "la portée a bougé, et ce contrôle ne mesure plus rien."
    )
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in fichiers)


def nomme(corpus: str, rel: str) -> bool:
    """Le nom du module (`routers/tickets/liees.py` → `liees`) paraît-il comme MOT entier ?"""
    nom = pathlib.PurePosixPath(rel).stem
    return re.search(rf"\b{re.escape(nom)}\b", corpus) is not None


def non_nommes(rels: list[str], corpus: str) -> list[str]:
    return [rel for rel in rels if not nomme(corpus, rel)]


def _routeurs() -> list[str]:
    modules = modules_app("routers", minimum=PLANCHER_ROUTEURS)
    return [m.rel for m in modules if not m.rel.endswith("/__init__.py")]


# ── Le témoin : le contrôle SAIT échouer ────────────────────────────────────


def test_temoin_un_module_que_personne_ne_nomme_est_releve():
    corpus = "from app.routers.alpha import router\nimport beta_utile"

    assert non_nommes(["routers/alpha.py", "routers/gamma.py", "routers/pkg/delta.py"], corpus) == [
        "routers/gamma.py",
        "routers/pkg/delta.py",
    ]


def test_temoin_le_nom_se_lit_comme_un_mot_entier():
    """`crud_extra` ne nomme pas `crud` : sans cela, une sous-chaîne suffirait."""
    assert not nomme("def test_crud_extra(): ...", "routers/crud.py")
    assert not nomme("monmodule_suite", "routers/suite.py")
    assert nomme("from app.routers.tickets import crud", "routers/tickets/crud.py")
    assert nomme("tickets/crud.py", "routers/tickets/crud.py")


def test_temoin_les_caracteres_du_nom_ne_sont_pas_des_motifs():
    #  Le point d'un nom n'est pas un joker : « axb » ne nomme pas « a.b ».
    assert not nomme("axb", "routers/a.b.py")
    assert nomme("un fichier a.b ici", "routers/a.b.py")


# ── Le contrôle réel ────────────────────────────────────────────────────────


def test_chaque_module_de_routeur_est_nomme_par_un_test():
    corpus = _corpus()

    orphelins = [rel for rel in non_nommes(_routeurs(), corpus) if rel not in EXCEPTIONS]

    assert not orphelins, (
        "Ces modules de `app/routers/` ne sont nommés par AUCUN fichier de `tests/` : "
        f"{orphelins}. Écrire le test du routeur — droits (401/403/404), cas nominal, cas "
        "limite — ou, si c'est vraiment voulu, déclarer l'exception avec sa raison."
    )


def test_une_exception_qui_ne_sert_plus_est_retiree():
    """La liste ne fait que baisser : un module nommé, ou disparu, sort des exceptions."""
    corpus = _corpus()
    existants = set(_routeurs())

    perimees = [rel for rel in EXCEPTIONS if rel not in existants or nomme(corpus, rel)]

    assert not perimees, (
        f"exception(s) à retirer de EXCEPTIONS (module nommé ou disparu) : {perimees}"
    )


def test_chaque_exception_porte_sa_raison():
    vides = [rel for rel, raison in EXCEPTIONS.items() if not raison.strip()]

    assert not vides, f"exception(s) sans raison : {vides}"


def test_cas_zero_les_routeurs_et_les_tests_sont_lus():
    assert len(_routeurs()) >= PLANCHER_ROUTEURS
    assert len(_corpus()) > 100_000
