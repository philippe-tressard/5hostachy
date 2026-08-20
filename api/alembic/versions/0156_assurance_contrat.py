"""L'assurance de la copropriété devient un CONTRAT, avec un prestataire.

Accompagne #490.

## Le fait

`Admin → Fiche copropriété` portait trois champs en TEXTE LIBRE :

| Champ | Ce que c'était réellement |
|---|---|
| `assurance_compagnie` | **un prestataire** — la table `prestataire` existe |
| `assurance_numero_police` | un numéro de contrat |
| `assurance_echeance` | l'échéance d'un contrat |

Or le projet a déjà `Prestataire` **et** `ContratEntretien`, avec leurs
échéances, leurs documents et leurs relances. L'assurance de la copropriété est
très exactement un contrat avec un prestataire — elle était saisie ici comme
trois chaînes qui ne renvoyaient à rien.

Conséquences concrètes, avant cette migration :

  * **le même assureur pouvait exister deux fois** — une fois en texte dans la
    fiche, une fois comme prestataire s'il avait été créé — et rien ne disait
    que c'était le même ;
  * l'échéance **ne remontait nulle part**, alors que les contrats ont déjà leur
    mécanique de relance ;
  * on ne pouvait pas y attacher l'attestation, qui est pourtant le document
    qu'on cherche le jour où on en a besoin.

## Ce que fait cette migration

Pour chaque copropriété dont `assurance_compagnie` est renseigné : elle
**retrouve ou crée** le prestataire portant ce nom, puis crée un
`contrat_entretien` de type `assurance` qui reprend le numéro et l'échéance.

⚠️ **Idempotente** : elle ne fait rien si un contrat d'assurance existe déjà pour
cette copropriété. Il n'y a qu'une copropriété aujourd'hui — donc une ligne à
reprendre — mais le geste devait être écrit et rejouable (#490).

⚠️ Le prestataire est retrouvé par son **nom exact**. Une casse ou un espace
différent créera un doublon : c'est le prix d'une reprise depuis du texte libre,
et c'est exactement ce que ce lot supprime pour l'avenir. Le cas se corrige à la
main, une fois, sur une base qui compte une seule ligne.

## 🔴 Les trois colonnes ne sont PAS supprimées

Elles restent en place, vides d'usage. Deux raisons :

1. **Un retour arrière doit rester possible.** Le code d'avant les lit ; les
   effacer rendrait le rollback destructeur, ce que `standards/06` interdit.
2. Une colonne inutilisée ne coûte rien ; une donnée perdue ne se retrouve pas.

Leur suppression fera l'objet d'une migration séparée, une fois cette version
éprouvée en production.

## `type_equipement = "assurance"` — une tension de nommage, assumée

`TypeEquipement` désigne des équipements (ascenseur, VMC, toiture). Une assurance
n'en est pas un. Mais la NOTION portée par `ContratEntretien` est bien la même :
un contrat avec un prestataire, un numéro, une échéance, un document. C'est le
champ qui est mal nommé — il désigne en fait la *catégorie du contrat* — et non
la ligne qu'on y ajoute.

Le renommer toucherait quinze appels pour un gain cosmétique ; on préfère écrire
la tension ici plutôt que d'inventer une seconde table de contrats, ce qui
recréerait exactement le doublon que ce lot supprime.
"""
from datetime import date

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0156"
down_revision = "0155"
branch_labels = None
depends_on = None

#: La catégorie du contrat créé. Doit correspondre à `TypeEquipement.assurance`.
#: `api/tests/test_assurance_contrat.py` échoue si les deux divergent.
TYPE_ASSURANCE = "assurance"

#: Le libellé du contrat repris. Il s'affiche tel quel dans la liste des
#: contrats — d'où une phrase lisible plutôt qu'un code.
LIBELLE = "Assurance de la copropriété"

#: La spécialité du prestataire créé, s'il faut le créer. `specialite` est
#: obligatoire sur `prestataire` : la laisser vide ferait échouer l'insertion.
SPECIALITE = "Assurance"


def upgrade() -> None:
    bind = op.get_bind()
    copros = bind.execute(
        text(
            "SELECT id, assurance_compagnie, assurance_numero_police, assurance_echeance "
            "FROM copropriete "
            "WHERE assurance_compagnie IS NOT NULL AND TRIM(assurance_compagnie) <> ''"
        )
    ).fetchall()

    for copro_id, compagnie, numero, echeance in copros:
        #  Déjà repris ? On ne touche à rien — l'idempotence tient à ce test.
        deja = bind.execute(
            text(
                "SELECT 1 FROM contrat_entretien "
                "WHERE copropriete_id = :c AND type_equipement = :t LIMIT 1"
            ).bindparams(c=copro_id, t=TYPE_ASSURANCE)
        ).first()
        if deja:
            continue

        nom = (compagnie or "").strip()
        presta = bind.execute(
            text("SELECT id FROM prestataire WHERE nom = :n LIMIT 1").bindparams(n=nom)
        ).first()
        if presta:
            presta_id = presta[0]
        else:
            bind.execute(
                text(
                    "INSERT INTO prestataire (nom, specialite, type_prestataire, actif, cree_le) "
                    #  ⚠️ `contrat_recurrent`, valeur RÉELLE de `TypePrestataire` :
                    #  j'avais d'abord écrit « contrat », qui n'existe pas. Une
                    #  migration ne valide rien à l'insertion sous SQLite — la
                    #  ligne serait passée, et l'énumération l'aurait refusée à
                    #  la LECTURE, des semaines plus tard.
                    "VALUES (:n, :s, 'contrat_recurrent', 1, :d)"
                ).bindparams(n=nom, s=SPECIALITE, d=date.today().isoformat())
            )
            presta_id = bind.execute(
                text("SELECT id FROM prestataire WHERE nom = :n LIMIT 1").bindparams(n=nom)
            ).first()[0]

        #  ⚠️ L'échéance devient `prochaine_visite`, et c'est le point : c'est ce
        #  champ que la mécanique de relance des contrats regarde. La ranger
        #  ailleurs aurait reconduit le défaut — « l'échéance ne remonte nulle
        #  part » — sous une autre forme.
        bind.execute(
            text(
                "INSERT INTO contrat_entretien "
                "(copropriete_id, prestataire_id, type_equipement, libelle, numero_contrat, "
                " date_debut, prochaine_visite, actif) "
                "VALUES (:c, :p, :t, :l, :n, :d, :e, 1)"
            ).bindparams(
                c=copro_id,
                p=presta_id,
                t=TYPE_ASSURANCE,
                l=LIBELLE,
                n=(numero or "").strip() or None,
                d=date.today().isoformat(),
                e=echeance,
            )
        )


def downgrade() -> None:
    #  On retire les contrats d'assurance créés ici — les trois colonnes
    #  d'origine n'ayant jamais été effacées, la fiche retrouve son état
    #  antérieur sans perte.
    #
    #  ⚠️ Le prestataire créé au passage n'est PAS supprimé : il a pu servir
    #  ailleurs entre-temps (un devis, un autre contrat), et supprimer une entité
    #  référencée est plus grave que laisser une ligne en trop.
    op.execute(
        text("DELETE FROM contrat_entretien WHERE type_equipement = :t AND libelle = :l")
        .bindparams(t=TYPE_ASSURANCE, l=LIBELLE)
    )


#  Pour que le test de concordance puisse le lire sans exécuter la migration.
_ = sa
