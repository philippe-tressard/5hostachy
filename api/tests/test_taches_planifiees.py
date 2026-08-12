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
import pytest
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
    # Ajoutée le 04/08/2026 : seule tâche lancée depuis le POSTE et non par un
    # cron des RPi. Ce qui compte pour la surveillance n'est pas d'où part la
    # tâche, mais qu'on puisse constater son absence.
    assert "export_hors_site" in valeurs


def test_toute_tache_attendue_a_un_producteur():
    """Une tâche inscrite au tableau d'attente doit avoir quelqu'un qui la poste.

    POURQUOI (04/08/2026) : `bascule` figurait dans `_PERIODICITE_ATTENDUE_H`, mais
    **aucun script ne postait jamais `tache=bascule`**. La ligne « Bascule
    actif/standby » affichait donc « Jamais exécutée » en permanence, alors que la
    bascule réussissait chaque nuit depuis avril.

    Deux dégâts, et le second est le vrai : la ligne apprenait une chose fausse, et
    surtout **elle serait restée identique si la bascule s'était arrêtée pour de
    bon**. Un rouge permanent ne peut plus rien signaler — c'est une alerte qu'on
    apprend à ignorer, donc un contrôle mort (standards/07 §5).

    Ce test verrouille la classe et non le cas : toute tâche ajoutée au tableau sans
    producteur échouera ici, avant d'aller peindre un faux rouge sur l'écran.
    """
    from pathlib import Path

    from app.routers.admin import _PERIODICITE_ATTENDUE_H

    racine = Path(__file__).resolve().parents[2]
    scripts = {p.name: p.read_text(encoding="utf-8") for p in racine.glob("*.sh")}
    assert len(scripts) >= 10, "chemin de scan cassé — ce test serait vert à vide"

    # Deux formes possibles : la charge utile mutualisée (`rapport_payload <tache>`,
    # cf. lib-rapport.sh) ou un `printf` local. Ne chercher qu'une des deux rendrait
    # ce test faux au premier refactor — et un test faux est pire qu'aucun test.
    for tache in _PERIODICITE_ATTENDUE_H:
        producteurs = [
            nom for nom, src in scripts.items()
            if f'"tache":"{tache}"' in src or f"rapport_payload {tache} " in src
        ]
        assert producteurs, (
            f"la tâche « {tache} » est attendue toutes les "
            f"{_PERIODICITE_ATTENDUE_H[tache]}h mais AUCUN script ne la poste : "
            f"elle affichera « Jamais exécutée » pour toujours, et son passage au "
            f"rouge ne voudra jamais rien dire. Soit un script la rapporte "
            f"(cf. lib-rapport.sh), soit elle sort du tableau."
        )


def test_export_hors_site_est_attendu_avec_une_cadence_tenable():
    """La copie hors site est suivie — mais à un rythme réellement soutenable.

    Elle est lancée à la main depuis un poste qui n'est pas allumé en
    permanence : l'attendre toutes les 24 h ferait crier ce contrôle presque
    tous les jours, et une alerte qui crie tout le temps finit ignorée. C'est
    ainsi qu'un contrôle meurt (standards/07 §5) — le seuil hebdomadaire est
    donc un choix, pas un réglage par défaut, et il est verrouillé ici.

    À l'inverse, ne PAS l'inscrire au tableau la rendrait invisible : son
    absence se lirait comme du calme, ce qui est précisément le « battement
    manquant » de standards/04 §4.
    """
    from app.routers.admin import _PERIODICITE_ATTENDUE_H

    assert _PERIODICITE_ATTENDUE_H["export_hors_site"] == 7 * 24


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


def test_telemetrie_nest_pas_dupliquee_dans_la_table_maintenance():
    """Même règle pour l'agrégation de télémétrie — `historique_telemetrie`.

    Ajoutée le 02/08/2026 : ce job tourne aussi toutes les nuits (02:00), et
    s'il s'arrête, les statistiques d'usage deviennent silencieusement fausses
    sans qu'aucun écran ne le signale — même besoin que la maintenance ou la
    sauvegarde, donc le même traitement générique
    (`_etat_tache_a_table_propre`) plutôt qu'un troisième bloc dupliqué.
    """
    from app.routers.admin import (
        _PERIODICITE_ATTENDUE_H,
        _PERIODICITE_TELEMETRIE_H,
        _etat_tache_a_table_propre,
    )

    assert "telemetrie" not in _PERIODICITE_ATTENDUE_H
    assert _PERIODICITE_TELEMETRIE_H == 24
    assert callable(_etat_tache_a_table_propre)


def test_retention_bornee_et_purgee_in_process():
    """Seuls les 10 derniers rapports sont conservés, et la purge est in-process.

    Elle était faite par `maintenance.sh` via
    `docker exec hostachy_api python -c "…engine…"` : un process DISTINCT
    d'uvicorn ouvrant `app.db` pendant que l'API tourne. C'est le motif que la
    règle d'or anti-corruption interdit — un process tiers qui referme la base
    se croit dernière connexion et peut unlinker le WAL sous le pool. Purger une
    dizaine de lignes ne justifiait pas ce risque.

    La limite d'affichage est bornée par la même constante : afficher plus que
    ce qu'on conserve n'aurait aucun sens.
    """
    import inspect

    from app.routers import admin

    assert admin._RAPPORTS_CONSERVES == 10
    assert callable(admin._purger_anciens_rapports)
    # La purge est appelée à la réception d'un rapport, pas par un script externe.
    source = inspect.getsource(admin.maintenance_rapport)
    assert "_purger_anciens_rapports" in source, (
        "la rétention doit être appliquée à chaque rapport reçu"
    )


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


