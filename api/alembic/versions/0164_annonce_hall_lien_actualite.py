"""`annonce_hall` : le bouton visait une route réservée au conseil syndical

Le modèle d'e-mail de l'affiche finissait par *« Voir l'historique des annonces »*,
vers `/espace-cs?onglet=annonces-hall`. Le front y pose une garde — `if (!$isCS)
goto('/tableau-de-bord')` — et ce courriel part désormais **aussi au syndic**
(#480, 01/09/2026), qui n'est pas conseiller : le bouton le renvoyait au tableau
de bord. C'était le seul modèle du site à viser une route à accès restreint.

Il pointe maintenant l'**actualité d'origine**, et seulement quand il y en a une.
Une affiche autonome part sans bouton : le PDF est en pièce jointe, c'est tout son
contenu, et un bouton qui ne mène nulle part vaut moins que pas de bouton.

⚠️ Le lien est calculé au point d'appel (`annonces_hall_courriels.lien_affiche`),
qui sert **les deux canaux** — courriel et groupe WhatsApp. Deux liens fabriqués
séparément pour la même affiche finiraient par diverger sans que rien ne le dise.

Revision ID: 0164
Revises: 0163
Create Date: 2026-09-01
"""
from alembic import op
from sqlalchemy import text

revision = "0164"
down_revision = "0163"
branch_labels = None
depends_on = None

_BOUTON_AVANT = (
    '<p style="text-align:center;margin:0">'
    '<a href="{{ app.url }}/espace-cs?onglet=annonces-hall" '
    'style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;'
    'font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">'
    "Voir l\u2019historique des annonces</a></p>"
)

_BOUTON_APRES = (
    '{% if annonce.lien %}<p style="text-align:center;margin:0">'
    '<a href="{{ app.url }}{{ annonce.lien }}" '
    'style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;'
    'font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">'
    "Voir l\u2019actualité d\u2019origine</a></p>{% endif %}"
)


def _remplacer(avant: str, apres: str) -> None:
    """Substitue le seul bloc du bouton, sans réécrire le corps entier.

    ⚠️ `modele_email` est **éditable par l'administration**. Réécrire `corps_html`
    en bloc — ce que font les migrations 0102 et 0108 — effacerait une
    personnalisation faite depuis l'écran d'administration. Ici on remplace la
    sous-chaîne, et le reste du corps est laissé tel que l'exploitant l'a voulu.

    🔒 `REPLACE(...)` est paramétré, jamais interpolé : aucune f-string SQL dans
    ce dépôt depuis le 31/08/2026.
    """
    #  Pas de garde `LIKE` : `REPLACE` ne fait rien quand le motif est absent, et
    #  un `LIKE` sur un fragment HTML traiterait ses `%` et `_` comme des jokers.
    op.get_bind().execute(
        text(
            "UPDATE modele_email SET corps_html = REPLACE(corps_html, :avant, :apres)"
            " WHERE code = 'annonce_hall'"
        ).bindparams(avant=avant, apres=apres)
    )


def upgrade():
    _remplacer(_BOUTON_AVANT, _BOUTON_APRES)


def downgrade():
    _remplacer(_BOUTON_APRES, _BOUTON_AVANT)
