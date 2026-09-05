#!/bin/sh
set -e

#  🔴 ON NE RESTE PAS ROOT (#769, 05/09/2026).
#
#  Le conteneur démarrait — et servait — en root. Un défaut d'exécution donnait
#  alors root sur le volume de données : le confinement Docker ne sépare rien
#  quand le processus est root.
#
#  ⚠️ POURQUOI LA BASCULE EST ICI ET PAS UN `USER` DANS LE DOCKERFILE : les trois
#  volumes sont déjà écrits par root sur les deux nœuds. Un conteneur qui
#  démarrerait directement en `app` ne pourrait plus ouvrir `app.db` — l'API
#  tomberait au premier déploiement, sur les deux nœuds, et la seule issue serait
#  un `chown` manuel sur une base de production. Ce script garde donc root le
#  temps de reprendre les propriétés, PUIS se relance en `app`.
#
#  ⚠️ Et il se relance AVANT les migrations : Alembic écrit `app.db`, son WAL et
#  son SHM. Les créer en root laisserait des fichiers que le processus applicatif
#  ne pourrait plus rouvrir au redémarrage suivant — la panne serait différée
#  d'un cycle, c'est-à-dire invisible au déploiement qui l'a causée.
#
#  `setpriv` vient de l'image de base (`util-linux`) : aucune dépendance ajoutée.
if [ "$(id -u)" = "0" ]; then
    echo "==> Reprise des propriétés des volumes (app:app)..."
    chown -R app:app /app/data /app/uploads /backups
    echo "==> Bascule vers l'utilisateur applicatif..."
    exec setpriv --reuid=app --regid=app --init-groups "$0" "$@"
fi

echo "==> Lancement des migrations Alembic... (utilisateur : $(id -un))"
alembic upgrade head

echo "==> Démarrage de l'API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
