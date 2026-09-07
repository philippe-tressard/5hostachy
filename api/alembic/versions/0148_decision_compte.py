"""Horodater la décision prise sur un compte — valider, refuser, désactiver.

`actif == False` servait à la fois de « en attente de validation », de « refusé »
et de « désactivé ». Les trois lecteurs de cet état (l'écran Admin, l'onglet
« Comptes & accès » de l'Espace CS, et le compteur du tableau de bord) étaient
donc **d'accord entre eux, et tous les trois sur la mauvaise définition** — c'est
ce qui rendait le défaut invisible à la relecture (#399).

Deux conséquences observables, corrigées par le même lot :

  • un compte **refusé** restait compté « en attente » pour toujours :
    `traiter_compte(action="refuser")` n'écrivait aucun état, il se contentait
    d'envoyer un e-mail. L'admin le refusait, il revenait au chargement suivant ;
  • un compte **désactivé** volontairement (départ d'un résident, suspension via
    `PATCH /admin/utilisateurs/{id}`) réapparaissait dans la file des validations.

## Rétro-remplissage : ce qu'on sait, et ce qu'on n'invente pas

Les comptes `actif = 1` ont forcément été validés un jour — on ne sait pas quand,
`cree_le` est la seule date disponible et elle est antérieure ou égale à la
décision. Elle suffit : le champ n'est lu que pour savoir SI la décision existe.

Les comptes `actif = 0`, eux, restent à NULL. On ne peut pas distinguer
rétroactivement un compte en attente d'un compte refusé — les deux ont produit
exactement les mêmes octets. Ils continuent donc d'être comptés « en attente »,
comme avant ce lot : **aucune régression, et aucun rattrapage inventé** sur des
données qui ne le portent pas. La correction vaut pour les décisions à venir, et
l'administration solde l'arriéré en traitant la file une dernière fois.

Revision ID: 0148
Revises: 0147
Create Date: 2026-08-17
"""
import sqlalchemy as sa
from alembic import op

revision = "0148"
down_revision = "0147"
branch_labels = None
depends_on = None

TABLE = "utilisateur"
COLONNE = "decision_compte_le"


def _colonnes(table: str) -> set:
    """Colonnes réellement présentes, lues sur la base en cours de migration.

    Même précaution qu'en 0137, 0142 et 0144 : ajouter une colonne déjà présente
    ferait échouer `alembic upgrade`, et `start.sh` a `set -e` — le conteneur ne
    démarrerait plus, sur les deux nœuds.
    """
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(table)}


def upgrade() -> None:
    if COLONNE in _colonnes(TABLE):
        return
    #  Nullable, et c'est la valeur qui porte le sens : NULL = « aucune décision
    #  prise ». Un défaut serveur ferait mentir la colonne dès la migration.
    op.add_column(TABLE, sa.Column(COLONNE, sa.DateTime(), nullable=True))
    #  SQL statique, aucune valeur interpolée : pas de f-string ici (règle du
    #  projet), et rien à passer en `bindparams`.
    op.execute(
        sa.text(
            "UPDATE utilisateur SET decision_compte_le = cree_le WHERE actif = 1"
        )
    )


def downgrade() -> None:
    if COLONNE not in _colonnes(TABLE):
        return
    op.drop_column(TABLE, COLONNE)
