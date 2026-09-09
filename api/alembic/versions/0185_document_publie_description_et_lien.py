"""`document_publie` : la description sous le titre, et un bouton qui mène quelque part (#852).

## Deux corrections, un seul modèle

**1. La description.** Ajoutée au document le 08/09/2026 et restée sur le seul
écran Résidence. Le fil d'actualité, la notification et ce courriel l'ignoraient —
signalé à l'écran le 09/09. Le titre NOMME le document, la description dit ce
qu'il couvre : sans elle, le destinataire doit ouvrir le fichier pour savoir s'il
le concerne.

**2. Le bouton conditionnel.** Seules TROIS des dix catégories de documents ont
une rubrique sur /residence. Pour les sept autres — fiche synthétique,
attestation, diagnostic, contrats, devis, document interne — `lien_document` rend
désormais `None`, et le gabarit écrivait alors `<site>/None`. Un bouton absent
vaut mieux qu'un bouton qui ment.

## Pourquoi une migration

`_poser_les_absents` ne pose que ce qui manque : `document_publie` existe déjà en
base, la version du seed n'y arriverait donc jamais. C'est le défaut que le
contrôle de #850 a rendu visible, et la 0184 en est le précédent immédiat.

`REPLACE` sur fragments ciblés, comme 0136 et 0184 : une installation qui aurait
retouché ce texte garde sa version ET reçoit les deux ajouts. Les deux
remplacements insèrent **à l'intérieur** du fragment cherché, si bien que le
fragment n'existe plus une fois l'ajout fait — rejouer `upgrade` ne l'applique pas
deux fois, et `test_email_templates` le vérifie.

Revision ID: 0185
Revises: 0184
Create Date: 2026-09-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0185"
down_revision = "0184"
branch_labels = None
depends_on = None

_TITRE = '"margin:0;font-weight:700;font-size:16px;color:#1E3A5F">{{ document.titre }}</p>'
_DESCRIPTION = (
    "{% if document.description %}"
    '<p style="margin:8px 0 0;font-size:14px;color:#5A6070">{{ document.description }}</p>'
    "{% endif %}"
)
_FIN_ENCART = "</td></tr></table>"
#: Le bouton ENTIER, et non son début : la garde doit envelopper le fragment
#: complet, sinon son `{% endif %}` devrait voyager séparément — et un `endif`
#: orphelin rend le modèle illisible, exactement le cas que le contrôle de santé
#: nomme depuis ce matin.
_BOUTON = (
    '<p style="text-align:center;margin:0"><a href="{{ app.url }}{{ document.lien }}" '
    'style="display:inline-block;background:#3D6B4F;color:#ffffff;font-weight:600;'
    'font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">'
    'Consulter le document</a></p>'
)

REMPLACEMENTS_CORPS: list[tuple[str, str, str]] = [
    #  La description s'insère entre le titre et la fermeture de l'encart.
    (
        "document_publie",
        _TITRE + _FIN_ENCART,
        _TITRE + _DESCRIPTION + _FIN_ENCART,
    ),
    #  La garde enveloppe le bouton. L'ancre reprend la fin de l'encart pour que
    #  le fragment cherché disparaisse une fois l'ajout fait : rejouer `upgrade`
    #  ne pose pas la garde deux fois.
    (
        "document_publie",
        _FIN_ENCART + _BOUTON,
        _FIN_ENCART + "{% if document.lien %}" + _BOUTON + "{% endif %}",
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
