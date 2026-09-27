"""Ce que l'écran de maintenance montre, et ce que le courriel de 06:00 en dit.

Deux constats du 27/09/2026, à l'origine de ce fichier :

1. **Les contrôles de fiabilité n'étaient pas sur l'écran.** `check-reliability.sh`
   (C1 à C30) n'écrivait que dans un journal et dans des courriels. Il rend
   désormais compte comme une tâche (`reliability`) — et ses WARN sans FAIL
   devaient se lire autrement qu'« À jour » ou « En échec » : c'est l'état
   `vigilance`.
2. **Ce que l'écran peignait en rouge ne partait chez personne.** Le courriel de
   06:00 ne regardait que la sauvegarde et la copie hors site. Il reprend
   maintenant les tâches manquantes ou en échec — sauf ce qu'un autre canal
   signale déjà, parce qu'un même fait ne doit jamais arriver deux fois.

Les décisions s'éprouvent sur les fonctions pures, horloge fixe, sans base.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.utils.sante_taches import (
    _PERIODICITE_ATTENDUE_H,
    DEJA_SIGNALE,
    STATUT_AVERTISSEMENT,
    _entree_sante,
    _sante_par_noeud,
    anomalies_a_signaler,
)

MAINTENANT = datetime(2026, 9, 27, 16, 0)


def ligne(noeud, heures_avant, statut="succes"):
    return SimpleNamespace(
        noeud=noeud, statut=statut, cree_le=MAINTENANT - timedelta(hours=heures_avant)
    )


def entree(tache, lignes):
    periode = _PERIODICITE_ATTENDUE_H[tache]
    return _entree_sante(
        tache, periode, _sante_par_noeud(tache, lignes, periode, "erreur", MAINTENANT)
    )


#  ── La vigilance : ni vert, ni rouge ─────────────────────────────────────────


def test_les_controles_de_fiabilite_sont_attendus_chaque_jour():
    """Leur battement est quotidien : son absence dit un contrôleur mort."""
    assert _PERIODICITE_ATTENDUE_H["reliability"] == 24


def test_des_warn_sans_fail_se_lisent_en_vigilance():
    e = entree("reliability", [ligne("rpi1", 1, STATUT_AVERTISSEMENT)])
    assert e["statut"] == "vigilance"


def test_un_rapport_propre_reste_a_jour():
    e = entree("reliability", [ligne("rpi1", 1)])
    assert e["statut"] == "ok"


def test_la_vigilance_est_moins_grave_qu_un_echec():
    """Le nœud en échec doit remonter, pas celui qui n'a que des WARN."""
    e = entree(
        "reliability",
        [ligne("rpi1", 1, STATUT_AVERTISSEMENT), ligne("rpi2", 2, "erreur")],
    )
    assert e["statut"] == "vigilance"
    assert e["noeud_en_retard"] == "rpi2"
    assert e["statut_en_retard"] == "erreur"


def test_un_controleur_muet_depuis_31_h_est_manquant():
    """24 h + 6 h de tolérance : au-delà, plus aucun des deux nœuds ne parle."""
    e = entree("reliability", [ligne("rpi1", 31), ligne("rpi2", 32)])
    assert e["statut"] == "manquante"


#  ── Le courriel de 06:00 : tout ce qui est rouge, une seule fois ──────────────


def _t(tache, statut, en_retard=None, noeud=None):
    return {
        "tache": tache,
        "statut": statut,
        "statut_en_retard": en_retard,
        "noeud_en_retard": noeud,
    }


def test_une_maintenance_en_echec_est_signalee():
    lignes = anomalies_a_signaler([_t("maintenance", "erreur")])
    assert any("maintenance" in x and "erreur" in x for x in lignes)
    assert "Administration › Maintenance" in lignes[-1]


def test_un_noeud_en_retard_est_nomme():
    lignes = anomalies_a_signaler([_t("telemetrie", "ok", "manquante", "rpi2")])
    assert any("telemetrie" in x and "rpi2" in x for x in lignes)


def test_rien_a_signaler_rien_n_est_ecrit():
    """Pas de ligne « Détail » seule : un courriel vide ne part pas."""
    assert anomalies_a_signaler([_t("maintenance", "ok"), _t("bascule", "en_cours")]) == []


def test_la_vigilance_ne_part_pas_par_ce_courriel():
    """Le digest quotidien de check-reliability la porte déjà."""
    assert anomalies_a_signaler([_t("reliability", "vigilance")]) == []


def test_ce_qu_un_autre_canal_signale_n_est_pas_repete():
    """Jamais deux courriels pour un même fait."""
    assert anomalies_a_signaler([_t("backup", "manquante")]) == []
    assert anomalies_a_signaler([_t("export_hors_site", "manquante")]) == []
    assert anomalies_a_signaler([_t("bascule", "erreur")]) == []
    assert anomalies_a_signaler([_t("reliability", "erreur")]) == []
    assert anomalies_a_signaler([_t("reliability", "ok", "manquante", "rpi2")]) == []


def test_ce_que_personne_d_autre_ne_voit_est_signale():
    """Les deux contrôleurs muets : C15 ne peut rien dire, il en fait partie."""
    assert anomalies_a_signaler([_t("reliability", "manquante")])
    #  Une bascule qui ne tourne plus du tout n'envoie pas d'alerte d'échec.
    assert anomalies_a_signaler([_t("bascule", "manquante")])


def test_chaque_exclusion_nomme_une_tache_reelle():
    """Une exclusion qui ne sert plus doit tomber, pas dormir.

    Une tâche renommée laisserait son entrée ici sans effet, et l'exclusion
    se lirait encore comme une décision.
    """
    connues = set(_PERIODICITE_ATTENDUE_H) | {"backup", "telemetrie"}
    orphelines = set(DEJA_SIGNALE) - connues
    assert not orphelines, f"exclusions sans tâche : {sorted(orphelines)}"
    for tache, (etats, canal) in DEJA_SIGNALE.items():
        assert etats and canal.strip(), f"« {tache} » : exclusion sans état ou sans canal"


def test_le_controle_de_6_h_lit_bien_les_taches():
    """Écrire la décision ne suffit pas : elle doit être BRANCHÉE.

    `collecter_problemes` est la seule liste des contrôles de 06:00 (et du bouton
    « Relancer le contrôle ») : on y cherche l'appel, dans l'arbre syntaxique.
    """
    src = (
        pathlib.Path(__file__).resolve().parents[1] / "app" / "utils" / "health_monitor.py"
    ).read_text(encoding="utf-8")
    fonction = next(
        n
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.FunctionDef) and n.name == "collecter_problemes"
    )
    appels = {
        n.func.id
        for n in ast.walk(fonction)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "problemes_taches" in appels
