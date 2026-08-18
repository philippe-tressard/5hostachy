"""Le workflow d'une petite annonce : cinq états, et l'horodatage qui les date.

Demandé le 18/08/2026 : *« Ajouter une section workflow (En cours ; vendu,
annuler) — les annonces restent à l'état vendu pendant 1 mois et sont archivées
dans une section pliée par défaut »*. Les états retenus après arbitrage : **En
cours · Réservé · Vendu · Donné · Annulé**.

🔴 **Cette migration contredit une déclaration écrite la veille**, et c'est
assumé : `front/src/lib/entites/annonce.ts` posait `sansObjet` sur la section 3
— *« une annonce n'a pas d'étapes de vie suivies à plusieurs »*. C'était mon
arbitrage ; l'utilisateur a tranché l'inverse. La déclaration est corrigée dans
le même lot, sans quoi `lint:etats` refuserait le rendu — c'est précisément à ça
qu'il sert.

## Les conversions, et pourquoi aucune ne perd d'information

| Avant | Après | Raison |
|---|---|---|
| `disponible` | `en_cours` | même notion, le libellé demandé |
| `archive` | `annule` | « archivé » désignait le geste *retirer de la liste* ; le seul état terminal qui ne ment pas sur une annonce non conclue est « Annulé » |

⚠️ Les annonces ex-`archive` reçoivent un `statut_change_le` **volontairement
ancien** (400 jours). Sans cela, elles réapparaîtraient dans la liste principale
pendant un mois : leur auteur les avait rangées, elles doivent le rester. C'est
la seule écriture de ce fichier qui ne soit pas une traduction mot à mot, et
c'est pour préserver une intention, pas une valeur.

Les autres lignes reçoivent `mis_a_jour_le`, à défaut `cree_le` — la meilleure
approximation disponible de « depuis quand cette annonce est-elle dans cet
état ». Une colonne laissée à `NULL` aurait fait retomber `_est_archivee` sur un
repli, donc sur une règle différente de celle qui s'appliquera ensuite.

## Pourquoi `archive` ne devient pas un sixième état

L'archivage n'est pas une étape que quelqu'un choisit : c'est une conséquence du
temps. Il se **calcule**. En faire un état aurait donné deux notions pour la même
chose — celle qu'on pose et celle qui arrive — libres de se contredire dès la
première annonce archivée à la main puis rouverte.

Revision ID: 0152
Revises: 0151
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0152"
down_revision = "0151"
branch_labels = None
depends_on = None

TABLE = "petite_annonce"
COLONNE = "statut_change_le"

#  Les annonces déjà rangées restent rangées : un horodatage plus vieux que le
#  délai d'archivage (30 jours) les envoie directement dans l'Historique.
JOURS_ANCIENNETE_ARCHIVEES = 400


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if COLONNE not in _colonnes(TABLE):
        op.add_column(TABLE, sa.Column(COLONNE, sa.DateTime(), nullable=True))

    bind = op.get_bind()

    #  ⚠️ `text(...).bindparams(...)` et jamais de f-string : la règle du projet
    #  vaut même quand les valeurs sont des constantes de ce fichier. Une
    #  exception « parce que c'est constant » est exactement ce qui rend la règle
    #  inapplicable au cas suivant.
    bind.execute(
        text(f"UPDATE {TABLE} SET statut = :apres WHERE statut = :avant").bindparams(
            avant="disponible", apres="en_cours"
        )
    )

    #  Les ex-archivées : état terminal ET horodatage ancien, dans le même geste.
    #  Les séparer laisserait, entre les deux instructions, une annonce annulée
    #  et fraîche — donc visible.
    bind.execute(
        text(
            f"UPDATE {TABLE} SET statut = :apres, {COLONNE} = datetime('now', :recul) "
            "WHERE statut = :avant"
        ).bindparams(
            avant="archive",
            apres="annule",
            recul=f"-{JOURS_ANCIENNETE_ARCHIVEES} days",
        )
    )

    #  Toutes les autres : la meilleure approximation disponible.
    bind.execute(
        text(
            f"UPDATE {TABLE} SET {COLONNE} = COALESCE(mis_a_jour_le, cree_le) "
            f"WHERE {COLONNE} IS NULL"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        text(f"UPDATE {TABLE} SET statut = :apres WHERE statut = :avant").bindparams(
            avant="en_cours", apres="disponible"
        )
    )
    #  `donne` n'existait pas avant : il retombe sur `vendu`, le seul état
    #  antérieur qui décrive une annonce conclue.
    bind.execute(
        text(f"UPDATE {TABLE} SET statut = :apres WHERE statut = :avant").bindparams(
            avant="donne", apres="vendu"
        )
    )
    bind.execute(
        text(f"UPDATE {TABLE} SET statut = :apres WHERE statut = :avant").bindparams(
            avant="annule", apres="archive"
        )
    )
    op.drop_column(TABLE, COLONNE)
