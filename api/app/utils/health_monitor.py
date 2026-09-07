"""Vérification quotidienne de santé du système — WhatsApp, sauvegardes, disque."""
import glob
import json
import logging
import os
import shutil
from datetime import datetime, timedelta

import httpx
from sqlmodel import Session, select

from app.config import get_settings
from app.database import SessionLocal
from app.utils.dates_fr import datetime_longue
from app.models.core import (
    ConfigSite, HistoriqueMaintenance, HistoriqueSauvegarde, StatutSauvegarde,
    TachePlanifiee, WhatsAppLog,
)

logger = logging.getLogger(__name__)

#  Âge au-delà duquel l'archive locale la plus récente est anormale : le cron
#  de sauvegarde tourne à 03:00 et ce contrôle à 06:00, sur le même nœud.
_AGE_MAX_ARCHIVE_LOCALE_H = 25


def _check_whatsapp(session: Session) -> list[str]:
    """Retourne une liste de problèmes WhatsApp détectés."""
    from app.utils.whatsapp import config_whatsapp, whatsapp_actif

    issues = []
    #  Ce contrôle n'a besoin que de trois clés, mais c'est la MÊME notion que
    #  celle des routers : il en gardait sa propre liste, cinquième exemplaire.
    #  Lire l'ensemble complet ne coûte rien et supprime la divergence.
    cfg = config_whatsapp(session)

    if not whatsapp_actif(cfg):
        return []

    api_url = cfg.get("whatsapp_api_url", "").strip()
    api_key = cfg.get("whatsapp_api_key", "").strip()
    if not api_url:
        return []

    # Vérifier le statut du bridge
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{api_url.rstrip('/')}/status", headers={"x-api-key": api_key})
            state = resp.json().get("state", "unknown")
        if state != "open":
            issues.append(f"Bridge WhatsApp déconnecté (état : {state}). Reconnexion requise via Admin → WhatsApp → Statut.")
    except Exception as exc:
        issues.append(f"Bridge WhatsApp injoignable : {exc}")
        return issues

    # Vérifier les logs des dernières 24h : >= 3 échecs consécutifs
    # (on ignore les anciens échecs antérieurs à une reconnexion)
    depuis = datetime.utcnow() - timedelta(hours=24)
    logs = session.exec(
        select(WhatsAppLog)
        .where(WhatsAppLog.envoye_le >= depuis)
        .order_by(WhatsAppLog.envoye_le.desc())
        .limit(5)
    ).all()
    if len(logs) >= 3 and all(l.statut == "échec" for l in logs[:3]):
        from zoneinfo import ZoneInfo
        extrait = "\n".join(
            f"    [{l.envoye_le.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Europe/Paris')).strftime('%d/%m %H:%M')}] "
            f"« {l.label[:40]} » → {l.erreur or 'erreur inconnue'}"
            for l in logs[:3]
        )
        issues.append(
            f"3 derniers envois WhatsApp en échec consécutif (dernières 24h) :\n{extrait}"
        )

    return issues


def _check_backups(session: Session) -> list[str]:
    """Retourne une liste de problèmes de sauvegarde détectés."""
    issues = []
    last_ok = session.exec(
        select(HistoriqueSauvegarde)
        .where(HistoriqueSauvegarde.statut == StatutSauvegarde.reussie)
        .order_by(HistoriqueSauvegarde.terminee_le.desc())
    ).first()

    if not last_ok or not last_ok.terminee_le:
        issues.append("Aucune sauvegarde réussie trouvée dans l'historique.")
        return issues

    age = datetime.utcnow() - last_ok.terminee_le
    if age > timedelta(hours=25):
        heures = int(age.total_seconds() / 3600)
        issues.append(
            f"Dernière sauvegarde réussie il y a {heures}h (> 25h). "
            f"Vérifier Admin → Sauvegardes."
        )

    # Dernière sauvegarde en échec ?
    last_any = session.exec(
        select(HistoriqueSauvegarde).order_by(HistoriqueSauvegarde.terminee_le.desc())
    ).first()
    if last_any and last_any.statut == StatutSauvegarde.echouee:
        issues.append(
            f"La dernière sauvegarde a échoué : {last_any.message_erreur or 'erreur inconnue'}."
        )

    issues += _check_archive_locale()
    return issues


