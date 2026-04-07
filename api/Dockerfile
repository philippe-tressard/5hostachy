FROM python:3.12-slim

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-dev \
    curl \
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
