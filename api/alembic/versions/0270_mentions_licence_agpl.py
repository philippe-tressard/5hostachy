"""Les mentions légales en base annoncent la licence AGPL-3.0-or-later (#1726).

La licence du projet change le 08/10/2026 : la « Licence 5Hostachy »
(source-available, clause commerciale) cède la place à l'AGPL-3.0-or-later.

Comme à chaque changement de licence (la 0180 pour MIT → Licence 5Hostachy),
les mentions servies aux résidents vivent EN BASE (`config_site`,
`mentions_legales`) : changer `LICENSE` et le gabarit du seed ne toucherait
rien de ce que les gens lisent, et la page publique continuerait d'annoncer une
clause commerciale qui n'existe plus.

## Ce qui est remplacé, et ce qui ne l'est jamais

Le passage posé par la 0180 — ses deux paragraphes de licence, au caractère
près — devient le paragraphe du seed (`PARAGRAPHE_LICENCE`, lu ici, jamais
recopié : deux rédactions d'un texte juridique divergeraient). L'ancien texte,
lui, est écrit en dur : c'est un fait passé, il ne changera plus.

Si le passage n'est plus là — page réécrite depuis Admin → Légal —, rien n'est
touché (`utils/textes_livres.remplacer_passage`) : écraser le texte de
quelqu'un pour y glisser une licence serait pire que l'incohérence corrigée.
Le downgrade fait le remplacement inverse, et lui seul.

Revision ID: 0270
Revises: 0269
"""

from alembic import op

revision = "0270"
down_revision = "0269"
branch_labels = None
depends_on = None

#: Le passage posé par la 0180 (son `NOUVEAU`, moins l'intertitre et le dernier
#: paragraphe sur les contenus, qui restent vrais).
ANCIEN = (
    "<p>Le code source de 5Hostachy est <strong>accessible</strong>, sous "
    '<a href="https://github.com/philippe-tressard/5hostachy/blob/main/LICENSE-5Hostachy.md" '
    'target="_blank" rel="noopener noreferrer">Licence 5Hostachy</a> — copyleft fondé sur les '
    "principes de l'AGPLv3, avec clauses commerciales. Les particuliers, "
    "associations et copropriétés peuvent l'utiliser <strong>gratuitement</strong> ; "
    "tout usage commercial requiert un accord préalable de l'auteur.</p>"
    "<p>⚠️ Ce n'est <em>pas</em> une licence libre au sens de l'OSI : la clause "
    "commerciale ajoute une restriction que l'AGPLv3 n'admet pas.</p>"
)


def _nouveau() -> str:
    """Le paragraphe juste, lu dans le seed — jamais recopié ici."""
    from app.seed.contenus_legaux import PARAGRAPHE_LICENCE

    return PARAGRAPHE_LICENCE


def _corriger(avant: str, apres: str) -> None:
    from app.utils.textes_livres import remplacer_passage

    remplacer_passage(
        op.get_bind(), "config_site", {"cle": "mentions_legales"}, "valeur", avant, apres
    )


def upgrade() -> None:
    _corriger(ANCIEN, _nouveau())


def downgrade() -> None:
    _corriger(_nouveau(), ANCIEN)
