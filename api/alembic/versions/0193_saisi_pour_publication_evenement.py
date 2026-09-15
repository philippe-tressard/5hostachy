"""« Saisi pour » sur les actualités et les événements (#953 bis, 15/09/2026).

## La demande

> « As-tu réalisé l'évolution d'ajout de la section “SAISI POUR” aux actualités
>   et Événements ? »

La notion existait sur les **tickets** depuis le 19/08 : le conseil syndical
enregistre ce qu'un résident a signalé par téléphone, ou ce qu'un intervenant
extérieur a rapporté. L'auteur est celui qui a tapé ; le propriétaire est celui
que ça concerne. Une actualité rédigée « pour » quelqu'un pose exactement la
même question.

Les trois colonnes sont désormais portées par `utils/saisi_pour.SaisiPourMixin`,
dont héritent `Ticket`, `Publication` et `Evenement`.

## ⚠️ Pas de clé étrangère sur `saisi_pour_user_id`, et c'est délibéré

SQLite refuse d'ajouter une colonne **contrainte** à une table existante :
`op.add_column(..., sa.ForeignKey(...))` crashe **après** avoir posé la colonne,
la révision n'est pas marquée, et `start.sh` (`set -e`) arrête le conteneur.
C'est arrivé **deux fois** — 0117 le 25/07/2026, 0165 le 01/09 — sans que
personne le voie, la garde d'idempotence faisant passer le redémarrage suivant.

Le modèle ne la déclare donc pas non plus : une base **neuve** (`create_all`) et
une base **migrée** porteraient sinon deux schémas différents.
`api/tests/test_migrations.py` refuse les deux.

📌 `Ticket` fait exception et garde la sienne : sa colonne existe depuis
l'origine, créée avec la table. Le mixin décrit le socle, l'entité qui en sait
plus l'enrichit.

## Idempotence

Les trois colonnes sont posées **si elles manquent**, table par table. Une
migration qui se rejoue — c'est arrivé à chaque crash ci-dessus — ne doit pas
échouer sur « duplicate column ».

Revision ID: 0193
Revises: 0192
Create Date: 2026-09-15
"""
import sqlalchemy as sa
from alembic import op

revision = "0193"
down_revision = "0192"
branch_labels = None
depends_on = None

#: Les tables qui reçoivent la notion, et les colonnes à poser.
TABLES = ("publication", "evenement")
COLONNES = {
    "saisi_pour_user_id": sa.Integer(),
    "saisi_pour_nom": sa.String(),
    "saisi_pour_email": sa.String(),
}


def _colonnes_existantes(conn, table: str) -> set[str]:
    return {
        ligne[1]
        for ligne in conn.execute(sa.text(f"PRAGMA table_info('{table}')"))  # noqa: S608
    }


def upgrade():
    conn = op.get_bind()
    for table in TABLES:
        presentes = _colonnes_existantes(conn, table)
        for nom, type_ in COLONNES.items():
            if nom in presentes:
                continue
            #  ⚠️ `nullable=True` sans valeur par défaut : les entrées existantes
            #  n'ont été saisies pour personne, et `NULL` le dit exactement. Un
            #  `server_default` les ferait toutes paraître renseignées.
            op.add_column(table, sa.Column(nom, type_, nullable=True))


def downgrade():
    for table in TABLES:
        for nom in COLONNES:
            #  SQLite sait retirer une colonne depuis 3.35 ; le `batch` couvre
            #  les versions antérieures et les autres moteurs.
            with op.batch_alter_table(table) as lot:
                lot.drop_column(nom)
