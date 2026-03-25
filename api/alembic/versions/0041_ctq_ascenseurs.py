"""0041 — DiagnosticType : insertion CTQ ascenseurs si absent + renommage"""

revision = '0041'
down_revision = '0040'
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    conn = op.get_bind()

    # INSERT OR IGNORE : ne fait rien si code='ascenseur' existe déjà
    conn.execute(sa.text("""
        INSERT OR IGNORE INTO diagnostic_type
            (code, nom, texte_legislatif, frequence, ordre, actif)
        VALUES (
            'ascenseur',
            'CTQ ascenseurs',
            'Décret n°2004-964 du 09/09/2004 — contrôle technique quinquennal obligatoire pour tout ascenseur, réalisé par un organisme agréé indépendant de l''entreprise de maintenance. À compléter par une vérification annuelle.',
            '5 ans',
            6,
            1
        )
    """))

    # Si l'entrée existait avec l'ancien nom, on le met à jour
    conn.execute(sa.text("""
        UPDATE diagnostic_type
        SET nom = 'CTQ ascenseurs'
        WHERE code = 'ascenseur' AND nom = 'Contrôle technique ascenseur'
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE diagnostic_type SET nom = 'Contrôle technique ascenseur'
        WHERE code = 'ascenseur' AND nom = 'CTQ ascenseurs'
    """))
