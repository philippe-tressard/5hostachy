"""Synthèse du tableau de santé des tâches — `GET /admin/maintenance/sante`.

Extrait de `test_taches_planifiees.py` le 13/08/2026 : ce fichier avait franchi
500 lignes et le contrôle de modularité a refusé qu'il grossisse — la règle du
socle est « l'existant se découpe AU FIL DE L'EAU », donc quand on y touche.

La coupure suit une vraie frontière, pas une commodité : ce qui reste là-bas
porte le MODÈLE et les périodicités attendues, ce qui vient ici porte la
SYNTHÈSE rendue à l'écran. Les deux changent pour des raisons différentes.
"""
from datetime import datetime, timedelta

import pytest

from app.models.core import HistoriqueMaintenance


@pytest.fixture()
def session_memoire():
    """Base en mémoire, isolée. Aucun `app.db` n'est approché (règle d'or)."""
    from sqlmodel import Session, SQLModel, create_engine

    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        yield s

#  ─────────────────────────────────────────────────────────────────────────────
#  Cohérence du tableau de santé — signalé à l'écran par l'utilisateur le
#  11/08/2026 : « certaines tâches sont doublées car exécutées sur 2 nœuds,
#  d'autres pas ». Le tableau mélangeait deux unités de ligne (la tâche pour les
#  unes, le couple tâche+nœud pour les autres), si bien qu'une ligne unique
#  pouvait vouloir dire « une seule exécution » OU « une seule ligne pour deux ».
#  ─────────────────────────────────────────────────────────────────────────────

def _sante(session):
    from app.routers.admin.exploitation import maintenance_sante
    return maintenance_sante(session=session, _=None)


def test_la_sante_rend_une_seule_ligne_par_tache(session_memoire):
    """Une tâche exécutée sur les DEUX nœuds ne produit qu'une ligne.

    C'est ce qui rend le tableau lisible comme une synthèse : l'unité de ligne
    est la tâche, jamais le couple tâche+nœud. Le détail par nœud reste
    disponible dans `noeuds`, il n'est simplement plus une ligne.
    """
    maintenant = datetime.utcnow()
    for noeud in ("rpi1", "rpi2"):
        session_memoire.add(HistoriqueMaintenance(
            tache="bascule", noeud=noeud, statut="succes",
            cree_le=maintenant - timedelta(hours=2)))
    session_memoire.commit()

    lignes = [t for t in _sante(session_memoire)["taches"] if t["tache"] == "bascule"]
    assert len(lignes) == 1, (
        f"{len(lignes)} lignes pour la bascule — le tableau redevient un mélange "
        "de tâches et de couples tâche+nœud."
    )
    assert len(lignes[0]["noeuds"]) == 2, "Le détail par nœud a été perdu au passage."


def test_la_synthese_porte_la_derniere_execution_reelle(session_memoire):
    """La date affichée est celle de la dernière exécution, pas celle du retardataire.

    ⚠️ Ce test REMPLACE `test_l_etat_affiche_est_celui_du_noeud_le_moins_a_jour`,
    et le contrat change sciemment (#331). L'ancien exigeait que la ligne porte
    TOUT du pire nœud : son état **et sa date**. Or la colonne s'intitule
    « Dernier rapport ». Le 13/08/2026, la copie hors site annonçait ainsi
    « 6 août 06:40 » alors qu'elle avait tourné le 11 août à 16:57 sur l'autre
    nœud — cinq jours plus récente. La colonne mentait sur ce qu'elle promettait.

    Ce qui garantissait qu'un nœud sain ne masque pas un nœud muet était l'état
    de synthèse ; c'est désormais `noeud_en_retard` **et** la sous-ligne par nœud,
    toujours visible à l'écran. La propriété est conservée — elle a changé de
    porteur, ce que le test suivant vérifie.
    """
    maintenant = datetime.utcnow()
    recent = maintenant - timedelta(hours=2)
    session_memoire.add(HistoriqueMaintenance(
        tache="bascule", noeud="rpi2", statut="succes", cree_le=recent))
    session_memoire.add(HistoriqueMaintenance(        # muet depuis 20 jours
        tache="bascule", noeud="rpi1", statut="succes",
        cree_le=maintenant - timedelta(days=20)))
    session_memoire.commit()

    ligne = [t for t in _sante(session_memoire)["taches"] if t["tache"] == "bascule"][0]
    assert ligne["derniere"] == recent, (
        "La colonne « Dernier rapport » doit porter la dernière exécution RÉELLE "
        f"({recent}), pas celle du nœud le plus en retard ({ligne['derniere']})."
    )
    assert ligne["statut"] == "ok", "L'état de synthèse suit la dernière exécution."
    assert ligne["noeud"] == "rpi2", "Le nœud nommé est celui qui a fait cette exécution."


