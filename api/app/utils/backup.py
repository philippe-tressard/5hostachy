"""Système de sauvegarde — APScheduler + rotation automatique."""
import glob
import os
import tarfile
from datetime import datetime

from sqlalchemy import text
from sqlmodel import Session, select

from app.config import get_settings
from app.database import engine
from app.models.core import ConfigSauvegarde, HistoriqueSauvegarde, StatutSauvegarde
from app.utils.noeud import noeud_courant

settings = get_settings()

#  Nommage des archives — convention PORTEUSE DE SENS, pas cosmétique.
#  L'horodatage dans le nom est déjà ce sur quoi repose la rotation (tri
#  lexicographique = tri chronologique). `export-hors-site.sh` le remonte à
#  l'API, et `health_monitor` le relit pour distinguer « l'export tourne » de
#  « la copie hors site est fraîche ». Trois lecteurs, donc UN SEUL endroit où
#  la convention est écrite, et un seul parseur.
PREFIXE_ARCHIVE = "hostachy_backup_"
MOTIF_ARCHIVE = f"{PREFIXE_ARCHIVE}*.tar.gz"
_FORMAT_HORODATAGE = "%Y%m%d_%H%M%S"
_SUFFIXE_ARCHIVE = ".tar.gz"


def horodatage_archive(nom_fichier: str) -> datetime | None:
    """Date UTC de création lue dans le nom d'une archive, ou None si illisible.

    Rend None plutôt que de lever : un nom non conforme (fichier déposé à la
    main, archive renommée) ne doit pas faire échouer un contrôle de santé —
    il doit le faire répondre « je ne sais pas », ce que l'appelant traite
    comme une anomalie et non comme un OK (standards/04 §1).
    """
    if not nom_fichier:
        return None
    base = os.path.basename(nom_fichier)
    if not base.startswith(PREFIXE_ARCHIVE) or not base.endswith(_SUFFIXE_ARCHIVE):
        return None
    brut = base[len(PREFIXE_ARCHIVE): -len(_SUFFIXE_ARCHIVE)]
    try:
        return datetime.strptime(brut, _FORMAT_HORODATAGE)
    except ValueError:
        return None


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
            entry = HistoriqueSauvegarde(declenchee_par="automatique", noeud=noeud_courant())
            session.add(entry)
            session.commit()
            session.refresh(entry)

        try:
            os.makedirs(settings.backup_dir, exist_ok=True)
            ts = datetime.utcnow().strftime(_FORMAT_HORODATAGE)
            filename = f"{PREFIXE_ARCHIVE}{ts}{_SUFFIXE_ARCHIVE}"
            dest = os.path.join(settings.backup_dir, filename)

            db_path = settings.database_url.replace("sqlite:////", "/")

            # WAL checkpoint avant copie : garantit que app.db contient
            # toutes les transactions committées (le WAL peut être en avance)
            if os.path.exists(db_path):
                with engine.connect() as _conn:
                    _conn.execute(text("PRAGMA wal_checkpoint(FULL)"))

                # Validation d'intégrité AVANT de sauvegarder : ne jamais écraser
                # les backups sains (rotation) par un snapshot d'une base corrompue.
                # Cf. corruption telemetry_event du 17/06/2026 : le backup de 01:00
                # contenait déjà la table malformée, devenu inutilisable.
                try:
                    with engine.connect() as _conn:
                        verdict_row = _conn.execute(text("PRAGMA quick_check")).first()
                    verdict = verdict_row[0] if verdict_row else "(aucun résultat)"
                except Exception as exc:
                    verdict = f"quick_check a échoué : {exc}"
                if verdict != "ok":
                    entry.statut = StatutSauvegarde.echouee
                    entry.message_erreur = (
                        f"Sauvegarde annulée — base corrompue (quick_check : {verdict}). "
                        f"Backups sains préservés (pas de rotation)."
                    )
                    entry.terminee_le = datetime.utcnow()
                    session.add(entry)
                    session.commit()
                    return

            with tarfile.open(dest, "w:gz") as tar:
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

    pattern = os.path.join(settings.backup_dir, MOTIF_ARCHIVE)
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

    scheduler = BackgroundScheduler(timezone="Europe/Paris")

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
