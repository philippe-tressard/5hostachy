"""Le périmètre d'une petite annonce — la notion que l'écran avait décrétée absente.

Demandé le 18/08/2026 : *« pour les petites annonces tu peux ajouter le
périmètre »*.

## Ce que la migration corrige, et qui n'était pas une contrainte de données

`FormulaireAnnonce.svelte` portait, en toutes lettres :

> « L'annonce n'a ni périmètre ni destinataires : elle s'adresse à tous les
>   résidents par nature. »

C'était une **absence de notion décrétée par un écran**, et le cadre #430 la
refuse : `sansObjet` dit « l'entité ne porte pas cette notion », et il se
déclare — il ne s'écrit pas dans un commentaire de formulaire. La copropriété
compte quatre bâtiments, un parking, des caves et une AFUL : une annonce de
covoiturage pour le bâtiment C ou un vide-cave du parking ont un périmètre, et
n'avaient aucun moyen de le dire.

## Pourquoi la MÊME forme que `publication.perimetre_cible`

Du JSON de codes (`["résidence"]`, `["bat:1","parking"]`), pas un texte libre.
`PerimetrePicker` et `perimetreLabel` ne savent lire que celle-là, et les
périmètres ont déjà divergé une fois (#316, sept clés en dur dans `utils.ts`
incapables de décrire une copropriété sans AFUL). Le sondage a été réaligné pour
la même raison le 16/08 (migration 0147) ; l'annonce l'est ici.

## Les lignes existantes

`server_default` pose `["résidence"]` sur toutes les annonces déjà déposées —
c'est ce que le produit leur appliquait de fait. Le lecteur retombe donc sur le
comportement d'avant : `estPerimetreParDefaut()` est vrai, et la carte n'affiche
aucun badge 🔹.

Revision ID: 0151
Revises: 0150
"""
import sqlalchemy as sa
from alembic import op

revision = "0151"
down_revision = "0150"
branch_labels = None
depends_on = None

TABLE = "petite_annonce"
COLONNE = "perimetre_cible"


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if COLONNE not in _colonnes(TABLE):
        op.add_column(
            TABLE,
            sa.Column(COLONNE, sa.String(), nullable=True, server_default='["résidence"]'),
        )


def downgrade() -> None:
    op.drop_column(TABLE, COLONNE)
