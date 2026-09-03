""" 
5Hostachy — Application de gestion de copropriété
API FastAPI v0.1
"""
import json as _json
import logging as _logging
import re as _re
import traceback as _traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pathlib import Path
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.exc import OperationalError as _SAOperationalError

from app.utils.limiter import limiter

_logger = _logging.getLogger("hostachy.api")


# ── Sérialisation UTC : toutes les datetime naïves sortent avec "Z" ───────────
# Problème : FastAPI 0.115+ / Pydantic v2 appelle model_dump(mode="json")
# qui convertit les datetime en chaînes ISO AVANT que ENCODERS_BY_TYPE ne
# puisse ajouter le suffixe "Z". Résultat : "2026-04-10T00:00:00" sans "Z"
# → le navigateur interprète comme heure locale au lieu d'UTC.
#
# Solution : UTCJSONResponse post-traite le JSON pour ajouter "Z" à toute
# chaîne ISO datetime naïve (sans timezone). Le _UTCEncoder reste en place
# pour les cas où un dict brut contient des objets datetime Python.
from fastapi.encoders import ENCODERS_BY_TYPE

ENCODERS_BY_TYPE[datetime] = (
    lambda dt: dt.isoformat() + "Z" if dt.tzinfo is None else dt.isoformat()
)

# Regex : "2026-04-10T00:00:00" ou "2026-04-10T00:00:00.123456" (sans suffixe TZ)
_NAIVE_DT_RE = _re.compile(r'"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)"')


