"""Santé des tâches planifiées — la DÉCISION, séparée de la requête.

Ce module ne connaît ni la base, ni FastAPI, ni le nœud qui répond : on lui
donne des lignes d'historique et une horloge, il rend un état par nœud et une
synthèse. C'est ce qui permet de l'éprouver par mutation, en quelques
millisecondes, sans conteneur — `api/tests/test_sante_taches_periodes.py`.

## Pourquoi il a été extrait (#542)

`routers/admin/exploitation.py` a franchi les 500 lignes en accueillant le
correctif des fausses alertes. La règle de modularité (rang 1) impose de
découper, et la coupure était déjà dessinée : d'un côté trois fonctions pures,
de l'autre des endpoints qui lisent la base. Le fichier n'a pas été coupé « à
l'endroit où ça dépassait », mais à la seule couture qui existait.

## Les deux notions que ce module tient séparées

**La période de la TÂCHE** — à quel rythme elle doit s'exécuter — et **la
période de chaque NŒUD** — à quel rythme *ce nœud-là* doit y participer. Les
confondre produit une fausse alerte quotidienne sur une infrastructure saine, et
c'est arrivé deux fois : le 09/08/2026 sur `bascule`, le 20/08/2026 sur
`backup` et `telemetrie`.
"""
from __future__ import annotations

_PERIODICITE_ATTENDUE_H = {
    "maintenance": 7 * 24,     # dimanche 03:00, sur les deux nœuds
    #  ⚠️ 48 h et non 24, parce que le rôle ALTERNE. `bascule.sh` sort
    #  immédiatement sur le standby (« Ce RPi n'est pas actif — rien à faire ») :
    #  seul le nœud actif agit, donc **chaque nœud n'opère qu'une nuit sur deux**.
    #  Attendre 24 h de chacun signalait un nœud sur deux comme « manquante »
    #  TOUS LES JOURS, sur une infrastructure parfaitement saine — constaté le
    #  09/08/2026, l'historique montrant l'alternance stricte 05→rpi1, 06→rpi2,
    #  07→rpi1, 08→rpi2.
    #
    #  C'est la même erreur que le seuil du cache de build le 06/08 : un seuil se
    #  règle sur le RÉGIME de ce qu'il surveille, pas sur la fréquence du cron
    #  (`standards/04-fiabilite-des-controles.md` §18). Avec la tolérance de 6 h,
    #  un nœud qui n'a rien fait depuis 54 h est en revanche réellement muet.
    "bascule": 48,             # 02:00, une nuit sur deux par nœud
    #  Copie hors site : lancée À LA MAIN depuis le poste, qui n'est pas
    #  allumé en permanence. Attendre 24 h ferait crier ce contrôle presque
    #  tous les jours, et une alerte qui crie tout le temps finit ignorée —
    #  c'est ainsi qu'un contrôle meurt (standards/07 §5). Une semaine est le
    #  rythme réellement tenable ; au-delà, l'absence redevient un signal.
    "export_hors_site": 7 * 24,
}
#
#  Même principe pour l'agrégation de TÉLÉMÉTRIE : sa propre table
#  `historique_telemetrie`, alimentée in-process par `run_telemetry_aggregation`.
#  Si ce job s'arrête, les statistiques d'usage deviennent silencieusement
#  fausses sans qu'aucun écran ne le signale — c'est le même besoin que pour la
#  maintenance et la sauvegarde, donc le même traitement plutôt qu'un régime à
#  part pour une troisième table.
_PERIODICITE_SAUVEGARDE_H = 24     # 03:00, tracée dans historique_sauvegarde
_PERIODICITE_TELEMETRIE_H = 24     # 02:00, tracée dans historique_telemetrie
#: 🔴 La période attendue de CHAQUE NŒUD, quand elle diffère de celle de la
#: tâche. Deux notions distinctes, et les confondre produit une fausse alerte
#: quotidienne sur une infrastructure saine.
#:
#: La sauvegarde et l'agrégation tournent sur l'ACTIF, chaque nuit — la tâche a
#: donc bien une période de 24 h. Mais le rôle ALTERNE : chaque nœud n'agit
#: qu'une nuit sur deux, et lui appliquer 24 h marque un nœud sur deux comme
#: « Exécution manquante » TOUS LES JOURS.
#:
#: ⚠️ Cette leçon était déjà écrite dix lignes plus haut, pour `bascule` :
#: « 48 h et non 24, parce que le rôle ALTERNE… constaté le 09/08/2026 ». Elle
#: n'avait pas été reportée sur ces deux tâches-là, faute qu'elles aient jamais
#: eu de sous-lignes par nœud. Le jour où elles en ont eu (#540), le défaut est
#: réapparu à l'identique — signalé à l'écran dans l'heure (#542).
#:
#: Une tâche absente de cette table est jugée sur sa propre période : c'est le
#: cas quand les deux nœuds l'exécutent vraiment chacun (maintenance).
_PERIODICITE_PAR_NOEUD_H = {
    "backup": 48,
    "telemetrie": 48,
}

