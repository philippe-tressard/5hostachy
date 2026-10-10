"""Les visites venues du calendrier retrouvent leur contrat (arbitré le 10/10/2026).

## Pourquoi

Un entretien PÉRIODIQUE est une affaire Entretien sous contrat ou à récurrence
(`utils/entretien_periodique`) : il quitte la relance syndic et se suit dans la
vue « Entretien périodique » du reporting. Les visites posées depuis un contrat
le portent depuis #1445 — mais pas celles que la 0212 a converties depuis le
calendrier : les « maintenances récurrentes » d'alors ne portaient ni contrat ni
fréquence, et la 0235 ne reprenait que les affaires qui avaient une fréquence.
En production, six visites de l'exercice restaient ainsi dans la relance syndic,
« Chez le prestataire », avec 203 jours sans modification.

## La reprise — la règle de la 0235, sur les visites qu'elle n'a pas vues

- une affaire **Entretien** issue d'un événement `maintenance_recurrente`, sans
  contrat ni fréquence, avec un prestataire ;
- le contrat **en cours** de ce prestataire dont le libellé figure dans le titre
  (« Prestataire — Libellé du contrat », la forme qu'« Init. prestataires »
  donnait), à défaut son **seul** contrat en cours ;
- jamais un contrat sans fréquence : l'affaire n'aurait aucun rythme.

Idempotente : une affaire rattachée n'est plus candidate. Données seules : le
code précédent lit `contrat_id` depuis la 0235, il reste compatible. `downgrade`
ne défait rien — rien ne distingue un rattachement d'ici d'un rattachement
saisi depuis.

Revision ID: 0272
Revises: 0271
"""

import sqlalchemy as sa
from alembic import op

revision = "0272"
down_revision = "0271"
branch_labels = None
depends_on = None


def retenir(contrats: list[dict], prestataire_id: int, titre: str) -> dict | None:
    """Le contrat du prestataire nommé par le titre, à défaut son seul contrat."""
    siens = [c for c in contrats if c["prestataire_id"] == prestataire_id]
    par_titre = next(
        (c for c in siens if c["libelle"] and c["libelle"].lower() in (titre or "").lower()),
        None,
    )
    return par_titre or (siens[0] if len(siens) == 1 else None)


def upgrade():
    conn = op.get_bind()
    contrats = [
        dict(ligne)
        for ligne in conn.execute(
            sa.text(
                "SELECT id, prestataire_id, libelle FROM contrat_entretien "
                "WHERE actif = :actif AND frequence_type IS NOT NULL "
                "AND type_equipement NOT IN ('assurance', 'syndic')"
            ).bindparams(actif=True)
        ).mappings()
    ]
    visites = conn.execute(
        sa.text(
            "SELECT t.id, t.prestataire_id, t.titre FROM ticket t "
            "JOIN evenement e ON e.id = t.promu_depuis_evenement_id "
            "WHERE t.categorie = 'entretien' AND e.type = 'maintenance_recurrente' "
            "AND t.contrat_id IS NULL AND t.frequence_type IS NULL "
            "AND t.prestataire_id IS NOT NULL"
        )
    ).mappings()
    for visite in list(visites):
        contrat = retenir(contrats, visite["prestataire_id"], visite["titre"])
        if contrat is not None:
            conn.execute(
                sa.text("UPDATE ticket SET contrat_id = :contrat WHERE id = :ticket").bindparams(
                    contrat=contrat["id"], ticket=visite["id"]
                )
            )


def downgrade():
    pass