class _UTCEncoder(_json.JSONEncoder):
    """Filet de sécurité : si un datetime arrive directement dans le JSON
    (retour de dict brut), on ajoute Z aussi."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            if obj.tzinfo is None:
                return obj.isoformat() + "Z"
            return obj.isoformat()
        return super().default(obj)


class UTCJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        body = _json.dumps(
            content,
            cls=_UTCEncoder,
            ensure_ascii=False,
        )
        # Post-traitement : ajouter "Z" aux datetime ISO naïves
        # (Pydantic v2 les a déjà converties en chaînes sans timezone)
        body = _NAIVE_DT_RE.sub(r'"\1Z"', body)
        return body.encode("utf-8")

from app.database import _run_migrations, engine
from app.routers import (
    auth, auth_mot_de_passe, tickets, publications, documents, lots, admin,
    notifications, acces, calendrier, calendrier_apercu, calendrier_historique, prestataires, compteurs, sondages, idees, copropriete,
    bailleur, config, diagnostics, annonces, regles_residence, delegations,
    telemetry, flux,
)
from app.routers import uploads, faq, signalements, annonces_hall, patrimoine
from app.routers import manuel
from app.routers import csp
from app.seed import seed
from app.utils.backup import setup_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation au démarrage
    # Note : la création des tables est gérée par Alembic (start.sh)
    # _run_migrations() gère uniquement les migrations manuelles SQLite (ALTER TABLE)
    _run_migrations()
    seed()

    # Purge des refresh tokens expirés ou révoqués
    from sqlmodel import Session, delete
    from app.models.core import RefreshToken
    with Session(engine) as _s:
        _s.exec(
            delete(RefreshToken).where(
                (RefreshToken.revoked == True) | (RefreshToken.expires_at < datetime.utcnow())
            )
        )
        _s.commit()

    # Nettoyage des sauvegardes orphelines restées "en_cours" suite à un
    # redémarrage/arrêt du conteneur en plein milieu du job (faussait le
    # contrôle de santé "dernière sauvegarde réussie")
    from datetime import timedelta as _timedelta
    from sqlmodel import select as _select
    from app.models.core import HistoriqueSauvegarde, StatutSauvegarde
    with Session(engine) as _s:
        _seuil = datetime.utcnow() - _timedelta(hours=2)
        _orphelines = _s.exec(
            _select(HistoriqueSauvegarde).where(
                (HistoriqueSauvegarde.statut == StatutSauvegarde.en_cours)
                & (HistoriqueSauvegarde.cree_le < _seuil)
            )
        ).all()
        for _b in _orphelines:
            _b.statut = StatutSauvegarde.echouee
            _b.message_erreur = "Interrompue par redémarrage du conteneur"
            _b.terminee_le = datetime.utcnow()
            _s.add(_b)
        if _orphelines:
            _s.commit()
            _logger.info("Sauvegardes orphelines nettoyées : %d marquée(s) en échec.", len(_orphelines))

    scheduler = setup_scheduler()

    # Planificateur WhatsApp : fenêtre de rattrapage 18h00 → 21h45 (toutes les
    # 15 min) au lieu d'une tentative unique à 18h00 pile — cf. incident du
    # 24/07/2026 (bridge indisponible à 18h00, message mensuel perdu).
    # La dédup dans whatsapp_scheduler.check_and_send() rend les tentatives
    # répétées sûres (aucun risque de doublon).
    from app.utils.whatsapp_scheduler import check_and_send as _wa_check
    scheduler.add_job(_wa_check, "cron", hour="18-21", minute="*/15", id="whatsapp_scheduled")

    # Agrégation télémétrie : chaque nuit à 2h
    from app.utils.telemetry_aggregation import run_telemetry_aggregation_cron
    scheduler.add_job(run_telemetry_aggregation_cron, "cron", hour=2, minute=0, id="telemetry_aggregation")

    # Contrôle santé quotidien : WhatsApp, sauvegardes, disque (06h00)
    from app.utils.health_monitor import run_health_check
    scheduler.add_job(run_health_check, "cron", hour=6, minute=0, id="health_check")

    #  Réponses par courriel aux tickets (#703). Toutes les 10 minutes : assez
    #  souvent pour qu'une réponse du syndic paraisse « immédiate » dans le fil,
    #  assez rare pour ne pas marteler la boîte IMAP.
    #
    #  ⚠️ `relever()` ne lève jamais — voir sa docstring : une exception ici
    #  tuerait le job pour de bon, et la relève s'arrêterait en silence. Elle
    #  rend un compte, qu'elle journalise.
    #
    #  Rien ne tourne tant que `imap_enabled` n'est pas posé en administration :
    #  la fonction sort immédiatement.
    from app.utils.courriel_boite import relever as _relever_reponses
    scheduler.add_job(_relever_reponses, "interval", minutes=10, id="courriel_reponses")

    yield
    # Nettoyage à l'arrêt
    scheduler.shutdown()

    # WAL checkpoint au shutdown : vide le fichier .db-wal avant que Docker tue le process.
    # Sans ça, si un job APScheduler est interrompu par SIGTERM, le WAL reste dans un état
    # intermédiaire → "database disk image is malformed" au prochain démarrage.
    try:
        from sqlalchemy import text as _text
        from app.database import engine as _engine
        with _engine.connect() as _conn:
            _conn.execute(_text("PRAGMA wal_checkpoint(TRUNCATE)"))
            _conn.commit()
        _logger.info("WAL checkpoint effectué au shutdown.")
    except Exception as _e:
        _logger.warning("WAL checkpoint échoué au shutdown (non bloquant) : %s", _e)


import os as _os
_enable_docs = _os.getenv("ENABLE_API_DOCS", "false").lower() == "true"

#  Version du CONTRAT de l'API, délibérément distincte de celle de l'application
#  (`front/package.json`). Elle était écrite en dur à deux endroits — ici et dans
#  la réponse de `/health` — donc rien ne garantissait qu'ils restent d'accord.
#
#  ⚠️ Ne pas la faire pointer vers la version applicative : `/health` est PUBLIC et
#  non authentifié, la rendre exacte divulguerait la version déployée sans qu'aucun
#  besoin ne l'impose. Le post-check lit la version servie dans le bundle du front,
#  ce qui n'expose rien de plus (décision du 03/08/2026, cf. la skill mep-precheck).
#  Aucun script d'infra ne consomme ce champ — vérifié le 06/08/2026.
API_VERSION = "0.2.0"

app = FastAPI(
    title="5Hostachy API",
    description="API de gestion de la copropriété — Résidence du Parc",
    version=API_VERSION,
    lifespan=lifespan,
    default_response_class=UTCJSONResponse,
    docs_url="/docs" if _enable_docs else None,
    redoc_url="/redoc" if _enable_docs else None,
    #  ⚠️ Le SCHÉMA aussi, pas seulement les deux pages qui l'affichent.
    #  Jusqu'au 08/08/2026 seuls `docs_url` et `redoc_url` étaient fermés :
    #  `openapi_url` gardait sa valeur par défaut, et `/api/openapi.json`
    #  répondait 200 en production. Le document rend l'intégralité de la surface
    #  — 279 routes, leurs paramètres, et tous les modèles avec leurs noms de
    #  champs. Ce n'est pas une ouverture d'accès : les autorisations restaient
    #  intactes. C'est une divulgation de surface d'attaque, qui épargne à un
    #  attaquant tout le travail d'énumération.
    #
    #  Le défaut n'était pas dans le réglage mais dans sa PORTÉE : son nom
    #  (`ENABLE_API_DOCS`) promettait de fermer la documentation, il n'en fermait
    #  que l'affichage. Un réglage doit couvrir tout ce que son nom annonce.
    openapi_url="/openapi.json" if _enable_docs else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ── Gestionnaires d'erreurs globaux ──────────────────────────────────────────

@app.exception_handler(_SAOperationalError)
async def db_operational_error_handler(request: Request, exc: _SAOperationalError):
    """SQLite I/O error, DB locked, pool corrompu → 503 avec log structuré.
    Le pool est purgé ici pour que la prochaine requête reparte sur une connexion saine.
    """
    from app.database import engine as _engine
    _engine.dispose()
    _logger.error(
        "DB OperationalError sur %s %s — pool purgé : %s",
        request.method, request.url.path, exc,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Base de données temporairement indisponible. Veuillez réessayer."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Filet de sécurité : toute exception non gérée → 500 loggué, jamais de crash silencieux."""
    _logger.error(
        "Exception non gérée sur %s %s :\n%s",
        request.method, request.url.path,
        _traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Erreur interne du serveur."},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://localhost"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Routeurs
app.include_router(auth.router)
#  Même préfixe `/auth`, monté à part : FastAPI additionne les routers, les URL
#  publiques sont donc inchangées (cf. en-tête de `routers/auth_mot_de_passe.py`).
app.include_router(auth_mot_de_passe.router)
app.include_router(lots.router)
app.include_router(tickets.router)
app.include_router(publications.router)
app.include_router(documents.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(acces.router)
app.include_router(calendrier.router)
#  L'Historique d'un événement — extrait le 18/08/2026 (modularité, rang 1).
app.include_router(calendrier_apercu.router)
app.include_router(calendrier_historique.router)
app.include_router(prestataires.router)
#  Même préfixe : les relevés de compteurs sont sortis de `prestataires.py`
#  (modularité, 29/08/2026), pas de l'API — les chemins n'ont pas bougé.
app.include_router(compteurs.router)
app.include_router(sondages.router)
app.include_router(idees.router)
app.include_router(annonces.router)
app.include_router(annonces_hall.router)
app.include_router(manuel.router)
app.include_router(copropriete.router)
app.include_router(uploads.router)
app.include_router(faq.router)
app.include_router(bailleur.router)
app.include_router(config.router)
app.include_router(diagnostics.router)
app.include_router(regles_residence.router)
app.include_router(delegations.router)
app.include_router(telemetry.router)
app.include_router(flux.router)
app.include_router(signalements.router)
app.include_router(patrimoine.router)
#  Collecte des violations de CSP (#536) : point PUBLIC — le navigateur poste
#  sans cookie. Borné par une limite de débit et un plafond de clés.
app.include_router(csp.router)

# Fichiers statiques (photos uploadées)
#  `UPLOADS_DIR` plutôt qu'un chemin figé : le motif existe déjà dans
#  `routers/documents.py` et `utils/fichiers.py`, donc on l'applique à
#  l'identique (CLAUDE.md — un pattern présent ≥ 2 fois fait loi). En
#  production rien ne change, la variable n'étant pas définie.
#  Ce qu'il débloque : importer `app.main` hors conteneur. Le `mkdir` d'un
#  chemin absolu échouait sur un poste de développement et sur un exécuteur
#  d'intégration continue — ce qui rendait l'application intestable dans son
#  ensemble, et laissait passer toute rupture d'assemblage (cf.
#  tests/test_demarrage.py).
uploads_dir = Path(_os.getenv("UPLOADS_DIR", "/app/uploads"))
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.get("/health", tags=["system"])
def health():
    """Health check : vérifie aussi la disponibilité de la DB.
    Retourne 503 si la DB est inaccessible (utilisé par check-stack.sh).
    """
    from sqlmodel import Session, text as _text
    from app.database import engine as _engine
    try:
        with Session(_engine) as _s:
            _s.exec(_text("SELECT 1"))  # type: ignore[arg-type]
        return {"status": "ok", "version": API_VERSION}
    except Exception as exc:
        _logger.error("Health check DB failed : %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "db_unavailable", "detail": "Base de données indisponible"},
        )
