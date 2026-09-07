"""`Publication` porte une galerie, comme `Ticket` et `Evenement`.

La publication était la seule des trois rubriques à ne stocker qu'UNE image
(`image_url`), là où `Ticket` et `Evenement` portent déjà `photos_urls`, un
tableau JSON. C'est ce qui rendait impossible d'ajouter plusieurs photos à une
actualité, et ce qui obligeait son formulaire à être différent de tous les autres
(signalé le 10/08/2026).

Cette migration ajoute `photos_urls` et y recopie l'`image_url` existante :
aucune photo n'est perdue, et une base non encore migrée reste lisible puisque la
colonne d'origine n'est pas touchée.

`image_url` n'est PAS supprimée : SQLite ne sait pas retirer une colonne sans
recréer la table, et le jeu n'en vaut pas la chandelle pour une colonne que plus
aucun code ne lit. Elle est marquée comme héritée dans le modèle.

Revision ID: 0134
Revises: 0133
Create Date: 2026-08-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0134"
down_revision = "0133"
branch_labels = None
depends_on = None


def _colonnes(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(sa.text(f"PRAGMA table_info('{table}')"))}


def upgrade() -> None:
    conn = op.get_bind()
    #  Idempotence : `start.sh` a `set -e`, une migration qui retombe sur une
    #  colonne déjà présente bloquerait le conteneur au démarrage.
    if "photos_urls" not in _colonnes(conn, "publication"):
        op.add_column("publication", sa.Column("photos_urls", sa.String(), nullable=True))

    #  Reprise des photos existantes. `json_quote` produit un littéral JSON
    #  correctement échappé — un nom de fichier contenant un guillemet ou un
    #  antislash casserait une concaténation de chaînes, et la galerie
    #  deviendrait illisible pour cette publication (parse_photos rend alors une
    #  liste vide : la photo serait perdue à l'affichage, silencieusement).
    conn.execute(sa.text(
        "UPDATE publication SET photos_urls = '[' || json_quote(image_url) || ']' "
        "WHERE image_url IS NOT NULL AND image_url <> '' "
        "AND (photos_urls IS NULL OR photos_urls = '' OR photos_urls = '[]')"
    ))


def downgrade() -> None:
    #  On ne remet rien dans `image_url` : elle n'a jamais été vidée. Retirer la
    #  colonne ajoutée suffit, et SQLite le permet depuis 3.35.
    conn = op.get_bind()
    if "photos_urls" in _colonnes(conn, "publication"):
        op.drop_column("publication", "photos_urls")
