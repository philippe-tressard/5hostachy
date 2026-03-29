"""
5Hostachy — Application de gestion de copropriété
API FastAPI v0.1
"""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pathlib import Path
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.utils.limiter import limiter

from app.database import _run_migrations, engine
from app.routers import (
    auth, tickets, publications, documents, lots, admin,
    notifications, acces, calendrier, prestataires, sondages, idees, copropriete,
    bailleur, config, diagnostics, annonces, regles_residence, delegations,
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

    yield
    # Nettoyage à l'arrêt
    scheduler.shutdown()


import os as _os
_enable_docs = _os.getenv("ENABLE_API_DOCS", "false").lower() == "true"

app = FastAPI(
    title="5Hostachy API",
    description="API de gestion de la copropriété — Résidence du Parc",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs" if _enable_docs else None,
    redoc_url="/redoc" if _enable_docs else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

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

# Fichiers statiques (photos uploadées)
uploads_dir = Path("/app/uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "version": "0.2.0"}
