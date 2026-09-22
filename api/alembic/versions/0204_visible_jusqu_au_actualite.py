"""Une actualité peut dire jusqu'à quand elle est valable (#1093).

## Un seul champ pour trois familles

| Famille | Exemple | Ce qu'on saisit |
|---|---|---|
| **permanente** *(défaut)* | « Nouveau règlement » | **rien** |
| **datée** | « Coupure d'eau jeudi 9h-12h » | **rien de plus** — `debut`/`fin` suffisent |
| **à durée de vie** | « Vends vélo » | `visible_jusqu_au` |

Dans deux cas sur trois, aucun champ nouveau n'apparaît à l'écran.

## 🔴 Ce que cette migration N'ajoute PAS

Il n'y a **pas** de colonne `perime_le`, et c'est le cœur de la décision.

La péremption se **dérive à la lecture** (`utils/archivage.perime_le`), jamais
ne se recopie à l'écriture. Une date calculée à la création survivrait à un
report d'événement — jeudi devient mardi, la colonne dit encore jeudi, et
l'actualité quitte le fil le jour où elle redevient utile. C'est le motif « deux
copies qui divergent sur le cas limite », déjà payé trois fois dans ce dépôt.

## Une `date`, pas un `datetime`

« Visible jusqu'au 22 » désigne le **jour entier**. Stocker un `datetime` à
minuit ferait disparaître l'information le matin même du jour où son auteur la
croit encore affichée. La comparaison se fait donc en dates, et la péremption
tombe au **soir** du jour dit.
"""
import sqlalchemy as sa
from alembic import op

revision = "0204"
down_revision = "0203"
branch_labels = None
depends_on = None

#: L'identifiant ne peut pas se lier en SQLite : il s'interpole depuis cette
#: constante, jamais depuis une donnée (cf. CLAUDE.md, conventions Alembic).
TABLE = "publication"
COLONNE = "visible_jusqu_au"


def _colonnes_existantes(conn, table: str) -> set[str]:
    """L'inspecteur, et pas un `PRAGMA table_info('{table}')` en f-string.

    Les vingt-sept f-strings de l'historique sont figées dans
    `test_migrations.py` : une migration appliquée ne se modifie jamais, donc
    c'est de l'historique et non un retard. Mais la vingt-huitième est refusée,
    et à raison — ici l'inspecteur rend la même chose sans écrire de SQL du
    tout, donc sans avoir à se demander si l'interpolation est sûre.
    """
    return {colonne["name"] for colonne in sa.inspect(conn).get_columns(table)}


def upgrade():
    conn = op.get_bind()
    if COLONNE in _colonnes_existantes(conn, TABLE):
        return
    #  ⚠️ `nullable=True` sans `server_default` : une actualité existante est
    #  permanente, et `NULL` le dit exactement. Une valeur par défaut les ferait
    #  toutes périmer le même jour — c'est-à-dire vider le fil d'un coup.
    #
    #  ⚠️ Et pas de `ForeignKey` ici non plus : SQLite refuse d'altérer les
    #  contraintes d'une table existante. Ce n'en est pas une, mais la règle
    #  vaut d'être rappelée là où elle a déjà bloqué deux conteneurs.
    op.add_column(TABLE, sa.Column(COLONNE, sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table(TABLE) as lot:
        lot.drop_column(COLONNE)
