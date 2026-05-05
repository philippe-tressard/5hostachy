"""Ticket : champs non_relancable + modele_email relance_syndic + config delai

Revision ID: 0104
Revises: 0103
Create Date: 2026-05-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0104"
down_revision = "0103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── Nouveaux champs sur la table ticket ───────────────────────────────
    columns = [row[1] for row in conn.execute(sa.text("PRAGMA table_info('ticket')"))]
    if "non_relancable" not in columns:
        op.add_column("ticket", sa.Column("non_relancable", sa.Boolean, server_default="0", nullable=False))
    if "non_relancable_motif" not in columns:
        op.add_column("ticket", sa.Column("non_relancable_motif", sa.Text, nullable=True))

    # ── Config : délai de relance syndic (jours) ──────────────────────────
    op.execute(
        "INSERT OR IGNORE INTO config_site (cle, valeur) VALUES ('relance_syndic_delai_jours', '30')"
    )

    # ── Template email relance_syndic (import depuis seed.py) ────────────
    from app.seed import EMAIL_TEMPLATES
    tpl = next(t for t in EMAIL_TEMPLATES if t[0] == 'relance_syndic')
    _code, libelle, sujet, corps_html, _desactivable = tpl

    corps_texte = "Relance ticket(s) non résolu(s) — {{ residence.nom }}"
    variables = '["civilite", "nom_gestionnaire", "residence", "tickets", "reference_copro"]'
    op.execute(
        sa.text(
            "INSERT OR IGNORE INTO modele_email "
            "(code, libelle, sujet, corps_html, corps_texte, variables_disponibles, desactivable, actif)"
            " VALUES (:code, :libelle, :sujet, :corps_html, :corps_texte, :variables, 0, 1)"
        ).bindparams(
            code="relance_syndic",
            libelle=libelle,
            sujet=sujet,
            corps_html=corps_html,
            corps_texte=corps_texte,
            variables=variables,
        )
    )


def downgrade() -> None:
    op.drop_column("ticket", "non_relancable")
    op.drop_column("ticket", "non_relancable_motif")
    op.execute("DELETE FROM config_site WHERE cle = 'relance_syndic_delai_jours'")
    op.execute("DELETE FROM modele_email WHERE code = 'relance_syndic'")
