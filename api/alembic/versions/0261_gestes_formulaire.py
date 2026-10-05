"""Les ouvertures et envois des formulaires sont comptés, et la politique le dit (#1633, 04/10/2026)

On savait qu'une page de formulaire avait été vue, pas si le geste avait abouti.
Le navigateur signale désormais, par la file de la mesure d'audience, l'ouverture
et l'envoi réussi de quelques formulaires, et le serveur les COMPTE
(`utils/gestes_formulaire`).

1. **`geste_formulaire`** — un compteur par jour et par geste (identifiant de la
   liste fermée du front, jamais un contenu), SANS identifiant de compte. Table
   neuve : aucune contrainte d'une table existante n'est altérée.
2. **La politique servie le dit** : le paragraphe `TELEMETRIE_GESTES`, lu dans le
   seed, est inséré juste après celui des durées d'affichage
   (`TELEMETRIE_PERFORMANCE`). Remplacement EXACT (`utils/textes_livres`) : un
   texte reformulé à la main n'est pas touché — l'administrateur l'ajoute alors
   depuis Admin › Légal.

Idempotente : la table n'est créée que si elle manque, le paragraphe n'est
inséré que s'il n'y est pas.

⚠️ Le nom de table et la clé de configuration sont des CONSTANTES du fichier.

Revision ID: 0261
Revises: 0260
"""

import sqlalchemy as sa

from alembic import op

revision = "0261"
down_revision = "0260"
branch_labels = None
depends_on = None

TABLE = "geste_formulaire"  # identifiants : constantes du fichier
INDEX = "ix_geste_formulaire_jour"
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
    from app.seed.contenus_legaux import TELEMETRIE_GESTES, TELEMETRIE_PERFORMANCE

    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if TABLE not in tables:
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("jour", sa.String(), nullable=False),
            sa.Column("geste", sa.String(), nullable=False),
            sa.Column("ouvertures", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("envois", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index(INDEX, TABLE, ["jour"])

    if "config_site" not in tables:
        return
    texte = _texte(conn)
    if texte is not None and TELEMETRIE_GESTES not in texte:
        _corriger(conn, TELEMETRIE_PERFORMANCE, TELEMETRIE_PERFORMANCE + TELEMETRIE_GESTES)


def downgrade() -> None:
    from app.seed.contenus_legaux import TELEMETRIE_GESTES

    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if "config_site" in tables:
        _corriger(conn, TELEMETRIE_GESTES, "")
    if TABLE in tables:
        op.drop_table(TABLE)
