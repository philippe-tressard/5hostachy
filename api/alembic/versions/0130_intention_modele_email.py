"""Annoncer en tête de chaque e-mail ce qui est attendu du destinataire.

Audit des modèles d'e-mail, volet 3. La plupart des modèles entrent dans le
détail sans annoncer la couleur : le lecteur doit lire jusqu'au bout pour savoir
si on l'informe ou si on attend un geste de lui. Sur un téléphone, dans une
liste de messages, cette information arrive trop tard.

Le bandeau est porté par une **colonne** de `modele_email` et rendu par le
gabarit commun (`email._wrap_email`), pas recopié dans chaque corps. Deux
raisons :

- une migration qui réécrirait vingt-quatre corps écraserait au passage les
  personnalisations faites depuis Admin → Emails, que ce dépôt s'applique
  justement à préserver par des `REPLACE()` chirurgicaux ;
- un préambule recopié vingt-quatre fois devient introuvable le jour où il faut
  le changer, et diverge entre les copies. C'est la duplication que le socle
  interdit, appliquée à du texte plutôt qu'à du code.

Les quatre valeurs (`information`, `action_requise`, `reponse_attendue`,
`archive`) sont éditables depuis Admin → Emails. Une valeur vide ou inconnue ne
rend aucun bandeau : un modèle sans intention déclarée reste exactement ce
qu'il était.

L'affectation ci-dessous vient de `seed.INTENTIONS_PAR_MODELE`, pour éviter
d'entretenir deux listes qui divergeraient. La clause `WHERE intention = ''`
rend la migration idempotente et respecte un choix déjà fait à la main.

Revision ID: 0130
Revises: 0129
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0130"
down_revision = "0129"
branch_labels = None
depends_on = None


def _colonne_existe(conn, table: str, colonne: str) -> bool:
    return colonne in [
        row[1] for row in conn.execute(sa.text(f"PRAGMA table_info({table})"))
    ]


def upgrade():
    conn = op.get_bind()

    if not _colonne_existe(conn, "modele_email", "intention"):
        with op.batch_alter_table("modele_email") as batch_op:
            batch_op.add_column(
                sa.Column("intention", sa.String(), nullable=False, server_default="")
            )

    from app.seed import INTENTIONS_PAR_MODELE

    for code, intention in INTENTIONS_PAR_MODELE.items():
        conn.execute(
            sa.text(
                "UPDATE modele_email SET intention = :intention "
                "WHERE code = :code AND (intention IS NULL OR intention = '')"
            ).bindparams(code=code, intention=intention)
        )


def downgrade():
    with op.batch_alter_table("modele_email") as batch_op:
        batch_op.drop_column("intention")
