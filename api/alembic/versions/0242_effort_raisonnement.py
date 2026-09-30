"""L'effort de raisonnement de chaque usage de l'assistant (30/09/2026)

Demandé : « gpt-5.6-luna + reasoning.effort=low = choix par défaut ? faut-il
le paramétrer ? ». L'application n'envoyait aucun effort : chaque modèle
raisonnait à son propre défaut — souvent « moyen » —, et ces jetons se paient
comme la réponse.

Le réglage `llm_<usage>_effort` est une clé de configuration : rien à créer.
Cette migration pose seulement les valeurs arbitrées le même jour, et
uniquement là où rien n'est encore réglé :

| Usage | Effort | Pourquoi |
|---|---|---|
| `reponse_courriel` | faible | mettre en forme, sans rien ajouter |
| `description` | faible | reformuler un texte court |
| `tarif_modele` | faible | trouver une ligne dans une grille |
| `synthese_contrat` | moyen | lire et citer un contrat entier |

Une clé vide n'envoie rien : l'administrateur y revient par « Par défaut du
modèle ». Un modèle qui ne raisonne pas refuse le réglage, et l'appel repart
sans lui (`Fournisseur.adapter`).

Revision ID: 0242
Revises: 0241
"""

import sqlalchemy as sa
from alembic import op

revision = "0242"
down_revision = "0241"
branch_labels = None
depends_on = None

EFFORTS = {
    "reponse_courriel": "faible",
    "description": "faible",
    "tarif_modele": "faible",
    "synthese_contrat": "moyen",
}


def upgrade() -> None:
    conn = op.get_bind()
    for usage, effort in EFFORTS.items():
        cle = f"llm_{usage}_effort"
        present = conn.execute(
            sa.text("SELECT 1 FROM config_site WHERE cle = :cle").bindparams(cle=cle)
        ).fetchone()
        if present is None:
            conn.execute(
                sa.text("INSERT INTO config_site (cle, valeur) VALUES (:cle, :valeur)").bindparams(
                    cle=cle, valeur=effort
                )
            )


def downgrade() -> None:
    conn = op.get_bind()
    for usage in EFFORTS:
        conn.execute(
            sa.text("DELETE FROM config_site WHERE cle = :cle").bindparams(
                cle=f"llm_{usage}_effort"
            )
        )
