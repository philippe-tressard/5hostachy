"""Un accès déjà en base est rattaché au nouvel arrivant — par ses TROIS vecteurs.

## 🔴 Ce que ces tests couvrent, et qui ne l'était par rien (18/09/2026, #779)

`_propagate_acces_pour_utilisateur` décide, à l'activation d'un compte, quels badges déjà
enregistrés appartiennent aussi à cette personne. Elle les cherche de trois
façons — par le lot, par le copropriétaire, par la table de liaison — et c'est
la troisième qui compte le plus : elle rattrape un accès que **personne ne
détient en direct**.

Quatre-vingts lignes, écrites **deux fois** : une moitié télécommande, une
moitié vigik. Et **aucun test ne l'appelait** — la suite couvrait l'appariement
des NOMS, pas l'attribution des accès. Une divergence entre les deux moitiés
n'aurait produit aucun signal : un accès manquant dans la liste d'un résident ne
lève rien et ne se plaint pas.

C'est le défaut que `utils/types_acces.py` raconte déjà pour le téléversement —
là, les jumelles avaient bel et bien divergé sur le `lot_id`. Ici, elles ne
l'avaient pas encore fait ; ces cas sont ce qui empêche qu'elles le puissent.

## Pourquoi chaque cas porte les DEUX types

Par paramétrage, jamais par recopie : un troisième accès entrerait dans ces cas
sans qu'on écrive une ligne. C'est le même parti que `test_declarer_acces.py`.

⚠️ Le **cas zéro** est le dernier test : sans lot actif, la fonction ne rattache
rien. Sans lui, un appariement qui rattacherait tout à tout le monde passerait
ces cas avec les honneurs.
"""
from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.copropriete import Lot
from app.models.core import StatutAcces, StatutImport, UserLot, Utilisateur
from app.utils.auto_match_service import (
    _auto_match_acces,
    _propagate_acces_pour_utilisateur,
)
from app.utils.types_acces import TELECOMMANDE, VIGIK

#: Les deux types, pour paramétrer chaque cas. `ids` rend le verdict lisible.
TYPES = [pytest.param(TELECOMMANDE, id="telecommande"), pytest.param(VIGIK, id="vigik")]


@pytest.fixture()
def session():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        yield s


def _utilisateur(session, nom: str) -> Utilisateur:
    u = Utilisateur(email=f"{nom}@exemple.fr", hashed_password="x", prenom="P", nom=nom)
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _lot(session, numero: str) -> Lot:
    lot = Lot(numero=numero, type_lot="appartement")
    session.add(lot)
    session.commit()
    session.refresh(lot)
    return lot


def _rattacher(session, user: Utilisateur, lot: Lot, type_lien: str = "propriétaire") -> None:
    session.add(UserLot(user_id=user.id, lot_id=lot.id, type_lien=type_lien, actif=True))
    session.commit()


def _acces(session, type_acces, *, code: str, porteur: Utilisateur, lot_id=None):
    """Un badge du type demandé — le descripteur donne la table, le test ne la nomme pas.

    ⚠️ `user_id` est NOT NULL sur les deux tables : un accès a TOUJOURS un
    porteur enregistré. C'est pourquoi le troisième vecteur ne se met pas en
    scène avec un badge « que personne ne détient », mais avec un badge dont le
    porteur n'est PAS copropriétaire du lot de l'arrivant — le seul lien qui
    reste est alors la table d'attribution.
    """
    user_id = porteur.id
    objet = type_acces.modele(
        code=code, lot_id=lot_id, user_id=user_id, statut=StatutAcces.actif
    )
    session.add(objet)
    session.commit()
    session.refresh(objet)
    return objet


def _attributions(session, type_acces, user_id: int) -> set[int]:
    """Les identifiants d'accès attribués à cet utilisateur, pour ce type."""
    liens = session.exec(
        select(type_acces.modele_attribution).where(
            type_acces.modele_attribution.user_id == user_id
        )
    ).all()
    return {getattr(lien, type_acces.colonne_attribution) for lien in liens}


def _compte(resultat, type_acces) -> int:
    """Le couple rendu garde son ordre historique : télécommandes, puis vigiks."""
    tc, vigik = resultat
    return tc if type_acces is TELECOMMANDE else vigik


@pytest.mark.parametrize("type_acces", TYPES)
def test_vecteur_1_un_acces_pose_sur_son_lot_lui_est_rattache(session, type_acces):
    arrivant = _utilisateur(session, "Arrivant")
    lot = _lot(session, "A1")
    _rattacher(session, arrivant, lot)
    ancien = _utilisateur(session, "Ancien")
    badge = _acces(session, type_acces, code="C1", porteur=ancien, lot_id=lot.id)

    resultat = _propagate_acces_pour_utilisateur(arrivant, session)
    session.commit()

    assert _attributions(session, type_acces, arrivant.id) == {badge.id}
    assert _compte(resultat, type_acces) == 1


