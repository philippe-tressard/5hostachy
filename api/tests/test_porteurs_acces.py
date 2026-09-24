"""Un badge appartient au LOT — ses porteurs s'en déduisent (#1194, 23/09/2026).

## Les trois arbitrages que ces cas tiennent

1. les porteurs se déduisent du lot : les copropriétaires du lot, **le conjoint
   exactement comme l'autre**, qu'il ait été rattaché avant ou après le badge ;
2. un badge remis au locataire reste visible des copropriétaires du lot ;
3. supprimer un compte laisse ses badges au lot.

## Ce qu'ils remplacent

`test_acces_existants_apparies.py` éprouvait les trois « vecteurs » par lesquels
`_propagate_acces_pour_utilisateur` RECOPIAIT les badges du ménage dans les
tables d'attribution, à l'activation d'un compte. La recopie a disparu avec la
fonction : il n'y a plus rien à propager, les porteurs se lisent. Le premier
cas ci-dessous est celui que la recopie ratait — un conjoint rattaché au lot
par l'administration, et non par l'activation de son compte.

⚠️ Chaque règle a son **cas zéro** : un calcul qui rendrait tout le monde
porteur de tout passerait les cas positifs sans faillir.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.models.copropriete import Batiment
from app.models.core import StatutAcces, StatutImport, UserLot
from app.utils.lot_des_imports import trouveur_de_lot
from app.utils.porteurs_acces import acces_de, ids_detenteurs, porteurs
from app.utils.resolution_acces import exiger_code_libre, rattacher, rattacher_les_reconnues
from app.utils.types_acces import TELECOMMANDE, VIGIK
from tests.aides_badges import (  # noqa: F401 — `session` est une fixture
    TYPES,
    _badge,
    _bail,
    _compte,
    _copro_du_fichier,
    _ligne,
    _lier,
    _lot,
    session,
)


# ── 1. Le conjoint ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("type_acces", TYPES)
def test_le_conjoint_rattache_APRES_le_badge_le_porte_aussi(session, type_acces):
    """🔴 Le cas que la recopie ratait : aucun compte n'est activé ici."""
    lot = _lot(session, type_acces)
    anne, paul = _compte(session, "Anne"), _compte(session, "Paul")
    _lier(session, anne, lot)
    badge = _badge(session, type_acces, lot=lot)

    _lier(session, paul, lot)

    assert porteurs(session, badge) == {anne.id, paul.id}
    assert [b.id for b in acces_de(session, type_acces, paul.id)] == [badge.id]


@pytest.mark.parametrize("type_acces", TYPES)
def test_un_badge_SANS_detenteur_connu_est_porte_par_son_lot(session, type_acces):
    """Un lot sans compte au moment de l'import, puis un inscrit : il le voit."""
    lot = _lot(session, type_acces)
    badge = _badge(session, type_acces, lot=lot)
    assert porteurs(session, badge) == set()

    arrivant = _compte(session, "Arrivant")
    _lier(session, arrivant, lot)
    assert porteurs(session, badge) == {arrivant.id}


@pytest.mark.parametrize("type_acces", TYPES)
def test_cas_zero_le_voisin_ne_porte_rien(session, type_acces):
    lot, autre_lot = _lot(session, type_acces, "1"), _lot(session, type_acces, "2")
    anne, voisin = _compte(session, "Anne"), _compte(session, "Voisin")
    _lier(session, anne, lot)
    _lier(session, voisin, autre_lot)
    _badge(session, type_acces, lot=lot)

    assert acces_de(session, type_acces, voisin.id) == []


def test_un_lien_DESACTIVE_ne_porte_plus_rien(session):
    lot = _lot(session, VIGIK)
    ancien = _compte(session, "Ancien")
    session.add(UserLot(user_id=ancien.id, lot_id=lot.id, type_lien="propriétaire", actif=False))
    session.commit()
    _badge(session, VIGIK, lot=lot)

    assert acces_de(session, VIGIK, ancien.id) == []


# ── 2. Le locataire ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("type_acces", TYPES)
def test_remis_au_locataire_il_est_porte_par_lui_ET_les_coproprietaires(session, type_acces):
    lot = _lot(session, type_acces)
    bailleur, locataire = _compte(session, "Bailleur"), _compte(session, "Locataire")
    _lier(session, bailleur, lot, "bailleur")
    _lier(session, locataire, lot, "locataire")

    remis = _badge(session, type_acces, code="R", lot=lot, chez_locataire=True)
    garde = _badge(session, type_acces, code="G", lot=lot)

    assert porteurs(session, remis) == {bailleur.id, locataire.id}
    assert porteurs(session, garde) == {bailleur.id}, (
        "le locataire porte un badge qu'on ne lui a pas remis"
    )


