"""Les courriels transférés par le conseil : mémoire des fils et messages versés (29/09/2026)

Un membre du conseil transfère à l'adresse des affaires un fil reçu dans sa
boîte personnelle : la relève le découpe en messages et les verse dans une
affaire — existante, désignée par « TK-… » ou par un transfert précédent du
même fil, ou créée (`utils/courriel_transfert`).

Deux tables :

- `fil_courriel` — l'objet d'origine normalisé d'un fil, et l'affaire où il se
  verse : les transferts suivants du même fil y vont sans repère ;
- `message_verse` — l'EMPREINTE de chaque message versé : un fil renvoyé ne
  double rien.

`ticket_id` est une colonne SIMPLE, sans clé étrangère, comme `courriel_releve`
(0234) : une ligne doit survivre à une affaire supprimée.

## La politique de confidentialité le dit, dans le même lot

Le fil versé porte le nom, l'adresse et le texte de personnes qui n'ont rien
envoyé au site, et chaque message passe par la mise en forme automatique. La
phrase est LUE dans le seed (`COURRIELS_TRANSFERES`), insérée après celle de la
mise en forme des réponses (0223). Idempotence : le passage cherché est cette
phrase suivie de la fin de l'élément ; une fois l'ajout fait il n'y figure plus.

Revision ID: 0237
Revises: 0236
"""

import sqlalchemy as sa

from alembic import op

revision = "0237"
down_revision = "0236"
branch_labels = None
depends_on = None

FIL = "fil_courriel"  # identifiants : constantes du fichier
VERSE = "message_verse"
FIN_D_ELEMENT = "</li>"


def _passages() -> tuple[str, str]:
    """(avant, après) — les phrases lues dans le seed."""
    from app.seed.contenus_legaux import ASSISTANT_SANS_GESTE, COURRIELS_TRANSFERES

    avant = ASSISTANT_SANS_GESTE + FIN_D_ELEMENT
    return avant, ASSISTANT_SANS_GESTE + COURRIELS_TRANSFERES + FIN_D_ELEMENT


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
    tables = sa.inspect(op.get_bind()).get_table_names()
    if FIL not in tables:
        op.create_table(
            FIL,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("cle", sa.String(), nullable=False),
            sa.Column("ticket_id", sa.Integer(), nullable=False),
            sa.Column("mis_a_jour_le", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_fil_courriel_cle", FIL, ["cle"], unique=True)
        op.create_index("ix_fil_courriel_ticket_id", FIL, ["ticket_id"])
    if VERSE not in tables:
        op.create_table(
            VERSE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ticket_id", sa.Integer(), nullable=False),
            sa.Column("empreinte", sa.String(), nullable=False),
            sa.Column("verse_le", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_message_verse_ticket_id", VERSE, ["ticket_id"])
        op.create_index("ix_message_verse_empreinte", VERSE, ["empreinte"])
    _politique(*_passages())


def downgrade() -> None:
    avant, apres = _passages()
    _politique(apres, avant)
    op.drop_table(VERSE)
    op.drop_table(FIL)