def test_un_noeud_muet_reste_signale_malgre_une_synthese_saine(session_memoire):
    """La propriété de sûreté, sous son nouveau porteur.

    C'est la moitié du contrat qu'il ne faut PAS perdre en corrigeant la date :
    une tâche morte sur un nœud depuis des semaines ne doit pas se lire « tout va
    bien » (défaut du 31/07/2026 — `maintenance.sh` ne tournait que sur l'actif,
    et le standby dérivait sans que rien ne le dise).
    """
    maintenant = datetime.utcnow()
    session_memoire.add(HistoriqueMaintenance(
        tache="bascule", noeud="rpi2", statut="succes",
        cree_le=maintenant - timedelta(hours=2)))
    session_memoire.add(HistoriqueMaintenance(
        tache="bascule", noeud="rpi1", statut="succes",
        cree_le=maintenant - timedelta(days=20)))
    session_memoire.commit()

    ligne = [t for t in _sante(session_memoire)["taches"] if t["tache"] == "bascule"][0]
    assert ligne["noeud_en_retard"] == "rpi1", (
        "Le nœud muet doit être nommé : sans lui, la synthèse saine du nœud actif "
        "referme exactement l'angle mort que ce tableau existe pour ouvrir."
    )
    assert ligne["statut_en_retard"] == "manquante"
    par_noeud = {n["noeud"]: n["statut"] for n in ligne["noeuds"]}
    assert par_noeud == {"rpi1": "manquante", "rpi2": "ok"}, (
        "Chaque nœud garde son propre état : c'est la sous-ligne toujours visible "
        f"qui porte l'alerte à l'écran, or elle est alimentée par ceci — {par_noeud}."
    )


def test_aucun_noeud_en_retard_quand_les_deux_sont_a_jour(session_memoire):
    """Pas d'avertissement sur une infrastructure saine.

    Le cas qui décide si l'avertissement sera lu ou ignoré : s'il s'affichait dès
    que les deux nœuds diffèrent d'une heure, il serait permanent, donc invisible
    (`standards/04-fiabilite-des-controles.md` §18 — un seuil se règle sur le
    régime de ce qu'il surveille).
    """
    maintenant = datetime.utcnow()
    for noeud, heures in (("rpi1", 2), ("rpi2", 26)):
        session_memoire.add(HistoriqueMaintenance(
            tache="bascule", noeud=noeud, statut="succes",
            cree_le=maintenant - timedelta(hours=heures)))
    session_memoire.commit()

    ligne = [t for t in _sante(session_memoire)["taches"] if t["tache"] == "bascule"][0]
    assert ligne["statut"] == "ok"
    assert ligne["noeud_en_retard"] is None, (
        "Un écart normal entre deux nœuds — le rôle alterne — ne doit pas produire "
        "un avertissement, sinon il en produira un tous les jours."
    )