@pytest.mark.parametrize("type_acces", TYPES)
def test_vecteur_2_un_acces_d_un_coproprietaire_sans_lot_renseigne(session, type_acces):
    """Le badge n'est posé sur aucun lot : il est trouvé par son PORTEUR."""
    arrivant = _utilisateur(session, "Arrivant")
    conjoint = _utilisateur(session, "Conjoint")
    lot = _lot(session, "A2")
    _rattacher(session, arrivant, lot)
    _rattacher(session, conjoint, lot)
    badge = _acces(session, type_acces, code="C2", porteur=conjoint, lot_id=None)

    _propagate_acces_pour_utilisateur(arrivant, session)
    session.commit()

    assert badge.id in _attributions(session, type_acces, arrivant.id)


@pytest.mark.parametrize("type_acces", TYPES)
def test_vecteur_3_un_acces_relie_par_la_SEULE_table_d_attribution(session, type_acces):
    """🔴 Le vecteur qui justifie les deux autres.

    Le badge n'a pas de lot, et son porteur enregistré n'est copropriétaire de
    rien ici : le seul lien avec le copropriétaire passe par la table
    d'attribution. Sans ce vecteur, il resterait invisible à l'arrivant — et
    c'est le cas qu'une moitié recopiée aurait pu perdre en silence.
    """
    arrivant = _utilisateur(session, "Arrivant")
    conjoint = _utilisateur(session, "Conjoint")
    lot = _lot(session, "A3")
    _rattacher(session, arrivant, lot)
    _rattacher(session, conjoint, lot)
    etranger = _utilisateur(session, "Etranger")
    badge = _acces(session, type_acces, code="C3", porteur=etranger, lot_id=None)
    type_acces.attribuer(session, user_id=conjoint.id, acces_id=badge.id)
    session.commit()

    _propagate_acces_pour_utilisateur(arrivant, session)
    session.commit()

    assert badge.id in _attributions(session, type_acces, arrivant.id)


@pytest.mark.parametrize("type_acces", TYPES)
def test_un_acces_deja_attribue_n_est_pas_compte_deux_fois(session, type_acces):
    """Les trois vecteurs se recoupent : c'est la règle, pas un accident."""
    arrivant = _utilisateur(session, "Arrivant")
    lot = _lot(session, "A4")
    _rattacher(session, arrivant, lot)
    badge = _acces(session, type_acces, code="C4", porteur=arrivant, lot_id=lot.id)
    type_acces.attribuer(session, user_id=arrivant.id, acces_id=badge.id)
    session.commit()

    resultat = _propagate_acces_pour_utilisateur(arrivant, session)
    session.commit()

    assert _attributions(session, type_acces, arrivant.id) == {badge.id}
    assert _compte(resultat, type_acces) == 0, "une attribution existante a été recomptée"


def test_les_deux_types_sont_rattaches_dans_le_MEME_appel(session):
    """Sinon un appel pourrait n'en traiter qu'un, et le couple rendu mentirait."""
    arrivant = _utilisateur(session, "Arrivant")
    lot = _lot(session, "A5")
    _rattacher(session, arrivant, lot)
    ancien = _utilisateur(session, "Ancien")
    tc = _acces(session, TELECOMMANDE, code="T5", porteur=ancien, lot_id=lot.id)
    vig = _acces(session, VIGIK, code="V5", porteur=ancien, lot_id=lot.id)

    nb_tc, nb_vigik = _propagate_acces_pour_utilisateur(arrivant, session)
    session.commit()

    assert (nb_tc, nb_vigik) == (1, 1), "le couple rendu ne décrit pas les deux types"
    assert _attributions(session, TELECOMMANDE, arrivant.id) == {tc.id}
    assert _attributions(session, VIGIK, arrivant.id) == {vig.id}


def test_cas_zero_sans_lot_actif_rien_n_est_rattache(session):
    """🔴 La preuve que ces cas mesurent quelque chose.

    Un appariement qui rattacherait tout à tout le monde passerait les cas
    ci-dessus sans faillir. Ici l'arrivant n'a aucun lot : la fonction doit
    rendre `(0, 0)` et ne rien créer, alors que deux badges existent.
    """
    arrivant = _utilisateur(session, "Arrivant")
    autre = _utilisateur(session, "Autre")
    lot = _lot(session, "A6")
    _rattacher(session, autre, lot)
    _acces(session, TELECOMMANDE, code="T6", porteur=autre, lot_id=lot.id)
    _acces(session, VIGIK, code="V6", porteur=autre, lot_id=lot.id)

    assert _propagate_acces_pour_utilisateur(arrivant, session) == (0, 0)
    session.commit()

    assert _attributions(session, TELECOMMANDE, arrivant.id) == set()
    assert _attributions(session, VIGIK, arrivant.id) == set()


