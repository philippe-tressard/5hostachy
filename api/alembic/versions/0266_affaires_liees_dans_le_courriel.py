"""`ticket_syndic` et sa copie disent les AFFAIRES LIÉES, sous l'historique.

Demandé le 05/10/2026 : quand une affaire est liée à une autre, l'historique du
courriel trace ce lien, puis le courriel ajoute, après l'historique, chaque
affaire liée avec le sien — de la plus ancienne à la plus récente.

La trace du lien et l'ordre se composent dans le CONTEXTE
(`routers/tickets/historique_courriel`) : la ligne de trace passe par la boucle
`historique` qui existe déjà. Ce que cette migration ajoute au gabarit est le
seul bloc `affaires_liees`.

## 🔴 Pourquoi une MIGRATION et pas seulement le seed

`_poser_les_absents` ne pose que ce qui manque : modifier `seed/emails/tickets.py`
seul n'aurait rien changé en production (0162, 0203). Le contexte fournit déjà
`affaires_liees` dans tous les cas, vide quand rien n'est lié : un modèle non
migré rend donc exactement ce qu'il rendait.

## `REPLACE()` ciblé

Le bloc s'insère juste avant le bouton, après l'historique — sur les deux
modèles qui portent ce corps (`ticket_syndic` et `ticket_copie_auteur`). Le
fragment cherché disparaît une fois remplacé : rejouer `upgrade` ne l'applique
donc pas deux fois (`remplacer_passage` ne remplace que s'il figure tel quel). Un modèle retouché depuis Admin → E-mails, dont ce passage
n'a pas la forme d'origine, n'est PAS touché — on ne réécrit pas par-dessus une
décision humaine.

⚠️ Les CARACTÈRES sont écrits tels quels, pas en séquences d'échappement : la
base stocke le caractère décodé, et un `instr(...) > 0` sur une séquence
resterait vert sans rien faire (0162).

Revision ID: 0266
Revises: 0265
"""

from alembic import op

from app.utils.textes_livres import remplacer_passage

revision = "0266"
down_revision = "0265"
branch_labels = None
depends_on = None

#: Le début du bouton « Consulter l'affaire » sur un modèle de ticket transmis,
#: collé à la fin du tableau d'historique.
_AVANT_BOUTON = '</table>{% endif %}<p style="text-align:center;margin:{% if is_commentaire %}16'

_BLOC = (
    '{% if affaires_liees %}<h3 style="margin:12px 0 8px;font-size:15px;color:#1E3A5F">Affaires liées</h3>'
    '{% for a in affaires_liees %}<table role="presentation" style="width:100%;margin:0 0 12px;'
    'border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr><td style="background:#F2EFE9;padding:16px">'
    '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Affaire #{{ a.numero }} · créée le {{ a.date_creation }}</p>'
    '<p style="margin:0 0 8px;font-weight:700;font-size:15px;color:#1E3A5F">{{ a.titre }}</p>'
    '<table role="presentation" style="border-collapse:collapse;width:100%;font-size:.88rem;margin:0;'
    'border:1px solid #D0D8E4;border-radius:8px;overflow:hidden">'
    '{% for h in a.historique %}<tr style="background:{% if loop.index is odd %}#F2EFE9{% else %}#FFFFFF{% endif %}">'
    '<td style="padding:.35rem .75rem;border-bottom:1px solid #D0D8E4;white-space:nowrap;color:#5A6070;font-size:.82rem">{{ h.date }}</td>'
    '<td style="padding:.35rem .75rem;border-bottom:1px solid #D0D8E4;color:#1A1A2E">{{ h.label }}</td></tr>{% endfor %}'
    "</table></td></tr></table>{% endfor %}{% endif %}"
)

#: (code, avant, après) — la même forme que 0203, relue par
#: `test_les_migrations_disent_la_meme_chose_que_le_seed`.
REMPLACEMENTS_CORPS: list[tuple[str, str, str]] = [
    (
        code,
        _AVANT_BOUTON,
        _AVANT_BOUTON.replace("</table>{% endif %}", "</table>{% endif %}" + _BLOC, 1),
    )
    for code in ("ticket_syndic", "ticket_copie_auteur")
]


def upgrade() -> None:
    conn = op.get_bind()
    for code, ancien, nouveau in REMPLACEMENTS_CORPS:
        remplacer_passage(conn, "modele_email", {"code": code}, "corps_html", ancien, nouveau)


def downgrade() -> None:
    conn = op.get_bind()
    for code, ancien, nouveau in REMPLACEMENTS_CORPS:
        remplacer_passage(conn, "modele_email", {"code": code}, "corps_html", nouveau, ancien)
