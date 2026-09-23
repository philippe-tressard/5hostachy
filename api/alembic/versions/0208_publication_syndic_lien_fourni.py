"""Le bouton de `publication_syndic` suit le lien que l'appelant fournit (23/09/2026).

Le gabarit écrivait en dur `{{ app.url }}/actualites#pub-{{ publication.id }}`.
Les SONDAGES le réemploient avec `publication.id` = l'identifiant du sondage : leur
courriel au syndic ou au CS menait à une autre actualité, ou à rien. Et
l'actualité devient une affaire (#1091).

Le lien vient désormais de l'appelant, relatif, dans `publication.lien` — comme
`document.lien` et `annonce.lien` dans les gabarits voisins.

Remplacement CIBLÉ (motif de 0203) : un gabarit retouché depuis Admin → E-mails
qui ne contient plus l'ancien lien n'est pas écrasé.
"""
import sqlalchemy as sa
from alembic import op

revision = "0208"
down_revision = "0207"
branch_labels = None
depends_on = None

ANCIEN = "{{ app.url }}/actualites#pub-{{ publication.id }}"
NOUVEAU = "{{ app.url }}{{ publication.lien }}"

_REQUETE = sa.text(
    "UPDATE modele_email SET corps_html = REPLACE(corps_html, :ancien, :nouveau) "
    "WHERE code = 'publication_syndic' AND instr(corps_html, :ancien) > 0"
)


def upgrade() -> None:
    op.get_bind().execute(_REQUETE.bindparams(ancien=ANCIEN, nouveau=NOUVEAU))


def downgrade() -> None:
    op.get_bind().execute(_REQUETE.bindparams(ancien=NOUVEAU, nouveau=ANCIEN))
