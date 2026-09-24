"""Tâches de maintenance exécutables directement depuis l'API."""
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlmodel import Session, select

from app.utils.noeud import noeud_courant
from app.utils.declenchement import AUTOMATIQUE
from app.database import engine
from app.models.core import (
    HistoriqueMaintenance,
    PublicationEvolution,
    WhatsAppLog,
)

#: Durée de conservation de l'historique des envois (#1073). La politique de
#: confidentialité l'annonce : `test_politique_confidentialite_couvre_le_code`
#: compare les deux, pour que le texte ne mente plus dans aucun sens.
CONSERVATION_COURRIELS_JOURS = 90


def _supprimer(sql: str, **params) -> int:
    """Un DELETE lié, dans sa propre connexion ; rend le nombre de lignes ôtées."""
    with engine.connect() as conn:
        n = conn.execute(text(sql), params).rowcount
        conn.commit()
    return n


def purger() -> tuple[dict[str, int], list[str]]:
    """Les purges de la maintenance, DANS le process de l'API (#1232).

    Deux appelants, une écriture : `run_maintenance` (déclenchement manuel) et
    `POST /admin/maintenance/purges`, que `maintenance.sh` appelle chaque
    dimanche. Le script les faisait lui-même par `docker exec … python`, API en
    marche — un process tiers qui ouvre `app.db`, ce que la règle d'or
    interdit. Une étape en échec n'arrête pas les suivantes : elle s'inscrit
    dans `erreurs`, et le compte de ce qui a réussi reste juste.
    """
    maintenant = datetime.now(timezone.utc)
    il_y_a_90_j = (maintenant - timedelta(days=90)).isoformat()
    comptes = dict.fromkeys(
        ("tokens", "prt", "notifications", "historique", "emails", "whatsapp", "evolutions"), 0
    )
    erreurs: list[str] = []

    etapes = (
        ("tokens", "purge tokens",
         "DELETE FROM refresh_token WHERE expires_at < :now OR revoked = 1",
         {"now": maintenant.isoformat()}),
        ("prt", "purge password reset tokens",
         "DELETE FROM password_reset_token WHERE expires_at < :now OR used = 1",
         {"now": maintenant.isoformat()}),
        ("notifications", "purge notifications",
         "DELETE FROM notification WHERE lue = 1 AND cree_le < :cutoff",
         {"cutoff": il_y_a_90_j}),
        ("historique", "purge historique",
         "DELETE FROM historique_maintenance WHERE cree_le < :cutoff",
         {"cutoff": (maintenant - timedelta(days=365)).isoformat()}),
        ("emails", "purge historique emails",
         "DELETE FROM historique_email WHERE cree_le < :cutoff",
         {"cutoff": (maintenant - timedelta(days=CONSERVATION_COURRIELS_JOURS)).isoformat()}),
    )
    for cle, libelle, sql, params in etapes:
        try:
            comptes[cle] = _supprimer(sql, **params)
        except Exception as exc:
            erreurs.append(f"{libelle}: {exc}")

    # Logs WhatsApp : garder les 6 derniers.
    try:
        with Session(engine) as s:
            anciens = s.exec(
                select(WhatsAppLog).order_by(WhatsAppLog.envoye_le.desc())
            ).all()[6:]
            for old in anciens:
                s.delete(old)
            s.commit()
            comptes["whatsapp"] = len(anciens)
    except Exception as exc:
        erreurs.append(f"logs WhatsApp: {exc}")

    # Évolutions archivées de plus de 90 jours.
    try:
        with Session(engine) as s:
            anciennes = s.exec(
                select(PublicationEvolution).where(
                    PublicationEvolution.cree_le < maintenant - timedelta(days=90)
                )
            ).all()
            for evol in anciennes:
                s.delete(evol)
            s.commit()
            comptes["evolutions"] = len(anciennes)
    except Exception as exc:
        erreurs.append(f"évolutions: {exc}")

    return comptes, erreurs


def run_maintenance(history_id: int | None = None) -> None:
    """La maintenance lancée depuis l'administration : `purger()`, puis VACUUM.

    Met à jour (ou crée) l'entrée HistoriqueMaintenance correspondante. La
    maintenance HEBDOMADAIRE, elle, est celle de `maintenance.sh`, qui demande
    les mêmes purges à l'API (`POST /admin/maintenance/purges`) puis compacte
    la base API arrêtée — aucun planificateur n'appelle cette fonction.
    """
    start = datetime.utcnow()

    with Session(engine) as session:
        entry: HistoriqueMaintenance | None = None
        if history_id:
            entry = session.get(HistoriqueMaintenance, history_id)
        if not entry:
            #  🔴 AUTOMATIQUE, et avec le nœud (18/09/2026). Ce repli est le
            #  chemin d'un appel SANS entrée préexistante — prévu pour un
            #  planificateur, qu'aucun `add_job` ne branche au 24/09/2026 (#1232). Il posait « manuelle » et aucun
            #  nœud — une maintenance automatique s'affichait donc comme
            #  déclenchée à la main, sur un nœud inconnu, dans la colonne que
            #  `TachesPlanifiees` montre. C'est le défaut que l'endpoint de
            #  lancement disait avoir corrigé en v2.32.0, resté entier ici.
            entry = HistoriqueMaintenance(
                declenchee_par=AUTOMATIQUE, noeud=noeud_courant()
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)

        comptes, erreurs = purger()
        tokens_supprimes = comptes["tokens"]

        # VACUUM + PRAGMA optimize SQLite — après les purges, qu'il compacte.
        try:
            with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
                conn.execute(text("VACUUM"))
                conn.execute(text("PRAGMA optimize"))
        except Exception as exc:
            erreurs.append(f"VACUUM: {exc}")

        # Taille DB après VACUUM
        taille_db: int | None = None
        try:
            db_path = str(engine.url).replace("sqlite:////", "/").replace("sqlite:///", "")
            if os.path.exists(db_path):
                taille_db = os.path.getsize(db_path)
        except Exception:
            pass

        end = datetime.utcnow()
        entry.statut = "erreur" if erreurs else "succes"
        entry.tokens_supprimes = tokens_supprimes
        entry.taille_db_octets = taille_db
        entry.duree_secondes = max(1, int((end - start).total_seconds()))
        entry.erreur = " | ".join(erreurs) if erreurs else None
        entry.terminee_le = end
        session.add(entry)
        session.commit()
