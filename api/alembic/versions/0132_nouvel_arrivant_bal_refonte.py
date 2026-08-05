"""`nouvel_arrivant_bal` : mise au standard visuel et ton partenarial.

Audit des modèles d'e-mail, volet 4. Ce modèle était le seul resté en HTML brut,
hérité tel quel de la migration 0066 : ni encadré, ni couleurs de la charte, un
sujet en abrégé (« MaJ Boites aux lettres ») et une demande sèche — « Merci de
préparer l'étiquette ».

C'est pourtant un message adressé au **syndic**, le même destinataire que
`relance_syndic`, dont le préambule a été repris le 01/08/2026 précisément pour
dire ce qu'on attend sans mettre personne en cause. Le nouveau texte donne la
raison concrète de la demande (le courrier revient à l'expéditeur, et c'est le
résident qui le signale) plutôt que de la poser comme une injonction.

Le sujet gagne la référence de copropriété sous garde `{% if %}`, comme
`ticket_syndic` : sans elle, il commençait par un tiret orphelin quand
`reference_copro` n'est pas renseignée.

**Le corps change entièrement**, donc pas de `REPLACE()` chirurgical possible.
La clause `WHERE` porte sur l'égalité stricte avec le texte d'origine : une
installation où le conseil syndical aurait retouché ce modèle depuis
Admin → Emails n'est pas écrasée. Elle garde son texte, ce qui est le
comportement voulu — mieux vaut ne pas embellir que de détruire un choix.

Revision ID: 0132
Revises: 0131
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0132"
down_revision = "0131"
branch_labels = None
depends_on = None

_ANCIEN_SUJET = "{{ reference_copro }} - Nouvel arrivant MaJ Boites aux lettres"
_ANCIEN_CORPS = (
    "<p>Bonjour,</p>"
    "<p>Nous vous informons de l'arrivée d'un nouveau résident :</p>"
    "<ul>"
    "<li><strong>Nom :</strong> {{ nom_complet }}</li>"
    "{% if batiment %}<li><strong>Bâtiment / Apt :</strong> {{ batiment }}</li>{% endif %}"
    "{% if ancien_resident %}<li><strong>Ancien résident :</strong> {{ ancien_resident }}</li>{% endif %}"
    "</ul>"
    "<p>Merci de préparer l'étiquette de boîte aux lettres correspondante.</p>"
    "<p>Cordialement,<br>Le Conseil Syndical</p>"
)


def _nouveau() -> tuple[str, str]:
    """Sujet et corps cibles, lus dans le seed pour n'en garder qu'une copie."""
    from app.seed import EMAIL_TEMPLATES

    _code, _libelle, sujet, corps, _desactivable = next(
        t for t in EMAIL_TEMPLATES if t[0] == "nouvel_arrivant_bal"
    )
    return sujet, corps


def _basculer(conn, sujet_attendu, corps_attendu, sujet_cible, corps_cible) -> None:
    conn.execute(
        sa.text(
            "UPDATE modele_email SET sujet = :sujet_cible, corps_html = :corps_cible "
            "WHERE code = 'nouvel_arrivant_bal' "
            "AND sujet = :sujet_attendu AND corps_html = :corps_attendu"
        ).bindparams(
            sujet_cible=sujet_cible,
            corps_cible=corps_cible,
            sujet_attendu=sujet_attendu,
            corps_attendu=corps_attendu,
        )
    )


def upgrade():
    sujet, corps = _nouveau()
    _basculer(op.get_bind(), _ANCIEN_SUJET, _ANCIEN_CORPS, sujet, corps)


def downgrade():
    sujet, corps = _nouveau()
    _basculer(op.get_bind(), sujet, corps, _ANCIEN_SUJET, _ANCIEN_CORPS)
