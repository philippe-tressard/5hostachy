"""Le verrou de bascule est posé — et relâché — sur les DEUX nœuds.

## L'incident (12/09/2026, 02:03 — split-brain en production)

La bascule nocturne a déplacé le rôle de rpi2 vers rpi1. Trois minutes plus tard,
`auto-deploy.sh` **sur rpi2** a déployé et démarré quatre conteneurs : les deux
nœuds servaient.

Les horodatages disent tout :

    02:00:01  bascule.sh démarre sur rpi2
    02:03:01  auto-deploy.sh (cron */5) lit `.active` sur rpi2 → « rpi2 »
              → il se croit actif → `docker compose up -d`
    02:04:11  bascule.sh écrit enfin `.active` = rpi1 sur rpi2

Soixante-dix secondes. La décision d'`auto-deploy` était **juste au regard de ce
qu'il pouvait lire** : `action_auto_deploy` rend « déployer » quand le rôle lu est
le sien, et c'est ce que le fichier disait encore.

## Pourquoi le verrou existait déjà et n'a pas protégé

`bascule.sh` pose `.bascule-lock` — et `action_auto_deploy` rend « attendre » dès
qu'il le voit, quel que soit le rôle. Le mécanisme était le bon.

🔴 **Mais le verrou n'était posé que sur le PEER.** Or le nœud exposé est celui
qui **bascule** : c'est lui dont le rôle est en train de changer, donc lui dont
`auto-deploy` peut lire un rôle périmé. Le nœud protégé était celui qui n'en avait
pas besoin.

C'est une asymétrie qu'aucun test ne pouvait voir : la fonction de décision est
pure et correcte, le script de bascule n'a pas de self-test, et l'écart n'apparaît
qu'à la seconde près, une nuit où un déploiement tombe dans la fenêtre.

## Ce que ce test vérifie

Que `bascule.sh` pose le verrou **localement** autant que sur le peer, et le
relâche localement partout où il le relâche sur le peer — chemins d'échec compris.

⚠️ Le second point compte autant que le premier : un rollback qui ne relâcherait
que le peer laisserait ce nœud verrouillé **à vie**, donc sans aucun déploiement,
en silence.
"""
from __future__ import annotations

import pathlib
import re

RACINE = pathlib.Path(__file__).resolve().parents[2] / "scripts"
BASCULE = RACINE / "exploitation" / "bascule.sh"
VERROU = RACINE / "lib" / "lib-verrou.sh"

#: Poser le verrou chez le voisin, et chez soi.
POSE_PEER = re.compile(r"touch\s+/opt/5hostachy/\.bascule-lock")
POSE_LOCAL = re.compile(r"touch\s+[\"']?\$REPO/\.bascule-lock")

#: Le relâcher, des deux côtés.
LIBERE_PEER = re.compile(r"rm\s+-f\s+/opt/5hostachy/\.bascule-lock")
LIBERE_LOCAL = re.compile(r"rm\s+-f\s+[\"']?\$REPO/\.bascule-lock")


def _source() -> str:
    return VERROU.read_text(encoding="utf-8")


def test_le_module_du_verrou_existe_et_porte_les_deux_gestes():
    """⚠️ Le cas zéro (`standards/04` §2). Module déplacé ou verrou renommé, et
    tous les contrôles ci-dessous vaudraient 0 == 0 — un vert sur rien."""
    assert VERROU.exists(), f"{VERROU} introuvable"
    src = _source()
    assert "verrou_poser()" in src and "verrou_liberer()" in src


def test_le_verrou_est_pose_sur_LES_DEUX_noeuds():
    """🔴 Le fait de l'incident : il n'était posé que sur le peer, et c'est le
    nœud qui BASCULE dont `auto-deploy` lit un rôle périmé."""
    src = _source()
    assert POSE_PEER.search(src), "le verrou n'est plus posé sur le peer"
    assert POSE_LOCAL.search(src), (
        "`verrou_poser` ne pose pas `.bascule-lock` sur LUI-MÊME — son propre "
        "auto-deploy peut démarrer les conteneurs pendant la bascule (12/09/2026)"
    )


