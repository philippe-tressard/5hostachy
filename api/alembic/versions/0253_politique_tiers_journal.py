"""La politique nomme la quatrième fonction tierce et le journal de sécurité (#1585, #1580)

Rien dans le schéma : la 0253 ne corrige que le TEXTE SERVI, comme les 0223,
0237, 0251 et 0252. Trois passages, tous lus dans le seed
(`app/seed/contenus_legaux`) — jamais recopiés ici :

1. **« Trois fonctions » → « Quatre fonctions »** (#1585) : la section 4 comptait
   trois services tiers ; le code en a une quatrième, de RÉCEPTION
   (`utils/courriel_boite` relève une boîte hébergée chez un tiers).
2. **La fonction de réception**, insérée après l'acheminement des courriels.
3. **Le journal de sécurité** (#1580), inséré après les durées d'affichage.

Remplacement EXACT (`utils/textes_livres`) : un texte reformulé à la main n'est
pas touché — l'administrateur l'ajoute alors depuis Admin › Légal.

Idempotente : chaque passage n'est posé que s'il n'y figure pas déjà.

⚠️ Le seed dit « À RENSEIGNER » pour le service de messagerie : lequel est un fait
de l'INSTANCE, que ni le produit ni cette migration ne connaissent.

Revision ID: 0253
Revises: 0252
"""

import sqlalchemy as sa

from alembic import op

revision = "0253"
down_revision = "0252"
branch_labels = None
depends_on = None

POLITIQUE = "politique_confidentialite"  # identifiant : constante du fichier
FIN_DE_LISTE = "</ul>"


def _texte(conn) -> str | None:
    ligne = conn.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = :c").bindparams(c=POLITIQUE)
    ).fetchone()
    return (ligne[0] or "") if ligne else None


def _corriger(conn, avant: str, apres: str) -> int:
    from app.utils.textes_livres import remplacer_passage

    return remplacer_passage(conn, "config_site", {"cle": POLITIQUE}, "valeur", avant, apres)


def _passages() -> list[tuple[str, str, str]]:
    """(marque de présence, avant, après) — les phrases lues dans le seed."""
    from app.seed.contenus_legaux import (
        ACHEMINEMENT_COURRIELS,
        FONCTIONS_TIERS,
        FONCTIONS_TIERS_ANCIEN,
        JOURNAL_SECURITE,
        RECEPTION_COURRIELS,
        TELEMETRIE_PERFORMANCE,
    )

    return [
        (FONCTIONS_TIERS, FONCTIONS_TIERS_ANCIEN, FONCTIONS_TIERS),
        (
            RECEPTION_COURRIELS,
            ACHEMINEMENT_COURRIELS + FIN_DE_LISTE,
            ACHEMINEMENT_COURRIELS + RECEPTION_COURRIELS + FIN_DE_LISTE,
        ),
        (JOURNAL_SECURITE, TELEMETRIE_PERFORMANCE, TELEMETRIE_PERFORMANCE + JOURNAL_SECURITE),
    ]


def upgrade() -> None:
    conn = op.get_bind()
    if "config_site" not in set(sa.inspect(conn).get_table_names()):
        return
    for marque, avant, apres in _passages():
        texte = _texte(conn)
        if texte is not None and marque not in texte:
            _corriger(conn, avant, apres)


def downgrade() -> None:
    conn = op.get_bind()
    if "config_site" not in set(sa.inspect(conn).get_table_names()):
        return
    for _, avant, apres in reversed(_passages()):
        _corriger(conn, apres, avant)
