"""Un ticket « Étude & travaux » peut être suivi au kanban (#833).

Demandé le 08/09/2026 :

> *« Les tickets de catégorie Étude & Travaux sont automatiquement ajoutés au
> Kanban selon le workflow : Ouvert = CS ; En cours = Syndic ; Résolu =
> Terminé ; Annulé = Annulé. À ce titre une nouvelle diffusion devient active
> par défaut "Kanban" (le CS peut la désactiver). »*

## Ce que cette colonne est, et ce qu'elle n'est PAS

`suivi_kanban` dit **si** le ticket paraît au tableau. Elle ne dit **pas où** :
la colonne se déduit du `statut`, et d'aucun autre champ.

🔴 C'est l'arbitrage du 08/09/2026, et c'est le cœur du sujet. Un second champ
d'état — une colonne `statut_kanban` sur le ticket, comme celle de `Evenement` —
aurait créé deux notions de suivi sur le même objet. Déplacer une carte aurait
changé l'une sans l'autre, et il aurait fallu décider laquelle fait foi. C'est la
règle que `$lib/kanban.ts` porte déjà pour les événements, et le défaut que
`utils/resolution_lots.py` vient de corriger ailleurs (#829).

La correspondance vit dans `app/utils/kanban_tickets.py`, source unique.

## Les tickets existants

    categorie = 'etude_travaux'  →  suivi_kanban = 1

Ils sont repris, et c'est le sens de « automatiquement ajoutés » : un chantier
en cours doit apparaître au tableau sans qu'on rouvre chaque ticket. Le conseil
décoche ceux qu'il ne veut pas y voir.

⚠️ **Pas de `ForeignKey` dans cet `add_column`** — SQLite refuse d'altérer les
contraintes d'une table existante, la migration crasherait *après* avoir ajouté
la colonne, et `start.sh` (`set -e`) bloquerait le conteneur. C'est arrivé deux
fois (0117, 0165). Ici la colonne est un booléen : la question ne se pose pas,
mais la garde d'idempotence reste, pour la même raison.
"""
import sqlalchemy as sa
from alembic import op

revision = "0181"
down_revision = "0180"
branch_labels = None
depends_on = None


def _colonnes(nom_table: str) -> set[str]:
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(nom_table)}


def upgrade() -> None:
    #  Garde d'idempotence : un redémarrage qui rejoue la migration ne doit pas
    #  échouer sur une colonne déjà posée.
    if "suivi_kanban" not in _colonnes("ticket"):
        op.add_column(
            "ticket",
            sa.Column("suivi_kanban", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    #  🔴 Jamais de f-string dans `op.execute()` (`CLAUDE.md`). La catégorie
    #  passe par `bindparams`, même si elle est ici une constante du code : la
    #  règle ne souffre pas d'exception « quand c'est sûr », sinon elle se
    #  négocie à chaque fois.
    op.execute(
        sa.text(
            "UPDATE ticket SET suivi_kanban = 1 WHERE categorie = :categorie"
        ).bindparams(categorie="etude_travaux")
    )


def downgrade() -> None:
    if "suivi_kanban" in _colonnes("ticket"):
        op.drop_column("ticket", "suivi_kanban")
