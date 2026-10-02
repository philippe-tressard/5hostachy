"""Les badges qu'un bail fait passer du bailleur au locataire — et leur retour (#1569, #1194).

`utils/acces_bail` n'était nommé par aucun test : ses trois gestes passent par les
routeurs du bailleur, qui le cachent. Ce fichier les tient en direct, pour les DEUX
types d'accès (vigik, télécommande) — le module les parcourt par `TYPES_ACCES`, et
un troisième type y entrerait sans qu'on y pense :

1. `confies` — les badges confiés par CE bail, jamais ceux d'un autre bail ni ceux
   restés chez le bailleur ;
2. `remettre` — « chez le locataire » : la case, le bail, et le détenteur (le
   locataire du bail — ou personne de connu s'il n'a pas de compte) ;
3. `rendre_au_bailleur` — tous, ou seulement le choix ; un type absent du choix n'en
   rend aucun ; le détenteur redevient le bailleur ; **sans commit**.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models.core import LocationBail
from app.utils.acces_bail import confies, remettre, rendre_au_bailleur
from app.utils.types_acces import TYPES_ACCES
from tests.aides_badges import TYPES, _badge, _bail, _compte, _lot


@pytest.fixture()
def scene(session):
    bailleur = _compte(session, "Bailleur")
    locataire = _compte(session, "Locataire")
    return bailleur, locataire


def _bail_sans_compte(session, lot, bailleur) -> LocationBail:
    bail = LocationBail(
        lot_id=lot.id,
        bailleur_id=bailleur.id,
        locataire_nom="Sans compte",
        date_entree=date(2026, 9, 1),
    )
    session.add(bail)
    session.commit()
    session.refresh(bail)
    return bail


# ── confies ─────────────────────────────────────────────────────────────────


def test_sans_aucun_badge_rien_n_est_confie(session, scene):
    bailleur, locataire = scene
    bail = _bail(session, _lot(session, TYPES_ACCES["vigik"]), bailleur, locataire)

    assert confies(session, bail.id) == []


def test_confies_rend_les_badges_des_deux_types_avec_leur_cle(session, scene):
    bailleur, locataire = scene
    lot_v = _lot(session, TYPES_ACCES["vigik"], numero="12")
    bail = _bail(session, lot_v, bailleur, locataire)
    objets = {}
    for i, type_acces in enumerate(TYPES_ACCES.values()):
        o = _badge(session, type_acces, code=f"CONF-{i}", lot=lot_v)
        remettre(o, bail)
        session.add(o)
        objets[type_acces.cle] = o
    session.commit()

    trouves = confies(session, bail.id)

    assert sorted(cle for cle, _ in trouves) == sorted(TYPES_ACCES)
    assert {cle: o.id for cle, o in trouves} == {cle: o.id for cle, o in objets.items()}


@pytest.mark.parametrize("type_acces", TYPES)
def test_un_badge_reste_chez_le_bailleur_n_est_pas_confie(session, scene, type_acces):
    bailleur, locataire = scene
    lot = _lot(session, type_acces)
    bail = _bail(session, lot, bailleur, locataire)
    badge = _badge(session, type_acces, code="RESTE", lot=lot, detenteur=bailleur)
    badge.bail_id = bail.id  # rattaché au bail, mais pas remis
    session.add(badge)
    session.commit()

    assert confies(session, bail.id) == []


@pytest.mark.parametrize("type_acces", TYPES)
def test_un_badge_confie_par_un_autre_bail_n_est_pas_compte(session, scene, type_acces):
    bailleur, locataire = scene
    lot = _lot(session, type_acces)
    bail = _bail(session, lot, bailleur, locataire)
    autre = _bail(session, _lot(session, type_acces, numero="99"), bailleur, locataire)
    badge = _badge(session, type_acces, code="AUTRE", lot=lot)
    remettre(badge, autre)
    session.add(badge)
    session.commit()

    assert confies(session, bail.id) == []
    assert [o.id for _, o in confies(session, autre.id)] == [badge.id]


# ── remettre ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("type_acces", TYPES)
def test_remettre_pose_la_case_le_bail_et_le_detenteur(session, scene, type_acces):
    bailleur, locataire = scene
    lot = _lot(session, type_acces)
    bail = _bail(session, lot, bailleur, locataire)
    badge = _badge(session, type_acces, code="R1", lot=lot, detenteur=bailleur)

    remettre(badge, bail)

    assert badge.chez_locataire is True
    assert badge.bail_id == bail.id
    assert badge.user_id == locataire.id


def test_remettre_a_un_locataire_sans_compte_ne_laisse_pas_le_bailleur_detenteur(session, scene):
    """Le badge est chez le locataire, qu'on connaisse son compte ou non (#1194)."""
    bailleur, _ = scene
    type_acces = TYPES_ACCES["vigik"]
    lot = _lot(session, type_acces)
    bail = _bail_sans_compte(session, lot, bailleur)
    badge = _badge(session, type_acces, code="R2", lot=lot, detenteur=bailleur)

    remettre(badge, bail)

    assert badge.chez_locataire is True
    assert badge.user_id is None, "le bailleur n'a plus le badge en main"


