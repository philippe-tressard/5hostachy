"""Les GESTES sur un badge qui appartient au lot (#1194) — bail, commande, parc.

Découpé de `test_porteurs_acces.py` le 23/09/2026 (plus de 500 lignes) : ce
fichier-là tient la RÈGLE (qui porte, le rattachement), celui-ci les gestes qui
l'appliquent. Aides communes : `tests/aides_badges.py`.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException  # noqa: F401
from sqlmodel import select

from app.models.copropriete import Batiment
from app.models.core import LotImport, StatutImport
from app.utils.lot_des_imports import trouveur_de_lot
from app.utils.porteurs_acces import acces_de, porteurs
from app.utils.resolution_acces import rattacher, rattacher_les_reconnues
from app.utils.types_acces import TELECOMMANDE, VIGIK
from tests.aides_badges import (  # noqa: F401 — `session` est une fixture
    TYPES, _badge, _bail, _compte, _copro_du_fichier, _ligne, _lier, _lot, session,
)


# ── 9. Le bail : un seul sens de « chez le locataire » (V3) ─────────────────


def test_remettre_par_le_bail_met_le_badge_dans_la_main_du_locataire(session):
    """🔴 Le bail laissait `user_id` au bailleur, l'import le donnait au locataire."""
    from app.routers.bailleur.acces import TransfertAccesIn, recuperer_acces, transferer_acces

    lot = _lot(session, VIGIK)
    bailleur, locataire = _compte(session, "Bailleur"), _compte(session, "Locataire")
    _lier(session, bailleur, lot, "bailleur")
    badge = _badge(session, VIGIK, lot=lot, detenteur=bailleur)
    bail = _bail(session, lot, bailleur, locataire)

    transferer_acces(bail.id, TransfertAccesIn(vigik_ids=[badge.id]), user=bailleur, session=session)
    session.refresh(badge)
    assert (badge.chez_locataire, badge.user_id) == (True, locataire.id)
    #  Le locataire du BAIL le porte, sans lien `user_lot` ; le bailleur le voit toujours.
    assert porteurs(session, badge) == {bailleur.id, locataire.id}

    recuperer_acces(bail.id, TransfertAccesIn(), user=bailleur, session=session)
    session.refresh(badge)
    assert (badge.chez_locataire, badge.user_id, badge.bail_id) == (False, bailleur.id, None)


def test_cas_zero_le_badge_d_un_autre_lot_ne_se_transfere_pas(session):
    from app.routers.bailleur.acces import TransfertAccesIn, transferer_acces

    lot, autre = _lot(session, VIGIK, "1"), _lot(session, VIGIK, "2")
    bailleur, locataire = _compte(session, "Bailleur"), _compte(session, "Locataire")
    _lier(session, bailleur, lot, "bailleur")
    etranger = _badge(session, VIGIK, code="E", lot=autre)
    bail = _bail(session, lot, bailleur, locataire)

    assert transferer_acces(bail.id, TransfertAccesIn(vigik_ids=[etranger.id]),
                            user=bailleur, session=session) == []
    session.refresh(etranger)
    assert etranger.chez_locataire is False


# ── 10. Une commande acceptée pose ses badges (V3) ──────────────────────────

def test_une_commande_acceptee_avec_ses_codes_pose_les_badges_sur_le_lot(session):
    """🔴 Elle n'en créait aucun : le badge remis n'existait nulle part."""
    from fastapi import BackgroundTasks

    from app.models.core import CommandeAcces
    from app.routers.admin.acces import CommandeAction, traiter_commande

    lot = _lot(session, VIGIK)
    anne, paul, cs = _compte(session, "Anne"), _compte(session, "Paul"), _compte(session, "Cs")
    _lier(session, anne, lot)
    _lier(session, paul, lot)
    cmd = CommandeAcces(user_id=anne.id, lot_id=lot.id, type="vigik")
    session.add(cmd)
    session.commit()

    traiter_commande(cmd.id, CommandeAction(action="accepter", codes=["N-1", " N-2 ", ""]),
                     BackgroundTasks(), session=session, admin=cs)

    badges = session.exec(select(VIGIK.modele)).all()
    assert sorted(b.code for b in badges) == ["N-1", "N-2"]
    assert all(b.lot_id == lot.id for b in badges)
    assert len(acces_de(session, VIGIK, paul.id)) == 2, "le conjoint ne voit pas les badges commandés"


def test_cas_zero_une_commande_acceptee_sans_code_ne_cree_rien(session):
    from fastapi import BackgroundTasks

    from app.models.core import CommandeAcces
    from app.routers.admin.acces import CommandeAction, traiter_commande

    lot = _lot(session, VIGIK)
    anne, cs = _compte(session, "Anne"), _compte(session, "Cs")
    cmd = CommandeAcces(user_id=anne.id, lot_id=lot.id, type="vigik")
    session.add(cmd)
    session.commit()

    traiter_commande(cmd.id, CommandeAction(action="accepter"), BackgroundTasks(), session=session, admin=cs)
    assert session.exec(select(VIGIK.modele)).first() is None


