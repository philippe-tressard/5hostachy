"""Qui voit une publication, selon le PUBLIC visé.

L'autre moitié du ciblage d'une actualité : le périmètre dit *où*, le public dit
*à qui*. `test_perimetres_arbre.py` couvre le premier ; celui-ci couvre le second,
qui n'avait aucun test alors qu'il décide d'un accès.

Écrit en ajoutant le destinataire « bailleurs » (13/08/2026). « Copropriétaires »
couvre les DEUX statuts `copropriétaire_*` : rien ne permettait de s'adresser aux
bailleurs sans toucher les copropriétaires occupants, alors que tout un pan du
produit leur est propre (baux, remise d'objets, accès confiés aux locataires).
"""
import pytest

from app.models.core import Publication, StatutUtilisateur, Utilisateur
from app.utils.visibility import publication_visible


def _publication(public: str | None) -> Publication:
    #  `perimetre_cible` absent : ce fichier ne teste QUE le public.
    return Publication(titre="T", contenu="C", perimetre_cible=None, public_cible=public)


def _lecteur(statut: StatutUtilisateur, roles: str = "résident") -> Utilisateur:
    return Utilisateur(nom="X", prenom="Y", email=f"{statut.value}@test.fr",
                       statut=statut, roles_json=roles, actif=True)


TOUS = [
    StatutUtilisateur.copropriétaire_résident,
    StatutUtilisateur.copropriétaire_bailleur,
    StatutUtilisateur.locataire,
]


@pytest.mark.parametrize("statut", TOUS)
def test_residents_vise_tout_le_monde(statut):
    assert publication_visible(_publication('["résidents"]'), _lecteur(statut)) is True


@pytest.mark.parametrize("statut", TOUS)
def test_public_absent_ne_restreint_rien(statut):
    assert publication_visible(_publication(None), _lecteur(statut)) is True


def test_coproprietaires_englobe_resident_ET_bailleur():
    """Comportement existant, épinglé : « Copropriétaires » ne distingue pas.

    C'est précisément ce qui rendait « Bailleurs » nécessaire — et ce qui ne doit
    pas changer, sous peine de retirer un public à des publications déjà parues.
    """
    pub = _publication('["copropriétaires"]')
    assert publication_visible(pub, _lecteur(StatutUtilisateur.copropriétaire_résident)) is True
    assert publication_visible(pub, _lecteur(StatutUtilisateur.copropriétaire_bailleur)) is True
    assert publication_visible(pub, _lecteur(StatutUtilisateur.locataire)) is False


def test_bailleurs_ne_vise_QUE_les_bailleurs():
    """Le nouveau destinataire : les copropriétaires occupants ne le reçoivent pas."""
    pub = _publication('["bailleurs"]')
    assert publication_visible(pub, _lecteur(StatutUtilisateur.copropriétaire_bailleur)) is True
    assert publication_visible(pub, _lecteur(StatutUtilisateur.copropriétaire_résident)) is False
    assert publication_visible(pub, _lecteur(StatutUtilisateur.locataire)) is False


def test_locataires_ne_vise_que_les_locataires():
    pub = _publication('["locataires"]')
    assert publication_visible(pub, _lecteur(StatutUtilisateur.locataire)) is True
    assert publication_visible(pub, _lecteur(StatutUtilisateur.copropriétaire_résident)) is False


def test_conseil_syndical_n_est_visible_que_du_conseil():
    pub = _publication('["conseil_syndical"]')
    for statut in TOUS:
        assert publication_visible(pub, _lecteur(statut)) is False
    #  Le CS et l'admin sortent avant tout filtrage : ils voient tout.
    assert publication_visible(
        pub, _lecteur(StatutUtilisateur.copropriétaire_résident, "conseil_syndical")
    ) is True


def test_public_inconnu_n_accorde_rien():
    """Une valeur non reconnue refuse — et c'est ce qui rend l'ajout de « bailleurs » sûr.

    Avant ce lot, `["bailleurs"]` tombait sur ce refus : aucune publication
    existante ne peut donc avoir changé de public en gagnant ce destinataire.
    """
    pub = _publication('["martiens"]')
    for statut in TOUS:
        assert publication_visible(pub, _lecteur(statut)) is False


def test_plusieurs_publics_s_additionnent():
    pub = _publication('["bailleurs", "locataires"]')
    assert publication_visible(pub, _lecteur(StatutUtilisateur.copropriétaire_bailleur)) is True
    assert publication_visible(pub, _lecteur(StatutUtilisateur.locataire)) is True
    assert publication_visible(pub, _lecteur(StatutUtilisateur.copropriétaire_résident)) is False
