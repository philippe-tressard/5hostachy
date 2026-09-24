"""Ce qu'un badge ouvre : la règle, et le fait que la MIGRATION dise la même chose.

## Pourquoi ce fichier (14/09/2026, #953)

`acces_deduit` décide ce qu'ouvre un badge quand personne ne l'a dit. La même
décision se prend à trois moments — la migration de reprise 0190, la création par
le conseil syndical, la résolution d'une ligne d'import.

⚠️ La migration ne peut PAS appeler la fonction : une migration ne doit pas
importer le code de l'application, qui change alors qu'elle non. Il y a donc
**deux écritures assumées** — une en Python, une en SQL — et c'est précisément le
genre de couple qui diverge en silence.

Ce fichier exerce les deux sur les **mêmes cas**, dans une base réelle. C'est le
motif de `lint:libelle-perimetre`, qui fait déjà cela entre le front et l'API.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine, select

#  ⚠️ L'import des modèles n'est pas décoratif : `SQLModel.metadata` ne connaît
#  que les tables des modules CHARGÉS. Sans lui, `create_all` ne crée rien et le
#  test échoue sur « no such table » — un cas zéro involontaire, mais un vrai.
from app.models.copropriete import Batiment, Copropriete, Lot
from app.models.core import StatutAcces, UserLot, Utilisateur, Vigik
from app.utils.acces_perimetre import acces_deduit, code_batiment

#: Les bâtiments des lots d'une personne, par NUMÉRO — la table de cas, partagée
#: par les deux écritures de la règle.
#:
#: ⚠️ L'attendu n'est PAS écrit ici : la règle porte sur `batiment_id`, que la
#: base attribue. L'écrire en dur reviendrait à supposer cette attribution —
#: exactement l'hypothèse qu'un test ne doit pas faire. Il se calcule depuis les
#: identifiants réellement créés (voir le test de la migration), et c'est ce qui
#: fait de ce fichier une COMPARAISON des deux écritures plutôt que deux
#: vérifications indépendantes.
CAS = [
    [2],
    [2, 2, 2],
    #  🔴 Le cas qui élargit la consigne : deux appartements, UN bâtiment.
    [7, 7],
    #  Deux bâtiments : on ne choisit pas.
    [2, 3],
    [],
    [None],
    #  Un parking (sans bâtiment) ne doit pas faire échouer la déduction.
    [2, None],
]


@pytest.fixture(autouse=True)
def sans_arbre():
    """🔴 Ces cas portent sur le REPLI, donc sur un arbre vide — et ça se pose.

    Depuis le 15/09/2026, `code_batiment` lit l'arbre avant de fabriquer `bat:3`
    (pour que la déduction et la liste d'accès autorisés parlent des mêmes
    codes). L'arbre est un **état de module**, partagé par toute la suite : un
    fichier exécuté avant celui-ci pouvait le laisser chargé, et ces tests-là
    échouaient alors sans rien avoir à se reprocher — c'est arrivé à l'écriture
    de `test_acces_choix.py`.

    Le vider ici rend la condition visible au lieu de la supposer.
    """
    from app.database import SessionLocal
    from app.models.perimetre import Perimetre
    from app.utils.perimetres import invalider_cache

    invalider_cache()
    try:
        with SessionLocal() as s:
            for ligne in sorted(s.exec(select(Perimetre)).all(), key=lambda n: -n.id):
                s.delete(ligne)
            s.commit()
    except OperationalError:
        pass  # la table n'existe pas encore : l'arbre est vide, c'est l'état voulu
    invalider_cache()
    yield
    invalider_cache()


@pytest.mark.parametrize(
    "batiments,attendu",
    [
        ([2], ["bat:2"]),
        ([2, 2, 2], ["bat:2"]),
        ([7, 7], ["bat:7"]),
        ([2, 3], None),
        ([], None),
        ([None], None),
        ([2, None], ["bat:2"]),
    ],
)
def test_la_regle_en_python(batiments, attendu):
    """Ici les entrées SONT des identifiants : la fonction n'en connaît pas d'autres."""
    assert acces_deduit(batiments) == attendu


def test_le_code_dun_batiment():
    assert code_batiment(4) == "bat:4"


@pytest.mark.parametrize("batiments_voulus", CAS, ids=lambda c: "-".join(map(str, c)) or "aucun")
def test_la_MIGRATION_dit_la_meme_chose(batiments_voulus):
    """La requête de la migration 0190, exercée sur une base réelle.

    ⚠️ La requête est recopiée ici, et c'est VOULU : la recopier sans l'exercer
    serait la duplication ; l'exercer sur les mêmes cas que la fonction en fait un
    contrôle. Si l'une des deux change, ce test le dit.
    """
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        #  ⚠️ Les fixtures passent par les MODÈLES : poser les lignes en SQL
        #  obligeait à connaître toutes les colonnes NOT NULL de quatre tables,
        #  et à les suivre. Seule la REQUÊTE reste en SQL — c'est elle qu'on
        #  éprouve, pas la façon de remplir la base.
        porteur = Utilisateur(email="a@b.fr", hashed_password="x", prenom="A", nom="B")
        copro = Copropriete(nom="C", adresse="1 rue de l'Essai")
        s.add(porteur)
        s.add(copro)
        s.commit()
        s.refresh(porteur)
        s.refresh(copro)

        batiments: dict[int, int] = {}
        #  Les identifiants tels que la BASE les a attribués : c'est sur eux que
        #  porte la règle, des deux côtés.
        ids_reels: list = []
        for rang, numero in enumerate(batiments_voulus, start=1):
            batiment_id = None
            if numero is not None:
                if numero not in batiments:
                    b = Batiment(copropriete_id=copro.id, numero=numero, nb_etages=5)
                    s.add(b)
                    s.commit()
                    s.refresh(b)
                    batiments[numero] = b.id
                batiment_id = batiments[numero]
            lot = Lot(batiment_id=batiment_id, numero=str(rang))
            ids_reels.append(batiment_id)
            s.add(lot)
            s.commit()
            s.refresh(lot)
            s.add(UserLot(user_id=porteur.id, lot_id=lot.id))
        badge = Vigik(code="A-1", user_id=porteur.id, statut=StatutAcces.actif)
        s.add(badge)
        s.commit()
        s.refresh(badge)

        #  ⚠️ La requête de 0190, mot pour mot.
        s.execute(
            text("""
            UPDATE vigik
               SET perimetre_cible = (
                   SELECT '["bat:' || MIN(lot.batiment_id) || '"]'
                     FROM user_lot
                     JOIN lot ON lot.id = user_lot.lot_id
                    WHERE user_lot.user_id = vigik.user_id
                      AND user_lot.actif = 1
                      AND lot.batiment_id IS NOT NULL
                   HAVING COUNT(DISTINCT lot.batiment_id) = 1
               )
             WHERE perimetre_cible IS NULL
               AND user_id IS NOT NULL
        """)
        )
        s.commit()
        obtenu = s.execute(
            text("SELECT perimetre_cible FROM vigik WHERE id = :i").bindparams(i=badge.id)
        ).scalar()

    import json

    attendu = acces_deduit(ids_reels)
    assert (json.loads(obtenu) if obtenu else None) == attendu, (
        f"la migration et `acces_deduit` divergent sur {batiments_voulus} "
        f"(identifiants {ids_reels}) : SQL={obtenu!r}, Python={attendu!r}"
    )
