"""Les tickets ÉCRITS AVANT l'ouverture restent fermés — #710, étape 2

🔴 ANNULÉE PAR LA MIGRATION 0169 le 03/09/2026, quelques heures après son
déploiement. Ce qui suit décrit un raisonnement que l'usage a réfuté :

> « la confidentialité est un geste explicite » — l'utilisateur, 03/09/2026

Un drapeau posé par une migration n'est le geste de personne, et un badge 🔒 sur
100 % des tickets ne distingue plus rien. Cette migration reste dans la chaîne —
on ne réécrit pas une migration appliquée — mais son effet est défait par 0169.
Lire 0169 avant de croire ce qui suit.


## La décision, et pourquoi elle penche de ce côté

L'ouverture en lecture arrive dans le même lot que cette migration : un résident
verra désormais les tickets dont le périmètre recoupe ses bâtiments.

Or `perimetre_cible` a pour défaut `["résidence"]` depuis la migration 0026 — un
périmètre **à portée globale**. Sans cette migration, l'ouverture rendrait donc
lisibles de TOUS les résidents, d'un seul coup, l'intégralité des tickets déjà
écrits : ceux qu'on a rédigés en sachant que seuls l'auteur et le conseil
syndical les liraient.

Deux façons de traiter ça, et une seule est réversible dans le bon sens :

| | |
|---|---|
| ouvrir tout, refermer après relecture | ce qui a été lu ne se dé-lit pas |
| **fermer tout, ouvrir après relecture** | un clic par ticket, décidé en connaissance de cause |

La seconde coûte du travail au conseil syndical. La première coûte une fuite si
personne ne relit — et personne ne relit ce qui a l'air déjà réglé.

## Ce que ça fait exactement

Tous les tickets existants passent à `confidentiel = 1`. Ils redeviennent donc
visibles de leur auteur, de la personne pour qui ils ont été saisis, et du CS —
c'est-à-dire **exactement ce qu'ils étaient hier**. Cette migration ne referme
rien : elle empêche une ouverture rétroactive.

Les tickets créés **après** sont ouverts par défaut, comme les actualités.

## Pourquoi ce n'est pas une migration de données douteuse

Une migration qui touche des données est presque toujours suspecte — celle-ci
est bornée à un booléen, sur les lignes déjà présentes, et elle est idempotente
au sens qui compte : la rejouer ne changerait rien, puisque les tickets créés
ensuite ne sont plus « existants au moment de la MEP ». C'est pourquoi elle
n'a pas de garde : la sélection est portée par la clause elle-même.

⚠️ `downgrade()` ne remet PAS les tickets à `confidentiel = 0`. On ne sait pas
lesquels le CS a rouverts entre-temps, et rouvrir en masse serait la fuite que
cette migration existe pour éviter. Un downgrade qui perd de l'information doit
la perdre du côté fermé.

Revision ID: 0167
Revises: 0166
Create Date: 2026-09-02
"""
from alembic import op
from sqlalchemy import text

revision = "0167"
down_revision = "0166"
branch_labels = None
depends_on = None


def upgrade():
    #  Pas de f-string : `standards/06` §3. Ici il n'y a même rien à lier — la
    #  requête est constante, et c'est la forme la plus sûre.
    op.execute(text("UPDATE ticket SET confidentiel = 1 WHERE confidentiel = 0"))


def downgrade():
    #  Volontairement inerte : voir l'en-tête. Rouvrir en masse des tickets que
    #  le CS a pu marquer délibérément serait exactement la fuite qu'on évite.
    pass
