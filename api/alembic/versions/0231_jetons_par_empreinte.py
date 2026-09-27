"""Les jetons stockés deviennent leur empreinte (#1389)

Les trois familles de jetons — rafraîchissement, mot de passe oublié,
vérification d'adresse — étaient stockées en clair : une copie de la base
donnait des jetons utilisables. Le code ne stocke plus que l'empreinte
(`app/auth/empreinte_jeton.py`) ; cette migration convertit ce qui est déjà en
base, pour que les sessions ouvertes et les liens déjà envoyés restent valides —
le cookie et le lien portent le jeton BRUT, dont l'empreinte est désormais celle
qu'on cherche.

Rejouable : une valeur qui a déjà la forme d'une empreinte (64 caractères
hexadécimaux, ce qu'aucun jeton brut n'a) n'est pas re-hachée.

Irréversible par nature : le `downgrade` ne peut pas retrouver un jeton depuis
son empreinte. Revenir au code d'avant fermerait les sessions et invaliderait
les liens en attente — sans perte de données, les comptes restant intacts.

Revision ID: 0231
Revises: 0230
"""

import sqlalchemy as sa

from alembic import op

revision = "0231"
down_revision = "0230"
branch_labels = None
depends_on = None

#: Les trois tables — des identifiants, constants dans ce fichier.
TABLES = ("refresh_token", "password_reset_token", "email_verification_token")


def convertir(conn, cle: str) -> int:
    """Remplace chaque jeton brut par son empreinte ; rend le nombre converti."""
    from app.auth.empreinte_jeton import empreinte, est_empreinte

    presentes = set(sa.inspect(conn).get_table_names())
    convertis = 0
    for nom in TABLES:
        if nom not in presentes:
            continue
        table = sa.table(nom, sa.column("id"), sa.column("token"))
        for id_, token in conn.execute(sa.select(table.c.id, table.c.token)).all():
            if not token or est_empreinte(token):
                continue
            conn.execute(
                table.update().where(table.c.id == id_).values(token=empreinte(token, cle))
            )
            convertis += 1
    return convertis


def upgrade() -> None:
    from app.config import get_settings

    convertir(op.get_bind(), get_settings().secret_key)


def downgrade() -> None:
    #  Rien à restaurer : une empreinte ne rend pas son jeton (voir l'en-tête).
    pass
