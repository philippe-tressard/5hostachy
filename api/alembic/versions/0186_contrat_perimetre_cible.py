"""`contrat_entretien.perimetre_cible` : un contrat couvre un PÉRIMÈTRE, pas un bâtiment.

## Pourquoi

Le carnet d'entretien (10/09/2026) devait pouvoir filtrer sur « Parking »,
« Caves » ou « Voie d'accès » — qui ne sont pas des bâtiments. Un contrat ne
portait que `batiment_id` : sur un tel filtre, il ne pouvait répondre ni oui ni
non.

L'arborescence administrée (`perimetre`) décrit le patrimoine ; la table des
bâtiments n'en décrit qu'une partie. Et elle s'enrichit **sans migration**, ce
qu'une colonne ne sait pas faire : un périmètre créé demain dans Admin →
Patrimoine devient immédiatement filtrable.

## La reprise de l'existant se fait ICI, et c'est le point de cette migration

Un contrat rattaché au bâtiment 3 devient `["bat:3"]`, les autres
`["résidence"]`. **Personne n'a rien à ressaisir**, et le filtre est exact dès le
premier démarrage — sans quoi tous les contrats existants auraient répondu
« résidence entière » et le filtre par bâtiment serait devenu faux le jour où il
devenait exact ailleurs.

⚠️ `batiment_id` **reste**, et devient une valeur DÉRIVÉE que le serveur
recalcule à chaque écriture (cf. le commentaire du modèle). Le supprimer aurait
demandé un `DROP COLUMN` sur une colonne portant une clé étrangère — le genre de
migration qui échoue après avoir modifié la table, et qui bloque alors le
conteneur au démarrage (`set -e` dans `start.sh`, arrivé deux fois : 0117 le
25/07/2026, 0165 le 01/09).
"""
import sqlalchemy as sa
from alembic import op

revision = "0186"
down_revision = "0185"
branch_labels = None
depends_on = None

TABLE = "contrat_entretien"
COLONNE = "perimetre_cible"


def _colonnes() -> set[str]:
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(TABLE)}


def upgrade() -> None:
    #  Garde d'idempotence : un redémarrage qui rejoue la migration ne doit pas
    #  échouer sur une colonne déjà posée.
    if COLONNE not in _colonnes():
        op.add_column(
            TABLE,
            sa.Column(COLONNE, sa.Text(), nullable=True, server_default='["résidence"]'),
        )

    #  ── La reprise, en deux ordres et sans f-string ─────────────────────────
    #
    #  ⚠️ `text(...)` et rien d'autre : une f-string dans `op.execute()` est
    #  interdite par les conventions du projet, et ici elle n'aurait même pas de
    #  variable à interpoler — c'est la forme qui compte, parce que la prochaine
    #  migration copiera celle-ci.
    conn = op.get_bind()

    #  Un bâtiment rattaché → le code du périmètre de ce bâtiment. Le préfixe
    #  `bat:` est celui de l'arborescence (`PREFIXE_BATIMENT`), employé partout
    #  ailleurs — tickets, publications, sondages.
    conn.execute(
        sa.text(
            "UPDATE contrat_entretien "
            "SET perimetre_cible = '[\"bat:' || batiment_id || '\"]' "
            "WHERE batiment_id IS NOT NULL "
            "  AND (perimetre_cible IS NULL OR perimetre_cible = :defaut)"
        ).bindparams(defaut='["résidence"]')
    )

    #  Aucun bâtiment → la résidence entière. C'est ce que la colonne valait
    #  implicitement : un contrat de nettoyage ou d'assurance ne visait aucun
    #  bâtiment parce qu'il les couvre tous.
    conn.execute(
        sa.text(
            "UPDATE contrat_entretien "
            "SET perimetre_cible = :defaut "
            "WHERE batiment_id IS NULL AND perimetre_cible IS NULL"
        ).bindparams(defaut='["résidence"]')
    )


def downgrade() -> None:
    if COLONNE in _colonnes():
        op.drop_column(TABLE, COLONNE)
