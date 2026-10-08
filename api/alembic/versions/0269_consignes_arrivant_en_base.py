"""Les consignes de la fiche arrivant passent en base, avec le texte de la résidence (#1727).

Jusqu'ici, `utils/fiche_arrivant.py` les écrivait en dur : jours de collecte des
encombrants par rue, nom du syndic. Elles vivent désormais dans `config_site`
(clé `consignes_arrivant`), éditables par le conseil syndical ; le seed n'en
porte qu'un gabarit générique (`seed/consignes_arrivant.GABARIT`).

Cette migration recopie, pour la résidence en service, le texte qu'imprimait la
fiche jusqu'ici — la fiche ne change donc pas d'un mot à la MEP. Deux formes
seulement changent, celles du nouveau format (TEXTE échappé au rendu,
`utils/consignes_arrivant`) :

- `<strong>…</strong>` devient `**…**` ;
- le nom du syndic devient `{syndic}`, lu dans le contrat au rendu — il
  périmerait sinon au premier changement de syndic.

Le texte ne vit qu'ICI, pas dans `api/app` : c'est une donnée de l'instance
(`test_consignes_arrivant.py` refuse les noms de rue et de syndic dans le code).

Une base qui porte déjà la clé n'est pas touchée : on n'écrit pas par-dessus une
saisie. Le retour arrière ne retire la ligne que si elle est restée intacte.

Revision ID: 0269
Revises: 0268
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0269"
down_revision = "0268"
branch_labels = None
depends_on = None

CLE = "consignes_arrivant"

CONSIGNES_RESIDENCE = [
    {
        "titre": "📦 1. Emménagement / déménagement",
        "contenu": (
            "Prévenez le conseil syndical du bâtiment concerné, **1 semaine à l'avance**, "
            "pour toute arrivée ou départ afin de permettre à ce dernier d'effectuer un état des lieux "
            "des parties communes avant et après.\n"
            "Pensez à demander l'autorisation à la mairie pour le stationnement des camions devant la copropriété.\n"
            "Protégez au mieux les parties communes lors des déménagements (ascenseur, escaliers, halls) "
            "et évacuez les cartons et encombrants rapidement, sans les laisser dans les couloirs ou les locaux à poubelles.\n"
            "Demander au syndic {syndic} de changer les noms sur la boîte aux lettres et l'interphone."
        ),
    },
    {
        "titre": "🗑 2. Sortie des poubelles et tri",
        "contenu": (
            "Déchets encombrants : **ne pas les laisser dans les parties communes**. "
            "Apportez-les à la déchèterie ou en collecte sur le trottoir :\n"
            "**Boulevard Hostachy** : Collecte des encombrants à partir de 6h, "
            "le 3ème samedi de chaque mois. Sortir la veille après 19h.\n"
            "**Rue Maurice Berteaux** : Collecte des encombrants à partir de 6h, "
            "le 4ème samedi de chaque mois. Sortir la veille après 19h."
        ),
    },
    {
        "titre": "🏢 3. Parties communes",
        "contenu": (
            "Gardez les couloirs, escaliers et halls propres. "
            "Ne laissez rien traîner : poubelles, poussettes, vélos, cartons, etc.\n"
            "Respectez la tranquillité des lieux : évitez de faire du bruit, surtout entre 22h et 7h.\n"
            "Ne donnez pas de code ou de clé aux personnes non autorisées."
        ),
    },
]

#: La valeur écrite — la même chaîne à l'aller et au retour.
VALEUR = json.dumps(CONSIGNES_RESIDENCE, ensure_ascii=False)


def upgrade():
    op.get_bind().execute(
        sa.text(
            "INSERT INTO config_site (cle, valeur) SELECT :cle, :valeur "
            "WHERE NOT EXISTS (SELECT 1 FROM config_site WHERE cle = :cle)"
        ).bindparams(cle=CLE, valeur=VALEUR)
    )


def downgrade():
    op.get_bind().execute(
        sa.text("DELETE FROM config_site WHERE cle = :cle AND valeur = :valeur").bindparams(
            cle=CLE, valeur=VALEUR
        )
    )
