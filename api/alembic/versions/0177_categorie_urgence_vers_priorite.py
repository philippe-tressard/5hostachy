"""« Urgence » n'était pas une catégorie, c'était une priorité (#820).

Question posée à l'écran le 07/09/2026 : *« n'y a-t-il pas d'autres catégories
de tickets ? »*. Il en manquait trois — mais le vrai défaut était ailleurs.

## 🔴 Ce que « Urgence » mélangeait

Une catégorie dit ce qu'un ticket **est** ; une priorité dit dans quel **délai**
il doit être traité. « Urgence » répondait à la seconde question dans la liste
qui pose la première. Un résident dont l'ascenseur est bloqué avec quelqu'un
dedans devait choisir entre « Panne » et « Urgence » — et perdait l'autre moitié
de l'information quel que soit son choix.

⚠️ Le remplacement existait **déjà**, et il servait déjà : `PrioriteTicket.haute`,
que la case « Urgent » du formulaire écrit depuis #766. Le commentaire de
`front/src/lib/tickets.ts` le disait en toutes lettres — *« `urgente` →
`priorite === 'haute'`, ce que la catégorie Urgence pose déjà »*. Les deux axes
se recoupaient, et le code le savait sans que personne en tire la conséquence.

## Ce que cette migration fait des tickets existants

    categorie = 'urgence'  →  categorie = 'panne'  ET  priorite = 'haute'

**La priorité est posée, jamais devinée.** Un ticket rangé en « Urgence » l'a été
pour dire qu'il pressait : c'est cette information-là qu'il faut sauver, et elle
n'existe nulle part ailleurs. La catégorie, elle, est reconstituable en lisant le
ticket — pas l'urgence, qui vivait dans la seule colonne qu'on retire.

⚠️ `panne` est un repli assumé, pas une déduction. L'ancienne description
disait « Inondation, panne majeure, danger immédiat » : une partie de ces
tickets relèverait aujourd'hui de « Dégât des eaux ». Les répartir demanderait
de LIRE chaque ticket, ce qu'une migration ne peut pas faire — et un tri
automatique aurait rangé des inondations en pannes **en prétendant les avoir
classées**. Le conseil syndical reclasse à la main ce qui doit l'être ; d'ici là
rien n'est perdu, et rien n'est faussement affirmé.

## Pourquoi un simple UPDATE suffit

`CategorieTicket` est une `(str, Enum)` : SQLite stocke la chaîne, il n'y a
aucun type à altérer. C'est aussi pourquoi la migration doit être écrite — sans
elle, les tickets gardent la valeur `'urgence'`, que l'énumération ne connaît
plus. Ils s'afficheraient avec leur valeur brute (`libelle_categorie` rend la
chaîne telle quelle, exprès) : lisible, mais faux.

Revision ID: 0177
Revises: 0176
"""
import sqlalchemy as sa
from alembic import op

revision = "0177"
down_revision = "0176"
branch_labels = None
depends_on = None


def upgrade() -> None:
    #  Idempotente : `start.sh` a `set -e`, et un second passage ne doit rien
    #  casser. Ici c'est acquis — après le premier, plus aucune ligne ne porte
    #  `'urgence'`, et l'UPDATE ne touche rien.
    #
    #  🔴 Jamais de f-string dans `op.execute()` (`CLAUDE.md`) : les valeurs
    #  passent par `bindparams`, même quand elles sont littérales et connues.
    op.execute(
        sa.text(
            "UPDATE ticket SET categorie = :cible, priorite = :priorite "
            "WHERE categorie = :ancienne"
        ).bindparams(cible="panne", priorite="haute", ancienne="urgence")
    )


def downgrade() -> None:
    #  🔴 Irréversible, et le dire vaut mieux que le faire à moitié.
    #
    #  Remettre `categorie = 'urgence'` demanderait de savoir QUELS tickets à
    #  priorité haute portaient cette catégorie avant. Rien ne le dit : la
    #  priorité haute existait déjà, posée par la case « Urgent », sur des
    #  tickets de toutes catégories. Un downgrade rendrait donc « urgence » à
    #  des tickets qui ne l'ont jamais eue.
    #
    #  Ne rien faire est le seul comportement honnête : la migration retirée,
    #  ces tickets restent des pannes à priorité haute, ce qu'ils sont.
    pass
