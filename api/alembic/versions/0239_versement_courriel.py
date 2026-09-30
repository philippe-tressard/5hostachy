"""Un transfert de courriel se défait d'un geste : la trace de chaque versement (#1482, 30/09/2026)

Un fil transféré à l'adresse des affaires est versé en autant de Suites que de
messages (0237). En cas d'erreur, le conseil doit pouvoir l'annuler, le
réaffecter à une autre affaire ou en faire une affaire neuve — **en une fois**.
Rien ne le permettait : une Suite ne savait pas de quel transfert elle venait.

- `versement_courriel` — un transfert versé, et ce qu'il a changé autour de ses
  Suites : le statut d'avant, le lien du fil d'avant ;
- `ticket_evolution.versement_id` — la Suite sait de quel transfert elle vient ;
- `message_verse.versement_id` et `evolution_id` — l'empreinte suit sa Suite
  quand on la déplace, et disparaît quand on l'annule.

Colonnes SIMPLES, sans clé étrangère : SQLite refuse d'altérer les contraintes
d'une table existante (0117, 0165), et une trace doit survivre à une affaire
supprimée, comme `courriel_releve` (0234).

Les transferts antérieurs n'ont pas de trace et ne se défont pas : aucune donnée
ne dit quelles Suites un transfert a écrites.

Revision ID: 0239
Revises: 0238
"""

import sqlalchemy as sa

from alembic import op

revision = "0239"
down_revision = "0238"
branch_labels = None
depends_on = None

VERSEMENT = "versement_courriel"  # identifiants : constantes du fichier
SUITES = "ticket_evolution"
VERSES = "message_verse"


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if VERSEMENT not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            VERSEMENT,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ticket_id", sa.Integer(), nullable=False),
            sa.Column("transfere_par_id", sa.Integer(), nullable=False),
            sa.Column("affaire_creee", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("statut_avant", sa.String(), nullable=True),
            sa.Column("cle_fil", sa.String(), nullable=True),
            sa.Column("fil_avant_id", sa.Integer(), nullable=True),
            sa.Column("seuil_evolution_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("objet", sa.String(), nullable=False, server_default=""),
            sa.Column("premier_nom", sa.String(), nullable=True),
            sa.Column("premier_adresse", sa.String(), nullable=True),
            sa.Column("cree_le", sa.DateTime(), nullable=False),
            sa.Column("annule_le", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_versement_courriel_ticket_id", VERSEMENT, ["ticket_id"])
    if "versement_id" not in _colonnes(SUITES):
        op.add_column(SUITES, sa.Column("versement_id", sa.Integer(), nullable=True))
        op.create_index("ix_ticket_evolution_versement_id", SUITES, ["versement_id"])
    colonnes = _colonnes(VERSES)
    if "versement_id" not in colonnes:
        op.add_column(VERSES, sa.Column("versement_id", sa.Integer(), nullable=True))
        op.create_index("ix_message_verse_versement_id", VERSES, ["versement_id"])
    if "evolution_id" not in colonnes:
        op.add_column(VERSES, sa.Column("evolution_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table(VERSES) as batch:
        batch.drop_index("ix_message_verse_versement_id")
        batch.drop_column("evolution_id")
        batch.drop_column("versement_id")
    with op.batch_alter_table(SUITES) as batch:
        batch.drop_index("ix_ticket_evolution_versement_id")
        batch.drop_column("versement_id")
    op.drop_table(VERSEMENT)
