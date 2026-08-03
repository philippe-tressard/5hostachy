"""Sortir la bibliothèque documentaire et les diagnostics du répertoire servi.

`/uploads/*` est publié en statique par Caddy, **sans authentification**. Or
`documents.py` et `diagnostics.py` écrivaient à la racine du volume : leurs
fichiers — PV d'assemblée générale, plan pluriannuel de travaux, modification du
règlement de copropriété, rapports de diagnostic — étaient accessibles à qui
connaissait l'URL, ce qui contournait entièrement le contrôle d'accès
applicatif (`document_visible`, session authentifiée) que leur endpoint de
téléchargement applique. 48 fichiers concernés le 03/08/2026.

Cette migration les déplace dans `prive/`, sous-répertoire **du même volume** —
choix délibéré : `bascule.sh` réplique le volume `5hostachy_uploads` par son nom
et `backup.py` archive `/app/uploads` par son chemin. Un volume dédié serait
absent des deux, donc ni répliqué vers le standby ni sauvegardé.

Le blocage lui-même est dans le `Caddyfile` (`handle /uploads/prive/*` → 404),
sur le modèle déjà en place pour `/uploads/annonces-hall/*`.

⚠️ **Ne lève jamais.** `start.sh` a `set -e` : une exception ici bloquerait le
conteneur, donc le site. Un fichier qu'on ne peut pas déplacer laisse sa ligne
inchangée — le téléchargement continue de fonctionner depuis l'ancien chemin, et
le contrôle de non-régression le signalera.

Idempotente : rejouée, elle ne trouve plus rien à déplacer. C'est nécessaire —
le standby rejoue les migrations au démarrage sur un volume déjà synchronisé.

Revision ID: 0124
Revises: 0123
Create Date: 2026-08-03
"""
import os
import shutil

import sqlalchemy as sa
from alembic import op

revision = "0124"
down_revision = "0123"
branch_labels = None
depends_on = None

RACINE = os.getenv("UPLOADS_DIR", "/app/uploads")
PRIVE = os.path.join(RACINE, "prive")

#: (table, colonne du chemin) — les deux entités dont le fichier est servi par un
#: endpoint authentifié, et n'a donc aucune raison d'être joignable en statique.
#: `devis_prestataire` en est volontairement absent : le front y accède par une
#: URL publique stockée en base, le déplacer casserait l'affichage tant qu'un
#: endpoint de téléchargement n'existe pas. Lot distinct.
CIBLES = (
    ("document", "fichier_chemin"),
    ("diagnostic_rapport", "fichier_chemin"),
)


def _deplacer(ancien: str) -> str | None:
    """Déplace un fichier vers `prive/`. Retourne le nouveau chemin, ou None."""
    if not ancien:
        return None
    nom = os.path.basename(ancien)
    nouveau = os.path.join(PRIVE, nom)

    # Déjà migré (ligne rejouée, ou volume synchronisé depuis l'actif).
    if os.path.dirname(os.path.normpath(ancien)) == os.path.normpath(PRIVE):
        return None
    if os.path.isfile(nouveau) and not os.path.isfile(ancien):
        return nouveau

    if not os.path.isfile(ancien):
        return None  # fichier absent : on ne touche pas à la ligne
    try:
        os.makedirs(PRIVE, exist_ok=True)
        shutil.move(ancien, nouveau)
        return nouveau
    except OSError:
        return None  # jamais bloquant


def upgrade():
    bind = op.get_bind()
    inspecteur = sa.inspect(bind)
    tables = set(inspecteur.get_table_names())

    for table, colonne in CIBLES:
        if table not in tables:
            continue
        lignes = bind.execute(
            sa.text(f"SELECT id, {colonne} AS chemin FROM {table}")  # noqa: S608
        ).fetchall()
        for ligne in lignes:
            nouveau = _deplacer(ligne.chemin or "")
            if not nouveau:
                continue
            bind.execute(
                sa.text(f"UPDATE {table} SET {colonne} = :chemin WHERE id = :id")  # noqa: S608
                .bindparams(chemin=nouveau, id=ligne.id)
            )


def downgrade():
    """Remonte les fichiers à la racine — donc les réexpose. À n'utiliser que
    pour revenir à une version antérieure du code, jamais comme correction."""
    bind = op.get_bind()
    inspecteur = sa.inspect(bind)
    tables = set(inspecteur.get_table_names())

    for table, colonne in CIBLES:
        if table not in tables:
            continue
        lignes = bind.execute(
            sa.text(f"SELECT id, {colonne} AS chemin FROM {table}")  # noqa: S608
        ).fetchall()
        for ligne in lignes:
            ancien = ligne.chemin or ""
            if os.path.dirname(os.path.normpath(ancien)) != os.path.normpath(PRIVE):
                continue
            cible = os.path.join(RACINE, os.path.basename(ancien))
            try:
                if os.path.isfile(ancien):
                    shutil.move(ancien, cible)
            except OSError:
                continue
            bind.execute(
                sa.text(f"UPDATE {table} SET {colonne} = :chemin WHERE id = :id")  # noqa: S608
                .bindparams(chemin=cible, id=ligne.id)
            )