# ── rendre_au_bailleur ──────────────────────────────────────────────────────


@pytest.fixture()
def deux_badges_confies(session, scene):
    bailleur, locataire = scene
    lot = _lot(session, TYPES_ACCES["vigik"])
    bail = _bail(session, lot, bailleur, locataire)
    badges = {}
    for cle, type_acces in TYPES_ACCES.items():
        o = _badge(session, type_acces, code=f"RET-{cle}", lot=lot, detenteur=bailleur)
        remettre(o, bail)
        session.add(o)
        badges[cle] = o
    session.commit()
    return bailleur, bail, badges


def test_rendre_sans_choix_rend_tous_les_badges_du_bail(session, deux_badges_confies):
    bailleur, bail, badges = deux_badges_confies

    rendus = rendre_au_bailleur(session, bail)
    session.commit()

    assert sorted(cle for cle, _ in rendus) == sorted(TYPES_ACCES)
    for objet in badges.values():
        session.refresh(objet)
        assert (objet.chez_locataire, objet.bail_id, objet.user_id) == (False, None, bailleur.id)
    assert confies(session, bail.id) == []


def test_rendre_un_choix_ne_rend_que_ces_identifiants(session, deux_badges_confies):
    bailleur, bail, badges = deux_badges_confies

    rendus = rendre_au_bailleur(session, bail, {"vigik": [badges["vigik"].id]})
    session.commit()

    assert [(cle, o.id) for cle, o in rendus] == [("vigik", badges["vigik"].id)]
    assert [cle for cle, _ in confies(session, bail.id)] == ["telecommande"]


def test_un_type_absent_du_choix_n_en_rend_aucun(session, deux_badges_confies):
    _, bail, _ = deux_badges_confies

    assert rendre_au_bailleur(session, bail, {"vigik": []}) == []
    assert rendre_au_bailleur(session, bail, {}) == []
    assert len(confies(session, bail.id)) == 2


def test_un_identifiant_d_un_autre_bail_ne_rend_rien(session, deux_badges_confies, scene):
    """Le choix désigne des identifiants ; ils doivent être ceux de CE bail."""
    bailleur, locataire = scene
    _, bail, badges = deux_badges_confies
    autre_lot = _lot(session, TYPES_ACCES["vigik"], numero="77")
    autre_bail = _bail(session, autre_lot, bailleur, locataire)

    assert rendre_au_bailleur(session, autre_bail, {"vigik": [badges["vigik"].id]}) == []
    assert len(confies(session, bail.id)) == 2


def test_rendre_ne_valide_pas_la_transaction(session, deux_badges_confies):
    """L'appelant décide de sa transaction : un rollback défait le retour."""
    _, bail, badges = deux_badges_confies

    rendre_au_bailleur(session, bail)
    session.rollback()

    assert len(confies(session, bail.id)) == 2
    for objet in badges.values():
        session.refresh(objet)
        assert objet.chez_locataire is True


def test_rendre_un_bail_sans_badge_ne_rend_rien(session, scene):
    bailleur, locataire = scene
    bail = _bail(session, _lot(session, TYPES_ACCES["vigik"]), bailleur, locataire)

    assert rendre_au_bailleur(session, bail) == []
    assert rendre_au_bailleur(session, bail, {"vigik": [1]}) == []
