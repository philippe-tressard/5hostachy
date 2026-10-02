"""La mesure d'audience ne sait plus QUI : colonne retirée, textes légaux corrigés (#1545)

## L'arbitrage (02/10/2026)

`standards/14` §4 : une mesure d'audience interne n'échappe au consentement
que si ses données sont NON RÉIDENTIFIANTES — « une télémétrie qui enregistre
qui a vu quelle page ne remplit pas ces conditions ». Elle portait `user_id`,
collecté par défaut. Choix retenu : ne plus savoir qui, plutôt que demander un
consentement préalable. Les agrégats (`telemetry_daily`, `telemetry_monthly`)
ne portaient déjà aucun identifiant ; ils restent.

## Ce que fait la migration

1. **`telemetry_event.user_id` est RETIRÉE** — pas vidée et gardée : une
   colonne que plus rien n'écrit est une invitation à la remplir de nouveau.
   SQLite ne sait pas retirer une colonne porteuse d'une clé étrangère : le
   mode `batch` recopie la table, ses index compris. La table ne garde que
   30 jours d'événements, la copie est brève.
2. **Les horodatages existants passent à l'heure près**, comme les nouveaux :
   un `cree_le` à la seconde se recouperait avec `derniere_connexion` et
   rendrait une identité à l'événement.
3. **Les textes servis cessent de mentir.** Ils vivent en base (Admin → Légal),
   le seed ne les atteint plus. Chaque correction est un remplacement EXACT
   (`utils/textes_livres.remplacer_passage`) : un texte reformulé à la main
   n'est pas touché. Les phrases NOUVELLES sont lues dans le seed ; les
   ANCIENNES sont écrites ici, en dur — un fait passé, elles ne changeront plus.

   - politique, posé par la 0199 : « rattachées à votre compte… effacer votre
     historique », et la durée « L'effacement demandé depuis votre profil est
     immédiat » — il n'y a plus d'historique à soi ;
   - politique, posé par la 0171 : « exporter et effacer leurs données depuis
     leur profil » — la télémétrie était la seule donnée concernée ;
   - politique, posé par la 0088 : « (anonymisées après 30 jours) » et
     « Télémétrie détaillée (avec identifiant) » ;
   - mentions légales, posé par la 0170 : « Chaque compte peut exporter et
     effacer ses propres données depuis son profil ».

   La base légale de la mesure d'audience est insérée au point 3 **si le texte
   n'en porte aucune** — la 0088 en avait posé une (« Télémétrie d'usage »),
   toujours exacte : on ne la double pas.

## Idempotence

La colonne n'est retirée que si elle existe ; l'arrondi à l'heure se rejoue
sans effet ; chaque passage remplacé disparaît du texte, et l'insertion vérifie
d'abord que la base légale n'y est pas.

Revision ID: 0246
Revises: 0245
"""

import sqlalchemy as sa
from alembic import op

revision = "0246"
down_revision = "0245"
branch_labels = None
depends_on = None

#: Identifiants : constantes du fichier (SQLite ne les lie pas).
TABLE = "telemetry_event"
COLONNE = "user_id"
POLITIQUE = "politique_confidentialite"
MENTIONS = "mentions_legales"

