"""pv_ag : ouvre l'accès aux locataires (profil résidence_tous)

Revision ID: 0072
Revises: 0071
"""
from alembic import op
import sqlalchemy as sa

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Récupérer l'id du profil résidence_tous
    profil = conn.execute(
        sa.text("SELECT id FROM profil_acces_document WHERE code = 'résidence_tous'")
    ).fetchone()

    if profil is None:
        profil = conn.execute(
            sa.text("SELECT id FROM profil_acces_document WHERE libelle LIKE '%Tous les r%sidents%'")
        ).fetchone()

    if profil is None:
        return  # profil introuvable, on ne peut pas migrer

    profil_id = profil[0]

    # Mettre à jour la catégorie pv_ag pour utiliser ce profil
    conn.execute(
        sa.text(
            "UPDATE categorie_document SET profil_acces_id = :pid WHERE code = 'pv_ag'"
        ),
        {"pid": profil_id},
    )


def downgrade() -> None:
    conn = op.get_bind()

    profil = conn.execute(
        sa.text("SELECT id FROM profil_acces_document WHERE code = 'copropriétaires_et_cs'")
    ).fetchone()

    if profil is None:
        return

    conn.execute(
        sa.text(
            "UPDATE categorie_document SET profil_acces_id = :pid WHERE code = 'pv_ag'"
        ),
        {"pid": profil[0]},
    )
