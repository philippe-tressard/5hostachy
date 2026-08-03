"""Sortir devis, ordres de service et photos de relevés du répertoire servi.

Dernier lot du cloisonnement de `/uploads/*` (cf. 0124). `prestataires.py`
écrivait encore à la racine du volume, et stockait des **URLs publiques** en
base — c'est ce qui l'avait tenu hors du lot précédent : le front les consomme
directement en `href` et en `src`, les déplacer sans plus aurait cassé
l'affichage.

Deux corrections en une :

  1. les fichiers rejoignent `prive/`, refusé par Caddy ;
  2. les URLs stockées pointent vers des endpoints **authentifiés** qui
     appliquent `require_cs_or_admin`.

Le second point n'est pas cosmétique. Depuis le 03/08/2026 ces fichiers étaient
couverts par `forward_auth` — qui ne vérifie que la présence d'une session, pas
le rôle. L'écran qui les affiche est pourtant réservé au conseil syndical : tout
résident disposant de l'URL pouvait lire un devis ou un contrat d'assurance.

Le front n'a rien à changer : il lit ces URLs depuis la base, que cette
migration réécrit.

⚠️ **Ne lève jamais** — `start.sh` a `set -e`. Une ligne qu'on ne peut pas
traiter reste inchangée et continue de fonctionner par l'ancien chemin, tant que
le fichier est encore à la racine.

Idempotente : rejouée, elle ne trouve plus d'URL `/uploads/` à réécrire.

Revision ID: 0125
Revises: 0124
Create Date: 2026-08-03
"""
import json
import os
import shutil

import sqlalchemy as sa
from alembic import op

revision = "0125"
down_revision = "0124"
branch_labels = None
depends_on = None

RACINE = os.getenv("UPLOADS_DIR", "/app/uploads")
PRIVE = os.path.join(RACINE, "prive")


def _deplacer(nom: str) -> bool:
    """Déplace `nom` de la racine vers `prive/`. True si le fichier est en place."""
    if not nom:
        return False
    cible = os.path.join(PRIVE, nom)
    if os.path.isfile(cible):
        return True  # déjà migré (rejeu, ou volume synchronisé depuis l'actif)
    source = os.path.join(RACINE, nom)
    if not os.path.isfile(source):
        return False
    try:
        os.makedirs(PRIVE, exist_ok=True)
        shutil.move(source, cible)
        return True
    except OSError:
        return False


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    # ── Devis : pièces jointes (JSON) et ordre de service ────────────────────
    if "devis_prestataire" in tables:
        lignes = bind.execute(sa.text(
            "SELECT id, fichiers_urls, os_fichier_url FROM devis_prestataire"
        )).fetchall()
        for ligne in lignes:
            try:
                fichiers = json.loads(ligne.fichiers_urls or "[]") or []
            except Exception:
                fichiers = []

            nouveaux, change = [], False
            for url in fichiers:
                nom = os.path.basename(str(url))
                if str(url).startswith("/uploads/") and _deplacer(nom):
                    nouveaux.append(f"/api/prestataires/devis/{ligne.id}/fichier/{nom}")
                    change = True
                else:
                    nouveaux.append(str(url))

            os_url = ligne.os_fichier_url
            if os_url and str(os_url).startswith("/uploads/"):
                nom = os.path.basename(str(os_url))
                if _deplacer(nom):
                    os_url = f"/api/prestataires/devis/{ligne.id}/fichier/{nom}"
                    change = True

            if change:
                bind.execute(
                    sa.text(
                        "UPDATE devis_prestataire SET fichiers_urls = :f, "
                        "os_fichier_url = :o WHERE id = :id"
                    ).bindparams(
                        f=json.dumps(nouveaux, ensure_ascii=False) if nouveaux else None,
                        o=os_url,
                        id=ligne.id,
                    )
                )

    # ── Relevés de compteur : photo ──────────────────────────────────────────
    if "releve_compteur" in tables:
        lignes = bind.execute(sa.text(
            "SELECT id, photo_url FROM releve_compteur WHERE photo_url IS NOT NULL"
        )).fetchall()
        for ligne in lignes:
            url = str(ligne.photo_url or "")
            if not url.startswith("/uploads/"):
                continue
            if not _deplacer(os.path.basename(url)):
                continue
            bind.execute(
                sa.text("UPDATE releve_compteur SET photo_url = :u WHERE id = :id")
                .bindparams(u=f"/api/prestataires/releves/{ligne.id}/photo", id=ligne.id)
            )


def downgrade():
    """Irréversible en pratique : les URLs de relevés ont perdu le nom de fichier.

    Le nom du fichier n'apparaît plus dans `/api/prestataires/releves/{id}/photo`,
    on ne peut donc pas reconstruire l'ancienne URL publique. Revenir en arrière
    demanderait de relire le disque — et réexposerait des documents. On s'abstient
    plutôt que de faire semblant.
    """
    pass
