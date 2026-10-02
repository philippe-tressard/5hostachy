"""Les erreurs vues dans le navigateur sont comptées, et la politique le dit (#1631, 02/10/2026)

Une erreur JavaScript chez un résident ne laissait aucune trace côté serveur :
le 16/09/2026, un écran figé ne se diagnostiquait que dans la console de qui le
subissait. Le navigateur les signale désormais par la file de la mesure
d'audience, et le serveur les COMPTE (`utils/erreurs_navigateur`).

1. **`erreur_navigateur`** — un compteur par jour, page et code, SANS
   identifiant de compte. Table neuve : aucune contrainte d'une table existante
   n'est altérée.
2. **La politique servie le dit** : le paragraphe `TELEMETRIE_ERREURS`, lu dans
   le seed, est inséré juste après celui de la mesure d'audience
   (`TELEMETRIE_COLLECTE`). Remplacement EXACT (`utils/textes_livres`) : un
   texte reformulé à la main n'est pas touché — l'administrateur l'ajoute alors
   depuis Admin › Légal.

Idempotente : la table n'est créée que si elle manque, le paragraphe n'est
inséré que s'il n'y est pas.

⚠️ Le nom de table et la clé de configuration sont des CONSTANTES du fichier.

Revision ID: 0251
Revises: 0250
"""

import sqlalchemy as sa

from alembic import op

revision = "0251"
down_revision = "0250"
branch_labels = None
depends_on = None

TABLE = "erreur_navigateur"  # identifiants : constantes du fichier
INDEX = "ix_erreur_navigateur_jour"
POLITIQUE = "politique_confidentialite"


def _texte(conn) -> str | None:
    ligne = conn.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = :c").bindparams(c=POLITIQUE)
    ).fetchone()
    return (ligne[0] or "") if ligne else None


def _corriger(conn, avant: str, apres: str) -> int:
    from app.utils.textes_livres import remplacer_passage

    return remplacer_passage(conn, "config_site", {"cle": POLITIQUE}, "valeur", avant, apres)


def upgrade() -> None:
    from app.seed.contenus_legaux import TELEMETRIE_COLLECTE, TELEMETRIE_ERREURS

    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if TABLE not in tables:
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("jour", sa.String(), nullable=False),
            sa.Column("page", sa.String(), nullable=False),
            sa.Column("code", sa.String(), nullable=False),
            sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("premiere_le", sa.DateTime(), nullable=False),
            sa.Column("derniere_le", sa.DateTime(), nullable=False),
        )
        op.create_index(INDEX, TABLE, ["jour"])

    if "config_site" not in tables:
        return
    texte = _texte(conn)
    if texte is not None and TELEMETRIE_ERREURS not in texte:
        _corriger(conn, TELEMETRIE_COLLECTE, TELEMETRIE_COLLECTE + TELEMETRIE_ERREURS)


def downgrade() -> None:
    from app.seed.contenus_legaux import TELEMETRIE_ERREURS

    conn = op.get_bind()
    if "config_site" in set(sa.inspect(conn).get_table_names()):
        _corriger(conn, TELEMETRIE_ERREURS, "")
    if TABLE in set(sa.inspect(conn).get_table_names()):
        op.drop_index(INDEX, TABLE)
        op.drop_table(TABLE)