# ── 11. Retours du 23/09/2026 : PARIS, STOCK, l'accès, le nom affiché ──────

def test_un_nom_de_famille_seul_designe_le_bon_copropriétaire(session):
    """« PARIS » est un propriétaire, pas la BANQUE NATIONALE DE PARIS."""
    _copro_du_fichier(session, "BANQUE NATIONALE DE PARIS", _lot(session, TELECOMMANDE, "460"))
    francis = _lot(session, TELECOMMANDE, "461")
    _copro_du_fichier(session, "PARIS FRANCIS", francis)
    ligne = _ligne(session, TELECOMMANDE, nom="PARIS", code="T4")
    assert trouveur_de_lot(TELECOMMANDE, session)(ligne) is True
    assert ligne.lot_id == francis.id


def test_une_ligne_STOCK_entre_au_parc_sans_lot(session):
    ligne = _ligne(session, TELECOMMANDE, nom="STOCK", code="S-1")
    assert rattacher_les_reconnues(TELECOMMANDE, session)["rattachees"] == 1
    objet = session.get(TELECOMMANDE.modele, ligne.telecommande_id)
    assert objet.lot_id is None and objet.user_id is None


def test_le_rattachement_deduit_ce_qu_ouvre_le_vigik(session):
    """🔴 Il ne le posait pas : colonne « Accès » vide sur tout le parc importé."""
    bat = Batiment(numero="3", copropriete_id=1)
    session.add(bat)
    session.commit()
    lot = _lot(session, VIGIK, "110", batiment_id=bat.id)
    objet = rattacher(VIGIK, _ligne(session, VIGIK, lot=lot, code="V-9"), session)
    assert objet.perimetre_cible == f'["bat:{bat.id}"]'


def test_sans_compte_le_parc_nomme_le_copropriétaire_du_fichier(session):
    from app.utils.porteurs_acces import noms_des_porteurs

    lot = _lot(session, VIGIK, "205")
    session.add(LotImport(numero="205", type_raw="AP", nom_coproprietaire="DURAND Paul", lot_id=lot.id))
    session.commit()
    badge = _badge(session, VIGIK, lot=lot)
    stock = _badge(session, VIGIK, code="ST")
    noms = noms_des_porteurs(session, [badge, stock])
    assert noms == {badge.id: "DURAND Paul (sans compte)", stock.id: "En stock"}


# ── 12. Le parc complète l'import ; supprimer une ligne erronée (23/09) ────

@pytest.mark.parametrize("type_acces", TYPES)
def test_un_badge_saisi_au_parc_rattache_sa_ligne_d_import(session, type_acces):
    """« Est-ce que cette vue enrichie peut compléter les imports ? »"""
    from app.routers.acces.parc import AccesAdminBody, creer_acces_admin, modifier_acces_admin

    lot = _lot(session, type_acces)
    cs = _compte(session, "Cs")
    ligne = _ligne(session, type_acces, code="P-1")
    autre = _ligne(session, type_acces, code="P-2")

    cree = creer_acces_admin(AccesAdminBody(code="P-1", lot_id=lot.id), type_acces=type_acces,
                             session=session, user=cs)
    session.refresh(ligne)
    assert (ligne.statut, ligne.lot_id) == (StatutImport.resolu, lot.id)
    assert getattr(ligne, type_acces.colonne_import) == cree.id

    #  Le code corrigé au parc : l'ancienne ligne est libérée, la bonne rattachée.
    modifier_acces_admin(cree.id, AccesAdminBody(code="P-2"), type_acces=type_acces,
                         session=session, user=cs)
    session.refresh(ligne)
    session.refresh(autre)
    assert getattr(ligne, type_acces.colonne_import) is None and ligne.statut == StatutImport.en_attente
    assert getattr(autre, type_acces.colonne_import) == cree.id and autre.statut == StatutImport.resolu


def test_cas_zero_une_ligne_ignoree_le_reste(session):
    from app.routers.acces.parc import AccesAdminBody, creer_acces_admin

    lot = _lot(session, VIGIK)
    ligne = _ligne(session, VIGIK, code="I-1")
    ligne.statut = StatutImport.ignore
    session.add(ligne)
    session.commit()
    creer_acces_admin(AccesAdminBody(code="I-1", lot_id=lot.id), type_acces=VIGIK,
                      session=session, user=_compte(session, "Cs"))
    session.refresh(ligne)
    assert ligne.statut == StatutImport.ignore


def test_supprimer_une_ligne_d_import_laisse_son_badge(session):
    from app.routers.acces.imports_vigik import supprimer_ligne_import_vigik

    lot = _lot(session, VIGIK)
    ligne = _ligne(session, VIGIK, lot=lot, code="D-1")
    objet = rattacher(VIGIK, ligne, session)
    session.commit()

    supprimer_ligne_import_vigik(ligne.id, session=session)
    assert session.get(VIGIK.modele_import, ligne.id) is None
    assert session.get(VIGIK.modele, objet.id) is not None