#: Ce que la 0199 a posé (lu alors dans `AJOUTS_1034`).
COLLECTE_AVANT = (
    "<li><strong>Mesure d'audience interne (télémétrie)\xa0:</strong> pages consultées et "
    "actions effectuées, rattachées à votre compte. Elle sert à savoir quels écrans servent, "
    "et à rien d'autre\xa0: elle n'alimente aucune publicité et ne quitte pas l'application. "
    "Vous pouvez la <strong>refuser</strong> et <strong>effacer</strong> votre historique "
    "depuis <em>Mon profil</em>, rubrique <em>Vos droits (RGPD)</em>.</li>"
)
CONSERVATION_AVANT = (
    "<li>Mesure d'audience\xa0: événements détaillés <strong>30\xa0jours</strong>, puis "
    "agrégats sans détail — par jour pendant 12\xa0mois, par mois pendant 10\xa0ans. "
    "L'effacement demandé depuis votre profil est immédiat.</li>"
)
#: Ce que la 0171 a posé.
DROITS_AVANT = (
    "Les titulaires d'un compte peuvent aussi passer par la messagerie de "
    "l'application, ou exporter et effacer leurs données depuis leur profil."
)
#: Ce que la 0088 a posé — et la correction, propre à ce texte d'instance que
#: le gabarit ne contient pas : elle s'écrit donc ici aussi.
NAVIGATION_AVANT = "(anonymisées après 30\xa0jours)"
NAVIGATION_APRES = "(enregistrées sans identifiant)"
DUREE_AVANT = "Télémétrie détaillée (avec identifiant)\xa0: 30\xa0jours."
DUREE_APRES = "Télémétrie détaillée (sans identifiant)\xa0: 30\xa0jours."
BASE_0088 = "Télémétrie d'usage</strong> — base"
#: Ce que la 0170 a posé dans les mentions légales.
MENTIONS_AVANT = " Chaque compte peut exporter et effacer ses propres données depuis son profil."

#: Où s'insère la base légale : la fin de la liste du point 3.
ANCRE_BASES = "</ul><h2>4. Destinataires</h2>"


def _corrections() -> list[tuple[str, str, str]]:
    """(clé, avant, après) — les phrases nouvelles lues dans le seed."""
    from app.seed.contenus_legaux import (
        DROITS_DEPUIS_LE_PROFIL,
        TELEMETRIE_COLLECTE,
        TELEMETRIE_CONSERVATION,
    )

    return [
        (POLITIQUE, COLLECTE_AVANT, TELEMETRIE_COLLECTE),
        (POLITIQUE, CONSERVATION_AVANT, TELEMETRIE_CONSERVATION),
        (POLITIQUE, DROITS_AVANT, DROITS_DEPUIS_LE_PROFIL),
        (POLITIQUE, NAVIGATION_AVANT, NAVIGATION_APRES),
        (POLITIQUE, DUREE_AVANT, DUREE_APRES),
        (MENTIONS, MENTIONS_AVANT, ""),
    ]


def _base_legale() -> str:
    from app.seed.contenus_legaux import TELEMETRIE_BASE_LEGALE

    return TELEMETRIE_BASE_LEGALE


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

    if TABLE in tables:
        if COLONNE in _colonnes(conn):
            with op.batch_alter_table(TABLE) as lot:
                lot.drop_column(COLONNE)
        conn.execute(
            sa.text(
                "UPDATE telemetry_event SET cree_le = strftime('%Y-%m-%d %H:00:00', cree_le) "
                "WHERE cree_le IS NOT NULL"
            )
        )

    if "config_site" not in tables:
        return
    for cle, avant, apres in _corrections():
        _corriger(conn, cle, avant, apres)
    base = _base_legale()
    politique = _texte(conn, POLITIQUE)
    if base not in politique and BASE_0088 not in politique:
        _corriger(conn, POLITIQUE, ANCRE_BASES, base + ANCRE_BASES)


def downgrade() -> None:
    conn = op.get_bind()
    #  Une colonne simple, sans clé étrangère (CLAUDE.md, migrations SQLite) :
    #  les lignes d'avant ne retrouvent pas leur auteur — on ne le savait plus.
    if COLONNE not in _colonnes(conn):
        op.add_column(TABLE, sa.Column(COLONNE, sa.Integer(), nullable=True))
    _corriger(conn, POLITIQUE, _base_legale() + ANCRE_BASES, ANCRE_BASES)
    #  Symétrique, sauf les mentions légales : la phrase retirée n'y a plus de
    #  place certaine, et la remettre ailleurs serait inventer.
    for cle, avant, apres in _corrections():
        if apres:
            _corriger(conn, cle, apres, avant)
