"""`nouvel_arrivant_bal` s'adresse à ses TROIS publics — syndic, arrivant, conseil (#848).

## Pourquoi une migration, et pas seulement le seed

`_poser_les_absents` ne pose que ce qui **manque**. `nouvel_arrivant_bal` existe
en production depuis la migration 0066 : la nouvelle version resterait donc dans
le code, et le message envoyé serait celui de 0132 — sans les consignes, et
identique pour les trois destinataires. C'est le piège classique d'une donnée de
référence déjà installée.

## Ce que le modèle gagne

Il ne s'adressait qu'au **syndic**. Il porte désormais `role_destinataire`
(`syndic` / `resident` / `cs`) : le socle du message — la carte d'arrivée, qui,
quel bâtiment, quel occupant précédent — est écrit **une fois** et sert aux
trois ; seules la formule d'appel et la demande changent.

🔴 Demandé le 08/09/2026, en deux temps. D'abord *« un mail envoyé au nouveau
résident et au CS du bâtiment comprenant le lien ou le PDF Consignes de la
copropriété »*. Puis, quand un modèle neuf a été proposé : *« je rappelle la
consigne de standardiser et non de dupliquer »*. Le second modèle aurait porté
les mêmes trois variables d'arrivée, la même carte, le même parcours — et les
deux auraient divergé au premier changement de l'un.

## La clause `WHERE`, et ce qu'elle protège

Comme en 0132 : l'égalité **stricte** avec le texte attendu. Une installation où
le conseil aurait retouché ce modèle depuis Admin → Emails n'est pas écrasée.

⚠️ Le compromis est assumé et il a un coût réel : un modèle retouché ne recevra
jamais les consignes, et **rien ne le signalera**. Mieux vaut cependant ne pas
enrichir que détruire un texte choisi. Si le cas se présente, la reprise se fait
depuis l'écran, pas depuis une migration qui écraserait tout le monde.

⚠️ Le sujet du **syndic** est inchangé au caractère près : c'est sous ce libellé
qu'il classe ses dossiers. Une « uniformisation » des trois objets casserait son
tri par affaire — et une uniformisation qui détruit un usage n'est pas une
standardisation.

Revision ID: 0182
Revises: 0181
Create Date: 2026-09-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0182"
down_revision = "0181"
branch_labels = None
depends_on = None

#: Le texte posé par la migration 0132, et attendu tel quel.
_ANCIEN_SUJET = "{{ prefixe_copro }}Nouvel arrivant — mise à jour des boîtes aux lettres"
_ANCIEN_CORPS = (
    '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
    '📪 Étiquette de boîte aux lettres à mettre à jour</h2>'
    '<p style="margin:0 0 16px">Un nouveau résident vient d’emménager dans la '
    'copropriété <strong>{{ residence.nom }}</strong>. Nous vous transmettons les '
    'éléments nécessaires pour que son étiquette de boîte aux lettres soit à jour.</p>'
    '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
    '<td style="background:#F2EFE9;padding:16px;border-left:4px solid #C9983A">'
    '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ nom_complet }}</p>'
    '{% if batiment %}<p style="margin:0 0 4px;font-size:14px;color:#5A6070">'
    'Bâtiment / appartement : <strong>{{ batiment }}</strong></p>{% endif %}'
    '{% if ancien_resident %}<p style="margin:0;font-size:14px;color:#5A6070">'
    'Occupant précédent : {{ ancien_resident }}</p>{% endif %}'
    '</td></tr></table>'
    '<p style="margin:0 0 16px">Une étiquette absente ou périmée fait revenir le '
    'courrier à l’expéditeur, et c’est le résident qui nous le signale. Un '
    'mot de votre part une fois la modification faite nous permettra de lui '
    'répondre sans vous relancer.</p>'
    '<p style="margin:8px 0 0">Cordialement,<br>'
    '<strong>Le Conseil Syndical</strong></p>'
)


def _cible() -> tuple[str, str]:
    """Sujet et corps visés, LUS DANS LE SEED pour n'en garder qu'une copie.

    Recopier le nouveau texte ici en ferait une seconde écriture : celle du seed
    évoluerait, celle-ci resterait, et une base neuve n'aurait pas le même
    message qu'une base migrée. C'est le geste de 0132, et il vaut toujours.
    """
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
    sujet, corps = _cible()
    _basculer(op.get_bind(), _ANCIEN_SUJET, _ANCIEN_CORPS, sujet, corps)


def downgrade():
    sujet, corps = _cible()
    _basculer(op.get_bind(), sujet, corps, _ANCIEN_SUJET, _ANCIEN_CORPS)