# ── Deux faux positifs constatés à l'écran le 09/08/2026 ────────────────────

@pytest.fixture()
def session_memoire():
    """Base en mémoire, isolée. Aucun `app.db` n'est approché (règle d'or)."""
    from sqlmodel import Session, SQLModel, create_engine

    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        yield s


def test_la_bascule_est_attendue_toutes_les_48h_car_le_role_alterne():
    """Un nœud n'agit qu'une nuit sur deux : l'attendre chaque jour est un faux rouge.

    `bascule.sh` sort immédiatement sur le standby (« Ce RPi n'est pas actif —
    rien à faire »). L'historique le montre : 05/08 rpi1, 06/08 rpi2, 07/08 rpi1,
    08/08 rpi2. Avec 24 h d'attente, **un nœud sur deux était signalé
    « Exécution manquante » tous les jours**, sur une infrastructure saine.

    Même erreur que le seuil du cache de build le 06/08 : un seuil se règle sur le
    RÉGIME de ce qu'il surveille, pas sur la fréquence du cron.
    """
    from app.routers.admin import _PERIODICITE_ATTENDUE_H

    assert _PERIODICITE_ATTENDUE_H["bascule"] >= 48, (
        "La bascule alterne : chaque nœud n'opère qu'une nuit sur deux. Une "
        "périodicité de 24 h peint un rouge permanent sur le nœud qui n'était pas "
        "actif — et un rouge permanent ne signale plus rien."
    )


def test_le_script_de_bascule_s_abstient_sur_le_standby():
    """Le fait sur lequel repose la périodicité de 48 h, vérifié et non supposé.

    Si `bascule.sh` se mettait à agir (et donc à rapporter) depuis les deux nœuds,
    48 h deviendrait deux fois trop permissif et l'absence cesserait de se voir.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "bascule.sh").read_text(encoding="utf-8")
    assert 'if [ "$ACTIVE" != "$SELF" ]' in source and "exit 0" in source, (
        "bascule.sh ne s'abstient plus sur le standby : la périodicité attendue "
        "de 48 h reposait sur cette abstention."
    )


def test_une_tache_hebdomadaire_survit_aux_quotidiennes(session_memoire):
    """La rétention ne doit pas effacer la preuve que le contrôle cherche.

    Constaté à l'écran le 09/08/2026 : « Maintenance hebdomadaire : jamais
    exécutée », alors qu'elle avait tourné le matin même — la purge gardait les
    dix lignes les plus récentes **toutes tâches confondues**, et les quotidiennes
    avaient chassé l'unique ligne hebdomadaire.

    Une tâche rare est justement celle dont l'absence doit se voir.
    """
    from datetime import datetime, timedelta

    from app.models.core import HistoriqueMaintenance
    from app.routers.admin import _purger_anciens_rapports

    base = datetime(2026, 8, 2, 1, 0)
    session_memoire.add(HistoriqueMaintenance(
        tache="maintenance", noeud="rpi1", statut="succes", cree_le=base))
    #  Trente exécutions quotidiennes postérieures : bien plus que le quota.
    for j in range(30):
        session_memoire.add(HistoriqueMaintenance(
            tache="bascule", noeud="rpi1" if j % 2 else "rpi2", statut="succes",
            cree_le=base + timedelta(days=j + 1)))
    session_memoire.commit()

    _purger_anciens_rapports(session_memoire)

    from sqlmodel import select
    restantes = session_memoire.exec(
        select(HistoriqueMaintenance).where(HistoriqueMaintenance.tache == "maintenance")
    ).all()
    assert len(restantes) == 1, (
        "La ligne hebdomadaire a été chassée par les quotidiennes : l'écran "
        "affichera « jamais exécutée » pour une tâche qui tourne."
    )
    bascules = session_memoire.exec(
        select(HistoriqueMaintenance).where(HistoriqueMaintenance.tache == "bascule")
    ).all()
    assert len(bascules) == 10, (
        f"{len(bascules)} lignes de bascule conservées — le quota par tâche ne "
        "s'applique plus, et la table croîtra sans fin."
    )


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


def test_l_etat_affiche_est_celui_du_noeud_le_moins_a_jour(session_memoire):
    """Un nœud sain ne doit pas masquer un nœud muet.

    Si l'on affichait le rapport le plus RÉCENT des deux, une tâche morte sur un
    nœud depuis des semaines s'afficherait « À jour » — exactement la panne que
    ce tableau existe pour voir (défaut du 31/07/2026 : maintenance.sh ne
    tournait que sur l'actif, et le standby dérivait sans que rien ne le dise).
    """
    maintenant = datetime.utcnow()
    session_memoire.add(HistoriqueMaintenance(
        tache="bascule", noeud="rpi2", statut="succes",
        cree_le=maintenant - timedelta(hours=2)))
    session_memoire.add(HistoriqueMaintenance(        # muet depuis 20 jours
        tache="bascule", noeud="rpi1", statut="succes",
        cree_le=maintenant - timedelta(days=20)))
    session_memoire.commit()

    ligne = [t for t in _sante(session_memoire)["taches"] if t["tache"] == "bascule"][0]
    assert ligne["statut"] == "manquante", (
        f"état « {ligne['statut']} » alors qu'un nœud n'a rien rapporté depuis "
        "20 jours : le nœud sain masque le nœud muet."
    )
    assert ligne["noeud"] == "rpi1", (
        "La ligne doit nommer le nœud qui PORTE l'état, sinon on voit un problème "
        "sans savoir où aller le chercher."
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
