"""Migration rôles v2 — ajout propriétaire / externe ; mise à jour utilisateurs et profils d'accès

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-10
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

# Nouveaux roles_autorises par code de profil (valeurs de rôles)
PROFIL_UPDATES = {
    "résidence_tous":        json.dumps(["propriétaire", "résident"]),
    "copropriétaires_et_cs": json.dumps(["propriétaire"]),
    "cs_syndic_uniquement":  json.dumps(["syndic"]),   # statut syndic ; CS bypassed en amont
    "lot_occupants":         json.dumps(["propriétaire", "résident"]),
    "lot_propriétaires":     json.dumps(["propriétaire"]),
}

# Mapping statut → rôles attribués
STATUT_ROLES_MAP = {
    "copropriétaire_résident": ["propriétaire", "résident"],
    "copropriétaire_bailleur": ["propriétaire"],
    "locataire":               ["résident"],
    "mandataire":              ["externe"],
    "syndic":                  ["externe"],
    # admin_technique : aucun rôle résidentiel injecté — roles_json conservé tel quel
}

# Rôle principal par statut
STATUT_PRIMARY = {
    "copropriétaire_résident": "propriétaire",
    "copropriétaire_bailleur": "propriétaire",
    "locataire":               "résident",
    "mandataire":              "externe",
    "syndic":                  "externe",
}

_PRIO = {"admin": 4, "conseil_syndical": 3, "propriétaire": 2, "résident": 1, "externe": 1}


def upgrade():
    conn = op.get_bind()

    # 1. Mise à jour des profils d'accès aux documents
    for code, new_roles in PROFIL_UPDATES.items():
        conn.execute(
            sa.text(
                "UPDATE profil_acces_document SET roles_autorises = :r WHERE code = :c"
            ),
            {"r": new_roles, "c": code},
        )

    # 2. Migration des rôles des utilisateurs existants
    users = conn.execute(
        sa.text("SELECT id, statut, roles_json, role FROM utilisateur")
    ).fetchall()

    for user in users:
        statut = user.statut
        if statut not in STATUT_ROLES_MAP:
            continue

        base_roles = STATUT_ROLES_MAP[statut]

        # Conserver les rôles élevés déjà accordés (admin, conseil_syndical)
        existing = (
            [r.strip() for r in user.roles_json.split(",") if r.strip()]
            if user.roles_json
            else [user.role]
        )
        elevated = [r for r in existing if r in ("admin", "conseil_syndical")]

        # Fusionner sans doublon en préservant l'ordre
        merged = list(dict.fromkeys(base_roles + elevated))

        # Rôle principal = le plus élevé
        top = max(merged, key=lambda r: _PRIO.get(r, 0))

        conn.execute(
            sa.text(
                "UPDATE utilisateur SET roles_json = :rj, role = :ro WHERE id = :id"
            ),
            {"rj": ",".join(merged), "ro": top, "id": user.id},
        )


def downgrade():
    # Rollback non destructif : les anciennes valeurs ne sont plus connues
    pass
