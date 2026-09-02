"""Annuler la confidentialité posée d'office par 0167 — elle n'était pas un geste

## Ce que 0167 a fait, et pourquoi c'était une erreur

Le 03/09/2026, la migration 0167 a marqué **tous** les tickets existants comme
confidentiels, à l'ouverture de la lecture par périmètre (#710). Le raisonnement
était : ces tickets ont été rédigés quand seuls l'auteur et le conseil les
lisaient, les ouvrir rétroactivement n'a pas été décidé.

Il était faux, et l'utilisateur l'a tranché en une phrase le jour même :

> « la confidentialité est un geste explicite »

Un drapeau posé par une migration n'est le geste de personne. Il ne dit pas
« ce dossier est sensible », il dit seulement « on n'a pas regardé ». Et un badge
🔒 sur **100 %** des tickets ne distingue plus rien : il devient du décor, et le
jour où le conseil marquera un vrai litige, personne ne le remarquera.

C'est le défaut classique de l'avertissement systématique — celui qu'on finit par
ne plus lire parce qu'il est partout.

## Ce que la règle devient

Le régime est **le même pour tous les tickets**, anciens et nouveaux : ouverts
aux résidents dont ils concernent les bâtiments, refermés **quand le conseil
syndical coche la case**. La visibilité d'un ticket ne dépend plus de sa date.

⚠️ Ce qui protège reste entier, et n'a jamais dépendu de ce drapeau :
`ticket_visible()` ne montre un ticket qu'aux résidents de son périmètre — un
dossier ciblé « Bât. 1 › Escaliers » n'est pas lisible du bâtiment 3. Le drapeau
ne sert qu'aux cas où même les voisins concernés ne doivent pas voir.

## 🔴 Le risque assumé, et il faut le dire

Cette migration remet `confidentiel = 0` sur **tous** les tickets. Si un membre
du conseil avait coché la case entre le déploiement de 0167 et celui-ci, son
geste serait effacé.

La colonne ne porte ni auteur ni date : rien ne permet de distinguer un marquage
volontaire du marquage d'office. La fenêtre est d'environ une heure, et le badge
n'a été découvert qu'à la fin — mais l'incertitude existe, et la taire aurait été
pire que le risque lui-même.

Revision ID: 0169
Revises: 0168
Create Date: 2026-09-03
"""
from alembic import op
from sqlalchemy import text

revision = "0169"
down_revision = "0168"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text("UPDATE ticket SET confidentiel = 0 WHERE confidentiel = 1"))


def downgrade():
    #  Volontairement inerte. Remettre la confidentialité d'office rejouerait
    #  exactement l'erreur que cette migration corrige — et un downgrade qui
    #  restaure un défaut n'est pas un downgrade.
    pass
