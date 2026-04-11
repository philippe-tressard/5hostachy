"""Tâches de maintenance exécutables directement depuis l'API."""
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlmodel import Session, select

from app.database import engine
from app.models.core import (
    HistoriqueMaintenance,
    Notification,
    PasswordResetToken,
    PublicationEvolution,
    WhatsAppLog,
)


def run_maintenance(history_id: int | None = None) -> None:
    """
    Exécute les tâches de maintenance Python (identiques au script maintenance.sh) :
      1. Purge des refresh tokens expirés / révoqués
      2. Purge des password reset tokens expirés / utilisés
      3. Purge des notifications lues > 90 jours
      4. Purge de l'historique maintenance > 12 mois
      5. VACUUM + PRAGMA optimize SQLite
      6. Nettoyage logs WhatsApp (garde les 6 derniers)
      7. Nettoyage évolutions archivées > 90 jours
    Met à jour (ou crée) l'entrée HistoriqueMaintenance correspondante.
    """
    start = datetime.utcnow()
    tokens_supprimes = 0
    erreurs: list[str] = []

    with Session(engine) as session:
        entry: HistoriqueMaintenance | None = None
        if history_id:
            entry = session.get(HistoriqueMaintenance, history_id)
        if not entry:
            entry = HistoriqueMaintenance(declenchee_par="manuelle")
            session.add(entry)
            session.commit()
            session.refresh(entry)

        # 1. Purge refresh tokens
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("DELETE FROM refresh_token WHERE expires_at < :now OR revoked = 1"),
                    {"now": datetime.now(timezone.utc).isoformat()},
                )
                conn.commit()
                tokens_supprimes = result.rowcount
        except Exception as exc:
            erreurs.append(f"purge tokens: {exc}")

        # 2. Purge password reset tokens expirés / utilisés
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("DELETE FROM password_reset_token WHERE expires_at < :now OR used = 1"),
                    {"now": datetime.now(timezone.utc).isoformat()},
                )
                conn.commit()
        except Exception as exc:
            erreurs.append(f"purge password reset tokens: {exc}")

        # 3. Purge notifications lues > 90 jours
        try:
            cutoff_notif = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
            with engine.connect() as conn:
                conn.execute(
                    text("DELETE FROM notification WHERE lue = 1 AND cree_le < :cutoff"),
                    {"cutoff": cutoff_notif},
                )
                conn.commit()
        except Exception as exc:
            erreurs.append(f"purge notifications: {exc}")

        # 4. Purge historique maintenance > 12 mois
        try:
            cutoff_hist = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
            with engine.connect() as conn:
                conn.execute(
                    text("DELETE FROM historique_maintenance WHERE cree_le < :cutoff"),
                    {"cutoff": cutoff_hist},
                )
                conn.commit()
        except Exception as exc:
            erreurs.append(f"purge historique: {exc}")

        # 5. VACUUM + PRAGMA optimize SQLite
        try:
            with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
                conn.execute(text("VACUUM"))
                conn.execute(text("PRAGMA optimize"))
        except Exception as exc:
            erreurs.append(f"VACUUM: {exc}")

        # 6. Nettoyage logs WhatsApp (garder 6 max)
        try:
            with Session(engine) as s:
                all_logs = s.exec(
                    select(WhatsAppLog).order_by(WhatsAppLog.envoye_le.desc())
                ).all()
                if len(all_logs) > 6:
                    for old in all_logs[6:]:
                        s.delete(old)
                    s.commit()
        except Exception as exc:
            erreurs.append(f"logs WhatsApp: {exc}")

        # 7. Nettoyage évolutions anciennes (> 90 jours)
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=90)
            with Session(engine) as s:
                old_evols = s.exec(
                    select(PublicationEvolution).where(PublicationEvolution.cree_le < cutoff)
                ).all()
                for evol in old_evols:
                    s.delete(evol)
                if old_evols:
                    s.commit()
        except Exception as exc:
            erreurs.append(f"évolutions: {exc}")

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
