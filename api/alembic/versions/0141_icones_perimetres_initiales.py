"""Icônes des périmètres — INITIALISATION, sans jamais écraser un choix.

Le champ `perimetre.icone` existait depuis `0138` et restait vide : aucune icône
du jeu de `Icon.svelte` ne disait « parking », « cave », « arbre », « escalier »
ni « ascenseur », et en inventer un nom aurait produit le point d'interrogation du
repli. Le jeu est complété côté front dans le même lot, et l'écran
`/admin/patrimoine` propose désormais un choix.

**Cette migration ne remplit que les icônes RESTÉES VIDES** (`icone IS NULL` ou
chaîne vide). Une icône déjà choisie depuis l'administration n'est jamais touchée
— c'est la règle explicite : le produit initialise, l'administrateur décide.
C'est aussi pourquoi elle est rejouable sans dommage.

Elle existe **en plus** du seed parce que le seed ne pose l'arbre qu'une fois
(marqueur `perimetres_semes`, migration `0140`) : sur l'installation en service,
l'arbre est déjà là et le seed ne repassera jamais. Sans cette migration, les
icônes n'arriveraient donc nulle part.

La correspondance code → icône est **importée** de `app/seed/patrimoine.py` plutôt
que recopiée ici : deux tables divergeraient au premier ajout, et c'est exactement
le défaut que tout ce chantier a passé son temps à corriger.
"""
from alembic import op
from sqlalchemy import text

revision = "0141"
down_revision = "0140"
branch_labels = None
depends_on = None


def _table_existe(nom: str) -> bool:
    return op.get_bind().execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:nom"),
        {"nom": nom},
    ).first() is not None


def upgrade() -> None:
    if not _table_existe("perimetre"):
        return

    from app.seed.patrimoine import icone_pour

    bind = op.get_bind()
    #  Uniquement les nœuds SANS icône : le `WHERE` est la garantie de non-écrasement.
    vides = bind.execute(
        text("SELECT id, code FROM perimetre WHERE icone IS NULL OR icone = ''")
    ).fetchall()

    for identifiant, code in vides:
        icone = icone_pour(code)
        if not icone:
            continue
        bind.execute(
            text("UPDATE perimetre SET icone = :icone WHERE id = :id AND (icone IS NULL OR icone = '')"),
            {"icone": icone, "id": identifiant},
        )


def downgrade() -> None:
    #  On ne remet pas à NULL : impossible de distinguer une icône posée ici d'une
    #  icône choisie depuis l'administration après coup. Effacer les deux serait
    #  détruire un choix de l'utilisateur pour défaire une commodité.
    pass