# ── 3. Donnée ancienne : un badge sans lot ──────────────────────────────────


def test_sans_lot_le_detenteur_et_ceux_qui_partagent_son_lot(session):
    lot = _lot(session, VIGIK)
    anne, paul, etranger = (
        _compte(session, "Anne"),
        _compte(session, "Paul"),
        _compte(session, "Etr"),
    )
    _lier(session, anne, lot)
    _lier(session, paul, lot)
    badge = _badge(session, VIGIK, detenteur=anne)

    assert porteurs(session, badge) == {anne.id, paul.id}
    assert etranger.id not in porteurs(session, badge)


# ── 4. « A un badge » ───────────────────────────────────────────────────────


def test_a_un_badge_ne_compte_pas_les_badges_PERDUS(session):
    lot = _lot(session, TELECOMMANDE)
    anne = _compte(session, "Anne")
    _lier(session, anne, lot)
    _badge(session, TELECOMMANDE, lot=lot, statut=StatutAcces.perdu)
    assert ids_detenteurs(session, TELECOMMANDE) == set()

    _badge(session, TELECOMMANDE, code="C2", lot=lot)
    assert ids_detenteurs(session, TELECOMMANDE) == {anne.id}


# ── 5. Rattacher une ligne d'import ─────────────────────────────────────────


@pytest.mark.parametrize("type_acces", TYPES)
def test_une_ligne_se_rattache_SANS_aucun_compte(session, type_acces):
    """🔴 Elle rendait 422 « Le propriétaire doit être lié avant de résoudre »."""
    lot = _lot(session, type_acces)
    ligne = _ligne(session, type_acces, lot=lot)

    objet = rattacher(type_acces, ligne, session)

    assert ligne.statut == StatutImport.resolu
    assert objet.lot_id == lot.id and objet.user_id is None


@pytest.mark.parametrize("type_acces", TYPES)
def test_cas_zero_sans_lot_rien_ne_se_rattache(session, type_acces):
    ligne = _ligne(session, type_acces)
    with pytest.raises(HTTPException) as refus:
        rattacher(type_acces, ligne, session)
    assert refus.value.status_code == 422


@pytest.mark.parametrize("type_acces", TYPES)
def test_un_code_REPETE_dans_le_fichier_ne_fait_qu_un_badge(session, type_acces):
    lot = _lot(session, type_acces)
    a = rattacher(type_acces, _ligne(session, type_acces, lot=lot, code="X"), session)
    b = rattacher(type_acces, _ligne(session, type_acces, lot=lot, code="X"), session)
    assert a.id == b.id
    assert len(session.exec(select(type_acces.modele)).all()) == 1


@pytest.mark.parametrize("type_acces", TYPES)
def test_le_rattachement_en_masse_ne_prend_que_les_lignes_au_lot_connu(session, type_acces):
    lot = _lot(session, type_acces)
    _ligne(session, type_acces, lot=lot, code="A")
    _ligne(session, type_acces, lot=lot, code="B")
    _ligne(session, type_acces, code="C")  # lot inconnu

    assert rattacher_les_reconnues(type_acces, session) == {"rattachees": 2, "restantes": 1}


@pytest.mark.parametrize("type_acces", TYPES)
def test_delier_le_lot_d_une_ligne_resolue_delie_le_badge(session, type_acces):
    """Le serveur ignorait `null` : une liaison posée par erreur ne se défaisait plus."""
    from app.routers.acces import socle_imports
    from app.routers.acces.socle_imports import PatchImportBody

    lot = _lot(session, type_acces)
    ligne = _ligne(session, type_acces, lot=lot)
    objet = rattacher(type_acces, ligne, session)
    session.commit()

    socle_imports.patch(type_acces, ligne.id, PatchImportBody(lot_id=None), session)

    assert session.get(type_acces.modele, objet.id).lot_id is None


@pytest.mark.parametrize("type_acces", TYPES)
def test_un_code_deja_porte_par_un_AUTRE_badge_est_refuse(session, type_acces):
    badge = _badge(session, type_acces, code="Z")
    exiger_code_libre(session, type_acces, "Z", sauf_id=badge.id)  # le sien : permis
    with pytest.raises(HTTPException) as refus:
        exiger_code_libre(session, type_acces, "Z")
    assert refus.value.status_code == 400


