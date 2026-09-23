"""Les tables d'attribution des badges disparaissent (#1194, V3 — 23/09/2026).

`user_vigik` et `user_telecommande` disaient « ce badge est aussi à cette
personne ». Depuis la 0213, un badge appartient à son lot et ses porteurs se
LISENT (`utils/porteurs_acces`) : plus aucun code ne les écrit ni ne les lit
depuis la v2.24.0. Les garder laisserait croire qu'elles font foi.

⚠️ Ce qu'elles contenaient n'est pas reconstruit au retour arrière : c'était
une réponse DÉRIVÉE, recopiée par sept chemins — la règle du lot la redonne.
Le retour arrière recrée les tables vides.
"""
import sqlalchemy as sa
from alembic import op

revision = "0214"
down_revision = "0213"
branch_labels = None
depends_on = None

#: Les deux tables et la colonne qui pointe le badge — identifiants constants.
TABLES = (("user_vigik", "vigik_id", "vigik"), ("user_telecommande", "telecommande_id", "telecommande"))


def upgrade() -> None:
    existantes = set(sa.inspect(op.get_bind()).get_table_names())
    for table, _colonne, _cible in TABLES:
        if table in existantes:
            op.drop_table(table)


def downgrade() -> None:
    existantes = set(sa.inspect(op.get_bind()).get_table_names())
    for table, colonne, cible in TABLES:
        if table not in existantes:
            op.create_table(
                table,
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("user_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
                sa.Column(colonne, sa.Integer(), sa.ForeignKey(cible + ".id"), nullable=False),
            )
