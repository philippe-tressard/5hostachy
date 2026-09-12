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


# ── La PÉREMPTION du verrou : une seule définition (12/09/2026, #915) ─────────
#
# Le correctif du split-brain ferme la fenêtre de course. Il ne dit rien du cas
# où la bascule est TUÉE entre la pose et la libération — coupure, `kill -9`,
# gel (les trois sont documentés sur rpi2). Le verrou survit alors, et
# `auto-deploy` l'attendait INDÉFINIMENT : plus aucun déploiement, en silence.
#
# Trois lecteurs portaient leur propre notion de « orphelin », un quatrième n'en
# avait aucune, et deux des seuils se contredisaient au point de rendre C12
# structurellement muet. Ces tests ancrent l'unicité.
MODULE_VERROU = RACINE / "lib" / "lib-verrou.sh"

#  Les seuils que le dépôt ne doit plus écrire qu'une fois. Le motif attrape une
#  affectation, jamais une mention en commentaire — un commentaire qui RACONTE la
#  divergence supprimée est utile, et c'est le faux positif que l'audit du 12/09
#  avait déjà rencontré ailleurs.
SEUIL_RECOPIE = re.compile(r"^\s*(LOCK_MAX_AGE_S|LOCK_STALE_MIN)\s*=\s*[0-9]", re.M)


def test_le_seuil_de_peremption_n_est_ecrit_qu_une_fois():
    """🔴 `health-watch` effaçait le verrou à 900 s et C12 n'alertait qu'à 20 min :
    la fenêtre d'alerte était VIDE, le fichier disparaissant toujours cinq minutes
    avant de devenir signalable. Deux copies d'une même notion qui divergent sur
    le cas limite — le motif que ce dépôt connaît déjà.

    Une seule affectation est admise : `VERROU_STALE_S` dans le module."""
    recopies = []
    for f in sorted(RACINE.rglob("*.sh")):
        for m in SEUIL_RECOPIE.finditer(f.read_text(encoding="utf-8")):
            recopies.append(f"{f.name} : {m.group(0).strip()}")
    assert not recopies, (
        "Seuil de péremption recopié — il vit dans lib-verrou.sh (VERROU_STALE_S) "
        "et se DÉRIVE ailleurs :" + nl + "  " + (nl + "  ").join(recopies)
    )


def test_les_trois_lecteurs_du_verrou_CONSOMMENT_la_decision_partagee():
    """Le module peut définir la péremption sans que personne l'appelle — et
    c'était l'état d'avant, où chacun la réécrivait chez lui.

    ⚠️ `auto-deploy` est le cas qui compte : il ne testait que la PRÉSENCE du
    fichier, donc il n'avait aucune limite du tout."""
    for nom in ("auto-deploy.sh", "health-watch.sh"):
        src = (RACINE / "exploitation" / nom).read_text(encoding="utf-8")
        assert "lib-verrou.sh" in src, f"{nom} ne source pas le module du verrou"
        assert "verrou_recent" in src, f"{nom} ne consomme pas la décision partagée"
    #  C12 est porté par le MODULE depuis le 12/09 — on suit donc la chaîne
    #  entière, et non un nom dans un fichier : `check-reliability` appelle
    #  `verrou_verdicts`, qui consomme `verdict_verrou_orphelin`. Chercher le
    #  verdict dans l'orchestrateur casserait au premier découpage, sans qu'aucun
    #  comportement ait changé.
    orch = (RACINE / "exploitation" / "check-reliability.sh").read_text(encoding="utf-8")
    assert "VERROU_STALE_S" in orch, "check-reliability ne dérive pas le seuil partagé"
    assert "verrou_verdicts" in orch, "C12 n'est pas appelé"
    module = MODULE_VERROU.read_text(encoding="utf-8")
    assert "verrou_verdicts()" in module, "le contrôle C12 ne vit pas avec son objet"
    assert "verdict_verrou_orphelin" in module, "C12 n'observe pas la trace du nettoyage"


