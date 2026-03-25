"""WhatsApp scheduled messages + log

Revision ID: 0065
Revises: 0064
Create Date: 2026-03-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_scheduled",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("label", sa.String, nullable=False),
        sa.Column("message", sa.String, nullable=False),
        sa.Column("cron_rule", sa.String, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("cree_le", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("mis_a_jour_le", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "whatsapp_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scheduled_id", sa.Integer, sa.ForeignKey("whatsapp_scheduled.id"), nullable=True),
        sa.Column("label", sa.String, nullable=False, server_default=""),
        sa.Column("message", sa.String, nullable=False),
        sa.Column("statut", sa.String, nullable=False, server_default="envoyé"),
        sa.Column("erreur", sa.String, nullable=True),
        sa.Column("envoye_le", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    # Seed the two recurring messages
    msg_hostachy = (
        "\U0001f4e2 Infos copro \u2013 Encombrants (*Boulevard Fernand Hostachy*)\n"
        "\U0001f4c5 Collecte : *3\u1d49* samedi du mois, d\u00e8s 6h*\n"
        "\U0001f557 Sortie : la veille apr\u00e8s 19h\n"
        "\n"
        "\u267b\ufe0f Merci de vider le local poubelle si des encombrants y ont \u00e9t\u00e9 d\u00e9pos\u00e9s provisoirement."
    )
    msg_berteaux = (
        "\U0001f4e2 Infos copro \u2013 Encombrants (*Rue Maurice Berteaux*)\n"
        "\U0001f4c5 Collecte : *4\u1d49* samedi du mois, d\u00e8s 6h*\n"
        "\U0001f557 Sortie : la veille apr\u00e8s 19h\n"
        "\n"
        "\u267b\ufe0f Merci de vider le local poubelle si des encombrants y ont \u00e9t\u00e9 d\u00e9pos\u00e9s provisoirement."
    )
    op.execute(
        "INSERT INTO whatsapp_scheduled (label, message, cron_rule, enabled) VALUES "
        f"('Encombrants Bd Hostachy', '{msg_hostachy.replace(chr(39), chr(39)*2)}', '3eme_samedi', 1), "
        f"('Encombrants Rue Berteaux', '{msg_berteaux.replace(chr(39), chr(39)*2)}', '4eme_samedi', 1)"
    )


def downgrade() -> None:
    op.drop_table("whatsapp_log")
    op.drop_table("whatsapp_scheduled")
