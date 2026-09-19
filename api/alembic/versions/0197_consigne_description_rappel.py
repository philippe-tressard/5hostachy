"""La consigne de l'assistant « description » rejoint le code (19/09/2026, #1059).

## Ce que cette migration corrige, et qui va au-delà de la demande

Demandé à l'écran : *« dans le cas d'une édition de type Commenter, la réponse
de l'assistant proposera, en préambule du texte, une phrase récapitulative de
l'historique de l'affaire en une phrase maximum (exemple : Pour rappel : xxxxxx,
en style citation) à la demande »*. La règle est écrite dans
`description_format.CONSIGNE_DEFAUT`.

🔴 **Mais la modifier dans le code n'aurait rien changé en production.** Le
prompt a été **semé** par la 0194 et vit en base depuis (`standards/06` §4) : le
code n'en est plus propriétaire. Or `CONSIGNE_DEFAUT` a été réécrit **deux fois
depuis**, sans qu'aucune migration ne suive :

| Version | Ce qu'elle apportait | Arrivée en base ? |
|---|---|---|
| v1.41.0 | la consigne d'origine, semée par la 0194 | oui |
| v1.44.0 (#1003) | « l'assistant peut mettre en valeur ce qui compte » | **non** |
| v1.44.4 (#1007) | « la mise en valeur était permise, elle n'était pas obtenue » | **non** |

Deux lots livrés, relus, déployés — et **sans effet** sur l'assistant que le
conseil syndical emploie, qui tournait encore sur la consigne de 973 caractères
de v1.41.0. Personne ne pouvait le voir : le code disait une chose, la base en
servait une autre, et aucun écran ne les rapprochait.

## Comment elle distingue « personne n'y a touché » d'un travail humain

Par l'**empreinte** du texte stocké, comparée à celles que le code a lui-même
écrites au fil des versions. Un prompt réécrit par l'administrateur n'en porte
aucune : il est conservé tel quel, et son auteur dispose de « Rétablir le prompt
d'origine » s'il veut la nouvelle version.

Des empreintes plutôt que les textes entiers : trois consignes recopiées ici
pèseraient 6 kio de littéraux figés, pour la seule question « est-ce encore le
nôtre ? ».

⚠️ La consigne de l'usage `synthese_contrat` a **le même écart** (elle a bougé
en v1.43.0). Elle n'est pas traitée ici : sa valeur est composée de fragments,
donc ses empreintes historiques ne se relisent pas aussi sûrement, et un lot ne
s'élargit pas en route. Suivi à part.

Revision ID: 0197
Revises: 0196
Create Date: 2026-09-19
"""
import hashlib

import sqlalchemy as sa
from alembic import op

from app.utils.description_format import CONSIGNE_DEFAUT

revision = "0197"
down_revision = "0196"
branch_labels = None
depends_on = None

CLE = "llm_description_prompt"

#: Empreintes SHA-256 des consignes que le CODE a écrites, dans l'ordre des
#: versions. Une valeur stockée qui en porte une est « restée la nôtre ».
#:
#: 🔴 Figées : ce sont des faits d'histoire. Les recalculer depuis le dépôt
#: ferait dépendre une migration de l'état courant du code, ce qu'une migration
#: ne fait jamais.
EMPREINTES_DU_CODE = (
    "09ab8479f6141ed79872a3a8403cda28c979660b834e31f488798cdd13a535dd",  # v1.41.0, semée par la 0194
    "06c895f446dbc262e78ed66b76dbf4c04505821fd5d408d5949a82f3646448de",  # v1.44.0, mise en valeur
    "0b42b5ba283a860df24cd7c12e9c8ae795edcc433eabba0e1eb89b18c0e0107b",  # v1.44.4, mise en valeur obligatoire
)


def _empreinte(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def _valeur(conn) -> str | None:
    ligne = conn.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = :cle").bindparams(cle=CLE)
    ).fetchone()
    return ligne[0] if ligne else None


def _poser(conn, texte: str) -> None:
    conn.execute(
        sa.text("UPDATE config_site SET valeur = :valeur WHERE cle = :cle").bindparams(
            valeur=texte, cle=CLE
        )
    )


def upgrade() -> None:
    conn = op.get_bind()
    stockee = _valeur(conn)
    if stockee is None:
        #  Base neuve : la 0194 a déjà posé la valeur du code, qui est la bonne.
        #  Rien à faire, et surtout pas créer la clé ici — deux endroits qui la
        #  posent, c'est deux vérités.
        return
    if _empreinte(stockee) in EMPREINTES_DU_CODE:
        _poser(conn, CONSIGNE_DEFAUT)


def downgrade() -> None:
    #  On ne remet pas une consigne antérieure : laquelle des trois ? Le retour
    #  en arrière du CODE suffit, puisque « Rétablir le prompt d'origine » y
    #  revient. Défaire ici écraserait peut-être une relecture faite entre-temps.
    pass
