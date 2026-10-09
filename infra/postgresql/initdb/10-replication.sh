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

#  Lues ici, une fois : l'image les pose. Une absence s'arrête en disant son nom
#  plutôt qu'en « unbound variable » sous `set -u`.
mdp=${PG_REPLICATION_PASSWORD:-}
utilisateur=${POSTGRES_USER:-}
base=${POSTGRES_DB:-}

if [ -z "$mdp" ]; then
    echo "10-replication.sh : PG_REPLICATION_PASSWORD absent — rôle de réplication NON créé." >&2
    exit 1
fi
if [ -z "$utilisateur" ] || [ -z "$base" ]; then
    echo "10-replication.sh : POSTGRES_USER ou POSTGRES_DB absent — appelé hors de l'image ?" >&2
    exit 1
fi

psql -v ON_ERROR_STOP=1 -v mdp="$mdp" --username "$utilisateur" --dbname "$base" <<'SQL'
CREATE ROLE replication WITH REPLICATION LOGIN PASSWORD :'mdp';
SQL