def _check_archive_locale() -> list[str]:
    """Vérifie qu'une archive RÉELLE et récente existe sur ce nœud.

    POURQUOI ce contrôle s'ajoute à celui de l'historique (04/08/2026) :
    `historique_sauvegarde` vit dans `app.db`, que `bascule.sh` réplique sur le
    peer — mais le volume Docker `backups`, lui, n'est jamais répliqué. Une
    ligne « réussie » ne prouvait donc PAS qu'un fichier existe : elle prouvait
    qu'une ligne a été écrite. Volume vidé, disque plein, archive tronquée,
    rotation trop agressive — le contrôle restait vert dans tous ces cas.
    C'est « vérifier l'artefact déclaré plutôt que le fait » (standards/04).

    Le contrôle tourne à 06:00 sur le nœud actif, qui a produit la sauvegarde de
    03:00 trois heures plus tôt : en marche nominale, une archive fraîche est
    forcément là. Après un failover survenu entre 03:00 et 06:00, ce nœud n'en a
    effectivement pas — et le signaler est correct, pas excessif : cela veut dire
    que si l'autre nœud est perdu, l'archive la plus récente a deux jours.
    """
    from app.utils.backup import MOTIF_ARCHIVE, horodatage_archive

    repertoire = get_settings().backup_dir
    try:
        chemins = sorted(glob.glob(os.path.join(repertoire, MOTIF_ARCHIVE)))
    except OSError as exc:
        return [f"Répertoire de sauvegarde illisible ({repertoire}) : {exc}."]

    if not chemins:
        return [
            f"Aucun fichier de sauvegarde présent sur ce nœud ({repertoire}), "
            f"alors que l'historique en annonce. Le volume `backups` n'est pas "
            f"répliqué entre les RPi : vérifier Admin → Sauvegardes."
        ]

    recent = chemins[-1]
    nom = os.path.basename(recent)
    try:
        taille = os.path.getsize(recent)
    except OSError as exc:
        return [f"Archive la plus récente illisible ({nom}) : {exc}."]

    if taille == 0:
        return [f"L'archive la plus récente est VIDE (0 octet) : {nom}."]

    horodatage = horodatage_archive(nom)
    if horodatage is None:
        # Ne pas savoir dater n'est pas un OK : c'est un INCONNU, donc une anomalie.
        return [f"Archive au nom non conforme, impossible d'en vérifier l'âge : {nom}."]

    age = datetime.utcnow() - horodatage
    if age > timedelta(hours=_AGE_MAX_ARCHIVE_LOCALE_H):
        heures = int(age.total_seconds() / 3600)
        return [
            f"L'archive la plus récente présente sur ce nœud date de {heures}h "
            f"({nom}) — au-delà des {_AGE_MAX_ARCHIVE_LOCALE_H}h attendues."
        ]
    return []


def _check_export_hors_site(session: Session) -> list[str]:
    """Vérifie qu'une copie des sauvegardes existe HORS des deux Raspberry Pi.

    POURQUOI (04/08/2026) : jusqu'ici, 100 % des archives vivaient dans des
    volumes Docker sur deux RPi posés au même endroit, sur la même box et la
    même alimentation. Les deux nœuds protègent de la panne d'UN nœud, jamais
    d'un `docker volume rm`, d'un rançongiciel ou d'un sinistre — qui emportent
    la base, les uploads ET toutes les sauvegardes d'un coup.
    `export-hors-site.sh` produit cette copie ; ce contrôle est ce qui empêche
    son oubli de passer inaperçu.

    Deux questions DISTINCTES, et c'est le point important :
      1. l'export a-t-il tourné récemment ?
      2. la copie qu'il a produite est-elle FRAÎCHE ?
    Un export qui s'exécute fidèlement mais recopie chaque fois la même archive
    périmée satisfait (1) et trahit (2). Ne vérifier que (1) fabriquerait
    exactement le faux vert que ce lot corrige ailleurs.
    """
    from app.utils.backup import horodatage_archive
    #  Seuil lu là où l'écran de santé le lit déjà : deux constantes séparées
    #  divergeraient au premier ajustement, et l'e-mail contredirait l'écran.
    from app.routers.admin import _PERIODICITE_ATTENDUE_H, _TOLERANCE_H

    tache = TachePlanifiee.export_hors_site.value
    seuil_h = _PERIODICITE_ATTENDUE_H[tache] + _TOLERANCE_H
    jours = int(seuil_h / 24)

    derniere = session.exec(
        select(HistoriqueMaintenance)
        .where(HistoriqueMaintenance.tache == tache)
        .order_by(HistoriqueMaintenance.cree_le.desc())
    ).first()

    if derniere is None:
        return [
            "Aucune copie hors site n'a jamais été enregistrée. Les sauvegardes "
            "n'existent que sur les deux RPi : un sinistre au domicile les perd "
            "toutes. Lancer export-hors-site.cmd depuis le poste."
        ]

    issues = []
    if derniere.statut == "erreur":
        issues.append(
            f"Le dernier export hors site a ÉCHOUÉ : "
            f"{derniere.erreur or 'erreur inconnue'}."
        )

    age_execution = datetime.utcnow() - derniere.cree_le
    if age_execution > timedelta(hours=seuil_h):
        j = int(age_execution.total_seconds() / 86400)
        issues.append(
            f"Aucun export hors site depuis {j} jours (seuil : {jours} jours). "
            f"Lancer export-hors-site.cmd depuis le poste."
        )

    #  Fraîcheur de l'archive RÉELLEMENT copiée — cf. docstring, question (2).
    details = {}
    if derniere.details:
        try:
            details = json.loads(derniere.details) or {}
        except ValueError:
            details = {}

    archive = details.get("archive")
    horodatage = horodatage_archive(archive) if archive else None
    if horodatage is None:
        issues.append(
            "Le dernier export hors site n'indique pas quelle archive il a "
            "copiée — impossible d'en vérifier la fraîcheur."
        )
    else:
        age_copie = datetime.utcnow() - horodatage
        if age_copie > timedelta(hours=seuil_h):
            j = int(age_copie.total_seconds() / 86400)
            issues.append(
                f"La sauvegarde copiée hors site date de {j} jours ({archive}) — "
                f"l'export s'exécute mais recopie une archive périmée."
            )

    if details.get("integrite") and details["integrite"] != "ok":
        issues.append(
            f"La copie hors site n'a pas passé le contrôle d'intégrité "
            f"(integrity_check : {details['integrite']})."
        )

    return issues


