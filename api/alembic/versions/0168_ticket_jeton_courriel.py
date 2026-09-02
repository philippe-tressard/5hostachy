"""`ticket.jeton_courriel` — répondre au ticket par courriel (#703)

Le jeton qui voyage dans l'adresse de réponse (`tickets+<jeton>@…`), et par
lequel une réponse retrouve son ticket. Voir `utils/courriel_entrant.py` pour
pourquoi c'est un tirage au sort et non l'identifiant du ticket.

## Les tickets EXISTANTS en reçoivent un

Sans quoi la fonction ne marcherait que pour les tickets créés après la mise en
service — et c'est justement sur un ticket en cours qu'on attend une réponse du
syndic. La colonne est donc remplie ligne par ligne, chacune avec son propre
tirage.

⚠️ `UPDATE ... SET jeton = <un seul tirage>` aurait été plus court et
catastrophique : tous les tickets auraient partagé la même adresse de réponse,
et connaître un jeton aurait donné le droit d'écrire sur tous. Le tirage se fait
donc côté Python, une fois par ligne.

## Index unique

Le jeton est la clé de recherche à chaque message reçu. Unique parce que deux
tickets qui le partageraient rendraient le rattachement ambigu — et un
rattachement ambigu, sur ce chemin-là, écrit la réponse du syndic sur le mauvais
dossier.

Revision ID: 0168
Revises: 0167
Create Date: 2026-09-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0168"
down_revision = "0167"
branch_labels = None
depends_on = None


def _colonnes(nom_table: str) -> set[str]:
    """Les colonnes présentes — la migration doit pouvoir se rejouer."""
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(nom_table)}


def upgrade():
    if "jeton_courriel" not in _colonnes("ticket"):
        #  Pas de `ForeignKey`, pas de contrainte dans l'`add_column` : SQLite
        #  refuse d'altérer les contraintes d'une table existante, et la
        #  migration crasherait APRÈS avoir ajouté la colonne (déjà vu deux fois,
        #  0117 et 0165). L'unicité est posée par un index, séparément.
        op.add_column("ticket", sa.Column("jeton_courriel", sa.String(), nullable=True))

    #  Un tirage PAR LIGNE — voir l'en-tête.
    from app.utils.courriel_entrant import nouveau_jeton

    lien = op.get_bind()
    ids = [r[0] for r in lien.execute(
        text("SELECT id FROM ticket WHERE jeton_courriel IS NULL")
    )]
    for ticket_id in ids:
        lien.execute(
            text("UPDATE ticket SET jeton_courriel = :j WHERE id = :i"),
            {"j": nouveau_jeton(), "i": ticket_id},
        )

    index = {i["name"] for i in sa.inspect(lien).get_indexes("ticket")}
    if "ix_ticket_jeton_courriel" not in index:
        op.create_index("ix_ticket_jeton_courriel", "ticket", ["jeton_courriel"], unique=True)


def downgrade():
    index = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("ticket")}
    if "ix_ticket_jeton_courriel" in index:
        op.drop_index("ix_ticket_jeton_courriel", table_name="ticket")
    if "jeton_courriel" in _colonnes("ticket"):
        op.drop_column("ticket", "jeton_courriel")
