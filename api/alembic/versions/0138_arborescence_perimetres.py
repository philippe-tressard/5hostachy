"""L'arborescence des périmètres entre en base — et sort du code.

Le périmètre d'un contenu (« résidence », « bat:3 », « parking ») était une table de
libellés **écrite en dur**, et elle l'était deux fois avec deux contenus différents :
`api/app/utils/perimetres.py` couvrait `bat:1` à `bat:9` par une boucle sur une
constante `_BATIMENTS = 9` sans rapport avec le contenu réel de la table `batiment`,
tandis que `front/src/lib/utils.ts` s'arrêtait à `bat:4`. Un cinquième bâtiment
s'affichait donc « Bât. 5 » côté API et **`bat:5` brut** à l'écran. Aucune description
n'existait nulle part : ni champ, ni aide, ni infobulle — et « AFUL » était omis de
quatre textes destinés aux résidents, alors que ce périmètre notifie tout le conseil
syndical.

Cette migration ne crée que la **table**. Les nœuds sont posés par
`app/seed/patrimoine.py`, qui suit la règle du paquet `seed` : il pose ce qui manque et
n'écrase jamais ce qui existe. Écrire les données ici les figerait, alors qu'elles sont
précisément ce que l'administration doit pouvoir refaire — le produit doit servir une
autre copropriété, qui n'a ni AFUL, ni quatre bâtiments, ni forcément de caves.

**Aucune donnée existante n'est migrée, et c'est voulu.** Les codes semés sont
identiques à ceux déjà stockés (`résidence`, `parking`, `cave`, `aful`, et `bat:{id}`
dérivé de la table `batiment`) : les cinq entités qui portent un périmètre — `ticket`,
`publication`, `evenement`, `devis_prestataire`, `annonce_hall` — continuent de
fonctionner sans qu'une seule de leurs lignes soit touchée, et leurs trois formats de
stockage (JSON, CSV, scalaire) restent lus tels quels.

Idempotente par consultation de `sqlite_master` : sur les installations en service,
`create_db_and_tables()` (SQLModel `create_all`) a pu créer la table avant qu'Alembic
n'arrive. `start.sh` a `set -e` — une migration qui échoue laisse le conteneur bloqué.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0138"
down_revision = "0137"
branch_labels = None
depends_on = None


def _table_existe(nom: str) -> bool:
    resultat = op.get_bind().execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:nom"),
        {"nom": nom},
    ).first()
    return resultat is not None


def upgrade() -> None:
    if _table_existe("perimetre"):
        return

    op.create_table(
        "perimetre",
        sa.Column("id", sa.Integer, primary_key=True),
        #  Ce qui est stocké dans les contenus. Unique et immuable après création :
        #  le modifier orphelinerait les tickets déjà publiés.
        sa.Column("code", sa.String, nullable=False),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("perimetre.id"), nullable=True),
        sa.Column("libelle", sa.String, nullable=False),
        sa.Column("libelle_court", sa.String, nullable=True),
        sa.Column("description", sa.String, nullable=False, server_default=""),
        sa.Column("icone", sa.String, nullable=True),
        #  La clé étrangère qui remplace le préfixe textuel `bat:`, analysé jusqu'ici
        #  à sept endroits du dépôt sans qu'aucun lien ne soit déclaré.
        sa.Column("batiment_id", sa.Integer, sa.ForeignKey("batiment.id"), nullable=True),
        #  Remplace la liste `SCOPES_RESIDENCE`, qui existait en trois exemplaires
        #  (visibility.py, flux/evenements.py, et le tableau de bord côté front).
        sa.Column("portee_globale", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("selectionnable", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("ordre", sa.Integer, nullable=False, server_default="0"),
        sa.Column("actif", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("cree_le", sa.DateTime, nullable=True),
        sa.Column("modifie_le", sa.DateTime, nullable=True),
        sa.Column(
            "modifie_par_id", sa.Integer, sa.ForeignKey("utilisateur.id"), nullable=True
        ),
    )
    op.create_index("ix_perimetre_code", "perimetre", ["code"], unique=True)


def downgrade() -> None:
    if not _table_existe("perimetre"):
        return
    op.drop_index("ix_perimetre_code", table_name="perimetre")
    op.drop_table("perimetre")
