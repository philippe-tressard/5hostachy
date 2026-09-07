"""`ticket_syndic` dit enfin le PÉRIMÈTRE, et cesse de rendre l'énumération.

Signalé le 31/08/2026, capture à l'appui :

> *« dans l'historique, il faut signaler l'auteur et le périmètre de chaque
> commentaire (sans doute au niveau du N° de ticket). Idem dans la section
> principale, il manque le périmètre, il faut l'ajouter car cette information est
> capitale pour le syndic ou le CS pour identifier le périmètre du problème. »*

Un syndic qui reçoit « ferme-porte explosif » sans savoir de quel bâtiment ni de
quelle cage d'escalier doit rappeler pour le demander. L'écran l'affiche depuis
toujours ; le courriel, jamais.

## 🔴 Pourquoi une MIGRATION et pas seulement le seed

`_poser_les_absents` ne pose que ce qui manque — et c'est voulu : les modèles se
retouchent depuis Admin → E-mails, et les réécrire à chaque déploiement
effacerait ce que le conseil syndical y a mis. Conséquence : **modifier
`EMAIL_TEMPLATES` seul n'aurait rien changé en production.** Le lot serait parti,
le courriel serait resté identique, et le défaut aurait été signalé une troisième
fois.

## `REPLACE()` ciblé, sur le modèle de la 0133

Trois fragments, remplacés seulement s'ils sont encore présents. Une
personnalisation faite ailleurs dans le modèle survit, et la clause `WHERE` rend
la migration idempotente.

⚠️ Un modèle dont le fragment a été retouché n'est PAS mis à jour — et c'est le
comportement voulu : on ne réécrit pas par-dessus une décision humaine. Le
contexte fournit les trois variables dans tous les cas ; un modèle non migré rend
donc du vide, jamais une variable indéfinie.

Revision ID: 0162
Revises: 0161
"""
import sqlalchemy as sa
from alembic import op

revision = "0162"
down_revision = "0161"
branch_labels = None
depends_on = None

#  (avant, après) — le périmètre du commentaire en cours, celui du ticket sur la
#  ligne du numéro, et celui de chaque entrée de l'historique.
#  ⚠️ Les CARACTÈRES sont écrits tels quels, pas en séquences d'échappement.
#  Le gabarit est du source Python, où « — » est une séquence : la base
#  stocke le caractère décodé. Une migration qui chercherait la séquence ne
#  trouverait jamais rien — et `instr(...) > 0` la rendrait silencieusement
#  inerte, c'est-à-dire verte sans avoir rien fait.
_FRAGMENTS = [
    (
        '{{ date_commentaire }}</p>',
        '{{ date_commentaire }}{% if commentaire_perimetre %} — 🔹 {{ commentaire_perimetre }}{% endif %}</p>',
    ),
    (
        '{% if ticket.categorie %} · {{ ticket.categorie }}{% endif %}',
        '{% if ticket.categorie %} · {{ ticket.categorie }}{% endif %}{% if ticket.perimetre %} · 🔹 {{ ticket.perimetre }}{% endif %}',
    ),
    (
        '{{ m.auteur_nom }} — {{ m.date }}</p>',
        '{{ m.auteur_nom }} — {{ m.date }}{% if m.perimetre %} — 🔹 {{ m.perimetre }}{% endif %}</p>',
    ),
]


def _remplacer(conn, ancien: str, nouveau: str) -> None:
    conn.execute(
        sa.text(
            "UPDATE modele_email SET corps_html = REPLACE(corps_html, :ancien, :nouveau) "
            "WHERE code = 'ticket_syndic' AND instr(corps_html, :ancien) > 0"
        ).bindparams(ancien=ancien, nouveau=nouveau)
    )


def upgrade():
    conn = op.get_bind()
    for ancien, nouveau in _FRAGMENTS:
        _remplacer(conn, ancien, nouveau)


def downgrade():
    conn = op.get_bind()
    for ancien, nouveau in _FRAGMENTS:
        _remplacer(conn, nouveau, ancien)
