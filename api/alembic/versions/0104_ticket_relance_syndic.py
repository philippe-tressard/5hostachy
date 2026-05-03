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

    # ── Template email relance_syndic ─────────────────────────────────────
    corps_html = (
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
        '🔔 Relance ticket(s) non résolu(s) depuis 1 mois</h2>'
        '<p style="margin:0 0 20px">{{ civilite }} {{ nom_gestionnaire }},</p>'
        '<p style="margin:0 0 20px">Le Conseil Syndical de la copropriété <strong>{{ residence.nom }}</strong> '
        'vous adresse la présente relance concernant les ticket(s) ci-dessous, '
        'transmis au syndic et restés <strong>sans avancées depuis plus d\'1 mois</strong>.</p>'
        '{% for item in tickets %}'
        '<table role="presentation" style="width:100%;margin:0 0 24px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden">'
        '<tr><td style="background:#F2EFE9;padding:16px">'
        '<p style="margin:0 0 8px;font-weight:700;font-size:15px;color:#1E3A5F">'
        '{{ item.numero }} — {{ item.titre }}'
        '{% if item.relance_count > 0 %}'
        ' <span style="background:#DC2626;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px;margin-left:8px">'
        'Relance n°{{ item.relance_count }}</span>'
        '{% else %}'
        ' <span style="background:#F59E0B;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px;margin-left:8px">'
        '1ère relance</span>'
        '{% endif %}'
        '</p>'
        '<p style="margin:0 0 6px;font-size:12px;color:#4B5563">'
        'Catégorie : {{ item.categorie | capitalize }} · Priorité : {{ item.priorite | capitalize }}'
        '{% if item.perimetre %} · Périmètre : {{ item.perimetre }}{% endif %}'
        '</p>'
        '<p style="margin:0 0 10px;font-size:13px;font-weight:600;color:#374151">Description :</p>'
        '<div style="font-size:13px;color:#1A1A2E;white-space:pre-line">{{ item.description }}</div>'
        '<p style="margin:12px 0 6px;font-size:13px;font-weight:600;color:#374151">Historique :</p>'
        '<ul style="margin:0;padding-left:1.2em;font-size:12px;color:#374151">'
        '{% for h in item.historique %}'
        '<li style="margin-bottom:3px">{{ h.date }} — {{ h.label }}</li>'
        '{% endfor %}'
        '</ul>'
        '</td></tr></table>'
        '{% endfor %}'
        '<p style="margin:24px 0 0">Nous vous remercions de bien vouloir nous tenir informés '
        'des actions engagées sur ces dossiers.</p>'
        '<p style="margin:8px 0 0">Cordialement,<br>'
        '<strong>Le Conseil Syndical de {{ residence.nom }}</strong></p>'
    )
    corps_texte = "Relance ticket(s) non résolu(s) — {{ residence.nom }}"
    variables = '["civilite", "nom_gestionnaire", "residence", "tickets", "reference_copro"]'
    op.execute(
        sa.text(
            "INSERT OR IGNORE INTO modele_email "
            "(code, libelle, sujet, corps_html, corps_texte, variables_disponibles, desactivable, actif)"
            " VALUES (:code, :libelle, :sujet, :corps_html, :corps_texte, :variables, 0, 1)"
        ).bindparams(
            code="relance_syndic",
            libelle="Relance tickets syndic non résolus",
            sujet="[🏢 {{ reference_copro }}] – Relance ticket(s) non résolu(s) depuis 1 mois",
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
