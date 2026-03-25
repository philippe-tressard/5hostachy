"""Tâches de maintenance exécutables directement depuis l'API."""
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlmodel import Session, select

from app.database import engine
from app.models.core import (
    HistoriqueMaintenance,
    PublicationEvolution,
    WhatsAppLog,
)


def run_maintenance(history_id: int | None = None) -> None:
    """
    Exécute les tâches de maintenance Python (identiques au script maintenance.sh) :
      1. Purge des refresh tokens expirés / révoqués
      2. VACUUM SQLite
      3. Nettoyage logs WhatsApp (garde les 6 derniers)
      4. Nettoyage évolutions archivées > 90 jours
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

        # 2. VACUUM SQLite
        try:
            with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
                conn.execute(text("VACUUM"))
        except Exception as exc:
            erreurs.append(f"VACUUM: {exc}")

        # 3. Nettoyage logs WhatsApp (garder 6 max)
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

        # 4. Nettoyage évolutions anciennes (> 90 jours)
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
