"""Le déploiement standard de CoproConnect : des images, jamais un build (#1755).

Lot DI-3 du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
§4.10, règle 8, D13). `deploiement/standard/compose.images.yml` se pose PAR-DESSUS
le `docker-compose.yml` de la racine, qui reste la seule description des services :
une copie complète de la composition aurait divergé au premier volume ajouté.

Ce que ce test tient :

- chaque service que la racine construit est remplacé, et seulement eux ;
- sa construction est retirée (`build: !reset`) — sans quoi une image introuvable
  serait construite en silence sur la machine ;
- son image est celle que la CI publie (`images.yml`), à la version
  `COPROCONNECT_VERSION`, exigée ;
- l'archive jointe aux notes de version emporte tout ce que le mode d'emploi cite.

Le comportement de Compose sur ces fichiers (`!reset` compris) a été éprouvé sur
le standby le 08/10/2026 avec Compose 5.6 : `config` ne garde aucun `build`, et
refuse de lire sans version.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
SURCOUCHE = RACINE / "deploiement" / "standard" / "compose.images.yml"
LISEZMOI = RACINE / "deploiement" / "standard" / "LISEZMOI.md"
COMPOSE = RACINE / "docker-compose.yml"
IMAGES = RACINE / ".github" / "workflows" / "images.yml"
NOTES = RACINE / "scripts" / "ci" / "notes-de-version.sh"


class _Lecteur(yaml.SafeLoader):
    """PyYAML ne connaît pas les étiquettes de Compose : `!reset` se lit en marqueur."""


_Lecteur.add_constructor("!reset", lambda _l, _n: "!reset")


def _yaml(chemin: Path) -> dict:
    return yaml.load(chemin.read_text(encoding="utf-8"), Loader=_Lecteur)  # noqa: S506 — SafeLoader


def _construits() -> set[str]:
    return {nom for nom, s in _yaml(COMPOSE)["services"].items() if s.get("build")}


def test_chaque_service_construit_prend_son_image():
    surcouche = _yaml(SURCOUCHE)["services"]
    construits = _construits()
    assert len(construits) >= 4, "le relevé de docker-compose.yml est cassé"
    assert set(surcouche) == construits, (
        f"surcouche : {sorted(surcouche)} ; services construits par la racine : {sorted(construits)}"
    )
    registre = yaml.safe_load(IMAGES.read_text(encoding="utf-8"))["env"]["REGISTRE"]
    for nom, service in surcouche.items():
        assert service.get("build") == "!reset", f"{nom} : la construction n'est pas retirée"
        attendu = re.compile(
            rf"^{re.escape(registre)}/coproconnect-{re.escape(nom)}:\$\{{COPROCONNECT_VERSION:\?.+\}}$"
        )
        assert attendu.match(service["image"]), f"{nom} : image inattendue « {service['image']} »"


def test_l_archive_emporte_ce_que_le_mode_d_emploi_cite():
    script = NOTES.read_text(encoding="utf-8")
    #  Le tableau des FICHIERS : une première colonne qui porte un chemin. Le
    #  tableau des réglages (`COPROCONNECT_…`) n'en est pas un.
    cites = {
        c
        for c in re.findall(r"^\| `([^`]+)` \|", LISEZMOI.read_text(encoding="utf-8"), re.M)
        if re.search(r"[./]", c)
    }
    assert cites, "le tableau des fichiers du mode d'emploi est illisible"
    for fichier in cites:
        assert fichier in script, f"l'archive n'emporte pas {fichier}, que le mode d'emploi cite"
        assert (RACINE / fichier).exists(), f"{fichier} n'existe pas"


# ── La mise à jour nocturne (#1756) ──────────────────────────────────────────

MISE_A_JOUR = RACINE / "deploiement" / "standard" / "mise-a-jour.sh"


def _constante(nom: str) -> str:
    for ligne in MISE_A_JOUR.read_text(encoding="utf-8").splitlines():
        if ligne.startswith(f"{nom}="):
            return ligne.split("=", 1)[1].strip().strip('"')
    raise AssertionError(f"{nom} introuvable dans mise-a-jour.sh")


def test_la_mise_a_jour_vise_le_depot_le_registre_et_les_services_publies():
    from app.utils.plateforme import DEPOT_SOURCE

    assert DEPOT_SOURCE.endswith("/" + _constante("DEPOT")), (
        "le dépôt suivi n'est pas celui du source"
    )
    registre = yaml.safe_load(IMAGES.read_text(encoding="utf-8"))["env"]["REGISTRE"]
    assert _constante("REGISTRE") == registre
    assert set(_constante("SERVICES").split()) == _construits()


def test_la_mise_a_jour_sauvegarde_avant_de_toucher_au_service():
    """L'ordre est la promesse (D15) : rien ne s'arrête avant que tout soit prêt."""
    #  Le code seul : l'en-tête du script raconte le déroulé et en cite les gestes.
    texte = "\n".join(
        ligne
        for ligne in MISE_A_JOUR.read_text(encoding="utf-8").splitlines()
        if not ligne.lstrip().startswith("#")
    )
    ordre = [
        "pull --quiet",  # images tirées, service intact
        "stop api",  # premier geste qui coupe
        "integrity_check",  # la sauvegarde est vérifiée…
        'sed -i "s/^COPROCONNECT_VERSION=',  # … avant de poser la version
        "up -d --remove-orphans",
    ]
    positions = [texte.index(m) for m in ordre]
    assert positions == sorted(positions), dict(zip(ordre, positions))
    assert "COPROCONNECT_SAUVEGARDES absent" in texte, "pas de mise à jour sans sauvegarde"
