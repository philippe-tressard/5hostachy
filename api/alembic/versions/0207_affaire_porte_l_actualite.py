"""Une affaire peut être une actualité : trois colonnes rapatriées (#1091).

Arbitré les 22 et 23/09/2026 : un seul objet, l'Affaire ; « Actualité » est une
catégorie (`CategorieTicket.actualite`), sans cycle (`StatutTicket.publie`).
Ce que l'actualité portait et que l'affaire n'avait pas :

| Colonne | D'où | Sens |
|---|---|---|
| `public_cible` | `Publication.public_cible` | le public visé, JSON — vide : tout le monde |
| `reserve_perimetre` | `Publication.confidentiel` | l'Accès « Réservé au périmètre » (#1096) |
| `archive_manuel` | `Publication.archivee` | l'archivage décidé par une personne |

⚠️ Aucune donnée n'est recopiée ici : la migration des publications est le
lot 4. Celle-ci ne fait qu'ouvrir les colonnes, sans clé étrangère (SQLite
refuse d'altérer les contraintes d'une table existante — 0117, 0165).
"""
import sqlalchemy as sa
from alembic import op

revision = "0207"
down_revision = "0206"
branch_labels = None
depends_on = None

#: L'identifiant ne peut pas se lier en SQLite : il vient de cette constante.
TABLE = "ticket"
COLONNES = (
    ("public_cible", sa.String(), None),
    ("reserve_perimetre", sa.Boolean(), sa.false()),
    ("archive_manuel", sa.Boolean(), sa.false()),
)


def _colonnes_existantes(conn, table: str) -> set[str]:
    return {colonne["name"] for colonne in sa.inspect(conn).get_columns(table)}


def upgrade():
    existantes = _colonnes_existantes(op.get_bind(), TABLE)
    for nom, type_, defaut in COLONNES:
        if nom in existantes:
            continue
        op.add_column(TABLE, sa.Column(
            nom, type_,
            nullable=defaut is None,
            server_default=defaut,
        ))


def downgrade():
    existantes = _colonnes_existantes(op.get_bind(), TABLE)
    with op.batch_alter_table(TABLE) as lot:
        for nom, _type, _defaut in COLONNES:
            if nom in existantes:
                lot.drop_column(nom)
