"""« Propreté » rejoint « Nuisance » — la frontière n'existait pas (#821).

Signalé le 07/09/2026, quelques heures après la livraison de la catégorie :

> *« Très sincèrement, Propreté je la regrouperais dans la catégorie Nuisance en
> complétant le libellé. »*

## 🔴 Trois signes le disaient déjà, et je ne les ai pas lus

J'avais créé « Propreté » sur l'argument « autre prestataire : le nettoyage, pas
le technique ». Il était faux, et le code écrit le matin même le montrait :

1. **Le geste est le même.** Le conseil relaie au syndic ou au prestataire ; il
   ne fait pas deux choses différentes. Mon critère — « une catégorie ne se
   justifie que si elle change ce qu'on FAIT du ticket » — était le bon, mais je
   l'avais appliqué à « qui exécute in fine » au lieu de « qui traite ».
2. **J'avais admis le recouvrement** en écrivant, dans `tickets.ts` : « un
   encombrant abandonné dans le hall est les deux à la fois ».
3. **J'avais dû expliquer la frontière dans le manuel.** Une frontière qu'il faut
   expliquer est une frontière qui n'existe pas.

Le libellé devient « Nuisance & propreté », et sa description couvre les deux :
« Bruit, odeurs, stationnement, parties communes, encombrants ».

## Ce que cette migration fait des tickets existants

    categorie = 'proprete'  →  categorie = 'nuisance'

Sans perte : les deux notions fusionnent, aucune information n'est écartée. C'est
la différence avec la migration 0177, qui repliait « urgence » sur « panne » en
sauvant l'urgence dans la priorité — là, il fallait choisir ; ici, non.

⚠️ La catégorie n'a vécu qu'une demi-journée en production (v3.114.0, 18h38 →
ce soir). Le nombre de tickets concernés est donc probablement nul. La migration
existe quand même : « probablement nul » n'est pas « nul », et un ticket qui
garderait la valeur `'proprete'` s'afficherait avec sa chaîne brute
(`libelle_categorie` rend la valeur telle quelle, exprès) — lisible, mais faux.

Revision ID: 0179
Revises: 0178
"""
import sqlalchemy as sa
from alembic import op

revision = "0179"
down_revision = "0178"
branch_labels = None
depends_on = None


def upgrade() -> None:
    #  Idempotente par nature : après le premier passage, plus aucune ligne ne
    #  porte `'proprete'` et l'UPDATE ne touche rien.
    #
    #  🔴 Jamais de f-string dans `op.execute()` (`CLAUDE.md`) : les valeurs
    #  passent par `bindparams`, même littérales et connues.
    op.execute(
        sa.text("UPDATE ticket SET categorie = :cible WHERE categorie = :ancienne").bindparams(
            cible="nuisance", ancienne="proprete"
        )
    )


def downgrade() -> None:
    #  🔴 Irréversible, et le dire vaut mieux que le faire à moitié.
    #
    #  Rendre `'proprete'` à une partie des tickets « nuisance » demanderait de
    #  savoir lesquels la portaient avant. Rien ne le dit — la catégorie
    #  « nuisance » existait déjà et portait ses propres tickets. Un downgrade
    #  attribuerait donc « propreté » à des tickets qui ne l'ont jamais eue.
    pass
