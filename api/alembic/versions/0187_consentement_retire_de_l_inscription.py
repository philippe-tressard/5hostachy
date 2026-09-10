"""La case de consentement quitte l'inscription, et la refuser produit enfin un effet

Revision ID: 0187
Revises: 0186
Create Date: 2026-09-10

## Ce que cette migration répare (#873)

`Utilisateur.consentement_communications` était **écrit à l'inscription et lu
nulle part** : quatre occurrences dans le dépôt, aucune lecture. Quelqu'un qui
laissait la case décochée recevait quand même tous les e-mails de son bâtiment
— on lui avait demandé son accord, il l'avait refusé, et rien n'avait changé.

Deux défauts, dont un de conformité (rang 1) : la promesse faite à l'inscription
était fausse, et le consentement n'était **jamais retirable** (RGPD art. 7.3 —
*« il doit être aussi simple de retirer son consentement que de le donner »*).

## L'arbitrage (Philippe, 10/09/2026) : retirer la case, basculer l'existant

Le consentement se donne et se retire désormais au **seul endroit où il
s'exerce** : Profil → Notifications (`preferences_notifications`), qui est bien
fait et dont le retrait existe déjà. L'inscription cesse de promettre ce qu'elle
ne tient pas.

Restaient les comptes existants, qui recevaient des e-mails malgré leur refus.
Ce `upgrade` honore ce refus : **c'est le seul moment où cette donnée aura servi
à quelque chose.**

⚠️ **On ne bascule QUE les comptes qui n'ont jamais touché leurs préférences.**
Un compte qui a refusé à l'inscription puis réglé son profil a fait un choix
POSTÉRIEUR et explicite : l'écraser avec une case vieille de plusieurs mois
remplacerait sa décision par la nôtre. La condition porte donc sur
`preferences_notifications` NULL, vide, ou égal au défaut posé à la création.

⚠️ **Les e-mails transactionnels ne sont pas touchés, et c'est VÉRIFIÉ, pas
supposé** : `send_email` ne consulte les préférences que si un `destinataire_id`
lui est passé, et ni `reinitialisation_mdp` ni `verification_email` n'en passent
(`routers/auth_mot_de_passe.py`, `routers/auth.py`). Un compte basculé garde donc
son mot de passe oublié et sa validation de compte.
`api/tests/test_courriels_transactionnels.py` refuse qu'on le leur ajoute.

## Pourquoi la colonne est SUPPRIMÉE

La garder aurait laissé une donnée personnelle qui ne sert plus à rien —
minimisation, RGPD art. 5.1.c —, et une colonne morte que le prochain lecteur
croirait branchée. C'est exactement ce qui a produit ce ticket. Son information
est consommée par ce `upgrade` avant de disparaître : elle n'est pas perdue, elle
est appliquée.

⚠️ `downgrade` recrée la colonne à `false` pour tout le monde : le consentement
d'origine n'est pas restaurable, et prétendre le contraire serait pire. Un retour
en arrière rendrait une case décochée — donc sans effet, comme avant.
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0187"
down_revision = "0186"
branch_labels = None
depends_on = None

#: Le défaut posé à la création d'un compte. Recopié ici À DESSEIN : une
#: migration décrit l'état du monde AU MOMENT où elle tourne, et doit rester
#: rejouable même si `preferences_mail.DEFAUTS` évolue demain
#: (`standards/06` §3 — le code et le schéma voyagent ensemble, mais une
#: migration ne suit pas le code qui bouge après elle).
_DEFAUT_A_L_EPOQUE = json.dumps({"mon_batiment_mail": True, "autres_batiments_mail": False})

#: Ce qu'on écrit pour un compte qui a refusé : aucun e-mail de notification.
_REFUS = json.dumps({"mon_batiment_mail": False, "autres_batiments_mail": False})


def _colonnes(bind) -> set[str]:
    return {r[1] for r in bind.execute(sa.text("PRAGMA table_info('utilisateur')"))}


def upgrade() -> None:
    bind = op.get_bind()
    if "consentement_communications" not in _colonnes(bind):
        return  # déjà passée (garde d'idempotence)

    #  🔴 Jamais de f-string dans un `op.execute` — `bindparams`, comme partout
    #  ailleurs dans ce dossier.
    bind.execute(
        sa.text(
            """
            UPDATE utilisateur
               SET preferences_notifications = :refus
             WHERE consentement_communications = 0
               AND (
                    preferences_notifications IS NULL
                 OR TRIM(preferences_notifications) = ''
                 OR preferences_notifications = :defaut
               )
            """
        ).bindparams(refus=_REFUS, defaut=_DEFAUT_A_L_EPOQUE)
    )

    with op.batch_alter_table("utilisateur") as batch:
        batch.drop_column("consentement_communications")


def downgrade() -> None:
    bind = op.get_bind()
    if "consentement_communications" in _colonnes(bind):
        return
    op.add_column(
        "utilisateur",
        sa.Column(
            "consentement_communications",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
