"""Tables d'association M2M user_vigik et user_telecommande

Permet d'associer un Vigik ou une Telecommande à plusieurs utilisateurs
(copropriétaires, conjoint partageant le même lot).

Backfill : crée une entrée UserVigik/UserTelecommande pour chaque
Vigik.user_id et Telecommande.user_id existant.

Revision ID: 0083
Revises: 0082
Create Date: 2026-04-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0083"
down_revision = "0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_vigik",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("vigik_id", sa.Integer, sa.ForeignKey("vigik.id"), nullable=False),
        sa.UniqueConstraint("user_id", "vigik_id", name="uq_user_vigik"),
    )

    op.create_table(
        "user_telecommande",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("telecommande_id", sa.Integer, sa.ForeignKey("telecommande.id"), nullable=False),
        sa.UniqueConstraint("user_id", "telecommande_id", name="uq_user_telecommande"),
    )

    # Backfill : chaque Vigik/TC existant → entrée pour le détenteur
    op.execute(
        "INSERT INTO user_vigik (user_id, vigik_id) "
        "SELECT user_id, id FROM vigik"
    )
    op.execute(
        "INSERT INTO user_telecommande (user_id, telecommande_id) "
        "SELECT user_id, id FROM telecommande"
    )

    # Backfill copropriétaires : pour chaque Vigik/TC lié à un lot,
    # ajouter les copropriétaires du même lot (conjoint, co-indivisaires…)
    # type_lien IN ('propriétaire','bailleur','mandataire') = copropriétaires
    op.execute(
        "INSERT INTO user_vigik (user_id, vigik_id) "
        "SELECT ul.user_id, v.id "
        "FROM vigik v "
        "JOIN user_lot ul ON ul.lot_id = v.lot_id AND ul.actif = 1 "
        "WHERE v.lot_id IS NOT NULL "
        "  AND ul.type_lien IN ('propriétaire', 'bailleur', 'mandataire') "
        "  AND NOT EXISTS ("
        "    SELECT 1 FROM user_vigik uv "
        "    WHERE uv.user_id = ul.user_id AND uv.vigik_id = v.id"
        "  )"
    )
    op.execute(
        "INSERT INTO user_telecommande (user_id, telecommande_id) "
        "SELECT ul.user_id, t.id "
        "FROM telecommande t "
        "JOIN user_lot ul ON ul.lot_id = t.lot_id AND ul.actif = 1 "
        "WHERE t.lot_id IS NOT NULL "
        "  AND ul.type_lien IN ('propriétaire', 'bailleur', 'mandataire') "
        "  AND NOT EXISTS ("
        "    SELECT 1 FROM user_telecommande ut "
        "    WHERE ut.user_id = ul.user_id AND ut.telecommande_id = t.id"
        "  )"
    )


def downgrade() -> None:
    op.drop_table("user_telecommande")
    op.drop_table("user_vigik")