def _check_disk() -> list[str]:
    """Retourne une alerte si l'espace disque est faible."""
    issues = []
    try:
        usage = shutil.disk_usage("/")
        pct_free = (usage.free / usage.total) * 100
        if pct_free < 15:
            free_gb = usage.free / (1024 ** 3)
            issues.append(
                f"Espace disque faible : {pct_free:.1f}% libre ({free_gb:.1f} Go). "
                f"Vérifier et nettoyer si nécessaire."
            )
    except Exception as exc:
        logger.warning("Impossible de vérifier l'espace disque : %s", exc)
    return issues


def _check_db_integrity() -> list[str]:
    """Vérifie l'intégrité de la base SQLite (PRAGMA quick_check).

    Exécuté DANS le process API (même connexion que l'app) → aucun accès
    multi-process. Détecte tôt une corruption (ex. telemetry_event 17/06/2026,
    découverte seulement par l'échec du job d'agrégation) au lieu d'attendre
    un signalement utilisateur.
    """
    from sqlalchemy import text
    from app.database import engine

    issues: list[str] = []
    try:
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA quick_check")).first()
        verdict = res[0] if res else "(aucun résultat)"
        if verdict != "ok":
            issues.append(
                f"Intégrité base CORROMPUE (PRAGMA quick_check : « {verdict} »). "
                f"Récupération requise (.recover) — voir CLAUDE.md → corruption DB."
            )
    except Exception as exc:
        # quick_check lui-même peut lever si la corruption est sévère
        issues.append(
            f"Intégrité base : quick_check a échoué ({exc}). "
            f"Base probablement corrompue — récupération requise (.recover)."
        )
    return issues


def _check_reference_copro(session: Session) -> list[str]:
    """La référence de copropriété doit être renseignée : le syndic trie dessus.

    Depuis le 11/08/2026, elle est obligatoire — sans exception — dans l'objet de
    tout message qui lui est adressé. Les six modèles concernés ouvrent donc leur
    objet par `{{ prefixe_copro }}`, composé par `email._prefixe_copro`.

    Ce préfixe rend une chaîne vide quand la clé n'est pas renseignée — il le
    faut, sinon l'objet commencerait par « 🏢  — ». Mais c'est précisément ce qui
    rend ce contrôle nécessaire : une clé vide ne produit alors aucune erreur,
    aucun objet dégradé, aucune trace. La règle serait vérifiée sur les modèles —
    les tests resteraient tous verts — et fausse à chaque envoi. Le seul endroit
    d'où l'écart se voit est ici, sur la configuration réelle de l'installation.
    """
    ligne = session.get(ConfigSite, "reference_copro")
    if (ligne.valeur if ligne else "").strip():
        return []
    return [
        "Référence de copropriété non renseignée : les messages adressés au "
        "syndic partent sans elle.\n"
        "Le syndic identifie ses dossiers par cette référence ; sans elle, tickets "
        "et publications transmis sortent de son tri par affaire.\n"
        "À renseigner dans Admin → Configuration du site → Référence de copropriété."
    ]


