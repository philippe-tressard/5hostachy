"""La politique servie dit que le lien d'une notification porte son canal (#1634, 04/10/2026)

Les liens des courriels et des messages du groupe WhatsApp portent désormais
une étiquette (`src=courriel:<modèle>` ou `src=whatsapp`, `utils/arrivees_notification`),
que le navigateur joint à la vue de page — rattachée au compte comme elle. Aucune
table ne change : seul le texte servi doit le dire.

Le paragraphe `TELEMETRIE_ARRIVEES`, lu dans le seed, est inséré juste après celui
des durées d'affichage (`TELEMETRIE_PERFORMANCE`). Remplacement EXACT
(`utils/textes_livres`) : un texte reformulé à la main n'est pas touché —
l'administrateur l'ajoute alors depuis Admin › Légal.

Idempotente : le paragraphe n'est inséré que s'il n'y est pas.

⚠️ La clé de configuration est une CONSTANTE du fichier.

Revision ID: 0262
Revises: 0261
"""

import sqlalchemy as sa

from alembic import op

revision = "0262"
down_revision = "0261"
branch_labels = None
depends_on = None

POLITIQUE = "politique_confidentialite"  # identifiant : constante du fichier


def _texte(conn) -> str | None:
    ligne = conn.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = :c").bindparams(c=POLITIQUE)
    ).fetchone()
    return (ligne[0] or "") if ligne else None


def _corriger(conn, avant: str, apres: str) -> int:
    from app.utils.textes_livres import remplacer_passage

    return remplacer_passage(conn, "config_site", {"cle": POLITIQUE}, "valeur", avant, apres)


def upgrade() -> None:
    from app.seed.contenus_legaux import TELEMETRIE_ARRIVEES, TELEMETRIE_PERFORMANCE

    conn = op.get_bind()
    if "config_site" not in set(sa.inspect(conn).get_table_names()):
        return
    texte = _texte(conn)
    if texte is not None and TELEMETRIE_ARRIVEES not in texte:
        _corriger(conn, TELEMETRIE_PERFORMANCE, TELEMETRIE_PERFORMANCE + TELEMETRIE_ARRIVEES)


def downgrade() -> None:
    from app.seed.contenus_legaux import TELEMETRIE_ARRIVEES

    conn = op.get_bind()
    if "config_site" in set(sa.inspect(conn).get_table_names()):
        _corriger(conn, TELEMETRIE_ARRIVEES, "")
