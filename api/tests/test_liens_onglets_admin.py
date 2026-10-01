"""Un lien vers un onglet d'administration vise un onglet QUI EXISTE (01/10/2026).

## Pourquoi

Les onglets « Comptes en attente », « Commandes d'accès » et « Demandes profil »
ont fusionné en un seul, « À traiter ». Arbitré ce jour-là : **pas de
redirection des anciennes clés** — les liens émis ont été corrigés à la place
(`utils/rattachement_bailleur.py` envoyait `/admin?onglet=comptes`).

Ce choix n'est sûr que si rien ne laisse passer la clé suivante. Or une clé
inconnue ne casse rien de visible : `admin/+page.svelte` l'ignore et ouvre
l'onglet par défaut. Le destinataire d'une notification arrive donc sur un
autre écran que celui annoncé, sans une erreur nulle part.

## Ce qu'il vérifie

Toute écriture `/admin?onglet=<clé>` — notifications et modèles d'e-mail côté
API, liens côté front — nomme une clé de `ONGLETS`, la liste unique de la page.
"""

from __future__ import annotations

import pathlib
import re

from tests.aides_sources import modules_app

RACINE = pathlib.Path(__file__).resolve().parents[2]
PAGE_ADMIN = RACINE / "front" / "src" / "routes" / "(app)" / "admin" / "+page.svelte"
FRONT = RACINE / "front" / "src"

LIEN = re.compile(r"/admin\?onglet=([A-Za-z0-9_-]+)")


def _onglets_declares() -> set[str]:
    source = PAGE_ADMIN.read_text(encoding="utf-8")
    bloc = re.search(r"const ONGLETS = \[(.*?)\] as const", source, re.S)
    assert bloc, f"`const ONGLETS = [...] as const` introuvable dans {PAGE_ADMIN}"
    cles = set(re.findall(r"'([a-z_]+)'", bloc.group(1)))
    #  Cas zéro : une lecture qui ne rend rien validerait tout lien en silence.
    assert len(cles) >= 10 and "a_traiter" in cles, f"lecture de ONGLETS suspecte : {cles}"
    return cles


def _liens() -> list[tuple[str, str]]:
    trouves = [(f"api/app/{m.rel}", cle) for m in modules_app() for cle in LIEN.findall(m.source)]
    for chemin in sorted(FRONT.rglob("*")):
        if chemin.suffix in {".svelte", ".ts"} and chemin.is_file():
            rel = chemin.relative_to(RACINE).as_posix()
            trouves += [(rel, cle) for cle in LIEN.findall(chemin.read_text(encoding="utf-8"))]
    return trouves


def test_chaque_lien_vise_un_onglet_declare():
    onglets = _onglets_declares()
    liens = _liens()
    #  Cas zéro : trois liens connus (rattachement, import TC, audit des lots).
    assert len(liens) >= 3, f"{len(liens)} lien(s) `/admin?onglet=` trouvés : la lecture a changé"
    inconnus = [f"{chemin} → {cle}" for chemin, cle in liens if cle not in onglets]
    assert not inconnus, (
        "Lien vers un onglet d'administration qui n'existe pas — la page ouvrirait "
        "l'onglet par défaut, sans un mot :\n  " + "\n  ".join(inconnus)
    )
