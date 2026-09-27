"""L'état des tâches planifiées, LU en base — une seule lecture, deux lecteurs.

Extrait de `routers/admin/exploitation.py` (`maintenance_sante`) le 27/09/2026,
quand un second lecteur est apparu : le contrôle de santé de 06:00, qui doit
signaler par courriel ce que l'écran montrait seul. Recopier la boucle dans
`health_monitor` aurait fait deux lectures de la même vérité — et c'est celle
qu'on ne voit pas, le courriel, qui aurait divergé la première.

La DÉCISION reste dans `sante_taches.py` (pure, testable sans base). Ce module
ne fait que lire les trois tables et assembler.
"""

from datetime import datetime

from sqlmodel import Session, select

from app.models.core import (
    HistoriqueMaintenance,
    HistoriqueSauvegarde,
    HistoriqueTelemetrie,
    StatutSauvegarde,
)
from app.utils import horloge
from app.utils.sante_taches import (
    _LIGNES_REMONTEES,
    _PERIODICITE_ATTENDUE_H,
    _PERIODICITE_SAUVEGARDE_H,
    _PERIODICITE_TELEMETRIE_H,
    _entree_sante,
    _etat_tache_a_table_propre,
    _sante_par_noeud,
    anomalies_a_signaler,
)


def etat_des_taches(session: Session, maintenant: datetime) -> list[dict]:
    """Une entrée par tâche, avec ses sous-lignes par nœud."""
    etat = []
    for tache, periode_h in _PERIODICITE_ATTENDUE_H.items():
        lignes = session.exec(
            select(HistoriqueMaintenance)
            .where(HistoriqueMaintenance.tache == tache)
            .order_by(HistoriqueMaintenance.cree_le.desc())
            .limit(20)
        ).all()
        #  ⚠️ Le groupement par nœud est celui de `_sante_par_noeud`, partagé
        #  avec les tâches à table propre (#540). Il vivait ici seul, et l'autre
        #  branche s'en passait — d'où une sous-ligne unique là où il en fallait
        #  deux, et deux formes pour le champ `noeuds` (#538).
        etat.append(
            _entree_sante(
                tache,
                periode_h,
                _sante_par_noeud(tache, lignes, periode_h, "erreur", maintenant),
            )
        )

    # Sauvegarde et agrégation télémétrie : lues dans LEUR table, pas recopiées
    # dans celle-ci — cf. commentaire de _PERIODICITE_ATTENDUE_H.
    lignes_sauvegarde = session.exec(
        select(HistoriqueSauvegarde)
        .order_by(HistoriqueSauvegarde.cree_le.desc())
        .limit(_LIGNES_REMONTEES)
    ).all()
    etat.append(
        _etat_tache_a_table_propre(
            "backup",
            lignes_sauvegarde,
            _PERIODICITE_SAUVEGARDE_H,
            StatutSauvegarde.echouee,
            maintenant,
        )
    )

    lignes_telemetrie = session.exec(
        select(HistoriqueTelemetrie)
        .order_by(HistoriqueTelemetrie.cree_le.desc())
        .limit(_LIGNES_REMONTEES)
    ).all()
    etat.append(
        _etat_tache_a_table_propre(
            "telemetrie",
            lignes_telemetrie,
            _PERIODICITE_TELEMETRIE_H,
            "erreur",
            maintenant,
        )
    )
    return etat


def problemes_taches(session: Session) -> list[str]:
    """Les lignes que le contrôle de 06:00 ajoute à son courriel."""
    return anomalies_a_signaler(etat_des_taches(session, horloge.maintenant()))
