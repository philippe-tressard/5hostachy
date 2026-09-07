"""`relance_courriel` — une adresse de réponse pour un envoi GROUPÉ (#703)

## Le trou, signalé par l'utilisateur le 03/09/2026

> « Quelle stratégie si un retour de mail à noreply@ d'une relance de tickets
>   traitant de plusieurs tickets relancés ? »

Le `Reply-To` d'un courriel de ticket porte le jeton **du ticket**. La relance
syndic, elle, est un envoi groupé : **un seul message pour N dossiers**. Elle
n'avait donc aucun jeton, et la réponse du syndic arrivait dans une boîte où rien
ne la rattachait à quoi que ce soit.

Verdict de la relève : `IGNORE`. **En silence.** C'est le seul cas où l'on perdait
une information qu'on avait soi-même sollicitée — et le pire, parce que le syndic
a répondu, il considère l'affaire traitée de son côté, et personne ne voit rien.

## Ce que cette table permet, et ce qu'elle refuse

Elle rattache un jeton à la LISTE des tickets d'un envoi. À la réception, la
réponse est donc identifiable — mais elle n'est **pas ventilée dans les fils**.

Le syndic écrit « pour le TK-123 on intervient jeudi, le TK-456 est clos ».
Recopier ce texte dans quatre fils le rendrait faux dans trois d'entre eux.
Aucune machine ne peut décider quelle phrase concerne quel dossier ; le faire
serait faire semblant de savoir. La réponse va donc au **conseil syndical**, avec
la liste des tickets concernés — il est déjà en copie de la relance, c'est donc le
bon récepteur.

## Pas de clé étrangère, et c'est délibéré

`tickets_json` est une liste d'identifiants, pas une table de liaison. Deux
raisons :

- SQLite refuse d'ajouter une contrainte à une table existante — la règle du
  dépôt depuis les migrations 0117 et 0165, qui ont toutes deux crashé pour
  l'avoir oubliée ;
- et surtout, cette liste dit ce que le MESSAGE contenait, pas ce que les tickets
  sont devenus. Un ticket supprimé ensuite ne doit pas effacer la trace de ce
  qu'on a écrit au syndic. Une clé étrangère avec cascade ferait exactement cela.

Revision ID: 0172
Revises: 0171
Create Date: 2026-09-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0172"
down_revision = "0171"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade():
    if "relance_courriel" in _tables():
        return
    op.create_table(
        "relance_courriel",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jeton", sa.String(), nullable=False),
        sa.Column("tickets_json", sa.String(), nullable=False, server_default="[]"),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_relance_courriel_jeton", "relance_courriel", ["jeton"], unique=True
    )


def downgrade():
    if "relance_courriel" not in _tables():
        return
    op.drop_index("ix_relance_courriel_jeton", table_name="relance_courriel")
    op.drop_table("relance_courriel")