def test_C12_observe_l_ACTE_de_nettoyage_et_non_l_objet_efface():
    """🔴 Le retournement qui rend le contrôle capable de parler.

    `health-watch` SUPPRIME le verrou orphelin ; C12 ne peut donc pas le mesurer
    sur le fichier — il n'existe plus quand il regarde. Il lit la trace datée que
    le nettoyage laisse dans le journal, comme le point 13 du pré-check se vérifie
    par « Alerte envoyée » et non par « Email KO ».

    Le fait collecté doit donc venir du JOURNAL de health-watch."""
    collecte = (RACINE / "lib" / "lib-collecte.sh").read_text(encoding="utf-8")
    assert "hostachy-health-watch.log" in collecte, (
        "la collecte ne lit pas le journal de health-watch : sans sa trace, C12 "
        "mesure un fichier que health-watch vient d'effacer, et rend OK"
    )
    assert "orphelin_dernier=" in collecte
    #  Le cas zéro : journal absent → INCONNU, jamais 0 (`standards/04` §2).
    assert "orphelin_dernier=inconnu" in collecte, (
        "journal absent doit rendre INCONNU, pas un compte nul lu comme un vert"
    )


def test_la_peremption_S_ABSTIENT_quand_elle_ne_peut_pas_MESURER():
    """⚠️ La prudence va ici dans l'autre sens que pour `bascule_en_cours` : on
    déciderait de DÉMARRER des conteneurs. Un horodatage illisible doit donc
    rendre « récent » — conclure « périmé » sur une mesure absente rouvrirait le
    split-brain du 12/09 par la porte du contrôle."""
    src = MODULE_VERROU.read_text(encoding="utf-8")
    corps = src[src.index("verrou_recent()") :]
    #  Les trois abstentions : non numérique, nul, âge négatif.
    for garde in ("*[!0-9]*)", '-le 0 ]', '-lt 0 ]'):
        assert garde in corps, f"garde manquante dans verrou_recent : {garde}"
    assert "echo non" in corps, "verrou_recent ne conclut jamais à la péremption"


def test_le_verrou_est_pose_AVANT_la_premiere_action():
    """🔴 La coordination ne vaut que si le verrou est posé avant que le script
    touche à quoi que ce soit (#915, corrigé le 12/09/2026).

    Il l'était APRÈS l'arrêt des conteneurs du peer : entre les deux, le cron
    `auto-deploy` du peer pouvait passer, lire un rôle encore à son nom, et
    relancer les conteneurs qu'on venait d'arrêter. Le split-brain du 12/09 par
    une autre porte que celle qui a été constatée.

    ⚠️ Le test porte sur `run`, l'enveloppe par laquelle `bascule.sh` EXÉCUTE.
    Ce qui la précède peut lire — joignabilité, espace disque — mais pas agir.
    La frontière n'est pas le nombre de lignes, c'est le moment où le script
    cesse d'observer.

    ⚠️ Les définitions de fonctions sont ignorées : `rollback()` contient des
    actions et n'est appelée qu'après la pose, par un `trap`."""
    src = BASCULE.read_text(encoding="utf-8")
    #  On ne regarde que le corps PRINCIPAL : tout ce qui est indenté appartient
    #  à une fonction ou à un bloc conditionnel intérieur.
    lignes = src.splitlines()
    i_pose = next(
        (n for n, l in enumerate(lignes) if l.strip() == "verrou_poser"), None
    )
    assert i_pose is not None, "`verrou_poser` introuvable dans bascule.sh"

    avant = []
    for n, l in enumerate(lignes[:i_pose]):
        nu = l.strip()
        if nu.startswith("#") or not nu:
            continue
        #  `run "` en début d'instruction : l'exécution réelle.
        if re.match(r"^run\s+[\"']", nu):
            avant.append(f"ligne {n + 1} : {nu[:70]}")

    assert not avant, (
        "Action(s) exécutée(s) AVANT la pose du verrou — `auto-deploy` peut "
        "passer entre les deux et défaire ce qui vient d'être fait :"
        + (chr(10) + "  ")
        + (chr(10) + "  ").join(avant)
    )
