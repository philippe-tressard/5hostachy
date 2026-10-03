"""Télémétrie : deux séries (gestionnaire ou non), la présence mensuelle, et la politique le dit (03/10/2026)

L'onglet Télémétrie gagne quatre vues (Jour, Mois, Année sur 12 mois, Total par
année) et un filtre « avec / sans gestionnaire du site ». Deux faits manquaient
aux agrégats pour le permettre :

1. **`gestionnaire`** sur `telemetry_daily` et `telemetry_monthly` — nullable,
   SANS valeur par défaut : les lignes déjà agrégées ne savent pas se séparer
   (`None` = non distingué), et l'écran dit jusqu'à quand c'est le cas. Les
   nouvelles lignes portent `True` (le gestionnaire du site) ou `False`. Deux
   colonnes simples : aucune clé étrangère, aucune contrainte altérée.
2. **`presence_mensuelle`** — par mois et par compte, le seul fait « venu »,
   pendant 12 mois : c'est ce qui permet à « Qui vient » d'exister sur la vue
   Année alors que les évènements détaillés ne vivent que 30 jours. Table
   neuve, un index par colonne de recherche et l'unicité du couple.
3. **La politique servie le dit** : le passage sur la conservation, lu dans le
   seed (`TELEMETRIE_CONSERVATION_ANCIEN` → `TELEMETRIE_CONSERVATION`), est
   remplacé EXACTEMENT (`utils/textes_livres`) ; un texte reformulé à la main
   n'est pas touché — l'administrateur l'ajoute alors depuis Admin › Légal.

Idempotente : une colonne ou une table qui existe n'est pas recréée, le passage
n'est remplacé que s'il figure tel quel.

⚠️ Les noms de tables, de colonnes et la clé de configuration sont des
CONSTANTES du fichier.

Revision ID: 0254
Revises: 0253
"""

import sqlalchemy as sa

from alembic import op

revision = "0254"
down_revision = "0253"
branch_labels = None
depends_on = None

AGREGATS = ("telemetry_daily", "telemetry_monthly")  # identifiants : constantes du fichier
COLONNE = "gestionnaire"
TABLE = "presence_mensuelle"
POLITIQUE = "politique_confidentialite"


def _texte(conn) -> str | None:
    ligne = conn.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = :c").bindparams(c=POLITIQUE)
    ).fetchone()
    return (ligne[0] or "") if ligne else None


def _corriger(conn, avant: str, apres: str) -> int:
    from app.utils.textes_livres import remplacer_passage

    return remplacer_passage(conn, "config_site", {"cle": POLITIQUE}, "valeur", avant, apres)


def _colonnes(conn, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(table)}


def upgrade() -> None:
    from app.seed.contenus_legaux import TELEMETRIE_CONSERVATION, TELEMETRIE_CONSERVATION_ANCIEN

    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    for table in AGREGATS:
        if table in tables and COLONNE not in _colonnes(conn, table):
            op.add_column(table, sa.Column(COLONNE, sa.Boolean(), nullable=True))
    if TABLE not in tables:
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("mois", sa.String(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.UniqueConstraint("mois", "user_id", name="uq_presence_mensuelle"),
        )
        op.create_index(f"ix_{TABLE}_mois", TABLE, ["mois"])
        op.create_index(f"ix_{TABLE}_user_id", TABLE, ["user_id"])
    if "config_site" in tables:
        texte = _texte(conn)
        if texte is not None and TELEMETRIE_CONSERVATION not in texte:
            _corriger(conn, TELEMETRIE_CONSERVATION_ANCIEN, TELEMETRIE_CONSERVATION)


def downgrade() -> None:
    from app.seed.contenus_legaux import TELEMETRIE_CONSERVATION, TELEMETRIE_CONSERVATION_ANCIEN

    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if "config_site" in tables:
        _corriger(conn, TELEMETRIE_CONSERVATION, TELEMETRIE_CONSERVATION_ANCIEN)
    if TABLE in tables:
        op.drop_table(TABLE)
    for table in AGREGATS:
        if table in tables and COLONNE in _colonnes(conn, table):
            with op.batch_alter_table(table) as lot:
                lot.drop_column(COLONNE)
