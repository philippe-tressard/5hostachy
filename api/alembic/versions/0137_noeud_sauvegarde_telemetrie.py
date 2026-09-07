"""Sauvegarde et agrégation télémétrie enregistrent enfin QUEL nœud les a exécutées.

Sur un HA à deux nœuds dont le rôle alterne chaque nuit, « quel nœud » est
précisément l'information qui compte : une sauvegarde qui ne tournerait plus que
d'un côté ne se verrait pas. `historique_maintenance` porte cette colonne depuis
l'unification des tâches planifiées ; `historique_sauvegarde` et
`historique_telemetrie` sont antérieures et ne l'avaient jamais reçue — l'écran
d'administration affichait donc « non enregistré » pour ces deux tâches (#312).

**Colonne nullable, sans valeur par défaut, et AUCUN rétro-remplissage.** Les
lignes déjà en base resteront `NULL`, donc « non enregistré », et c'est le seul
état correct : personne ne sait sur quel nœud elles ont tourné. Le 11/08/2026,
la valeur avait été inventée à la lecture — on affichait le nœud qui répondait à
la requête, faux une fois sur deux dès la bascule suivante. La corriger dans
l'autre sens, en peuplant les anciennes lignes, referait exactement la même
faute : présenter une valeur par défaut comme une mesure (`standards/04`).

La valeur est désormais posée **à l'écriture**, par `utils/noeud.py`, aux quatre
points où une ligne naît (job automatique et déclenchement manuel, pour chacune
des deux tâches). La colonne se remplira donc d'elle-même à la première
exécution suivant le déploiement, et le front l'affiche déjà dès qu'elle est
renseignée — `TachesPlanifiees.svelte` n'a pas à changer.

Indexée comme celle d'`historique_maintenance` : les vues de santé filtrent par
nœud, et les deux tables se lisent de la même façon.

Revision ID: 0137
Revises: 0136
Create Date: 2026-08-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0137"
down_revision = "0136"
branch_labels = None
depends_on = None

#: (table, index) — les deux tables reçoivent exactement le même traitement.
TABLES = (
    ("historique_sauvegarde", "ix_historique_sauvegarde_noeud"),
    ("historique_telemetrie", "ix_historique_telemetrie_noeud"),
)


def _colonnes(table: str) -> set:
    """Colonnes réellement présentes, lues sur la base en cours de migration.

    Le projet traîne une dette connue : les migrations ne sont pas idempotentes
    et `upgrade head` depuis zéro échoue déjà. On ne la creuse pas — ajouter une
    colonne qui existe déjà ferait échouer `alembic upgrade`, or `start.sh` a
    `set -e` : un conteneur qui ne démarre plus, sur les deux nœuds.
    """
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(table)}


def upgrade() -> None:
    for table, index in TABLES:
        if "noeud" in _colonnes(table):
            continue
        op.add_column(table, sa.Column("noeud", sa.String(), nullable=True))
        op.create_index(index, table, ["noeud"])


def downgrade() -> None:
    for table, index in TABLES:
        if "noeud" not in _colonnes(table):
            continue
        op.drop_index(index, table_name=table)
        op.drop_column(table, "noeud")
