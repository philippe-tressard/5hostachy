"""Système de sauvegarde — APScheduler + rotation automatique."""
import glob
import os
import tarfile
from datetime import datetime

from sqlmodel import Session, select

from app.config import get_settings
from app.database import engine
from app.models.core import ConfigSauvegarde, HistoriqueSauvegarde, StatutSauvegarde

settings = get_settings()


def run_backup(history_id: int | None = None):
    """
    Lance une sauvegarde : app.db + répertoire uploads → .tar.gz
    Met à jour l'entrée HistoriqueSauvegarde correspondante.
    """
    with Session(engine) as session:
        entry: HistoriqueSauvegarde | None = None
        if history_id:
            entry = session.get(HistoriqueSauvegarde, history_id)
        if not entry:
            entry = HistoriqueSauvegarde(declenchee_par="automatique")
            session.add(entry)
            session.commit()
            session.refresh(entry)

        try:
            os.makedirs(settings.backup_dir, exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"hostachy_backup_{ts}.tar.gz"
            dest = os.path.join(settings.backup_dir, filename)

            with tarfile.open(dest, "w:gz") as tar:
                db_path = settings.database_url.replace("sqlite:////", "/")
                if os.path.exists(db_path):
                    tar.add(db_path, arcname="app.db")
                uploads = "/app/uploads"
                if os.path.exists(uploads):
                    tar.add(uploads, arcname="uploads")

            size = os.path.getsize(dest)
            entry.statut = StatutSauvegarde.reussie
            entry.fichier_nom = filename
            entry.fichier_chemin = dest
            entry.taille_octets = size
            entry.terminee_le = datetime.utcnow()

            _rotate_backups(session)

        except Exception as exc:
            entry.statut = StatutSauvegarde.echouee
            entry.message_erreur = str(exc)
            entry.terminee_le = datetime.utcnow()

        session.add(entry)
        session.commit()


def _rotate_backups(session: Session):
    """Supprime les sauvegardes au-delà du nombre de versions à conserver."""
    cfg: ConfigSauvegarde | None = session.exec(select(ConfigSauvegarde)).first()
    keep = cfg.nb_versions_conservees if cfg else settings.backup_keep_versions

    pattern = os.path.join(settings.backup_dir, "hostachy_backup_*.tar.gz")
    files = sorted(glob.glob(pattern))  # order par date (timestamp dans le nom)

    to_delete = files[: max(0, len(files) - keep)]
    for f in to_delete:
        try:
            os.remove(f)
        except OSError:
            pass

    # Marquer comme supprimées dans l'historique
    all_entries = session.exec(
        select(HistoriqueSauvegarde).where(
            HistoriqueSauvegarde.statut == StatutSauvegarde.reussie
        )
    ).all()
    deleted_names = {os.path.basename(f) for f in to_delete}
    for e in all_entries:
        if e.fichier_nom in deleted_names:
            session.delete(e)
    session.commit()


def setup_scheduler():
    """Configure APScheduler selon ConfigSauvegarde (ou paramètres .env par défaut)."""
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()

    with Session(engine) as session:
        cfg: ConfigSauvegarde | None = session.exec(select(ConfigSauvegarde)).first()

    # Si la config existe et est désactivée, on ne programme rien
    if cfg is not None and not cfg.active:
        scheduler.start()
        return scheduler

    freq = cfg.frequence.value if cfg else settings.backup_frequency
    hour = cfg.heure_execution if cfg else settings.backup_hour
    dow = cfg.jour_semaine if cfg else settings.backup_day_of_week

    # Les valeurs de l'enum FrequenceSauvegarde sont en français
    if freq in ("quotidienne", "daily"):
        scheduler.add_job(run_backup, "cron", hour=hour, minute=0, id="backup")
    elif freq in ("hebdomadaire", "weekly"):
        scheduler.add_job(run_backup, "cron", day_of_week=dow, hour=hour, minute=0, id="backup")
    elif freq in ("mensuelle", "monthly"):
        dom = cfg.jour_mois if cfg else 1
        scheduler.add_job(run_backup, "cron", day=dom, hour=hour, minute=0, id="backup")

    scheduler.start()
    return scheduler
