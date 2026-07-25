FROM python:3.12-slim

WORKDIR /app

# Dépendances système
# libpango/libcairo/libharfbuzz + polices : rendu PDF WeasyPrint
# (fiche arrivant, annonces de hall). Aucune compilation : install rapide sur ARM64.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-dev \
    curl \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libfontconfig1 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    fonts-dejavu-core \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Code source
COPY . .

# Répertoires de données
RUN mkdir -p /app/data /app/uploads /backups

# Script de démarrage (migrations + uvicorn)
RUN chmod +x /app/start.sh

# Migrations + démarrage
CMD ["/app/start.sh"]