# ── Résolution automatique d'une ligne d'import ─────────────────────────────
#
#  🔴 Ce bloc REMPLACE un contrôle statique de `test_appariement_acces.py`, qui
#  cherchait la chaîne « session.add(tc) » dans le fichier source et se disait
#  contraint : *« la logique est trop couplée à la base pour être exercée ici »*.
#  Elle ne l'est pas — une base en mémoire suffit, et c'est ce que ces cas font.
#  Un contrôle qui lit le TEXTE d'une fonction casse au premier renommage de
#  variable et ne dit rien du comportement (`standards/04` §14).


def _ligne_import(session, type_acces, *, nom: str, reference: str, chez_locataire=False,
                  locataire=None, lot_id=None):
    """Une ligne de staging du bon type — le descripteur nomme la colonne."""
    ligne = type_acces.modele_import(
        nom_proprietaire=nom,
        statut=StatutImport.en_attente,
        lot_id=lot_id,
        chez_locataire=chez_locataire,
        nom_locataire=locataire,
    )
    setattr(ligne, type_acces.colonne_code_import, reference)
    session.add(ligne)
    session.commit()
    session.refresh(ligne)
    return ligne


@pytest.mark.parametrize("type_acces", TYPES)
def test_l_auto_resolution_cree_le_badge_sans_revue(session, type_acces):
    """Elle ne propose pas : elle crée l'accès et marque l'import résolu.

    C'est ce qui rend l'appariement large conséquent — le filet de sécurité est
    la revue du conseil syndical, pas une validation préalable.
    """
    arrivant = _utilisateur(session, "Tressard")
    ligne = _ligne_import(session, type_acces, nom="Tressard", reference="REF-1")

    crees = _auto_match_acces(arrivant, session, type_acces)
    session.commit()
    session.refresh(ligne)

    assert crees == 1
    assert ligne.statut == StatutImport.resolu
    objet = session.get(type_acces.modele, getattr(ligne, type_acces.colonne_import))
    assert objet is not None, "l'import est résolu mais aucun accès n'a été créé"
    assert objet.code == "REF-1"
    assert objet.user_id == arrivant.id


@pytest.mark.parametrize("type_acces", TYPES)
def test_un_acces_remis_au_locataire_est_marque_CHEZ_LUI(session, type_acces):
    """🔴 Le défaut que la mise en commun corrige (18/09/2026).

    La branche vigik de l'appariement automatique ne reportait PAS
    `chez_locataire` sur l'objet créé, quand la branche télécommande le faisait —
    exactement le défaut que #847 avait corrigé côté écran, survivant ici parce
    que le code était ailleurs.

    Il décide : `routers/bailleur/acces.py` ne propose au transfert que les accès
    `not chez_locataire`. Un badge remis au locataire et marqué « chez le
    propriétaire » se reproposait au locataire SUIVANT, alors qu'il était déjà
    dans la poche du locataire en place.
    """
    locataire = _utilisateur(session, "Locataire")
    ligne = _ligne_import(
        session,
        type_acces,
        nom="Proprio",
        reference="REF-2",
        chez_locataire=True,
        locataire="Locataire",
    )
    #  Le propriétaire est déjà lié : c'est le locataire qui vient de s'inscrire.
    proprio = _utilisateur(session, "Proprio")
    ligne.user_proprietaire_id = proprio.id
    session.add(ligne)
    session.commit()

    _auto_match_acces(locataire, session, type_acces)
    session.commit()
    session.refresh(ligne)

    objet = session.get(type_acces.modele, getattr(ligne, type_acces.colonne_import))
    assert objet is not None, "l'accès n'a pas été créé"
    assert objet.user_id == locataire.id, "le détenteur n'est pas celui qui l'a en main"
    assert objet.chez_locataire is True, (
        "`chez_locataire` n'est pas reporté sur l'accès : il se reproposera au "
        "transfert vers le locataire suivant."
    )


@pytest.mark.parametrize("type_acces", TYPES)
def test_cas_zero_un_nom_qui_ne_correspond_pas_ne_resout_rien(session, type_acces):
    """Sans lui, un appariement qui dirait oui à tout passerait les cas ci-dessus."""
    arrivant = _utilisateur(session, "Tressard")
    ligne = _ligne_import(session, type_acces, nom="Personne Autre", reference="REF-3")

    assert _auto_match_acces(arrivant, session, type_acces) == 0
    session.commit()
    session.refresh(ligne)
    assert ligne.statut == StatutImport.en_attente
    assert getattr(ligne, type_acces.colonne_import) is None
