"""Historique des tâches planifiées : nœud, portée, tâche et détails chiffrés.

`historique_maintenance` ne pouvait décrire qu'une seule réalité : la maintenance
applicative du nœud ACTIF. Deux conséquences mesurées le 02/08/2026 :

1. Le standby exécute bien une hygiène locale (le 02/08 : 3,358 Go de cache de
   build purgés et 66 338 lignes de log rotées) mais ne l'enregistre nulle part —
   `maintenance.sh` poste sur `http://localhost/api/...`, or il n'y a pas d'API
   sur le nœud passif. La moitié du travail d'hygiène était invisible.
2. Sans colonne `noeud`, une ligne ne dit pas *qui* a agi, et une absence de
   ligne ne distingue pas « pas exécuté », « échoué » et « exécuté sans pouvoir
   l'enregistrer ».

Quatre colonnes, toutes NULLABLE ou avec défaut serveur : aucune réécriture de
table, et les lignes existantes restent valides (elles décrivent bien une
maintenance applicative, d'où les valeurs par défaut retenues).

⚠️ Le nom de table reste `historique_maintenance` alors qu'elle porte désormais
toutes les tâches planifiées : un renommage imposerait une migration plus lourde
sur une base de production SQLite pour un gain cosmétique. Le modèle le
documente.

Revision ID: 0122
Revises: 0121
Create Date: 2026-08-02
"""
import sqlalchemy as sa
from alembic import op

revision = "0122"
down_revision = "0121"
branch_labels = None
depends_on = None

_TABLE = "historique_maintenance"

# (nom, type, défaut serveur) — le défaut vaut aussi pour les lignes existantes.
_COLONNES = (
    ("tache", sa.String(), "maintenance"),
    ("noeud", sa.String(), None),
    ("portee", sa.String(), "applicative"),
    ("details", sa.Text(), None),
)


def _colonnes_existantes(conn) -> set:
    return {r[1] for r in conn.execute(sa.text(f"PRAGMA table_info({_TABLE})"))}


def upgrade():
    conn = op.get_bind()
    presentes = _colonnes_existantes(conn)
    for nom, type_, defaut in _COLONNES:
        if nom in presentes:            # idempotent : une reprise ne casse pas
            continue
        op.add_column(
            _TABLE,
            sa.Column(nom, type_, nullable=True,
                      server_default=sa.text(f"'{defaut}'") if defaut else None),
        )
    presentes = _colonnes_existantes(conn)
    if "tache" in presentes:
        op.create_index("ix_historique_maintenance_tache", _TABLE, ["tache"])
    if "noeud" in presentes:
        op.create_index("ix_historique_maintenance_noeud", _TABLE, ["noeud"])


def downgrade():
    for idx in ("ix_historique_maintenance_noeud", "ix_historique_maintenance_tache"):
        op.drop_index(idx, table_name=_TABLE)
    for nom, _, _ in reversed(_COLONNES):
        op.drop_column(_TABLE, nom)
