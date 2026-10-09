#!/bin/bash
# =============================================================================
#  10-replication.sh — Le rôle de réplication, posé à l'initialisation (DI-7b)
#
#  Exécuté UNE fois par l'image officielle, quand la base est créée (dossier
#  `/docker-entrypoint-initdb.d`). Sans `PG_REPLICATION_PASSWORD`, il s'arrête :
#  un rôle de réplication sans mot de passe serait une porte ouverte sur le LAN.
#  Une réplique, elle, n'est jamais initialisée : elle naît d'une copie du
#  primaire (`scripts/exploitation/reconstruire-replique.sh`) et n'exécute rien ici.
# =============================================================================
set -euo pipefail

if [ -z "${PG_REPLICATION_PASSWORD:-}" ]; then
    echo "10-replication.sh : PG_REPLICATION_PASSWORD absent — rôle de réplication NON créé." >&2
    exit 1
fi

psql -v ON_ERROR_STOP=1 -v mdp="$PG_REPLICATION_PASSWORD" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE replication WITH REPLICATION LOGIN PASSWORD :'mdp';
SQL
