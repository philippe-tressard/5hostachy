"""Les deux autres questions « existe-t-il ? » de `utils/recuperer` (#1571).

`ou_404` répond pour un objet par son identifiant. Restaient deux 404 écrits à la
main, chacun en plusieurs exemplaires : le **fichier absent du disque** (« Fichier
introuvable sur le serveur », quatre fois) et la **ligne unique** d'une table de
réglage (« Copropriété non configurée », trois fois). Même question, même helper.
"""

import pytest
from fastapi import HTTPException

from app.models.copropriete import Copropriete
from app.utils.recuperer import fichier_ou_404, premier_ou_404


def test_fichier_present_rend_son_chemin(tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF")
    assert fichier_ou_404(str(f)) == str(f)


@pytest.mark.parametrize("chemin", [None, "", "/n/existe/pas.pdf"])
def test_fichier_absent_est_un_404_qui_le_nomme(chemin):
    with pytest.raises(HTTPException) as e:
        fichier_ou_404(chemin, "PDF")
    assert e.value.status_code == 404
    assert e.value.detail == "PDF introuvable sur le serveur"


def test_un_repertoire_n_est_pas_un_fichier(tmp_path):
    with pytest.raises(HTTPException) as e:
        fichier_ou_404(str(tmp_path))
    assert e.value.detail == "Fichier introuvable sur le serveur"


def test_premier_ou_404_dit_le_detail_donne(session):
    with pytest.raises(HTTPException) as e:
        premier_ou_404(session, Copropriete, "Copropriété non configurée")
    assert (e.value.status_code, e.value.detail) == (404, "Copropriété non configurée")


def test_premier_ou_404_rend_la_ligne(session):
    copro = Copropriete(nom="Résidence témoin", adresse="1 rue du Test")
    session.add(copro)
    session.commit()
    assert premier_ou_404(session, Copropriete, "x").id == copro.id


#  Deux questions de plus, écrites chacune en plusieurs exemplaires (08/10/2026) :
#  « cette clé figure-t-elle dans la table ? » (type de source d'affiche, section
#  de contrat) et « le résultat est-il là ? » (rapport à prolonger, source
#  d'affiche, cible d'un signalement).


def test_connu_ou_404_rend_la_valeur_de_la_cle():
    from app.utils.recuperer import connu_ou_404

    assert connu_ou_404({"syndic": ("syndic_contrat_id", 2)}, "syndic", "x") == (
        "syndic_contrat_id",
        2,
    )


def test_cle_inconnue_est_un_404_qui_dit_le_detail():
    from app.utils.recuperer import connu_ou_404

    with pytest.raises(HTTPException) as e:
        connu_ou_404({"syndic": 1}, "inconnue", "Section inconnue")
    assert (e.value.status_code, e.value.detail) == (404, "Section inconnue")


def test_present_ou_404_rend_la_valeur_meme_vide_mais_pas_none():
    from app.utils.recuperer import present_ou_404

    #  `is None`, jamais un test de vérité : un dict vide ou un 0 est un résultat.
    assert present_ou_404({}, "x") == {}
    assert present_ou_404(0, "x") == 0


def test_absent_est_un_404_qui_dit_le_detail():
    from app.utils.recuperer import present_ou_404

    with pytest.raises(HTTPException) as e:
        present_ou_404(None, "Contenu introuvable")
    assert (e.value.status_code, e.value.detail) == (404, "Contenu introuvable")
