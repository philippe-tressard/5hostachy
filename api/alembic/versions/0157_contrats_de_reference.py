"""Les deux contrats de RÉFÉRENCE de la fiche : assurance et syndic.

## Ce que ça change

La fiche de copropriété affichait l'assurance en la DÉDUISANT : « le contrat
d'assurance actif le plus récent gagne » (#490). La règle était écrite, juste, et
**implicite** — rien à l'écran ne disait laquelle des lignes faisait foi, et une
copropriété qui garde l'ancien contrat en base (c'est tout l'intérêt d'en avoir
fait un contrat) dépendait d'une comparaison de dates pour afficher le bon
assureur.

Elle devient un **choix** : `assurance_contrat_id` désigne le contrat, et l'écran
le sélectionne dans la liste des contrats d'assurance.

Et le SYNDIC entre dans le même moule. Il n'existait nulle part comme
organisation : `MembreSyndic` porte ses PERSONNES — et dix modules les lisent,
dont tout le routage des courriels au cabinet — mais rien ne portait le cabinet
lui-même, son mandat, son échéance, ses documents.

## Ce que ça NE change PAS, et c'est délibéré

⚠️ **`MembreSyndic` n'est pas touché.** Le prestataire porte l'ORGANISATION, les
membres restent les PERSONNES, et le chemin des courriels ne bouge pas d'une
ligne. Fusionner les deux aurait donné deux listes des mêmes gens — exactement la
faute que #490 a corrigée pour l'assurance, mais cette fois sur le circuit des
notifications, où elle se serait vue le jour où un e-mail ne serait pas parti.

## Les colonnes `assurance_*` restent, et ne servent toujours à rien

Elles subsistent depuis #490 pour qu'un retour arrière reste possible. Rien ne
les lit. Ne pas les ressusciter : `copropriete_lue` les efface explicitement
avant de composer la réponse.

Revision ID: 0157
Revises: 0156
"""
from alembic import op
import sqlalchemy as sa

revision = "0157"
down_revision = "0156"
branch_labels = None
depends_on = None


def _colonnes(table: str) -> set[str]:
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(table)}


def upgrade() -> None:
    presentes = _colonnes("copropriete")

    #  ⚠️ Idempotent PAR COLONNE, et non par migration : une base rejouée ou
    #  partiellement migrée existe dans ce projet (dette connue). Une seule des
    #  deux colonnes peut donc être là.
    #
    #  🔴 DEUX COLONNES ENTIÈRES, SANS CONTRAINTE — et les deux tentatives
    #  précédentes ont été MESURÉES, pas supposées.
    #
    #  1. `batch_alter_table` + clé étrangère anonyme →
    #     `ValueError: Constraint must have a name`
    #  2. `op.add_column` + clé étrangère nommée →
    #     `NotImplementedError: No support for ALTER of constraints in SQLite`
    #
    #  ⚠️ `start.sh` a `set -e` : l'une comme l'autre aurait planté au démarrage
    #  et **bloqué le conteneur**, donc le site. Trouvé en faisant tourner la
    #  migration sur une base jetable AVANT de livrer — aucun test de la CI ne
    #  l'aurait vu, `test_migrations.py` ne vérifiant que la chaîne des révisions.
    #
    #  La contrainte reste DÉCLARÉE côté modèle (`Copropriete.assurance_contrat_id`
    #  porte son `foreign_key=`) : c'est là qu'elle documente la relation, et
    #  c'est de là qu'elle serait matérialisée le jour d'une reconstruction de
    #  table. Elle ne serait de toute façon pas VÉRIFIÉE : cette base tourne avec
    #  `PRAGMA foreign_keys=OFF` — mesuré, et suivi en #546.
    #
    #  Le mode « batch » aurait en outre RECRÉÉ `copropriete`, que `batiment` et
    #  `contrat_entretien` référencent. Éviter cette recréation pour deux colonnes
    #  nullables est un gain en soi.
    for nom in ("assurance_contrat_id", "syndic_contrat_id"):
        if nom not in presentes:
            op.add_column("copropriete", sa.Column(nom, sa.Integer(), nullable=True))

    #  🔴 REPRISE DE L'EXISTANT — sans elle, la fiche perdrait son assurance le
    #  jour du déploiement, et le défaut ressemblerait à « il n'y a plus de
    #  contrat » alors que le contrat est là.
    #
    #  On applique une dernière fois la règle qu'on remplace : le contrat
    #  d'assurance actif le plus récent devient le contrat DÉSIGNÉ. À partir de
    #  là, seul le choix compte.
    op.execute(
        sa.text(
            """
            UPDATE copropriete
               SET assurance_contrat_id = (
                     SELECT c.id FROM contrat_entretien c
                      WHERE c.copropriete_id = copropriete.id
                        AND c.type_equipement = :type_assurance
                        AND c.actif = 1
                      ORDER BY c.date_debut DESC, c.id DESC
                      LIMIT 1
                   )
             WHERE assurance_contrat_id IS NULL
            """
        ).bindparams(type_assurance="assurance")
    )

    #  Le syndic, lui, n'a rien à reprendre : aucun contrat de ce type n'existe
    #  encore. Le champ reste vide jusqu'à ce que l'administration le renseigne,
    #  et l'écran dit « non renseigné » plutôt que d'inventer.


def downgrade() -> None:
    #  Sans contrainte à défaire, le retrait est direct — pas de mode « batch »
    #  ici non plus, donc pas de recréation de table.
    for nom in ("syndic_contrat_id", "assurance_contrat_id"):
        op.drop_column("copropriete", nom)
