"""`calendrier_evenement_suivi` annonce ses pièces jointes — en base aussi (#852).

## Ce qui manquait

Le 18/08/2026, le modèle de suivi a gagné une ligne : « 📎 Pièces jointes
ci-dessous. », affichée quand l'entrée d'historique en transporte. La ligne a été
écrite dans le seed — et **nulle part ailleurs**.

Or `_poser_les_absents` ne pose que ce qui manque : le modèle existait déjà en
base depuis sa création, donc il n'a jamais été repris. Trois semaines durant,
une base neuve annonçait les pièces et une base en service ne les annonçait pas.
Le lecteur recevait des fichiers dont le message ne parlait pas.

Rien ne pouvait le dire avant le contrôle quotidien de #850 : les tests lisent le
dépôt, et le dépôt était juste. C'est ce contrôle qui l'a trouvé, le 09/09/2026 —
sa première prise.

## Pourquoi un `REPLACE` ciblé et non l'égalité stricte

0182 exige le texte attendu au caractère près, pour ne pas écraser un modèle
retouché depuis Admin → Emails. C'est le bon geste quand on **réécrit** un
message entier. Ici on n'ajoute qu'une ligne entre deux repères qu'une
reformulation ne touche pas : le `{% endif %}` du commentaire de suivi, et le
bouton « Voir le calendrier ». Une installation qui aurait réécrit le texte autour
garde sa version **et** reçoit la ligne.

L'ancre inclut `</div>{% endif %}` : l'ajout se glisse **à l'intérieur** du
fragment recherché, si bien que le fragment cherché n'existe plus une fois
l'ajout fait. Rejouer `upgrade` ne l'appliquerait donc pas deux fois — même
propriété que 0136, et `test_email_templates` la vérifie.

Revision ID: 0184
Revises: 0183
Create Date: 2026-09-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0184"
down_revision = "0183"
branch_labels = None
depends_on = None

#: L'ancre : la fin de l'encart de commentaire, puis le bouton. Une reformulation
#: du texte n'y touche pas.
_ANCRE_AVANT = "</div>{% endif %}"
_ANCRE_APRES = '<p style="text-align:center;margin:0"><a href="{{ app.url }}/calendrier"'

#: La ligne ajoutée, telle qu'elle est écrite dans le seed.
_LIGNE = (
    '{% if fichiers %}<p style="margin:0 0 16px;font-size:13px;color:#5A6070">'
    "\U0001f4ce Pièces jointes ci-dessous.</p>{% endif %}"
)

#  Même convention que `REMPLACEMENTS` (0136), appliquée au CORPS : le balayage
#  générique de `test_email_templates` vérifie que le fragment voulu est bien
#  celui du seed, que l'ancien n'y est plus, et que rejouer la migration
#  n'appliquerait pas l'ajout deux fois.
REMPLACEMENTS_CORPS: list[tuple[str, str, str]] = [
    (
        "calendrier_evenement_suivi",
        _ANCRE_AVANT + _ANCRE_APRES,
        _ANCRE_AVANT + _LIGNE + _ANCRE_APRES,
    ),
]


def _remplacer(conn, code: str, ancien: str, nouveau: str) -> None:
    conn.execute(
        sa.text(
            "UPDATE modele_email SET corps_html = REPLACE(corps_html, :ancien, :nouveau) "
            "WHERE code = :code AND instr(corps_html, :ancien) > 0"
        ).bindparams(code=code, ancien=ancien, nouveau=nouveau)
    )


def upgrade():
    conn = op.get_bind()
    for code, ancien, nouveau in REMPLACEMENTS_CORPS:
        _remplacer(conn, code, ancien, nouveau)


def downgrade():
    conn = op.get_bind()
    for code, ancien, nouveau in reversed(REMPLACEMENTS_CORPS):
        _remplacer(conn, code, nouveau, ancien)
