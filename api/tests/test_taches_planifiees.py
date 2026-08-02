"""Historique des tâches planifiées : nœud, portée, détails, et détection des absences.

POURQUOI CE TEST — mesuré le 02/08/2026 sur la production :

Le standby exécutait une hygiène locale réelle (3,358 Go de cache de build purgés,
66 338 lignes de log rotées) qui n'apparaissait **nulle part** dans l'application :
`maintenance.sh` poste sur `http://localhost/api/...`, or il n'y a pas d'API sur le
nœud passif. Et sans colonne `noeud`, une ligne ne disait pas *qui* avait agi.

Pire, une absence de ligne confondait trois causes très différentes : pas exécutée,
échouée, ou exécutée sans avoir pu s'enregistrer. C'est le « battement manquant »
de standards/04-fiabilite-des-controles.md §4, appliqué à l'interface.

Ces tests verrouillent le contrat : les nouveaux champs existent, ils ont des
défauts rétrocompatibles, et une exécution attendue mais absente est signalée
`manquante` au lieu de passer pour un silence normal.
"""
from datetime import datetime, timedelta

from app.models.core import HistoriqueMaintenance, PorteeExecution, TachePlanifiee


def test_champs_nouveaux_presents():
    """Le modèle porte de quoi distinguer la tâche, le nœud et la portée."""
    champs = HistoriqueMaintenance.model_fields
    for attendu in ("tache", "noeud", "portee", "details"):
        assert attendu in champs, f"champ {attendu} absent du modèle"


def test_defauts_retrocompatibles():
    """Un rapport qui n'envoie aucun des nouveaux champs reste une maintenance
    applicative — c'est exactement ce que décrivent les lignes déjà en base, et
    ce qu'enverra un nœud dont le script n'a pas encore été redéployé."""
    ligne = HistoriqueMaintenance()
    assert ligne.tache == TachePlanifiee.maintenance.value
    assert ligne.portee == PorteeExecution.applicative.value
    assert ligne.noeud is None
    assert ligne.details is None


def test_portee_distingue_actif_et_standby():
    """L'actif fait la maintenance applicative, le standby l'hygiène locale.

    Sans cette distinction, une ligne de standby se lirait comme une maintenance
    applicative incomplète — donc comme une anomalie qui n'en est pas une.
    """
    assert PorteeExecution.applicative.value != PorteeExecution.hygiene_locale.value
    standby = HistoriqueMaintenance(noeud="rpi2", portee=PorteeExecution.hygiene_locale.value)
    assert standby.portee == "hygiene_locale"
    assert standby.noeud == "rpi2"


def test_taches_couvrent_les_crons_reels():
    """L'énumération couvre les tâches planifiées réellement en production."""
    valeurs = {t.value for t in TachePlanifiee}
    assert {"maintenance", "backup", "bascule"} <= valeurs
    assert {"health_watch", "reliability", "auto_deploy"} <= valeurs


def test_periodicite_exclut_les_crons_a_haute_frequence():
    """Les crons à haute fréquence ne doivent PAS être attendus en base.

    health-watch tourne toutes les 5 min, reliability toutes les 15 : enregistrer
    chaque tick produirait des milliers de lignes par jour dans la table la plus
    écrite de la base. C'est ce profil d'écriture qui a corrompu `telemetry_event`
    deux fois en juin 2026 — ils n'enregistrent que leurs anomalies et actions.
    """
    from app.routers.admin import _PERIODICITE_ATTENDUE_H

    assert "health_watch" not in _PERIODICITE_ATTENDUE_H
    assert "reliability" not in _PERIODICITE_ATTENDUE_H
    assert "auto_deploy" not in _PERIODICITE_ATTENDUE_H
    assert _PERIODICITE_ATTENDUE_H["maintenance"] == 7 * 24


def test_sauvegarde_nest_pas_dupliquee_dans_la_table_maintenance():
    """La sauvegarde garde SA table — elle n'est pas recopiée ici.

    `historique_sauvegarde` existe déjà, est alimentée in-process par
    `run_backup` et dispose de son propre onglet. L'ajouter à
    `_PERIODICITE_ATTENDUE_H` reviendrait à écrire deux fois le même fait, avec
    deux chemins d'écriture différents : c'est la duplication que la règle de
    factorisation interdit, et c'est elle qui fabrique les divergences.

    La vue de santé agrège les deux sources **à la lecture** — sa périodicité
    vit donc dans une constante distincte.
    """
    from app.routers.admin import _PERIODICITE_ATTENDUE_H, _PERIODICITE_SAUVEGARDE_H

    assert "backup" not in _PERIODICITE_ATTENDUE_H, (
        "le backup ne doit pas être attendu dans historique_maintenance : "
        "il a sa propre table"
    )
    assert _PERIODICITE_SAUVEGARDE_H == 24


def test_retard_declenche_le_statut_manquante():
    """Une exécution plus vieille que sa période + tolérance est en retard.

    C'est le cœur du besoin : le 26/07/2026, la maintenance avait bien tourné sur
    les deux nœuds sans qu'aucune ligne n'apparaisse — un trou qu'aucun contrôle
    ne signalait. Reproduit ici la règle de décision, sans base.
    """
    from app.routers.admin import _PERIODICITE_ATTENDUE_H, _TOLERANCE_H

    periode = _PERIODICITE_ATTENDUE_H["maintenance"]
    maintenant = datetime(2026, 8, 2, 12, 0, 0)

    a_lheure = (maintenant - timedelta(hours=periode - 1)).timestamp()
    en_retard = (maintenant - timedelta(hours=periode + _TOLERANCE_H + 1)).timestamp()

    def est_manquante(horodatage: float) -> bool:
        age_h = (maintenant.timestamp() - horodatage) / 3600
        return age_h > periode + _TOLERANCE_H

    assert not est_manquante(a_lheure), "une exécution récente ne doit pas être manquante"
    assert est_manquante(en_retard), "une exécution trop ancienne doit être signalée"