_TOLERANCE_H = 6                   # marge avant de déclarer un retard


#  Gravité croissante : sert à choisir l'état d'une tâche qui s'exécute sur les
#  DEUX nœuds. C'est toujours le PIRE qui doit remonter — un nœud sain ne
#  compense pas un nœud muet, il le masque.
#: 🔴 LE STATUT QU'UN SCRIPT ÉCRIT AVANT DE TRAVAILLER (#488).
#:
#: L'écran lisait LES RAPPORTS et rien d'autre : il répondait donc à « ai-je un
#: compte rendu récent ? » quand la question posée est « la tâche a-t-elle
#: tourné ? ». Une tâche qui tourne et dont le rapport est refusé s'affichait
#: « À jour » sur le rapport précédent, puis « en retard » — deux jours de faux
#: vert puis un faux rouge, du 16 au 18/08/2026.
#:
#: `maintenance.sh` écrit désormais une ligne AVANT son travail. Si le rapport
#: de fin n'arrive pas, la dernière ligne du nœud reste `en_cours`, et l'écart
#: devient lisible en base.
STATUT_EN_COURS = "en_cours"

#: ⚠️ Au-delà de ce délai, un battement sans fin de course n'est plus « en
#: cours » : c'est un rapport PERDU. La maintenance la plus longue tient en
#: quelques minutes — deux heures sont larges, et le fait qu'elles soient larges
#: est le but : on ne veut pas signaler une exécution qui traîne.
#:
#: 🔴 Un battement de démarrage sans fin de course ne doit JAMAIS se lire comme
#: un succès (`standards/04` §4). Les deux états ci-dessous existent pour cela,
#: et ils sont DISTINCTS de « manquante » : la tâche a tourné, c'est sa remontée
#: qui est cassée. Confondre les deux enverrait chercher au mauvais endroit.
_DELAI_FIN_DE_COURSE_H = 2

#: `rapport_perdu` est plus grave qu'une erreur : une erreur, on la voit ; un
#: rapport perdu rend l'écran MUET, et c'est ce silence qui a duré deux jours.
_GRAVITE = {
    "ok": 0,
    "en_cours": 0,
    "erreur": 1,
    "rapport_perdu": 2,
    "manquante": 3,
    "aucune_execution": 4,
}


#: Combien de lignes remonter pour retrouver les deux nœuds d'une tâche.
#:
#: Le rôle alterne chaque nuit : une tâche qui ne tourne que sur l'ACTIF change
#: donc de nœud tous les jours, et deux exécutions suffisent en théorie. Vingt
#: laissent de la marge pour une tâche hebdomadaire ou un nœud qui a manqué
#: plusieurs tours — c'est justement celui-là qu'on cherche à voir.
_LIGNES_REMONTEES = 20


