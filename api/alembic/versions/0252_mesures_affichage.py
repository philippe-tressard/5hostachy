"""Les durées d'affichage des écrans sont mesurées, et la politique le dit (#1632, 03/10/2026)

« Le site rame » se diagnostiquait à la main : rien ne disait combien de temps
un résident attend un écran. Le navigateur mesure désormais le chargement de
la première page et chaque passage d'un écran à l'autre, et le serveur garde
ces durées (`utils/mesures_affichage`).

1. **`mesure_affichage`** — une ligne par mesure (un centile ne se calcule pas
   sur des compteurs), au jour près, SANS identifiant de compte. Table neuve :
   aucune contrainte d'une table existante n'est altérée.
2. **La politique servie le dit** : le paragraphe `TELEMETRIE_PERFORMANCE`, lu
   dans le seed, est inséré juste après celui des erreurs (`TELEMETRIE_ERREURS`,
   posé par la 0251). Remplacement EXACT (`utils/textes_livres`) : un texte
   reformulé à la main n'est pas touché — l'administrateur l'ajoute alors
   depuis Admin › Légal.

Idempotente : la table n'est créée que si elle manque, le paragraphe n'est
inséré que s'il n'y est pas.

⚠️ Le nom de table et la clé de configuration sont des CONSTANTES du fichier.

Revision ID: 0252
Revises: 0251
"""

import sqlalchemy as sa

from alembic import op

revision = "0252"
down_revision = "0251"
branch_labels = None
depends_on = None

TABLE = "mesure_affichage"  # identifiants : constantes du fichier
INDEX = "ix_mesure_affichage_jour"
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
    from app.seed.contenus_legaux import TELEMETRIE_ERREURS, TELEMETRIE_PERFORMANCE

    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if TABLE not in tables:
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("jour", sa.String(), nullable=False),
            sa.Column("page", sa.String(), nullable=False),
            sa.Column("indicateur", sa.String(), nullable=False),
            sa.Column("duree_ms", sa.Integer(), nullable=False),
        )
        op.create_index(INDEX, TABLE, ["jour"])

    if "config_site" not in tables:
        return
    texte = _texte(conn)
    if texte is not None and TELEMETRIE_PERFORMANCE not in texte:
        _corriger(conn, TELEMETRIE_ERREURS, TELEMETRIE_ERREURS + TELEMETRIE_PERFORMANCE)


def downgrade() -> None:
    from app.seed.contenus_legaux import TELEMETRIE_PERFORMANCE

    conn = op.get_bind()
    if "config_site" in set(sa.inspect(conn).get_table_names()):
        _corriger(conn, TELEMETRIE_PERFORMANCE, "")
    if TABLE in set(sa.inspect(conn).get_table_names()):
        op.drop_index(INDEX, TABLE)
        op.drop_table(TABLE)
