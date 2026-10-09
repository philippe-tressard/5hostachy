"""La promotion d'une version sur `replica` (#1754, 08/10/2026).

Lot DI-2 du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
§4.10, règles 1 et 5, D11). Les répliques CoproFirst suivent `replica` ; une
version y passe par le workflow « Promotion », lancé à la main par l'auteur.

Ce que ce test tient, sur la forme du workflow :

- il ne se lance QU'À LA MAIN : jamais sur un push ni sur une PR — une version
  ne se promeut pas parce qu'elle a été fusionnée ;
- la saisie de l'auteur ne s'interpole dans aucun `run:` : elle passe par
  l'environnement et `promotion.sh` la valide (une saisie ne doit pas pouvoir
  s'exécuter) ;
- aucun droit par défaut ; l'écriture du dépôt ne sert qu'à avancer `replica`
  et publier les notes ;
- la décision vit dans `scripts/ci/promotion.sh`, et ses deux scripts portent un
  `--selftest` lancé par la CI.

La décision elle-même (refus d'une version sans tag, hors de `main`, ou qui ne
serait pas en avant de `replica`) est éprouvée par ce `--selftest`.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
WORKFLOW = RACINE / ".github" / "workflows" / "promotion.yml"
CI = RACINE / ".github" / "workflows" / "ci.yml"


def _flux() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_la_promotion_ne_se_lance_qu_a_la_main():
    flux = _flux()
    declencheurs = flux.get("on") or flux.get(True)
    assert set(declencheurs) == {"workflow_dispatch"}, declencheurs
    assert declencheurs["workflow_dispatch"]["inputs"]["version"]["required"] is True


def test_la_saisie_ne_s_interpole_dans_aucun_script():
    for nom, job in _flux()["jobs"].items():
        for etape in job["steps"]:
            run = etape.get("run", "")
            assert "${{" not in run, (
                f"{nom} › {etape.get('name')} interpole une expression dans son script"
            )


def test_droits_au_plus_juste():
    flux = _flux()
    assert flux["permissions"] == {}
    job = flux["jobs"]["promouvoir"]
    assert job["permissions"] == {"contents": "write", "checks": "read"}


def test_la_decision_vit_dans_un_script_eprouve_par_la_ci():
    texte = WORKFLOW.read_text(encoding="utf-8")
    for script in ("scripts/ci/promotion.sh", "scripts/ci/notes-de-version.sh"):
        assert (RACINE / script).exists(), script
        assert f"bash {script}" in texte, f"le workflow n'appelle pas {script}"
        assert re.search(
            rf"bash {re.escape(script)}\s+--selftest", CI.read_text(encoding="utf-8")
        ), f"{script} --selftest n'est lancé par aucun job de la CI"


def test_replica_n_avance_jamais_de_force():
    script = (RACINE / "scripts/ci/promotion.sh").read_text(encoding="utf-8")
    pousses = [
        ligne
        for ligne in script.splitlines()
        if "git push" in ligne and not ligne.lstrip().startswith("#")
    ]
    assert pousses, "promotion.sh ne pousse plus replica"
    assert not [
        p for p in pousses if "--force" in p or " -f " in p or "+" in p.split("origin", 1)[-1]
    ], pousses