def _sante_par_noeud(
    tache: str, lignes, periode_h: float, statut_erreur, maintenant,
) -> dict:
    """L'état d'une tâche, **un sous-état par nœud** — pour TOUTES les tâches.

    ## Pourquoi cette fonction existe (#540)

    Signalé à l'écran le 20/08/2026, capture à l'appui : « Sauvegarde
    quotidienne » et « Agrégation télémétrie » n'affichaient qu'**une** sous-ligne
    là où « Bascule » et « Copie hors site » en affichaient deux.

    Ce n'était pas un défaut d'affichage. Les deux branches de calcul ne
    lisaient pas la même chose :

    | Tâches | Lecture | Nœuds possibles |
    |---|---|---|
    | maintenance, bascule, export | 20 dernières lignes, groupées par nœud | 2 |
    | sauvegarde, télémétrie | `.limit(1)` — **une seule ligne** | 1, toujours |

    🔴 La seconde branche ne pouvait **physiquement** pas montrer deux nœuds,
    quel que soit le contenu de la base. Or ces deux tables portent une colonne
    `noeud` indexée depuis la migration 0137, et ces tâches tournent sur l'actif
    — qui alterne chaque nuit. Les deux nœuds y sont donc, et l'écran n'en
    montrait qu'un.

    ⚠️ **Conséquence, et c'est le sujet de #488** : si un nœud cessait
    complètement de sauvegarder, l'écran continuerait d'afficher « À jour » avec
    le nœud de l'autre. Un nœud sain compenserait un nœud muet — exactement ce
    que les sous-lignes ont été introduites pour empêcher (#331).

    ⚠️ Le commentaire de la boucle historique attribuait ce manque à des tâches
    « qui n'enregistrent pas leur nœud ». C'était vrai le 11/08/2026 ; la colonne
    existe depuis, et la raison n'a pas été relue. Une explication juste à
    l'écriture devient un alibi quand ce qu'elle décrit a changé.

    ## Ce que la fonction rend

    `detail` (un état par nœud, trié), `recente` (la dernière exécution réelle,
    tous nœuds confondus) et `pire` (le nœud le plus dégradé). La synthèse porte
    la date de `recente` : retenir le pire ÉTAT est juste, lui emprunter sa DATE
    fait mentir la colonne « Dernier rapport » (#331, 13/08/2026).
    """
    lignes = list(lignes)
    if not lignes:
        return {}

    #  🔴 Les deux seuils se déduisent ICI, pas chez les appelants.
    #
    #  La recherche dans `_PERIODICITE_PAR_NOEUD_H` a d'abord vécu aux deux
    #  points d'appel : deux copies du même geste, donc deux occasions de
    #  diverger — et un test de mutation les a trouvées TOUTES DEUX aveugles,
    #  puisque les tests de cette fonction lui passent des seuils explicites.
    #  Rentrer la recherche dans la fonction supprime le câblage plutôt que de
    #  le tester (`standards/02` §1).
    periode_noeud_h = _PERIODICITE_PAR_NOEUD_H.get(tache, periode_h)

    def _etat(ligne, seuil_h):
        age_h = (maintenant - ligne.cree_le).total_seconds() / 3600
        #  🔴 Le battement de début se lit AVANT tout le reste : une tâche qui a
        #  démarré a TOURNÉ, quoi qu'en dise l'âge de son dernier rapport.
        #  L'ordre compte — tester « manquante » d'abord dirait « jamais
        #  exécutée » d'une tâche dont on a la trace du démarrage.
        if ligne.statut == STATUT_EN_COURS:
            statut = "en_cours" if age_h <= _DELAI_FIN_DE_COURSE_H else "rapport_perdu"
        elif age_h > seuil_h + _TOLERANCE_H:
            statut = "manquante"
        elif ligne.statut == statut_erreur:
            statut = "erreur"
        else:
            statut = "ok"
        return statut, round(age_h, 1)

    #  🔴 « inconnu » N'EST PAS UN NŒUD (#542).
    #
    #  Les lignes antérieures à la migration 0137 n'ont pas de `noeud`. Les
    #  regrouper sous « INCONNU » leur donnait une sous-ligne — donc l'apparence
    #  d'une troisième sonde — que RIEN ne pourra jamais rafraîchir : la colonne
    #  est renseignée à chaque écriture depuis. Elle restait donc « Exécution
    #  manquante » à jamais, et contaminait `pire`, d'où un badge « INCONNU en
    #  retard » permanent sur la synthèse.
    #
    #  ⚠️ Un avertissement permanent ne se lit plus (`standards/04` §18) — et le
    #  commentaire de `noeud_en_retard`, vingt lignes plus bas, le cite déjà.
    #  Ces lignes restent comptées pour la SYNTHÈSE : la tâche a bien tourné, on
    #  ne sait simplement pas où.
    par_noeud: dict = {}
    for ligne in lignes:
        cle = getattr(ligne, "noeud", None)
        if not cle:
            continue
        if cle not in par_noeud:
            par_noeud[cle] = ligne

    #  La SYNTHÈSE porte la dernière exécution réelle, nœud enregistré ou non,
    #  et se juge sur la période de la TÂCHE.
    plus_recente = max(lignes, key=lambda ligne: ligne.cree_le)
    statut_s, retard_s = _etat(plus_recente, periode_h)
    synthese = {
        "noeud": getattr(plus_recente, "noeud", None),
        "statut": statut_s,
        "portee": getattr(plus_recente, "portee", "applicative"),
        "derniere": plus_recente.cree_le,
        "retard_heures": retard_s,
    }

    #  Chaque NŒUD se juge sur SA période — une nuit sur deux pour les tâches
    #  qui ne tournent que sur l'actif.
    detail = []
    for noeud, ligne in sorted(par_noeud.items()):
        statut, retard = _etat(ligne, periode_noeud_h)
        detail.append({
            "noeud": noeud,
            "statut": statut,
            #  `portee` n'existe que sur `historique_maintenance` ; les deux
            #  autres tables n'ont qu'une portée, applicative.
            "portee": getattr(ligne, "portee", "applicative"),
            "derniere": ligne.cree_le,
            "retard_heures": retard,
        })
    return {
        "detail": detail,
        "synthese": synthese,
        #  Aucun nœud enregistré : pas de « pire nœud » à nommer.
        "pire": max(detail, key=lambda d: _GRAVITE.get(d["statut"], 0)) if detail else None,
    }


