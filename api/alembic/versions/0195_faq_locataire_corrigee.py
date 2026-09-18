"""La réponse FAQ sur le locataire ne décrivait plus le produit (18/09/2026).

## Ce que la réponse affirmait, et ce que le code dit

Semée par la migration 0035, elle annonçait :

    « Dans 5Hostachy, il dispose d'un accès limité : actualités, calendrier,
      demandes, FAQ et consultation de ses accès (badges). Il ne peut pas gérer
      les lots ni commander des accès directement. »

Deux affirmations sont devenues fausses, et la seconde peut coûter un geste à
un résident qui s'y fie :

| Affirmation | Ce que le code fait |
|---|---|
| « il ne peut pas commander des accès directement » | `POST /acces/commandes` n'exige qu'une session et un **lien avec le lot**, quel qu'en soit le type. L'écran « Mes lots & accès » porte les boutons « + Nouvel accès » et « + Déclarer un accès ». |
| la liste des cinq rubriques | `Nav.svelte` ne réserve que **quatre** entrées — Prestataires et Espace CS au conseil syndical, Délégations aux aidants, Admin aux administrateurs. Tout le reste s'ouvre à qui porte le rôle `résident`. |

Et le cadre était inexact : il n'existe pas de rôle « locataire ». Les rôles sont
`propriétaire`, `résident`, `externe`, `conseil_syndical`, `admin`. Être
locataire est un **type de lien avec un lot**, pas un niveau d'accès — la
différence tient à ce à quoi la personne est rattachée, pas à des rubriques
retirées.

Reste exact, et conservé : il ne gère pas les lots, et la gestion locative vise
les copropriétaires et leurs mandataires.

## 🔴 Pourquoi une migration, et pas une correction à l'écran

La réponse a été **semée** : elle vit en base, et le texte du code ne la décrit
plus (`standards/06` §4). Corriger la migration 0035 ne changerait donc rien à
une installation en service, et l'écran d'administration ne laisse pas de trace
relisible. Une migration corrige la donnée **là où elle est**, avec sa raison, et
le fait sur toutes les installations.

⚠️ Elle ne réécrit QUE le texte semé, comparé mot pour mot. Un administrateur
qui aurait déjà reformulé cette réponse garde la sienne : une migration de
données n'écrase pas un travail humain qu'elle ne sait pas relire.

Revision ID: 0195
Revises: 0194
Create Date: 2026-09-18
"""
import sqlalchemy as sa
from alembic import op

revision = "0195"
down_revision = "0194"
branch_labels = None
depends_on = None

QUESTION = "Qu'est-ce qu'un locataire dans l'application ?"

#: Le texte SEMÉ par la 0035, à l'espace près. La comparaison est exacte : c'est
#: elle qui distingue « personne n'y a touché » de « quelqu'un l'a réécrit ».
ANCIENNE = (
    "Un locataire est une personne qui loue un lot appartenant à un copropriétaire. "
    "Dans 5Hostachy, il dispose d'un accès limité : actualités, calendrier, demandes, "
    "FAQ et consultation de ses accès (badges). Il ne peut pas gérer les lots ni "
    "commander des accès directement."
)

NOUVELLE = (
    "Un locataire est une personne qui loue un lot appartenant à un copropriétaire. "
    "Ce n'est pas un rôle à part : il dispose du rôle **résident**, et accède donc aux "
    "mêmes rubriques que les autres résidents — actualités, calendrier, demandes, "
    "communauté, annuaire, résidence, FAQ. Depuis **Mes lots & accès**, il consulte ses "
    "badges et télécommandes, peut en commander un nouveau et déclarer ceux qu'il détient "
    "déjà. En revanche, il ne gère pas les lots, et la gestion locative est réservée aux "
    "copropriétaires et à leurs mandataires."
)


def _remplacer(conn, avant: str, apres: str) -> int:
    """Remplace la réponse si — et seulement si — elle est encore celle semée."""
    resultat = conn.execute(
        sa.text(
            "UPDATE faq_item SET reponse = :apres, mis_a_jour_le = CURRENT_TIMESTAMP "
            "WHERE question = :question AND reponse = :avant"
        ).bindparams(question=QUESTION, avant=avant, apres=apres)
    )
    return resultat.rowcount or 0


def upgrade() -> None:
    conn = op.get_bind()
    _remplacer(conn, ANCIENNE, NOUVELLE)


def downgrade() -> None:
    #  Symétrique, et sous la même garde : on ne remet l'ancien texte que si le
    #  nouveau est intact. Un retour en arrière ne doit pas défaire une
    #  reformulation faite entre-temps.
    conn = op.get_bind()
    _remplacer(conn, NOUVELLE, ANCIENNE)
