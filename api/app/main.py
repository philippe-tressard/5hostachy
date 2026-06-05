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
    auth, tickets, publications, documents, lots, admin,
    notifications, acces, calendrier, prestataires, sondages, idees, copropriete,
    bailleur, config, diagnostics, annonces, regles_residence, delegations,
    telemetry, flux,
)
from app.routers import uploads, faq
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

    scheduler = setup_scheduler()

    # Planificateur WhatsApp : vérification chaque jour à 18h
    from app.utils.whatsapp_scheduler import check_and_send as _wa_check
    scheduler.add_job(_wa_check, "cron", hour=18, minute=0, id="whatsapp_scheduled")

    # Agrégation télémétrie : chaque nuit à 2h
    from app.utils.telemetry_aggregation import run_telemetry_aggregation_cron
    scheduler.add_job(run_telemetry_aggregation_cron, "cron", hour=2, minute=0, id="telemetry_aggregation")

    # Contrôle santé quotidien : WhatsApp, sauvegardes, disque (09h00)
    from app.utils.health_monitor import run_health_check
    scheduler.add_job(run_health_check, "cron", hour=9, minute=0, id="health_check")

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

app = FastAPI(
    title="5Hostachy API",
    description="API de gestion de la copropriété — Résidence du Parc",
    version="0.2.0",
    lifespan=lifespan,
    default_response_class=UTCJSONResponse,
    docs_url="/docs" if _enable_docs else None,
    redoc_url="/redoc" if _enable_docs else None,
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
app.include_router(lots.router)
app.include_router(tickets.router)
app.include_router(publications.router)
app.include_router(documents.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(acces.router)
app.include_router(calendrier.router)
app.include_router(prestataires.router)
app.include_router(sondages.router)
app.include_router(idees.router)
app.include_router(annonces.router)
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

# Fichiers statiques (photos uploadées)
uploads_dir = Path("/app/uploads")
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
        return {"status": "ok", "version": "0.2.0"}
    except Exception as exc:
        _logger.error("Health check DB failed : %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "db_unavailable", "detail": "Base de données indisponible"},
        )
