"""La mesure d'audience sait de nouveau QUI : colonne et textes légaux rétablis

## Pourquoi (02/10/2026)

La 0246 (#1545) a retiré `telemetry_event.user_id` et passé les textes légaux
« sans identifiant ». Le tableau de bord y a perdu ses statistiques par
utilisateur — une suppression fonctionnelle que l'utilisateur du produit
n'avait pas autorisée. Il en a demandé le rétablissement le jour même.

## Ce que fait la migration

1. **`telemetry_event.user_id` revient**, en colonne simple — SANS clé
   étrangère : SQLite refuse d'altérer les contraintes d'une table existante,
   et la migration crasherait après avoir ajouté la colonne (CLAUDE.md). Les
   événements enregistrés entre la 0246 et celle-ci restent sans auteur, et
   ceux d'avant la 0246 aussi : la colonne a été détruite, pas vidée.
2. **Les textes servis disent de nouveau ce que fait le code** — rattachée au
   compte, refusable, exportable, effaçable. Remplacements EXACTS
   (`utils/textes_livres.remplacer_passage`) : un texte reformulé à la main
   n'est pas touché. Les phrases posées par la 0246 sont écrites ici en dur —
   un fait passé ; les phrases rétablies sont lues dans le seed.

## Idempotence

La colonne n'est ajoutée que si elle manque ; chaque passage remplacé
disparaît du texte ; la phrase des mentions légales n'est réinsérée que si
elle n'y est pas.

Revision ID: 0247
Revises: 0246
"""

import sqlalchemy as sa
from alembic import op

revision = "0247"
down_revision = "0246"
branch_labels = None
depends_on = None

#: Identifiants : constantes du fichier (SQLite ne les lie pas).
TABLE = "telemetry_event"
COLONNE = "user_id"
POLITIQUE = "politique_confidentialite"
MENTIONS = "mentions_legales"

#: Ce que la 0246 a posé (lu alors dans le seed).
COLLECTE_0246 = (
    "<li><strong>Mesure d'audience interne (télémétrie)\xa0:</strong> pages consultées et "
    "actions effectuées, enregistrées <strong>sans identifiant</strong>\xa0: elles ne sont "
    "rattachées ni à votre compte ni à votre adresse IP, et ne sont horodatées qu'à l'heure "
    "près. Elle sert à savoir quels écrans servent, et à rien d'autre\xa0: elle n'alimente "
    "aucune publicité et ne quitte pas l'application. Vous pouvez la <strong>refuser</strong> "
    "depuis <em>Mon profil</em>, rubrique <em>Vos droits (RGPD)</em>\xa0: votre navigateur "
    "n'envoie alors plus rien.</li>"
)
BASE_LEGALE_0246 = (
    "<li><strong>Mesure d'audience interne</strong> — base\xa0: intérêt légitime "
    "(art.\xa06-1-f) à savoir quels écrans servent. Elle ne porte aucun identifiant\xa0; "
    "vous pouvez vous y opposer depuis votre profil (art.\xa021).</li>"
)
CONSERVATION_0246 = (
    "<li>Mesure d'audience\xa0: événements sans identifiant <strong>30\xa0jours</strong>, puis "
    "agrégats — par jour pendant 12\xa0mois, par mois pendant 10\xa0ans.</li>"
)
DROITS_0246 = "Les titulaires d'un compte peuvent aussi passer par la messagerie de l'application."
NAVIGATION_0246 = "(enregistrées sans identifiant)"
NAVIGATION_RETABLIE = "(anonymisées après 30\xa0jours)"
DUREE_0246 = "Télémétrie détaillée (sans identifiant)\xa0: 30\xa0jours."
DUREE_RETABLIE = "Télémétrie détaillée (avec identifiant)\xa0: 30\xa0jours."

#: La phrase des mentions légales que la 0246 a retirée, et où elle se tenait :
#: juste après le renvoi à la politique (posé par la 0170).
MENTIONS_PHRASE = " Chaque compte peut exporter et effacer ses propres données depuis son profil."
MENTIONS_ANCRE = '<a href="/politique-confidentialite">politique de confidentialité</a>.'


def _corrections() -> list[tuple[str, str, str]]:
    """(clé, posé par la 0246, rétabli) — les phrases rétablies lues dans le seed."""
    from app.seed.contenus_legaux import (
        DROITS_DEPUIS_LE_PROFIL,
        TELEMETRIE_BASE_LEGALE,
        TELEMETRIE_COLLECTE,
        TELEMETRIE_CONSERVATION,
    )

    return [
        (POLITIQUE, COLLECTE_0246, TELEMETRIE_COLLECTE),
        (POLITIQUE, BASE_LEGALE_0246, TELEMETRIE_BASE_LEGALE),
        (POLITIQUE, CONSERVATION_0246, TELEMETRIE_CONSERVATION),
        (POLITIQUE, DROITS_0246, DROITS_DEPUIS_LE_PROFIL),
        (POLITIQUE, NAVIGATION_0246, NAVIGATION_RETABLIE),
        (POLITIQUE, DUREE_0246, DUREE_RETABLIE),
    ]


def _corriger(conn, cle: str, avant: str, apres: str) -> int:
    from app.utils.textes_livres import remplacer_passage

    return remplacer_passage(conn, "config_site", {"cle": cle}, "valeur", avant, apres)


def _texte(conn, cle: str) -> str:
    ligne = conn.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = :c").bindparams(c=cle)
    ).fetchone()
    return (ligne[0] or "") if ligne else ""


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade() -> None:
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())

    if TABLE in tables and COLONNE not in _colonnes(conn):
        op.add_column(TABLE, sa.Column(COLONNE, sa.Integer(), nullable=True))

    if "config_site" not in tables:
        return
    for cle, avant, apres in _corrections():
        _corriger(conn, cle, avant, apres)
    if MENTIONS_PHRASE.strip() not in _texte(conn, MENTIONS):
        _corriger(conn, MENTIONS, MENTIONS_ANCRE, MENTIONS_ANCRE + MENTIONS_PHRASE)


def downgrade() -> None:
    conn = op.get_bind()
    if TABLE in set(sa.inspect(conn).get_table_names()) and COLONNE in _colonnes(conn):
        with op.batch_alter_table(TABLE) as lot:
            lot.drop_column(COLONNE)
    for cle, avant, apres in _corrections():
        _corriger(conn, cle, apres, avant)
    _corriger(conn, MENTIONS, MENTIONS_PHRASE, "")