def test_la_liberation_touche_LES_DEUX_noeuds():
    """Un chemin d'abandon qui ne libérerait que le peer laisserait ce nœud
    verrouillé à vie, donc sans aucun déploiement — et en silence."""
    src = _source()
    assert LIBERE_PEER.search(src) and LIBERE_LOCAL.search(src)


def test_le_verrou_du_PEER_ne_se_touche_que_dans_le_module():
    """🔴 Le geste BILATÉRAL est écrit une fois. Il l'était cinq fois dans
    `bascule.sh`, et c'est ce qui a permis à une moitié de rester asymétrique —
    chaque recopie est une occasion de n'en faire que la moitié.

    ⚠️ Un verrou posé LOCALEMENT n'est pas visé : `health-watch.sh` et
    `MaJ-Hostachy.sh` protègent le nœud sur lequel ils agissent, et c'est leur
    besoin réel. Confondre les deux gestes ferait crier ce contrôle sur du code
    sain — et un contrôle qui crie à tort finit désarmé."""
    fautifs = []
    for f in sorted(RACINE.rglob("*.sh")):
        if f == VERROU:
            continue
        code = (chr(10)).join(
            l for l in f.read_text(encoding="utf-8").splitlines()
            if not l.lstrip().startswith("#")
        )
        if POSE_PEER.search(code) or LIBERE_PEER.search(code):
            fautifs.append(f"{f.name} : touche au verrou du PEER — passer par `lib-verrou.sh`")
    assert not fautifs, "Verrou bilatéral manipulé hors du module :" + (chr(10) + "  ") + (
        chr(10) + "  "
    ).join(fautifs)


def test_tout_verrou_LOCAL_pose_est_relache_par_un_trap():
    """🔴 La règle la plus déployée, et `bascule.sh` était le seul à ne pas la
    suivre : `health-watch.sh` et `MaJ-Hostachy.sh` arment un `trap … EXIT` dès
    qu'ils posent le verrou. Lui le relâchait à la main sur cinq chemins — c'est
    exactement ce qui permet d'en oublier un, et une sortie imprévue
    (`set -e`, `kill`) ne l'aurait relâché sur aucun.

    Le verrou est désormais armé PAR la pose, dans le module."""
    sans_trap = []
    for f in sorted(RACINE.rglob("*.sh")):
        src = f.read_text(encoding="utf-8")
        code = (chr(10)).join(
            l for l in src.splitlines() if not l.lstrip().startswith("#")
        )
        if not POSE_LOCAL.search(code):
            continue
        if "trap" not in code:
            sans_trap.append(f"{f.name} : pose `.bascule-lock` sans armer de `trap`")
    assert not sans_trap, "Verrou local sans filet de libération :" + (chr(10) + "  ") + (
        chr(10) + "  "
    ).join(sans_trap)


def test_la_decision_d_auto_deploy_fait_PRIMER_le_verrou():
    """Le verrou ne sert que si la décision le regarde AVANT le rôle. C'est déjà
    le cas — ce test l'ancre, parce que c'est ce qui rend la pose suffisante."""
    src = (RACINE / "exploitation" / "auto-deploy.sh").read_text(encoding="utf-8")
    i_verrou = src.index('[ "${3:-}" = "oui" ] && { echo attendre; return; }')
    i_role = src.index('[ "$1" = "$2" ] && echo deployer || echo aligner')
    assert i_verrou < i_role, "le verrou doit primer sur le rôle dans action_auto_deploy"


def test_bascule_PASSE_bien_par_le_module():
    """Le module peut exister sans que personne l'emploie — ce serait le pire des
    deux mondes : un geste correct, et un script qui ne l'appelle pas."""
    src = BASCULE.read_text(encoding="utf-8")
    assert "lib-verrou.sh" in src
    assert "verrou_poser" in src and "verrou_liberer" in src
