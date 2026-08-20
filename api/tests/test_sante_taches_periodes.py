"""Deux fausses alertes que l'écran a produites en production (#542).

Le 20/08/2026, après avoir donné leurs sous-lignes par nœud à « Sauvegarde
quotidienne » et « Agrégation télémétrie » (#540), l'écran en affichait **trois**
par tâche, dont deux fausses :

    ↳ INCONNU   Exécution manquante   12 août 2026, 03:00
    ↳ RPI1      Exécution manquante   19 août 2026, 04:00
    ↳ RPI2      À jour                20 août 2026, 04:00

## 🔴 Fausse alerte n° 1 — « INCONNU » n'est pas une sonde

Les lignes antérieures à la migration 0137 n'ont pas de `noeud`. Les regrouper
leur donnait l'apparence d'une troisième sonde que **rien ne pourra jamais
rafraîchir** : la colonne est renseignée à chaque écriture depuis. Cette
sous-ligne restait donc « Exécution manquante » à jamais, et contaminait le pire
nœud — d'où un badge « INCONNU en retard » permanent sur la synthèse.

## 🔴 Fausse alerte n° 2 — 24 h par nœud, sur une tâche qui alterne

La sauvegarde tourne sur l'ACTIF, chaque nuit. La tâche a donc bien une période
de 24 h, mais **chaque nœud n'agit qu'une nuit sur deux**. Lui appliquer 24 h
marque un nœud sur deux comme « manquante » tous les jours, sur une
infrastructure parfaitement saine.

⚠️ **Cette leçon était déjà écrite dans le fichier**, pour `bascule` : *« 48 h et
non 24, parce que le rôle ALTERNE… constaté le 09/08/2026 »*. Elle n'avait pas
été reportée sur ces deux tâches-là, faute qu'elles aient jamais eu de
sous-lignes. Le jour où elles en ont eu, le défaut est réapparu à l'identique.

## Pourquoi ces tests-ci, et pas un test d'endpoint

Les deux défauts sont des **décisions**, pas des chemins : quel seuil pour quelle
sonde, et qu'est-ce qui compte comme sonde. Ils s'éprouvent sur la fonction
pure, avec une horloge fixe — sans base, sans conteneur, en quelques
millisecondes.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.utils.sante_taches import (
    _PERIODICITE_PAR_NOEUD_H,
    _PERIODICITE_SAUVEGARDE_H,
    _sante_par_noeud,
)

#: Horloge FIXE. Sans elle, un test qui passe à 23 h 59 échoue à 0 h 01.
MAINTENANT = datetime(2026, 8, 20, 16, 30)


def ligne(noeud, jours_avant, statut="succes", heure=4):
    """Une exécution, telle que la lit `_sante_par_noeud`."""
    return SimpleNamespace(
        noeud=noeud,
        statut=statut,
        cree_le=datetime(2026, 8, 20, heure, 0) - timedelta(days=jours_avant),
    )


def _grouper(lignes, tache="backup", periode_h=24):
    """La tâche entre, les deux seuils s'en déduisent.

    ⚠️ Les tests passaient d'abord les deux seuils explicitement. Un test de
    mutation a montré qu'ils étaient alors **aveugles au câblage** : remplacer
    `_PERIODICITE_PAR_NOEUD_H.get(tache, …)` par `periode_h` aux deux points
    d'appel ne les faisait pas broncher. Passer par la tâche réelle éprouve la
    décision ET la table qui la porte.
    """
    return _sante_par_noeud(tache, lignes, periode_h, "echouee", MAINTENANT)


#  ── Fausse alerte n° 1 : « inconnu » n'est pas un nœud ──────────────────────


def test_une_ligne_sans_noeud_ne_cree_pas_de_sous_ligne():
    """Le cas exact vu à l'écran : une 3ᵉ sonde qui n'existe pas."""
    res = _grouper([ligne("rpi2", 0), ligne("rpi1", 1), ligne(None, 8)])
    assert [d["noeud"] for d in res["detail"]] == ["rpi1", "rpi2"], (
        "les lignes sans nœud enregistré forment une sonde fantôme"
    )


def test_une_ligne_sans_noeud_ne_contamine_pas_le_pire():
    """🔴 C'est elle qui produisait le badge « INCONNU en retard » permanent.

    Une sonde que rien ne peut rafraîchir reste éternellement en retard, et un
    avertissement permanent ne se lit plus (`standards/04` §18).
    """
    res = _grouper([ligne("rpi2", 0), ligne("rpi1", 1), ligne(None, 30)])
    assert res["pire"]["noeud"] != "inconnu"
    assert res["pire"]["statut"] == "ok", "un nœud sain est déclaré en retard"


def test_une_ligne_sans_noeud_compte_QUAND_MEME_pour_la_synthese():
    """⚠️ Elle n'est pas une sonde, mais la tâche a bien tourné.

    L'exclure de la synthèse ferait dire « aucune exécution » à un écran qui a
    des exécutions sous les yeux — le défaut inverse, et plus grave.
    """
    res = _grouper([ligne(None, 0)])
    assert res["synthese"]["derniere"] is not None
    assert res["synthese"]["statut"] == "ok"
    assert res["detail"] == [], "aucun nœud enregistré : aucune sous-ligne"


#  ── Fausse alerte n° 2 : la période de la TÂCHE ≠ celle d'un NŒUD ───────────


def test_un_noeud_qui_a_agi_avant_hier_n_est_pas_en_retard():
    """Le rôle alterne : chaque nœud n'agit qu'une nuit sur deux.

    rpi1 a sauvegardé il y a ~36 h. Avec 24 h, il était « manquante » — tous les
    jours, sur une infrastructure saine.
    """
    res = _grouper([ligne("rpi2", 0), ligne("rpi1", 1)])
    etats = {d["noeud"]: d["statut"] for d in res["detail"]}
    assert etats == {"rpi1": "ok", "rpi2": "ok"}, etats


def test_un_noeud_vraiment_muet_reste_signale():
    """⚠️ La tolérance ne doit pas devenir un aveuglement.

    Quatre jours sans agir dépassent largement les 48 h + 6 h : c'est le cas que
    les sous-lignes existent pour montrer.
    """
    res = _grouper([ligne("rpi2", 0), ligne("rpi1", 4)])
    etats = {d["noeud"]: d["statut"] for d in res["detail"]}
    assert etats["rpi1"] == "manquante"
    assert etats["rpi2"] == "ok"


def test_la_synthese_se_juge_sur_la_periode_de_la_TACHE():
    """Deux seuils, deux questions — et c'est le fond de ce lot.

    Aucun nœud n'a sauvegardé depuis 36 h. Chacun pris isolément est dans les
    clous (48 h), mais la TÂCHE, elle, aurait dû tourner cette nuit : la
    synthèse doit le dire.
    """
    res = _grouper([ligne("rpi1", 1), ligne("rpi2", 3)])
    assert res["synthese"]["statut"] == "manquante", (
        "la synthèse hérite du seuil par nœud : une tâche non exécutée passe inaperçue"
    )
    assert {d["statut"] for d in res["detail"]} == {"ok", "manquante"}


#  ── La déclaration elle-même ────────────────────────────────────────────────


def test_les_taches_qui_alternent_sont_declarees():
    """🔴 Le cas zéro de ce lot : sans la déclaration, rien ne change.

    `_PERIODICITE_PAR_NOEUD_H` est le seul endroit qui distingue « la tâche
    tourne toutes les 24 h » de « chaque nœud agit une nuit sur deux ». Vide ou
    amputée, le repli sur la période de la tâche ramène exactement la fausse
    alerte quotidienne.
    """
    for tache in ("backup", "telemetrie"):
        assert _PERIODICITE_PAR_NOEUD_H.get(tache) == 2 * _PERIODICITE_SAUVEGARDE_H, (
            f"{tache} tourne sur l'ACTIF et le rôle alterne : chaque nœud n'agit "
            "qu'une nuit sur deux."
        )



def test_une_tache_absente_de_la_table_garde_la_periode_de_la_tache():
    """La maintenance hebdomadaire tourne sur les DEUX nœuds, pas en alternance.

    Le repli sur la période de la tâche n'est donc pas un défaut de
    configuration : c'est le cas normal, et il ne faut surtout pas lui appliquer
    le doublement réservé aux tâches qui alternent.

    rpi2 n'a pas fait sa maintenance depuis huit jours (192 h). Avec la période
    de la tâche (168 h + 6 h de marge) il est signalé — c'est le comportement
    attendu. S'il héritait d'un doublement, il faudrait deux SEMAINES de silence
    pour qu'un nœud muet apparaisse.
    """
    res = _grouper([ligne("rpi1", 0), ligne("rpi2", 8)], tache="maintenance", periode_h=168)
    etats = {d["noeud"]: d["statut"] for d in res["detail"]}
    assert etats == {"rpi1": "ok", "rpi2": "manquante"}, etats



#  ── La FORME des sous-lignes, éprouvée à l'exécution ────────────────────────


#: Ce que l'écran lit sur chaque sous-ligne. Une clé absente n'explose pas : la
#: ligne s'affiche vide et se lit « rien à signaler » — le défaut de #538.
CLES_SOUS_LIGNE = {"noeud", "statut", "portee", "derniere", "retard_heures"}


def test_chaque_sous_ligne_porte_les_cles_attendues():
    """🔴 Reprend, à l'exécution, ce que l'analyse statique ne voit plus.

    `test_sante_taches_forme.py` inspectait les littéraux affectés à `noeuds`.
    Depuis l'assemblage unique, `noeuds` reçoit un NOM — il n'y a plus de
    dictionnaire à lire dans le source. La vérification n'a pas disparu : elle a
    changé de nature, et c'est ici qu'elle vit.
    """
    res = _grouper([ligne("rpi1", 0), ligne("rpi2", 1)])
    assert res["detail"], "cas zéro : sans sous-ligne, ce test ne mesure rien"
    for sous_ligne in res["detail"]:
        assert set(sous_ligne) == CLES_SOUS_LIGNE, sorted(set(sous_ligne))
        assert isinstance(sous_ligne["noeud"], str), (
            "une sous-ligne doit porter un OBJET, pas une chaîne (#538)"
        )
    assert set(res["synthese"]) == CLES_SOUS_LIGNE, (
        "la synthèse et les sous-lignes partagent la même forme : l'écran les "
        "rend avec le même composant"
    )
