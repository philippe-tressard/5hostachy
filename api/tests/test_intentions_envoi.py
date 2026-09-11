"""Un champ de mise à jour est une COLONNE, ou une intention déclarée.

## L'incident (12/09/2026, 500 en production)

`PATCH /publications/25` rendait **500** : `ValueError: "Publication" object has
no field "envoyer_auteur"`. Corriger une actualité déjà publiée — le geste le plus
banal de l'écran — échouait dès que l'écran envoyait la case « m'envoyer une
copie ».

La cause n'est pas une faute de frappe : `envoyer_auteur` est une **intention
d'envoi**, vraie pour la requête qui la porte et jamais stockée. Le schéma le
disait, en toutes lettres, juste au-dessus du champ :

    #  Voir `PublicationCreate` : la case ne se stocke pas, c'est une intention
    #  d'envoi. À la mise à jour elle vaut pour CET enregistrement.
    envoyer_auteur: Optional[bool] = None

Mais la boucle qui applique le corps au modèle, elle, ne le savait pas :

    for k, v in data.items():
        setattr(pub, k, v)

Elle suppose que **tout champ du corps est une colonne**. Le commentaire était au
bon endroit et ne protégeait rien — c'est le motif que ce dépôt connaît le mieux :
*le seul fichier qui parlait du sujet disait que le problème n'existait pas.*

## Ce que ce test vérifie

Pour chaque couple (schéma de mise à jour, modèle), tout champ du schéma est soit
une colonne du modèle, soit **déclaré** dans les intentions que le routeur écarte
avant la boucle.

⚠️ Il vérifie les deux sens. Un champ déclaré comme intention alors qu'il EST une
colonne serait tout aussi grave : la boucle ne l'écrirait plus, et la correction
partirait sans effet ni message — un défaut silencieux, donc pire.
"""
from __future__ import annotations

import pytest

from app.models.core import Publication
from app.routers.publications.crud import INTENTIONS_HORS_MODELE
from app.schemas_publications import PublicationUpdate

#: (nom lisible, schéma de mise à jour, modèle, intentions déclarées par le
#: routeur qui l'applique).
#:
#: 🔴 Ajouter une ligne ici quand un nouveau routeur applique un corps à un
#: modèle par une boucle. La table est courte exprès : elle ne couvre que les
#: routes qui affectent en masse, les seules exposées à ce défaut.
COUPLES = [
    ("publications", PublicationUpdate, Publication, INTENTIONS_HORS_MODELE),
]


@pytest.mark.parametrize("nom, schema, modele, intentions", COUPLES)
def test_tout_champ_est_une_colonne_ou_une_intention_declaree(nom, schema, modele, intentions):
    colonnes = set(modele.model_fields)
    orphelins = [
        champ
        for champ in schema.model_fields
        if champ not in colonnes and champ not in intentions
    ]
    assert not orphelins, (
        f"{nom} : ces champs ne sont ni des colonnes ni des intentions déclarées — "
        f"la boucle `setattr` lèvera dessus : {orphelins}"
    )


@pytest.mark.parametrize("nom, schema, modele, intentions", COUPLES)
def test_aucune_intention_ne_masque_une_VRAIE_colonne(nom, schema, modele, intentions):
    """⚠️ L'erreur symétrique, et elle est pire : silencieuse. Déclarer comme
    intention un champ qui EST une colonne le ferait sortir du lot avant la
    boucle — la correction partirait sans effet, et sans message."""
    colonnes = set(modele.model_fields)
    usurpateurs = [champ for champ in intentions if champ in colonnes]
    assert not usurpateurs, (
        f"{nom} : ces champs sont de VRAIES colonnes, les écarter les rendrait "
        f"non modifiables en silence : {usurpateurs}"
    )


@pytest.mark.parametrize("nom, schema, modele, intentions", COUPLES)
def test_chaque_intention_declaree_existe_dans_le_schema(nom, schema, modele, intentions):
    """Une intention qui ne correspond à aucun champ est une entrée périmée : elle
    ne protège plus rien, et masque la prochaine."""
    inconnues = [champ for champ in intentions if champ not in schema.model_fields]
    assert not inconnues, f"{nom} : intentions déclarées mais absentes du schéma : {inconnues}"


def test_le_routeur_ECARTE_vraiment_les_intentions():
    """🔴 Déclarer la liste ne suffit pas : le fait qui compte est qu'elle soit
    appliquée AVANT la boucle. Sans cette vérification, retirer la boucle de
    nettoyage laisserait les trois tests ci-dessus au vert."""
    import inspect

    from app.routers.publications import crud

    source = inspect.getsource(crud.update_publication)
    pop = source.index("INTENTIONS_HORS_MODELE")
    boucle = source.index("for k, v in data.items():")
    assert pop < boucle, "les intentions doivent être retirées AVANT la boucle d'affectation"


def test_le_cas_zero_le_couple_fautif_est_bien_MESURE():
    """⚠️ `standards/04` §2. Si `PublicationUpdate` cessait d'exposer des champs —
    import cassé, schéma vidé —, les tests ci-dessus passeraient en ne comparant
    rien."""
    assert len(PublicationUpdate.model_fields) >= 10
    assert len(Publication.model_fields) >= 10
    assert "envoyer_auteur" in PublicationUpdate.model_fields
