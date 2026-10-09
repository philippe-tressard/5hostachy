"""L'application se nomme une fois, la base mise à part (DI-7b, #1781).

Sous PostgreSQL, une RÉPLIQUE de la base tourne en permanence sur le standby.
Les scripts qui comptaient « tout hostachy » pour dire « ce nœud est actif »
y auraient vu un split-brain sans fin, et un `docker compose stop` sans liste
aurait arrêté la réplique. `scripts/lib/lib-applicatifs.sh` nomme l'application ;
ce contrôle tient :

- ses listes suivent `docker-compose.yml` (tout service, sauf la base) ;
- aucun script ne recompte `docker ps … name=hostachy` ;
- aucun script n'arrête TOUT le compose, sauf déclaré ici avec sa raison.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from tests.conftest import scripts_shell_versionnes

RACINE = Path(__file__).resolve().parents[2]
MODULE = RACINE / "scripts" / "lib" / "lib-applicatifs.sh"
COMPOSE = yaml.safe_load((RACINE / "docker-compose.yml").read_text(encoding="utf-8"))

#: La base : le seul service qui n'est pas de l'application.
BASE = "postgres"

#: Les scripts qui arrêtent TOUT le compose, et pourquoi c'est voulu.
ARRETS_COMPLETS = {
    "scripts/exploitation/health-watch.sh": (
        "le failover ISOLE l'ancien actif : son application ET sa base, qui serait "
        "sinon un second primaire (DI-7b, la reconstruction en réplique suit)"
    ),
}


def _liste(nom: str) -> list[str]:
    m = re.search(rf'^{nom}="([^"]+)"', MODULE.read_text(encoding="utf-8"), re.M)
    assert m, f"`{nom}` n'est plus déclaré dans lib-applicatifs.sh"
    return m.group(1).split()


def _scripts() -> list[Path]:
    trouves = scripts_shell_versionnes()
    assert len(trouves) >= 50, "la portée des scripts a changé : le contrôle ne mesure plus rien"
    return trouves


def test_les_services_applicatifs_sont_ceux_du_compose_sauf_la_base():
    services = set(COMPOSE["services"]) - {BASE}
    assert set(_liste("SERVICES_APPLICATIFS")) == services
    assert BASE in COMPOSE["services"], "la base n'est plus dans le compose : revoir ce contrôle"


def test_les_conteneurs_suivent_les_services_au_meme_rang():
    attendus = [COMPOSE["services"][s]["container_name"] for s in _liste("SERVICES_APPLICATIFS")]
    assert _liste("CONTENEURS_APPLICATIFS") == attendus


def test_aucun_script_ne_recompte_tout_hostachy():
    fautes = [
        f"{p.relative_to(RACINE).as_posix()}:{n}"
        for p in _scripts()
        if p != MODULE
        for n, ligne in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if "filter name=hostachy" in ligne and not ligne.lstrip().startswith("#")
    ]
    assert not fautes, (
        "compter « tout hostachy » compte aussi la réplique de la base — employer "
        f"`compter_applicatifs` ou `$COMPTER_APPLICATIFS` : {fautes}"
    )


def test_aucun_arret_complet_du_compose_sans_raison():
    #  Un arrêt COMPLET : `stop|down` sans aucun service nommé derrière. Un arrêt
    #  ciblé (`stop postgres`, `stop $SERVICES_APPLICATIFS`) n'en est pas un.
    motif = re.compile(r"docker compose (stop|down)\s*($|[;&|>\"')]|2>)")
    vus = {
        p.relative_to(RACINE).as_posix()
        for p in _scripts()
        for ligne in p.read_text(encoding="utf-8").splitlines()
        if motif.search(ligne) and not ligne.lstrip().startswith("#")
    }
    assert vus == set(ARRETS_COMPLETS), (
        "un `docker compose stop` sans `$SERVICES_APPLICATIFS` arrête aussi la base — "
        f"le restreindre, ou le déclarer dans ARRETS_COMPLETS avec sa raison : "
        f"non déclarés {sorted(vus - set(ARRETS_COMPLETS))}, déclarés sans emploi "
        f"{sorted(set(ARRETS_COMPLETS) - vus)}"
    )
