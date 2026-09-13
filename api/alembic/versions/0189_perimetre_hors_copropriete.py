"""`perimetre.hors_copropriete` : ce qui n'appartient pas à la copropriété n'est pas couvert par elle.

## Le défaut (13/09/2026, #943, signalé à l'écran)

> « Il y a une exception pour la sélection de l'AFUL : elle n'est pas incluse
>   dans “toute copropriété”. La sélection d'AFUL ne doit faire ressortir que les
>   éléments ayant a minima la catégorie AFUL. »

Sur le carnet d'entretien, filtrer sur **AFUL** remontait toutes les lignes
marquées « Copropriété entière » — l'assurance, les interventions générales, les
tickets sans périmètre. Le filtre ne filtrait donc presque rien.

La règle fautive est le troisième chemin de `couvre()` : *« une portée globale —
un contrat de nettoyage qui couvre toute la résidence entretient AUSSI le
parking »*. C'est juste **pour le parking de la résidence**, et faux pour
l'AFUL : une association foncière urbaine libre est une entité juridiquement
distincte. Ce que la copropriété entretient « en entier » ne l'entretient pas.

## Pourquoi une COLONNE et non un `if code == "aful"`

Le dépôt répète partout — modèle, seed, routeurs, sélecteur — qu'*« une autre
copropriété n'a ni AFUL, ni quatre bâtiments »*, et l'arborescence est
**administrée**. Un nom de nœud écrit dans une règle centrale serait du
spécifique au cœur du générique.

Le drapeau énonce un **fait** — ce nœud appartient à un tiers — dont la règle de
filtrage n'est que la conséquence. Une voie communale, un terrain mitoyen
conventionné relèvent de la même catégorie, et se déclareront sans une ligne de
code.

⚠️ **Distinct de `portee_globale`, et les deux coexistent sur l'AFUL.**
« Concerne tous les résidents » (qui VOIT) et « appartient à la copropriété » (ce
qui la COUVRE) sont deux questions ; l'AFUL répond oui à la première et non à la
seconde. Cette migration ne touche donc pas à la visibilité : une actualité
« résidence » reste lisible de tous, et c'est voulu.

## La reprise

`hors_copropriete = 1` sur le nœud de code `aful` s'il existe. C'est une **reprise
de données**, pas une règle : elle marque une fois l'installation existante, comme
la migration 0186 a rattaché les contrats à leur bâtiment. Sans elle, le défaut
signalé resterait présent jusqu'à ce que quelqu'un coche la case à la main — et
personne ne saurait qu'il faut la cocher.

Défaut `0` partout ailleurs : aucun périmètre existant ne change de comportement.
"""
import sqlalchemy as sa
from alembic import op

revision = "0189"
down_revision = "0188"
branch_labels = None
depends_on = None

TABLE = "perimetre"
COLONNE = "hors_copropriete"


def _colonnes() -> set[str]:
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(TABLE)}


def upgrade() -> None:
    #  Garde d'idempotence : `start.sh` a `set -e`, une migration qui crashe
    #  laisse le conteneur bloqué.
    if COLONNE not in _colonnes():
        op.add_column(
            TABLE,
            sa.Column(COLONNE, sa.Boolean(), nullable=False, server_default="0"),
        )

    #  ⚠️ `text(...)` et jamais une f-string — la forme compte, parce que la
    #  prochaine migration copiera celle-ci.
    op.get_bind().execute(
        sa.text(
            "UPDATE perimetre SET hors_copropriete = 1 WHERE lower(code) = :code"
        ).bindparams(code="aful")
    )


def downgrade() -> None:
    if COLONNE in _colonnes():
        op.drop_column(TABLE, COLONNE)