# ── 6. Retrouver le lot sans compte ─────────────────────────────────────────


def test_le_vigik_retrouve_son_lot_par_batiment_et_appartement(session):
    bat = Batiment(numero="2", copropriete_id=1)
    session.add(bat)
    session.commit()
    lot = _lot(session, VIGIK, "312", batiment_id=bat.id)
    ligne = _ligne(session, VIGIK, batiment_raw="2", appartement_raw="312")

    assert trouveur_de_lot(VIGIK, session)(ligne) is True
    assert ligne.lot_id == lot.id


def test_la_telecommande_retrouve_le_parking_de_son_coproprietaire(session):
    parking = _lot(session, TELECOMMANDE, "450")
    _copro_du_fichier(session, "M. MARTIN-LEROY Jean", parking)
    ligne = _ligne(session, TELECOMMANDE, nom="MARTIN LEROY")

    assert trouveur_de_lot(TELECOMMANDE, session)(ligne) is True
    assert ligne.lot_id == parking.id


def test_plusieurs_parkings_le_premier_est_retenu(session):
    """Arbitré le 23/09/2026 : « si plusieurs parkings, prendre le 1er »."""
    p10, p9 = _lot(session, TELECOMMANDE, "10"), _lot(session, TELECOMMANDE, "9")
    _copro_du_fichier(session, "DURAND Paul", p10, p9)
    ligne = _ligne(session, TELECOMMANDE, nom="DURAND", code="T1")
    assert trouveur_de_lot(TELECOMMANDE, session)(ligne) is True
    assert ligne.lot_id == p9.id, "« 9 » vient avant « 10 »"


def test_le_nom_complet_departage_des_homonymes(session):
    _copro_du_fichier(session, "DUBREUIL FRANCOIS", _lot(session, TELECOMMANDE, "451"))
    sylvie = _lot(session, TELECOMMANDE, "452")
    _copro_du_fichier(session, "DUBREUIL Sylvie", sylvie)
    ligne = _ligne(session, TELECOMMANDE, nom="DUBREUIL SYLVIE", code="T3")
    assert trouveur_de_lot(TELECOMMANDE, session)(ligne) is True
    assert ligne.lot_id == sylvie.id


def test_cas_zero_deux_homonymes_ne_rattachent_rien(session):
    """On ne devine pas la personne : un mauvais lot montrerait le code aux voisins."""
    _copro_du_fichier(session, "BERNARD Luc", _lot(session, TELECOMMANDE, "453"))
    _copro_du_fichier(session, "BERNARD Anne", _lot(session, TELECOMMANDE, "454"))
    homonymes = _ligne(session, TELECOMMANDE, nom="BERNARD", code="T2")
    assert trouveur_de_lot(TELECOMMANDE, session)(homonymes) is False
    assert homonymes.lot_id is None


# ── 7. Supprimer un compte ──────────────────────────────────────────────────


@pytest.mark.parametrize("type_acces", TYPES)
def test_supprimer_un_compte_LAISSE_ses_badges_au_lot(session, type_acces):
    from app.routers.admin.utilisateurs import supprimer_utilisateur

    lot = _lot(session, type_acces)
    anne, admin = _compte(session, "Anne"), _compte(session, "Admin")
    _lier(session, anne, lot)
    badge = _badge(session, type_acces, lot=lot, detenteur=anne)

    supprimer_utilisateur(anne.id, session=session, admin=admin)

    reste = session.get(type_acces.modele, badge.id)
    assert reste is not None, "le badge a disparu avec le compte"
    assert reste.lot_id == lot.id and reste.user_id is None


# ── 8. Le porteur, pour un geste ────────────────────────────────────────────


def test_le_conjoint_peut_signaler_la_perte_du_badge_du_menage(session):
    from app.auth.appartenance import exiger_acces_du_porteur

    lot = _lot(session, VIGIK)
    anne, paul, voisin = _compte(session, "Anne"), _compte(session, "Paul"), _compte(session, "V")
    _lier(session, anne, lot)
    _lier(session, paul, lot)
    badge = _badge(session, VIGIK, lot=lot, detenteur=anne)

    assert exiger_acces_du_porteur(session, VIGIK, badge.id, paul).id == badge.id
    with pytest.raises(HTTPException) as refus:
        exiger_acces_du_porteur(session, VIGIK, badge.id, voisin)
    assert refus.value.status_code == 404
