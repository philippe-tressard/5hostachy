"""La politique de confidentialité nomme la seule transmission automatique à l'assistant (#1322)

Elle affirmait : « Rien n'est transmis si l'assistant est désactivé, et rien ne
l'est automatiquement : la demande est toujours un geste explicite. » Depuis
#1322, la réponse du syndic reçue par courriel est mise en forme par l'assistant
à la relève, sans geste — quand l'administration en active l'usage. La phrase
servie devenait fausse ; un texte juridique qui ment est un défaut de rang 1.

Les deux phrases sont LUES dans le seed (`ASSISTANT_SANS_GESTE_ANCIEN`,
`ASSISTANT_SANS_GESTE`), jamais recopiées ici — même règle que la 0218. Le
remplacement est exact (`utils/textes_livres.remplacer_passage`) : une politique
réécrite depuis Admin → Légal n'est pas touchée.

Revision ID: 0223
Revises: 0222
"""

from alembic import op

revision = "0223"
down_revision = "0222"
branch_labels = None
depends_on = None

CLE = "politique_confidentialite"


def _phrases() -> tuple[str, str]:
    from app.seed.contenus_legaux import ASSISTANT_SANS_GESTE, ASSISTANT_SANS_GESTE_ANCIEN

    return ASSISTANT_SANS_GESTE_ANCIEN, ASSISTANT_SANS_GESTE


def _remplacer(avant: str, apres: str) -> None:
    from app.utils.textes_livres import remplacer_passage

    remplacer_passage(op.get_bind(), "config_site", {"cle": CLE}, "valeur", avant, apres)


def upgrade() -> None:
    ancien, nouveau = _phrases()
    _remplacer(ancien, nouveau)


def downgrade() -> None:
    ancien, nouveau = _phrases()
    _remplacer(nouveau, ancien)
