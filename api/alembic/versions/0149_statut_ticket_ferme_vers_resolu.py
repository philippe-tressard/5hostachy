"""Les tickets `fermé` deviennent `résolu` — le workflow n'a que quatre états.

`fermé` traînait dans `StatutTicket` depuis le tout premier commit (`2792b76`),
annoté « conservé pour compatibilité données existantes ». Le code n'en faisait
pourtant rien de particulier : même `ferme_le`, même bascule vers l'Historique,
même exclusion des relances syndic et des compteurs « à traiter » que `résolu`.
Sa seule différence observable — un ticket `fermé` n'acceptait plus de réponse —
n'était écrite nulle part comme une intention.

Il n'était donc pas un cinquième état, mais un doublon du troisième : les états
sont **ouvert · en cours · résolu · annulé** (#415, arbitré le 17/08/2026).

## Ce que fait cette migration

Elle bascule en `résolu` les tickets qui portent encore `fermé`, ainsi que la
graphie sans accent `ferme` d'un modèle antérieur — que `app/database.py`
normalisait jusqu'ici en `fermé`, c'est-à-dire vers la valeur qui disparaît.

Elle **ne touche pas** à `ticket_evolution` : les lignes du fil qui racontent
« Statut : Ouvert → Fermé » sont l'histoire de ce ticket, et la réécrire serait
inventer un passé qui n'a pas eu lieu. Ces valeurs restent affichables
(`STATUT_LABELS`, `STATUTS_TICKET_HISTORIQUES`) sans jamais être proposables.

Effet de bord assumé : ces tickets redeviennent répondables, comme tout ticket
résolu.

Revision ID: 0149
Revises: 0148
Create Date: 2026-08-17
"""
import sqlalchemy as sa
from alembic import op

revision = "0149"
down_revision = "0148"
branch_labels = None
depends_on = None


def upgrade() -> None:
    #  SQL statique, aucune valeur interpolée : pas de f-string ici (règle du
    #  projet). Sans effet si aucune ligne ne porte ces valeurs — ce que
    #  personne ne peut vérifier depuis le poste, `app.db` ne s'ouvrant pas à
    #  chaud depuis un process tiers.
    op.execute(
        sa.text("UPDATE ticket SET statut = 'résolu' WHERE statut IN ('fermé', 'ferme')")
    )


def downgrade() -> None:
    #  Irréversible **par construction** : après la montée, plus rien ne
    #  distingue un ticket anciennement `fermé` d'un ticket résolu de longue
    #  date. Restaurer au jugé rendrait `fermé` à des tickets qui ne l'ont
    #  jamais porté. La descente est donc un no-op déclaré, pas un oubli.
    pass
