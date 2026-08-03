"""Réparer les URLs de photos de relevé cassées par la 0125.

La 0125 a remplacé `releve_compteur.photo_url` par `/api/prestataires/releves/
{id}/photo` — une URL qui **ne contient plus le nom du fichier**. Or l'endpoint
dérivait ce nom de cette même URL : `basename` rendait « photo », et toutes les
photos de relevé sont devenues introuvables. La seule copie du nom vivait dans
cette colonne ; l'écraser l'a détruite.

Les fichiers, eux, n'ont jamais bougé de `prive/` : seul le pointeur est perdu.

**Origine du mapping ci-dessous** : la base du nœud **standby**, dont la copie
datait de la bascule de 02:00 et n'avait donc pas subi la 0125. Lue sur une
copie, sans jamais ouvrir la base d'origine (règle d'or). C'est une réparation
de données propre à cette installation — ailleurs, aucune clé ne correspondra et
la migration ne fera rien.

Deux garde-fous : on ne touche qu'une ligne encore dans la forme cassée, et
seulement si le fichier existe réellement dans `prive/`. Ne lève jamais —
`start.sh` a `set -e`.

Revision ID: 0126
Revises: 0125
Create Date: 2026-08-03
"""
import os

import sqlalchemy as sa
from alembic import op

revision = "0126"
down_revision = "0125"
branch_labels = None
depends_on = None

PRIVE = os.path.join(os.getenv("UPLOADS_DIR", "/app/uploads"), "prive")

#: id du relevé → nom du fichier, récupéré sur le standby le 03/08/2026.
NOMS_PERDUS = {
    1: "e47a1f1abc054173aa09459a7b8f5652_eau-2023.png",
    2: "1c665a0aa98d43efbbe2d263a77e92c4_eau-2024.png",
    3: "704e5c1ac18d4a8f853263effaf8f443_eau-2025-04.png",
    5: "e51f470ab8db48c7b7aa2215af5245e3_eau-2025.png",
}

#: Forme cassée : une URL de photo qui se termine par « /photo », donc sans nom.
_CASSEE = "/photo"


def upgrade():
    bind = op.get_bind()
    if "releve_compteur" not in set(sa.inspect(bind).get_table_names()):
        return

    lignes = bind.execute(sa.text(
        "SELECT id, photo_url FROM releve_compteur WHERE photo_url IS NOT NULL"
    )).fetchall()

    for ligne in lignes:
        url = str(ligne.photo_url or "")
        # Déjà réparée, ou jamais cassée (URL portant un nom de fichier).
        if not url.endswith(_CASSEE):
            continue
        nom = NOMS_PERDUS.get(ligne.id)
        if not nom:
            continue  # installation différente : rien à réparer ici
        if not os.path.isfile(os.path.join(PRIVE, nom)):
            continue  # fichier absent : ne pas écrire un pointeur mort
        bind.execute(
            sa.text("UPDATE releve_compteur SET photo_url = :u WHERE id = :id")
            .bindparams(u=f"{url}/{nom}", id=ligne.id)
        )


def downgrade():
    """Retour à la forme cassée : sans objet. On ne défait pas une réparation."""
    pass