def _entree_sante(tache: str, periode_h: float, groupes: dict) -> dict:
    """Assemble l'entrée de réponse à partir des sous-états — une seule fois.

    Les deux branches composaient ce dictionnaire séparément, et c'est ainsi que
    `noeuds` a fini par porter deux formes (#538) : une liste d'objets d'un côté,
    une liste de chaînes de l'autre. Un assemblage unique rend la divergence
    impossible plutôt qu'improbable.
    """
    if not groupes:
        return {"tache": tache, "noeud": None, "noeuds": [], "noeud_enregistre": False,
                "statut": "aucune_execution", "derniere": None,
                "retard_heures": None, "periodicite_heures": periode_h,
                "noeud_en_retard": None, "statut_en_retard": None}
    detail, synthese, pire = groupes["detail"], groupes["synthese"], groupes["pire"]
    degrade = bool(pire) and _GRAVITE.get(pire["statut"], 0) > _GRAVITE.get(synthese["statut"], 0)
    return {
        "tache": tache,
        "noeud": synthese["noeud"],
        "noeuds": detail,
        #  Faux quand la dernière exécution est antérieure à 0137 : l'écran écrit
        #  alors « non enregistré » plutôt qu'un nom de nœud inventé.
        "noeud_enregistre": bool(synthese["noeud"]),
        "portee": synthese["portee"],
        "statut": synthese["statut"],
        "derniere": synthese["derniere"],
        "retard_heures": synthese["retard_heures"],
        "periodicite_heures": periode_h,
        #  Nommé seulement s'il est RÉELLEMENT plus grave que la dernière
        #  exécution : sinon l'écran afficherait un avertissement sur une
        #  infrastructure saine, et un avertissement permanent ne se lit plus
        #  (`standards/04-fiabilite-des-controles.md` §18).
        "noeud_en_retard": pire["noeud"] if degrade else None,
        "statut_en_retard": pire["statut"] if degrade else None,
    }


def _etat_tache_a_table_propre(
    tache: str, lignes_historique, periode_h: float, statut_erreur, maintenant,
) -> dict:
    """Santé d'une tâche qui a SA PROPRE table (sauvegarde, agrégation).

    ⚠️ Elle reçoit désormais **les N dernières lignes** et non la seule dernière
    (#540). Avec `.limit(1)`, cette branche ne pouvait physiquement montrer qu'UN
    nœud — quel que soit le contenu de la base — là où les tâches de
    `historique_maintenance` en montraient deux. Or ces tables portent une
    colonne `noeud` depuis la migration 0137, et ces tâches tournent sur l'ACTIF,
    qui alterne chaque nuit : les deux nœuds y sont.

    Le nœud est **lu en base**, jamais déduit ici. Jusqu'au 11/08/2026 on y
    mettait `noeud_courant()` — le nœud qui répond à CETTE requête — dans une
    colonne que le lecteur comprend comme « le nœud qui a exécuté la tâche ». Le
    rôle alternant, c'était faux une fois sur deux.

    Les lignes antérieures à 0137 restent `None`, donc « inconnu » — jamais une
    valeur inventée (`standards/04` : ne pas présenter un défaut comme une
    mesure).
    """
    return _entree_sante(
        tache, periode_h,
        _sante_par_noeud(tache, lignes_historique, periode_h, statut_erreur, maintenant),
    )
