"""Le journal des messages relevés dans la boîte des réponses (#1447)

Le 28/09/2026, un message relevé a été IGNORÉ sans qu'on puisse dire pourquoi :
la relève ne gardait que des totaux, dans un journal de conteneur effacé par
deux MEP le même jour. Chaque verdict laisse désormais sa ligne — expéditeur,
objet, affaire, verdict et motif, jamais le corps (`models/courriel.CourrielReleve`).

`ticket_id` est une colonne SIMPLE, sans clé étrangère : la ligne doit survivre
à une affaire supprimée.

## La politique de confidentialité le dit, dans le même lot

La table garde l'adresse de l'expéditeur : la phrase de conservation est
insérée dans le texte servi, après celle de l'historique des envois. Elle est
LUE dans le seed (`CONSERVATION_RELEVES`), jamais recopiée ici — la règle de la
0199 et de la 0218.

Idempotence : le passage cherché est `CONSERVATION_COURRIELS` suivi de la fin
de liste. Une fois la phrase insérée, il n'y figure plus, et un second passage
ne touche à rien ; un texte reformulé depuis Admin → Légal non plus.

Revision ID: 0234
Revises: 0233
"""

import sqlalchemy as sa

from alembic import op

revision = "0234"
down_revision = "0233"
branch_labels = None
depends_on = None

TABLE = "courriel_releve"  # identifiant : constante du fichier
FIN_DE_LISTE = "</li></ul>"


def _passages() -> tuple[str, str]:
    """(avant, après) — les deux phrases lues dans le seed."""
    from app.seed.contenus_legaux import CONSERVATION_COURRIELS, CONSERVATION_RELEVES

    avant = CONSERVATION_COURRIELS + FIN_DE_LISTE
    apres = CONSERVATION_COURRIELS + "</li>" + CONSERVATION_RELEVES + "</ul>"
    return avant, apres


def _politique(avant: str, apres: str) -> None:
    from app.utils.textes_livres import remplacer_passage

    remplacer_passage(
        op.get_bind(),
        "config_site",
        {"cle": "politique_confidentialite"},
        "valeur",
        avant,
        apres,
    )


def upgrade() -> None:
    if TABLE not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("releve_le", sa.DateTime(), nullable=False),
            sa.Column("envoye_le", sa.DateTime(), nullable=True),
            sa.Column("expediteur", sa.String(), nullable=False),
            sa.Column("objet", sa.String(), nullable=False),
            sa.Column("decision", sa.String(), nullable=False),
            sa.Column("motif", sa.String(), nullable=False),
            sa.Column("ticket_id", sa.Integer(), nullable=True),
            sa.Column("affaire", sa.String(), nullable=True),
        )
        op.create_index("ix_courriel_releve_releve_le", TABLE, ["releve_le"])
        op.create_index("ix_courriel_releve_ticket_id", TABLE, ["ticket_id"])
    _politique(*_passages())


def downgrade() -> None:
    avant, apres = _passages()
    _politique(apres, avant)
    op.drop_table(TABLE)