def test_une_execution_sans_noeud_enregistre_n_en_invente_pas(session_memoire):
    """Une ligne antérieure à la migration 0137 n'a pas de nœud — et on ne le comble pas.

    Jusqu'au 11/08/2026 on y mettait le nœud qui répondait à la requête, donc le
    nœud ACTIF du moment et non celui qui avait exécuté la tâche. Le rôle
    alternant chaque nuit, la sauvegarde faite par rpi1 s'affichait « rpi2 » dès
    la bascule suivante : une valeur par défaut présentée comme une mesure.

    `backup` et `telemetrie` ont reçu la colonne le 12/08/2026 (#312), mais les
    lignes déjà en base restent `NULL` — aucun rétro-remplissage, personne ne
    sachant sur quel nœud elles ont tourné. C'est ce cas-là que ce test garde.
    """
    lignes = {t["tache"]: t for t in _sante(session_memoire)["taches"]}
    for tache in ("backup", "telemetrie"):
        assert lignes[tache]["noeud"] is None, (
            f"« {tache} » annonce le nœud {lignes[tache]['noeud']} alors qu'aucune "
            "ligne ne l'a enregistré — c'est le nœud qui répond, pas celui qui a agi."
        )
        assert lignes[tache]["noeud_enregistre"] is False, (
            f"« {tache} » se déclare traçable par nœud : l'écran affichera un nœud "
            "au lieu de « non enregistré »."
        )


def test_le_noeud_enregistre_est_restitue_tel_quel(session_memoire):
    """Le pendant du test précédent, et le seul qui prouve que #312 sert à quelque chose.

    Sans lui, retirer la colonne — ou cesser de la renseigner à l'écriture —
    laisserait tous les tests verts : le test ci-dessus est satisfait par
    l'absence de nœud, qui est justement ce qu'on vient de corriger. Un
    garde-fou qui ne peut échouer que dans un sens ne garde que ce sens.

    La valeur doit ressortir **telle qu'elle a été écrite**, jamais recalculée à
    la lecture : c'est toute la différence entre « le nœud qui a exécuté » et
    « le nœud qui répond aujourd'hui ».
    """
    from datetime import datetime

    from app.models.core import (
        HistoriqueSauvegarde, HistoriqueTelemetrie, StatutSauvegarde,
    )

    session_memoire.add(HistoriqueSauvegarde(
        declenchee_par="automatique", statut=StatutSauvegarde.reussie, noeud="rpi1",
        cree_le=datetime.utcnow(),
    ))
    session_memoire.add(HistoriqueTelemetrie(
        declenchee_par="cron", statut="succes", noeud="rpi2",
        cree_le=datetime.utcnow(),
    ))
    session_memoire.commit()

    lignes = {t["tache"]: t for t in _sante(session_memoire)["taches"]}
    for tache, attendu in (("backup", "rpi1"), ("telemetrie", "rpi2")):
        assert lignes[tache]["noeud"] == attendu, (
            f"« {tache} » devait restituer le nœud enregistré ({attendu}), "
            f"obtenu {lignes[tache]['noeud']!r}"
        )
        assert lignes[tache]["noeud_enregistre"] is True, (
            f"« {tache} » a un nœud en base mais se déclare non traçable : "
            "l'écran affichera « non enregistré » sur une donnée qui existe."
        )


def test_chaque_tache_attendue_apparait_exactement_une_fois(session_memoire):
    """Cas zéro du tableau : aucune tâche ne doit disparaître de la synthèse.

    Sans cette borne, une refonte qui déduplique trop rendrait un tableau vide —
    et un tableau vide se lit comme « rien à signaler ».
    """
    taches = [t["tache"] for t in _sante(session_memoire)["taches"]]
    assert len(taches) == len(set(taches)), f"doublons dans la synthèse : {taches}"
    for attendue in ("maintenance", "bascule", "export_hors_site", "backup", "telemetrie"):
        assert attendue in taches, f"« {attendue} » a disparu du tableau de santé"
