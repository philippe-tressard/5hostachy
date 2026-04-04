#!/bin/sh
set -e

echo "==> Lancement des migrations Alembic..."
alembic upgrade head

echo "==> Démarrage de l'API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
