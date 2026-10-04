"""Le jour de la dernière visite de chaque compte, rempli de ce que la base sait, et la politique le dit (#1629, 04/10/2026)

L'onglet Télémétrie compte les comptes DORMANTS (sans visite depuis 60 et 90
jours). Les évènements, seuls à porter le compte au jour près, vivent 30 jours ;
la présence mensuelle ne sait que le mois ; `utilisateur.derniere_connexion` ne
bouge qu'à la saisie du mot de passe — une session se renouvelle seule pendant
7 jours glissants. D'où :

1. **`derniere_visite`** — un jour par compte, sans autre colonne. Table neuve :
   aucune contrainte d'une table existante n'est altérée.
2. **Le remplissage, depuis ce que la base sait** — sinon chaque compte venu
   avant la mise en production passerait pour dormant dès que ses évènements
   seraient purgés :
   - les **évènements** : le jour de la plus récente (au jour UTC, à quelques
     heures près la nuit) ;
   - à défaut, la **présence mensuelle** : le DERNIER jour du dernier mois de
     présence, au plus tard la veille des 30 jours d'évènements — une borne
     haute : un compte n'est jamais dit dormant à tort ; il peut l'être avec
     quelques semaines de retard, le temps que les vraies visites remplacent
     ces bornes ;
   - jamais un compte qui a refusé la mesure d'audience.
3. **La politique servie le dit** : le paragraphe `TELEMETRIE_DERNIERE_VISITE`,
   lu dans le seed, est inséré juste après celui de la conservation
   (`TELEMETRIE_CONSERVATION`). Remplacement EXACT (`utils/textes_livres`) : un
   texte reformulé à la main n'est pas touché — l'administrateur l'ajoute alors
   depuis Admin › Légal.

Idempotente : la table n'est créée que si elle manque, un compte déjà noté ne
l'est pas deux fois, le paragraphe n'est inséré que s'il n'y est pas.

⚠️ Les noms de tables et la clé de configuration sont des CONSTANTES du fichier ;
les requêtes du remplissage les écrivent en clair, sans f-string.

Revision ID: 0260
Revises: 0259
"""

from datetime import timedelta

import sqlalchemy as sa

from alembic import op

revision = "0260"
down_revision = "0259"
branch_labels = None
depends_on = None

TABLE = "derniere_visite"  # identifiants : constantes du fichier
INDEX = "ix_derniere_visite_jour"
POLITIQUE = "politique_confidentialite"
SOURCES = ("telemetry_event", "presence_mensuelle", "utilisateur")

DEPUIS_LES_EVENEMENTS = (
    "INSERT INTO derniere_visite (user_id, jour) "
    "SELECT e.user_id, date(max(e.cree_le)) FROM telemetry_event e "
    "JOIN utilisateur u ON u.id = e.user_id "
    "WHERE u.opt_out_telemetrie = 0 "
    "AND e.user_id NOT IN (SELECT user_id FROM derniere_visite) "
    "GROUP BY e.user_id"
)
DEPUIS_LA_PRESENCE = (
    "INSERT INTO derniere_visite (user_id, jour) "
    "SELECT p.user_id, min(date(max(p.mois) || '-01', '+1 month', '-1 day'), :plafond) "
    "FROM presence_mensuelle p "
    "JOIN utilisateur u ON u.id = p.user_id "
    "WHERE u.opt_out_telemetrie = 0 "
    "AND p.user_id NOT IN (SELECT user_id FROM derniere_visite) "
    "GROUP BY p.user_id"
)


def _texte(conn) -> str | None:
    ligne = conn.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = :c").bindparams(c=POLITIQUE)
    ).fetchone()
    return (ligne[0] or "") if ligne else None


def _corriger(conn, avant: str, apres: str) -> int:
    from app.utils.textes_livres import remplacer_passage

    return remplacer_passage(conn, "config_site", {"cle": POLITIQUE}, "valeur", avant, apres)


def upgrade() -> None:
    from app.seed.contenus_legaux import TELEMETRIE_CONSERVATION, TELEMETRIE_DERNIERE_VISITE
    from app.utils import horloge

    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if TABLE not in tables:
        op.create_table(
            TABLE,
            sa.Column("user_id", sa.Integer(), primary_key=True),
            sa.Column("jour", sa.String(), nullable=False),
        )
        op.create_index(INDEX, TABLE, ["jour"])

    if all(source in tables for source in SOURCES):
        conn.execute(sa.text(DEPUIS_LES_EVENEMENTS))
        plafond = (horloge.aujourd_hui() - timedelta(days=31)).isoformat()
        conn.execute(sa.text(DEPUIS_LA_PRESENCE).bindparams(plafond=plafond))

    if "config_site" not in tables:
        return
    texte = _texte(conn)
    if texte is not None and TELEMETRIE_DERNIERE_VISITE not in texte:
        _corriger(conn, TELEMETRIE_CONSERVATION, TELEMETRIE_CONSERVATION + TELEMETRIE_DERNIERE_VISITE)


def downgrade() -> None:
    from app.seed.contenus_legaux import TELEMETRIE_DERNIERE_VISITE

    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if "config_site" in tables:
        _corriger(conn, TELEMETRIE_DERNIERE_VISITE, "")
    if TABLE in tables:
        op.drop_table(TABLE)
