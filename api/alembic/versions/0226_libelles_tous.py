"""« Tous », jamais « tous les résidents », dans les textes semés en base (#1305)

Depuis v2.49.3 (#1279), le choix sans restriction s'écrit « Tous » : un
copropriétaire bailleur, un mandataire ou le syndic n'est pas un résident.
Deux textes semés le disaient encore, et le seed ne réécrit pas une ligne déjà
posée :

- le libellé du profil documentaire `résidence_tous` ;
- les descriptions des périmètres à portée globale (copropriété, parking, AFUL,
  espaces verts, cheminements).

Les textes sont LUS dans le seed, jamais recopiés ici. Le remplacement est exact
(`utils/textes_livres`) : une ligne reformulée depuis l'administration n'est pas
touchée.

Revision ID: 0226
Revises: 0225
"""

from alembic import op

revision = "0226"
down_revision = "0225"
branch_labels = None
depends_on = None

PROFIL = "résidence_tous"
PERIMETRES = ("résidence", "parking", "aful", "espaces-verts", "cheminements")


def _appliquer(sens: int) -> None:
    from app.seed.patrimoine import PASSAGES_TOUS_LES_RESIDENTS
    from app.seed.profils_documents import LIBELLE_TOUS, LIBELLE_TOUS_ANCIEN
    from app.utils.textes_livres import remplacer_passage, remplacer_si_intact

    conn = op.get_bind()
    avant, apres = (LIBELLE_TOUS_ANCIEN, LIBELLE_TOUS)[::sens]
    remplacer_si_intact(
        conn,
        "profil_acces_document",
        {"code": PROFIL, "libelle": avant},
        {"libelle": apres},
    )
    for ancien, nouveau in PASSAGES_TOUS_LES_RESIDENTS:
        a, n = (ancien, nouveau)[::sens]
        for code in PERIMETRES:
            remplacer_passage(conn, "perimetre", {"code": code}, "description", a, n)


def upgrade() -> None:
    _appliquer(1)


def downgrade() -> None:
    _appliquer(-1)
