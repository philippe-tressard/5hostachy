"""L'archivage unifié : une date de décision pour les idées, un délai pour le site.

Accompagne `app/utils/archivage.py` — la règle unique du point 2 de #515.

## 1. `idee.statut_change_le` — la colonne qui manquait

Six objets sur sept savaient dater leur passage à l'état terminal. L'idée, non :
elle ne portait que `cree_le`.

Sans cette colonne, la règle serait retombée sur la date de **création**, et
aurait archivé chaque idée à son anniversaire — qu'elle ait été décidée hier ou
jamais. La règle aurait été *vraie pour six objets et fausse pour un*, exactement
ce que le ticket annonçait. Ce n'est pas une relecture qui l'a vu, c'est le test
de concordance `test_les_champs_declares_existent_sur_le_modele`.

### Le remplissage : la date du déploiement, et non `cree_le`

⚠️ C'est la réponse au point 5 du ticket — *« combien d'objets basculeraient d'un
coup à l'archive le jour du déploiement ? Sept écrans qui se vident en même
temps, c'est un effet de bord visible par tous les résidents. »*

Trois remplissages étaient possibles, un seul est acceptable :

| Remplissage | Effet le jour du déploiement |
|---|---|
| `cree_le` | ❌ toutes les idées décidées et anciennes disparaissent **d'un coup** |
| `NULL` | ❌ aucune idée décidée ne s'archivera **jamais** — la règle serait inerte |
| **maintenant** | ✅ compte à rebours de 30 jours qui repart pour tout le monde |

Le troisième ne prétend pas connaître une date qu'on n'a pas : il pose
explicitement « la décision est réputée prise au déploiement ». C'est faux dans
le détail et honnête dans l'effet — personne ne perd de vue son idée du jour au
lendemain, et la règle entre en vigueur progressivement.

Seules les idées **en état terminal** sont remplies. Une idée « ouverte » n'a
pas de décision à dater : sa colonne reste `NULL`, et c'est juste.

## 2. `archivage_delai_jours` — le réglage unique

Il remplace la lecture de `archivage_delai_heures` (48 h) et de
`publie_visibilite_jours` (30 j), et rend enfin réglable le `ARCHIVAGE_JOURS =
30` qui était **codé en dur** dans `annonces.py` — donc invisible depuis
l'écran d'administration.

⚠️ Les deux anciennes clés ne sont PAS supprimées. Un retour arrière du code
doit retrouver sa configuration : les effacer rendrait le rollback destructeur.
Elles ne sont simplement plus lues (hormis en repli, cf. `seuil_archivage_jours`).

⚠️ `archivage_delai_heures` conserve un usage, et un seul : la **purge** des
actualités annulées (`PURGE_ANNULE_HEURES`), qui SUPPRIME des données. Elle n'a
jamais eu le même sens que l'archivage, et les confondre aurait retardé d'un
mois une suppression. Voir l'en-tête de `app/utils/archivage.py`.
"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0155"
down_revision = "0154"
branch_labels = None
depends_on = None

#: Les états qui closent une idée. Repris de `REGLES["idee"].statuts_terminaux` —
#: ⚠️ une copie, faute de pouvoir importer le code applicatif dans une migration
#: (elle doit rester exécutable même si le module bouge). Le test
#: `test_migration_0155_couvre_les_memes_statuts_terminaux` échoue si les deux
#: listes divergent.
STATUTS_TERMINAUX_IDEE = ("retenue", "realisee", "rejetee")


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "statut_change_le" not in _colonnes("idee"):
        op.add_column("idee", sa.Column("statut_change_le", sa.DateTime, nullable=True))

    #  🔴 Jamais de f-string dans un `op.execute` — `bindparams`, toujours.
    marqueurs = ", ".join(f":s{i}" for i in range(len(STATUTS_TERMINAUX_IDEE)))
    requete = text(
        "UPDATE idee SET statut_change_le = :maintenant "
        f"WHERE statut IN ({marqueurs}) AND statut_change_le IS NULL"
    ).bindparams(
        maintenant=datetime.utcnow(),
        **{f"s{i}": s for i, s in enumerate(STATUTS_TERMINAUX_IDEE)},
    )
    op.execute(requete)

    #  Le réglage unique. `INSERT` conditionnel : rejouer la migration ne doit
    #  pas écraser une valeur que l'administration aurait déjà ajustée.
    op.execute(
        text(
            "INSERT INTO config_site (cle, valeur) SELECT :cle, :valeur "
            "WHERE NOT EXISTS (SELECT 1 FROM config_site WHERE cle = :cle)"
        ).bindparams(cle="archivage_delai_jours", valeur="30")
    )


def downgrade() -> None:
    #  La colonne se retire ; le réglage reste. Supprimer `archivage_delai_jours`
    #  ferait perdre un choix d'administration au premier retour arrière, et
    #  personne ne saurait qu'il a existé.
    if "statut_change_le" in _colonnes("idee"):
        op.drop_column("idee", "statut_change_le")
