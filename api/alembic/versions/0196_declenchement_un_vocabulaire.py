"""La colonne « Déclenchée par » parlait trois langues (18/09/2026).

## Ce que l'écran montrait

`TachesPlanifiees` affiche `declenchee_par` **tel quel**. Trois vocabulaires y
coexistaient pour deux idées — `manuelle`, `automatique`, `cron` — selon la
tâche et selon le chemin emprunté. Le lecteur voyait « cron » pour une
télémétrie et « automatique » pour une sauvegarde, sans qu'aucune différence ne
le justifie.

⚠️ Et une valeur était FAUSSE : le repli de `run_maintenance` — le chemin du
planificateur — posait `manuelle` et aucun nœud. Une maintenance automatique
s'affichait donc comme déclenchée à la main. Le code est corrigé dans le même
lot ; cette migration s'occupe de ce qui est DÉJÀ écrit.

## Ce qu'elle fait, et ce qu'elle ne fait pas

Elle traduit `cron` en `automatique` sur les trois historiques. C'est un
vocabulaire d'AFFICHAGE : aucun fait ne change, seul le mot employé pour le
dire.

🔴 Elle ne touche PAS aux lignes `manuelle` de la maintenance, et c'est
délibéré : on ne sait pas, après coup, lesquelles venaient du planificateur et
lesquelles d'un clic. Les réécrire toutes en `automatique` effacerait de vrais
lancements manuels ; les laisser garde une trace imparfaite mais honnête. Le
défaut ne se reproduit plus à partir de cette version — c'est tout ce qu'une
migration peut promettre ici (`standards/06` : ne pas inventer une donnée qu'on
n'a pas).

Revision ID: 0196
Revises: 0195
Create Date: 2026-09-18
"""
import sqlalchemy as sa
from alembic import op

revision = "0196"
down_revision = "0195"
branch_labels = None
depends_on = None

#: Les trois historiques qui portent la colonne.
TABLES = ("historique_sauvegarde", "historique_maintenance", "historique_telemetrie")

#: Les mots d'hier → le mot d'aujourd'hui. `manuelle` n'y figure pas : il est
#: déjà du vocabulaire.
TRADUCTIONS = {
    "cron": "automatique",
    "auto": "automatique",
    "automatic": "automatique",
}


def _tables_presentes(conn) -> list[str]:
    """Celles qui existent VRAIMENT — une base neuve les a toutes, pas une ancienne."""
    connues = set(sa.inspect(conn).get_table_names())
    return [t for t in TABLES if t in connues]


def upgrade() -> None:
    conn = op.get_bind()
    for table in _tables_presentes(conn):
        for ancien, nouveau in TRADUCTIONS.items():
            conn.execute(
                sa.text(
                    f"UPDATE {table} SET declenchee_par = :nouveau "  # noqa: S608 — nom de table de la liste ci-dessus
                    "WHERE declenchee_par = :ancien"
                ).bindparams(nouveau=nouveau, ancien=ancien)
            )


def downgrade() -> None:
    #  Le retour rend `cron` aux trois tables : c'est le mot que les scripts
    #  d'infra envoyaient, et la version précédente du code le réécrirait de
    #  toute façon au premier rapport.
    conn = op.get_bind()
    for table in _tables_presentes(conn):
        conn.execute(
            sa.text(
                f"UPDATE {table} SET declenchee_par = 'cron' "  # noqa: S608
                "WHERE declenchee_par = 'automatique'"
            )
        )
