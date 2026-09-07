"""Une pièce jointe de ticket ou d'événement devient un `Document` (#390).

## Ce que ça prépare

Le site porte **deux** mécanismes de pièce jointe, et chacun est le meilleur sur
un axe différent : `FichiersUpload` → `*_urls` a l'interface (vignettes, retrait,
téléversement immédiat) et un modèle vide ; la table `document` a le modèle riche
(titre, type MIME, profil d'accès, auteur, date) et une interface pauvre.

La cible de #390 est de garder l'interface du premier et le modèle du second. Ces
deux colonnes sont le rattachement qui manquait : un `document` sait déjà dire
qu'il appartient à une catégorie, un contrat ou une publication — il ne savait pas
dire qu'il appartient à un ticket ou à un événement.

## Pourquoi DEUX colonnes et non trois

Le ticket annonçait « tickets, événements, évolutions ». Mais les « évolutions »
sont **trois tables distinctes** — `ticket_evolution`, `publication_evolution`,
`evenement_evolution` — chacune rattachée à son propre porteur. Une pièce jointe
déposée dans une évolution appartient donc au ticket, à l'actualité ou à
l'événement qui la porte, jamais à l'évolution elle-même : c'est ce que
« qui voit le porteur » veut dire, et `publication_id` existe déjà.

## Ce que ça NE change PAS

**Aucune ligne n'est créée ni déplacée.** Les `*_urls` existants restent en place
et continuent de fonctionner à l'identique : cette migration ouvre un chemin, elle
n'en ferme aucun. La reprise des pièces jointes existantes est un lot à part —
elle implique de **déplacer les fichiers** de `uploads/fichiers/` (servi par Caddy
sous `forward_auth`, donc lisible de toute session qui connaît l'URL) vers
`uploads/prive/` (404 chez Caddy, atteignable seulement par l'endpoint authentifié
qui applique `document_visible`). C'est cette différence de RÉGIME, et non le
modèle, qui est la vraie faille décrite dans #390.

Revision ID: 0158
Revises: 0157
"""
from alembic import op
import sqlalchemy as sa

revision = "0158"
down_revision = "0157"
branch_labels = None
depends_on = None


def _colonnes(table: str) -> set[str]:
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(table)}


def upgrade() -> None:
    presentes = _colonnes("document")

    #  ⚠️ Idempotent PAR COLONNE, comme 0157 : une base rejouée ou partiellement
    #  migrée existe dans ce projet (dette connue, cf. la mémoire
    #  `project_migrations_non_idempotentes`).
    #
    #  Colonnes NUES, sans contrainte de clé étrangère — et ce n'est pas un oubli :
    #  0157 a mesuré les deux échecs sur SQLite (« Constraint must have a name »
    #  puis « No support for ALTER of constraints in SQLite »), et `start.sh` a
    #  `set -e` : une migration qui plante BLOQUE le conteneur, donc le site.
    #  La contrainte reste DÉCLARÉE côté modèle, où elle documente la relation.
    #  Elle ne serait de toute façon pas vérifiée : cette base tourne avec
    #  `PRAGMA foreign_keys=OFF` (mesuré, suivi en #546).
    for nom in ("ticket_id", "evenement_id"):
        if nom not in presentes:
            op.add_column("document", sa.Column(nom, sa.Integer(), nullable=True))


def downgrade() -> None:
    #  Retrait par `batch_alter_table` : SQLite ne sait pas supprimer une colonne
    #  autrement qu'en recréant la table. On ne le fait QUE dans le downgrade —
    #  personne ne recrée `document` pour ajouter deux colonnes nullables.
    with op.batch_alter_table("document") as lot:
        for nom in ("ticket_id", "evenement_id"):
            lot.drop_column(nom)