def _en_problemes(issues: list[str]) -> list[dict]:
    """Découpe « titre\\ndétail\\ndétail » en {titre, details} pour le modèle.

    Les `_check_*` rendent des chaînes dont les lignes suivantes sont des
    précisions techniques. Le découpage se fait ici, pas dans le modèle : un
    modèle d'e-mail affiche, il ne défait pas un format.
    """
    problemes = []
    for issue in issues:
        lignes = issue.split("\n")
        problemes.append({
            "titre": lignes[0],
            "details": [l.strip() for l in lignes[1:] if l.strip()],
        })
    return problemes


def _send_alert(to: str, issues: list[str], session: Session) -> None:
    """Envoie l'alerte système par le moteur d'e-mail commun.

    Cette fonction parlait à SMTP en direct et fabriquait son HTML en f-strings,
    doublant un moteur d'envoi qui existait à côté. Quatre conséquences, toutes
    silencieuses : l'alerte n'apparaissait pas dans `historique_email` (donc
    l'envoi le plus critique du système était le seul dont on ne pouvait pas
    vérifier le départ), elle n'était pas modifiable depuis Admin → Emails, elle
    ignorait `smtp_ssl_tls` en ne gérant que STARTTLS, et les deux modèles
    prévus pour elle — `sauvegarde_echec` et `alerte_espace_disque` — dormaient
    en base sans que rien ne les envoie.

    Ces deux modèles sont fusionnés en un seul, `alerte_systeme` : le contrôle
    quotidien découvre les problèmes ensemble et n'envoie qu'un message. Deux
    modèles pour un envoi ne se maintiennent pas — ils divergent.

    `send_email` est une coroutine et ce contrôle tourne dans un fil
    d'APScheduler (`BackgroundScheduler`), sans boucle d'événements : `asyncio.
    run` en ouvre une pour la durée de l'envoi, ce qui est le cas d'usage prévu.
    """
    import asyncio

    from zoneinfo import ZoneInfo

    from app.utils.email import send_email

    cfg = {
        r.cle: r.valeur
        for r in session.exec(
            select(ConfigSite).where(ConfigSite.cle.in_(("site_nom", "site_url")))
        ).all()
    }
    site_nom = cfg.get("site_nom") or "5Hostachy"
    site_url = (cfg.get("site_url") or "https://5hostachy.fr").rstrip("/")

    contexte = {
        "problemes": _en_problemes(issues),
        "nb_problemes": len(issues),
        # Heure de Paris : ce message est lu par une personne, pas par une
        # machine. `datetime_longue` et non `datetime_longue_paris` — la
        # conversion de fuseau est faite ici, sur un instant réellement daté.
        "date_controle": datetime_longue(datetime.now(ZoneInfo("Europe/Paris"))),
        "residence": {"nom": site_nom},
        "app": {"url": site_url},
    }

    try:
        asyncio.run(send_email(code="alerte_systeme", to=to, context=contexte))
        logger.info("Alerte santé envoyée à %s (%d problème(s)).", to, len(issues))
    except Exception as exc:
        logger.error("Échec envoi alerte santé : %s", exc)


def run_health_check() -> None:
    """Job quotidien : vérifie WhatsApp, sauvegardes, disque — alerte si problème."""
    from app.utils.email import get_site_manager_notification_email

    session = SessionLocal()
    try:
        issues: list[str] = []
        issues += _check_db_integrity()
        issues += _check_whatsapp(session)
        issues += _check_backups(session)
        issues += _check_export_hors_site(session)
        issues += _check_disk()
        issues += _check_reference_copro(session)

        if not issues:
            logger.info("Contrôle santé quotidien : tout est OK.")
            return

        logger.warning("Contrôle santé : %d problème(s) détecté(s).", len(issues))
        for i in issues:
            logger.warning("  • %s", i)

        to, _ = get_site_manager_notification_email(session)
        if to:
            _send_alert(to, issues, session)
        else:
            logger.warning("Alerte santé non envoyée : aucun email admin configuré.")
    except Exception as exc:
        logger.error("Erreur contrôle santé quotidien : %s", exc)
    finally:
        session.close()
