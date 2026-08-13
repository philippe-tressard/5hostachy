"""L'arborescence des périmètres cesse de se reposer à chaque déploiement.

`seed()` est appelé par `main.py` au démarrage de l'API, donc **à chaque
déploiement**. `poser_arborescence` posait alors « ce qui manque » — et un
périmètre supprimé depuis l'administration ressuscitait à la mise à jour
suivante. Signalé à l'usage le 13/08/2026 : « à chaque mise à jour mes périmètres
ajoutés, supprimés sont perdus ».

La règle du paquet `seed` (« pose ce qui manque, ne met jamais à jour ») protège
les **modifications**, pas les **suppressions** : un seed ne distingue pas un nœud
supprimé d'un nœud jamais posé. Il faut une mémoire, et c'est
`ConfigSite["perimetres_semes"]`.

Cette migration pose ce marqueur sur les installations **qui ont déjà leur
arborescence**, faute de quoi le déploiement suivant l'aurait reposée une dernière
fois — en annulant une fois de plus les suppressions de l'administrateur.

⚠️ La condition « la table `perimetre` contient au moins une ligne » n'est pas
décorative. Sur une base **vierge**, Alembic s'exécute AVANT le seed : poser le
marqueur inconditionnellement laisserait cette installation sans aucun périmètre,
pour toujours, sans le moindre message. C'est le cas zéro de cette migration.
"""
from alembic import op
from sqlalchemy import text

revision = "0140"
down_revision = "0139"
branch_labels = None
depends_on = None

CLE = "perimetres_semes"


def _table_existe(nom: str) -> bool:
    return op.get_bind().execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:nom"),
        {"nom": nom},
    ).first() is not None


def upgrade() -> None:
    if not (_table_existe("perimetre") and _table_existe("config_site")):
        return

    bind = op.get_bind()
    #  Base vierge : le seed n'a pas encore tourné, il doit pouvoir poser l'arbre.
    deja_peuplee = bind.execute(text("SELECT 1 FROM perimetre LIMIT 1")).first()
    if not deja_peuplee:
        return

    #  Idempotent : une seconde exécution ne duplique pas la clé.
    bind.execute(
        text(
            "INSERT INTO config_site (cle, valeur) SELECT :cle, '1' "
            "WHERE NOT EXISTS (SELECT 1 FROM config_site WHERE cle = :cle)"
        ),
        {"cle": CLE},
    )


def downgrade() -> None:
    if not _table_existe("config_site"):
        return
    op.get_bind().execute(
        text("DELETE FROM config_site WHERE cle = :cle"), {"cle": CLE}
    )
