"""Une ligne « résolue » SANS lot n'échappe plus au rapprochement (#1338, 26/09/2026).

## Le constat

Signalé à l'écran : *« pourquoi dans l'import TC le rattachement des lots par
rapport au nom n'est pas possible, si plusieurs parkings — par exemple GARCIA »*.

Sur la sauvegarde du 26/09, les dix lignes « GARCIA » étaient au statut
**résolu**, sans lot : résolues sous l'ancien modèle (par personne), avant que le
badge n'appartienne au lot (#1194). Le fichier des lots connaissait « GARCIA
ALAIN » et ses deux parkings — la règle par le nom l'aurait trouvé. Mais le
rapprochement ne lisait que les lignes en attente : ces lignes étaient sautées.
Soixante télécommandes dans ce cas, dont trente-trois sans lot au parc non plus.

## La règle

« Rapprocher » reprend d'abord les lignes résolues sans lot :

- leur badge a un lot au parc → la ligne le recopie, et reste résolue ;
- il n'en a pas → la ligne repasse à rattacher ; la règle du nom lui propose son
  lot, et « Rattacher » reste le geste de l'administration.
"""

from __future__ import annotations

from app.models.core import StatutImport
from app.routers.acces.socle_imports import auto_match
from app.utils.resolution_acces import rattacher_les_reconnues
from app.utils.types_acces import TELECOMMANDE
from tests.aides_badges import (  # noqa: F401 — `session` est une fixture
    _badge,
    _copro_du_fichier,
    _ligne,
    _lot,
    session,
)


def _resolue(session, ligne, badge):
    ligne.statut = StatutImport.resolu
    setattr(ligne, TELECOMMANDE.colonne_import, badge.id)
    session.add(ligne)
    session.commit()
    return ligne


def test_garcia_resolu_sans_lot_retrouve_son_premier_parking(session):
    """Le cas signalé : résolu, sans lot, deux parkings au fichier des lots."""
    p479, p446 = _lot(session, TELECOMMANDE, "479"), _lot(session, TELECOMMANDE, "446")
    _copro_du_fichier(session, "GARCIA ALAIN", p479, p446)
    badge = _badge(session, TELECOMMANDE, code="1106736742")
    ligne = _resolue(session, _ligne(session, TELECOMMANDE, nom="GARCIA", code="1106736742"), badge)

    auto_match(TELECOMMANDE, session)
    session.refresh(ligne)
    assert ligne.lot_id == p446.id, "le premier parking, « 446 » avant « 479 »"
    assert ligne.statut != StatutImport.resolu, "elle repasse à rattacher"

    #  Le rattachement reste le geste de l'administration — et il pose le lot
    #  sur le badge EXISTANT, sans en créer un second.
    assert rattacher_les_reconnues(TELECOMMANDE, session)["rattachees"] == 1
    session.refresh(badge)
    session.refresh(ligne)
    assert badge.lot_id == p446.id
    assert ligne.statut == StatutImport.resolu


def test_un_badge_deja_au_lot_recopie_son_lot_sur_la_ligne(session):
    parking = _lot(session, TELECOMMANDE, "12")
    badge = _badge(session, TELECOMMANDE, code="T9", lot=parking)
    ligne = _resolue(session, _ligne(session, TELECOMMANDE, nom="INCONNU", code="T9"), badge)

    auto_match(TELECOMMANDE, session)
    session.refresh(ligne)
    assert ligne.lot_id == parking.id
    assert ligne.statut == StatutImport.resolu, "déjà juste au parc : rien à refaire"


def test_cas_zero_une_ligne_resolue_AVEC_lot_ne_bouge_pas(session):
    ancien, autre = _lot(session, TELECOMMANDE, "20"), _lot(session, TELECOMMANDE, "21")
    _copro_du_fichier(session, "DUPONT Jean", autre)
    badge = _badge(session, TELECOMMANDE, code="T1", lot=ancien)
    ligne = _ligne(session, TELECOMMANDE, nom="DUPONT Jean", code="T1", lot=ancien)
    _resolue(session, ligne, badge)

    auto_match(TELECOMMANDE, session)
    session.refresh(ligne)
    assert (ligne.lot_id, ligne.statut) == (ancien.id, StatutImport.resolu)


def test_cas_zero_un_nom_ambigu_reste_a_preciser(session):
    """Deux homonymes : on ne devine pas — un mauvais lot montrerait le code aux voisins."""
    _copro_du_fichier(session, "BERNARD Luc", _lot(session, TELECOMMANDE, "30"))
    _copro_du_fichier(session, "BERNARD Anne", _lot(session, TELECOMMANDE, "31"))
    badge = _badge(session, TELECOMMANDE, code="T2")
    ligne = _resolue(session, _ligne(session, TELECOMMANDE, nom="BERNARD", code="T2"), badge)

    auto_match(TELECOMMANDE, session)
    session.refresh(ligne)
    assert ligne.lot_id is None
    assert ligne.statut != StatutImport.resolu, "elle apparaît « lot à préciser »"


def test_un_meme_nom_sous_deux_numeros_de_compte_est_un_seul_coproprietaire(session):
    """FERMONT, 26/09/2026 : « FERMONT MARC ; CATHERINE » sous 408944 ET 408946.

    Deux numéros de compte, un seul ménage : la règle y voyait deux
    copropriétaires et refusait de choisir. Un nom COMPLET identique désigne les
    mêmes personnes ; le premier parking de l'ensemble est retenu."""
    from app.models.core import LotImport

    appart, p12, p7 = (
        _lot(session, TELECOMMANDE, "200"),
        _lot(session, TELECOMMANDE, "12"),
        _lot(session, TELECOMMANDE, "7"),
    )
    appart.type = "appartement"
    session.add(appart)
    for no, lot in (("408944", appart), ("408944", p12), ("408946", p7)):
        session.add(
            LotImport(
                numero=lot.numero,
                type_raw="PS",
                no_coproprietaire=no,
                nom_coproprietaire="FERMONT MARC ; CATHERINE",
                lot_id=lot.id,
            )
        )
    session.commit()
    ligne = _ligne(session, TELECOMMANDE, nom="FERMONT", code="T7")

    auto_match(TELECOMMANDE, session)
    session.refresh(ligne)
    assert ligne.lot_id == p7.id, "le premier parking des deux comptes, « 7 » avant « 12 »"
