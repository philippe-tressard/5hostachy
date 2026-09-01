"""Ouvrir les actualités à toute la copropriété n'accorde AUCUN accès nouveau.

## La contrainte, telle qu'elle a été posée

Le 14/08/2026, en ouvrant les actualités aux autres bâtiments (#339) :

> « Les règles genre bailleurs (hors propriétaire) comme une agence immobilière,
> si elles n'avaient pas de visibilité, elles n'auront toujours pas de
> visibilité. »

C'est la propriété que ce fichier verrouille. L'ouverture porte sur l'axe
**bâtiment** ; elle ne touche pas l'axe **public**.

## Pourquoi un test, et pas une relecture

`perimetre_visible` est appelée par cinq chemins et combinée en ET avec
`public_cible`, `ProfilAccesDocument` et les règles mandataire. Rien, en
relisant, ne dit qu'un assouplissement au milieu de cette chaîne n'ouvre pas une
porte ailleurs — et un contenu devenu visible de trop de monde **ne produit aucun
signal** : personne ne se plaint de voir quelque chose. C'est la classe de défaut
que `standards/03` et l'audit du 26/07/2026 décrivent : trois dérives d'accès
installées sans que rien ne les signale, toutes invisibles sans rouvrir le
fichier concerné.

Le contrôle rejoue donc **tous** les couples (publication × profil) contre la
règle d'avant, et exige que le seul écart possible soit un refus qui portait
uniquement sur le bâtiment.
"""
from __future__ import annotations

import itertools

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models.copropriete import Lot
from app.models.core import Publication, StatutUtilisateur, UserLot, Utilisateur
from app.utils import mes_batiments
from tests.purge_test import purger_ligne
from app.utils import perimetres as P
from app.utils.visibility import perimetre_visible, publication_visible

#: Les publics que porte `public_cible`, plus les deux formes de ciblage vide.
PUBLICS = [
    None,
    '["résidents"]',
    '["copropriétaires"]',
    '["bailleurs"]',
    '["locataires"]',
    '["conseil_syndical"]',
    '["copropriétaires","locataires"]',
]

#: Un profil = (rôles, statut, bâtiment de rattachement). Les trois cas que la
#: contrainte nomme — bailleur non résident, agence (mandataire), locataire —
#: sont présents explicitement.
PROFILS = [
    ("résident", StatutUtilisateur.locataire, 1),
    ("résident", StatutUtilisateur.locataire, None),
    ("propriétaire", StatutUtilisateur.copropriétaire_résident, 1),
    ("propriétaire", StatutUtilisateur.copropriétaire_bailleur, 2),
    ("propriétaire", StatutUtilisateur.copropriétaire_bailleur, None),
    ("mandataire", StatutUtilisateur.copropriétaire_bailleur, None),
    ("mandataire", None, None),
]


def _utilisateur(roles, statut, batiment_id, *, restreint=False) -> Utilisateur:
    return Utilisateur(
        nom="X", prenom="Y", email=f"{roles}-{statut}-{batiment_id}-{restreint}@test.fr",
        roles_json=roles, statut=statut, batiment_id=batiment_id, actif=True,
        restreindre_a_mes_batiments=restreint,
    )


def _publication(perimetre_cible, public_cible, *, confidentiel=False) -> Publication:
    return Publication(
        titre="T", contenu="C", auteur_id=1,
        perimetre_cible=perimetre_cible, public_cible=public_cible,
        confidentiel=confidentiel,
    )


# ── Le contrôle central ───────────────────────────────────────────────────────

def test_aucun_profil_ne_gagne_un_acces_qu_il_n_avait_pas(batiments):
    """Le seul écart admis : un refus qui portait UNIQUEMENT sur le bâtiment.

    Autrement dit, pour tout couple (publication × profil), si l'ancienne règle
    refusait alors que le public convenait, le nouvel accès est légitime ; si elle
    refusait pour une raison de public, le refus doit tenir.
    """
    cibles = [None, "[]"] + [f'["bat:{b}"]' for b in batiments] + ['["bat:%d","bat:%d"]' % (batiments[0], batiments[1])]

    gains_illegitimes = []
    for cible, public, (roles, statut, bat) in itertools.product(cibles, PUBLICS, PROFILS):
        user = _utilisateur(roles, statut, bat)
        pub = _publication(cible, public)

        obtenu = publication_visible(pub, user)
        if not obtenu:
            continue

        #  Le nouvel accès n'est légitime que si le PUBLIC l'autorisait déjà.
        #  On rejoue la seconde moitié de la règle, celle qui n'a pas bougé, en
        #  neutralisant l'axe bâtiment (une publication sans périmètre passe
        #  toujours la première moitié).
        public_seul = publication_visible(_publication(None, public), user)
        if not public_seul:
            gains_illegitimes.append(
                f"  {roles}/{statut}/bât.{bat} voit une publication {public} ciblée {cible}"
            )

    assert not gains_illegitimes, (
        "Ces profils gagnent un accès que le public cible leur refusait — "
        "l'ouverture a débordé de l'axe bâtiment :\n" + "\n".join(gains_illegitimes)
    )


def test_le_public_cible_refuse_toujours_ce_qu_il_refusait(batiments):
    """Le cas nommé par l'utilisateur : bailleur non résident et agence.

    Une publication réservée aux locataires ne devient pas lisible d'un bailleur
    parce qu'on a ouvert les bâtiments.
    """
    bailleur = _utilisateur("propriétaire", StatutUtilisateur.copropriétaire_bailleur, None)
    agence = _utilisateur("mandataire", None, None)

    for cible in (None, f'["bat:{batiments[0]}"]', f'["bat:{batiments[2]}"]'):
        pub = _publication(cible, '["locataires"]')
        assert publication_visible(pub, bailleur) is False, cible
        assert publication_visible(pub, agence) is False, cible

        reservee_cs = _publication(cible, '["conseil_syndical"]')
        assert publication_visible(reservee_cs, bailleur) is False, cible
        assert publication_visible(reservee_cs, agence) is False, cible


# ── Ce qui change volontairement ──────────────────────────────────────────────

def test_une_actualite_d_un_autre_batiment_devient_lisible(batiments):
    """Le changement demandé, énoncé dans le sens positif."""
    resident = _utilisateur("résident", StatutUtilisateur.locataire, batiments[0])
    autre = _publication(f'["bat:{batiments[2]}"]', '["résidents"]')
    assert publication_visible(autre, resident) is True


def test_la_case_du_profil_rend_l_ancien_comportement(batiments):
    """Cochée, elle restreint — et elle ne fait que ça."""
    restreint = _utilisateur("résident", StatutUtilisateur.locataire, batiments[0], restreint=True)
    autre = _publication(f'["bat:{batiments[2]}"]', '["résidents"]')
    sien = _publication(f'["bat:{batiments[0]}"]', '["résidents"]')

    assert publication_visible(autre, restreint) is False
    assert publication_visible(sien, restreint) is True


def test_la_case_ne_donne_jamais_acces_a_plus(batiments):
    """Se restreindre ne peut pas ouvrir : le verdict coché ⊆ le verdict décoché."""
    for bat, cible in itertools.product([None] + batiments, [f'["bat:{b}"]' for b in batiments] + [None]):
        libre = _utilisateur("résident", StatutUtilisateur.locataire, bat)
        coche = _utilisateur("résident", StatutUtilisateur.locataire, bat, restreint=True)
        pub = _publication(cible, '["résidents"]')
        if publication_visible(pub, coche):
            assert publication_visible(pub, libre), (
                f"la restriction OUVRE un accès pour bât.{bat} sur {cible}"
            )


def test_sans_batiment_connu_la_restriction_ne_vide_pas_le_fil(batiments):
    """Cas zéro : cocher une case ne doit pas laisser devant un écran vide."""
    sans_rien = _utilisateur("résident", StatutUtilisateur.locataire, None, restreint=True)
    pub = _publication(f'["bat:{batiments[1]}"]', '["résidents"]')
    assert publication_visible(pub, sans_rien) is True


# ── Ce qui ne doit PAS avoir bougé ────────────────────────────────────────────

def test_les_autres_contenus_gardent_leur_regle_de_batiment(batiments):
    """Documents, sondages et AG : `perimetre_visible` sans le drapeau d'ouverture.

    C'est le défaut du paramètre qui les protège — il vaut False. Ce test existe
    pour que ce défaut ne s'inverse pas au détour d'une refonte : l'ouverture doit
    rester quelque chose qu'un appelant DEMANDE, jamais quelque chose qu'il subit.
    """
    resident = _utilisateur("résident", StatutUtilisateur.locataire, batiments[0])
    autre_batiment = [f"bat:{batiments[2]}"]

    assert perimetre_visible(autre_batiment, resident) is False
    assert perimetre_visible(autre_batiment, resident, ouvert_a_la_copropriete=True) is True


def test_le_conseil_syndical_et_l_admin_voient_toujours_tout(batiments):
    for roles in ("conseil_syndical", "admin"):
        user = _utilisateur(roles, StatutUtilisateur.locataire, batiments[0], restreint=True)
        pub = _publication(f'["bat:{batiments[2]}"]', '["locataires"]')
        assert publication_visible(pub, user) is True


def test_un_ciblage_illisible_refuse_toujours(batiments):
    """L'ouverture ne doit pas transformer une donnée abîmée en autorisation."""
    resident = _utilisateur("résident", StatutUtilisateur.locataire, batiments[0])
    assert publication_visible(_publication("{ceci n'est pas du JSON", '["résidents"]'), resident) is False


# ── Confidentiel (#347) : refermer l'ouverture, et RIEN de plus ───────────────
#
#  La case « 🔒 Confidentiel » ne s'appuie sur aucune règle d'accès nouvelle :
#  elle repasse `ouvert_a_la_copropriete` à sa valeur par défaut, c'est-à-dire au
#  comportement d'avant #339. Ces contrôles vérifient les deux moitiés de cette
#  phrase — qu'elle referme bien, et qu'elle n'ouvre nulle part.

def test_confidentiel_ne_rend_jamais_une_publication_plus_visible(batiments):
    """Le sens de la confidentialité : elle RESTREINT, elle n'accorde jamais.

    Sur tous les couples (périmètre × public × profil × préférence d'affichage),
    le verdict « confidentielle » doit être **inclus** dans le verdict de la même
    publication non confidentielle. Un seul contre-exemple signifierait qu'une
    case censée protéger montre le contenu à quelqu'un de plus — et un contenu
    devenu visible de trop de monde ne produit aucun signal : personne ne se
    plaint de *voir* quelque chose.
    """
    cibles = [None, "[]"] + [f'["bat:{b}"]' for b in batiments]

    gains = []
    for cible, public, (roles, statut, bat), restreint in itertools.product(
        cibles, PUBLICS, PROFILS, (False, True)
    ):
        user = _utilisateur(roles, statut, bat, restreint=restreint)
        if not publication_visible(_publication(cible, public, confidentiel=True), user):
            continue
        if not publication_visible(_publication(cible, public), user):
            gains.append(
                f"  {roles}/{statut}/bât.{bat} (restreint={restreint}) voit la version "
                f"CONFIDENTIELLE de {public} ciblée {cible}, pas la version ouverte"
            )

    assert not gains, (
        "La confidentialité OUVRE un accès au lieu de le fermer :\n" + "\n".join(gains)
    )


def test_confidentiel_referme_le_fil_aux_autres_batiments(batiments):
    """Le changement demandé, énoncé dans le sens positif."""
    resident = _utilisateur("résident", StatutUtilisateur.locataire, batiments[0])
    autre = _publication(f'["bat:{batiments[2]}"]', '["résidents"]', confidentiel=True)
    sien = _publication(f'["bat:{batiments[0]}"]', '["résidents"]', confidentiel=True)

    assert publication_visible(autre, resident) is False
    assert publication_visible(sien, resident) is True
    #  Et la même publication non confidentielle reste lisible : c'est bien la
    #  case, et elle seule, qui a refermé le périmètre.
    assert publication_visible(_publication(f'["bat:{batiments[2]}"]', '["résidents"]'), resident) is True


def test_confidentiel_se_combine_en_et_avec_le_public_cible(batiments):
    """Elle restreint l'axe bâtiment ; elle n'accorde rien sur l'axe public.

    Le cas nommé par l'utilisateur le 14/08/2026 vaut aussi ici : un bailleur non
    résident ou une agence à qui le public cible refusait la publication ne la
    gagnent pas parce qu'elle est devenue confidentielle sur « leur » bâtiment.
    """
    bailleur = _utilisateur("propriétaire", StatutUtilisateur.copropriétaire_bailleur, batiments[0])
    agence = _utilisateur("mandataire", None, batiments[0])
    cible = f'["bat:{batiments[0]}"]'

    for public in ('["locataires"]', '["conseil_syndical"]'):
        pub = _publication(cible, public, confidentiel=True)
        assert publication_visible(pub, bailleur) is False, public
        assert publication_visible(pub, agence) is False, public


def test_le_conseil_syndical_et_l_admin_voient_les_confidentielles(batiments):
    """Ils rédigent et corrigent : leur retirer l'accès rendrait la case ingérable."""
    for roles in ("conseil_syndical", "admin"):
        user = _utilisateur(roles, StatutUtilisateur.locataire, batiments[0])
        pub = _publication(f'["bat:{batiments[2]}"]', '["résidents"]', confidentiel=True)
        assert publication_visible(pub, user) is True


def test_un_ciblage_illisible_refuse_aussi_en_confidentiel(batiments):
    """Une donnée abîmée ne devient pas une autorisation, dans les deux régimes."""
    resident = _utilisateur("résident", StatutUtilisateur.locataire, batiments[0])
    pub = _publication("{ceci n'est pas du JSON", '["résidents"]', confidentiel=True)
    assert publication_visible(pub, resident) is False


def test_sans_batiment_connu_le_confidentiel_se_referme(batiments):
    """La limite épinglée ici a été **levée** le 02/09/2026, sur arbitrage.

    Ce test disait l'inverse, et disait pourquoi : `perimetre_visible` portait un
    repli permissif — un compte sans bâtiment de rattachement accédait à toute la
    résidence. La confidentialité n'étant que ce même chemin
    (`ouvert_a_la_copropriete=False`), elle en héritait : un compte sans bâtiment
    voyait les actualités confidentielles de tous les bâtiments.

    Il concluait par *« le jour où ce repli sera repris, la confidentialité en
    dépend »*. Le repli est repris — *« un utilisateur sans bâtiment ne doit rien
    voir car il n'est pas résident »* —, et c'est ce test qui le constate côté
    confidentialité. Il garde donc exactement le même rôle : rendre visible la
    dépendance entre les deux notions, dans un sens comme dans l'autre.
    """
    sans_batiment = _utilisateur("résident", StatutUtilisateur.locataire, None)
    pub = _publication(f'["bat:{batiments[2]}"]', '["résidents"]', confidentiel=True)
    assert publication_visible(pub, sans_batiment) is False



# ── La fermeture du repli ne RETIRE que — elle n'accorde rien ─────────────────
#
#  🔴 C'est l'invariant que ce fichier entier existe pour tenir, appliqué au lot
#  du 02/09/2026. Fermer un accès est facile à faire pénasser pour anodin ; la
#  première écriture du correctif décidait sur `batiments_de_l_utilisateur()`
#  tout entier — rattachement ET lots — et ÉLARGISSAIT au passage : un bailleur
#  rattaché au bâtiment A, propriétaire d'un lot dans le bâtiment B, gagnait
#  l'accès à B. Un élargissement obtenu en croyant ne faire que restreindre, et
#  qu'aucun test existant n'attrapait, tous portant sur le rattachement seul.


@pytest.fixture()
def bailleur_avec_lot(batiments):
    """Un compte SANS rattachement, mais propriétaire d'un lot — donc résident.

    C'est le cas que la fermeture ne doit pas emporter : `batiment_id` est nul,
    comme pour un compte technique, et pourtant ce compte a bien un pied dans la
    copropriété.
    """
    with Session(engine) as session:
        user = Utilisateur(
            nom="Bailleur", prenom="Sans", email="bailleur-sans-rattachement@test.fr",
            roles_json="propriétaire", statut=StatutUtilisateur.copropriétaire_bailleur,
            batiment_id=None, actif=True,
        )
        session.add(user)
        lot = Lot(batiment_id=batiments[1], numero="B12")
        session.add(lot)
        session.commit()
        session.refresh(user)
        session.refresh(lot)
        session.add(UserLot(user_id=user.id, lot_id=lot.id, actif=True))
        session.commit()
        mes_batiments.invalider_cache()

        yield user

        for ul in session.exec(
            select(UserLot).where(UserLot.user_id == user.id)
        ).all():
            purger_ligne(session, UserLot, ul.id)
        purger_ligne(session, Lot, lot.id)
        purger_ligne(session, Utilisateur, user.id)
        session.commit()
        mes_batiments.invalider_cache()


def test_un_lot_suffit_a_ne_pas_etre_coupe(bailleur_avec_lot, batiments):
    """Détenir un lot, c'est être de la copropriété — même sans rattachement.

    Sans cette nuance, la fermeture aurait coupé de vrais copropriétaires en
    croyant n'écarter que des comptes techniques : un bailleur n'a par
    construction aucun `batiment_id`, c'est son locataire qui habite.
    """
    #  Le bâtiment de son lot : il le voit.
    assert perimetre_visible([f"bat:{batiments[1]}"], bailleur_avec_lot) is True
    #  Un autre bâtiment : il ne le voit pas. C'est là que la fermeture opère —
    #  avant, le repli lui rendait `True` sur celui-ci aussi.
    assert perimetre_visible([f"bat:{batiments[0]}"], bailleur_avec_lot) is False


def test_un_lot_n_elargit_rien_a_qui_a_deja_un_rattachement(batiments):
    """🔴 La contrainte du 14/08/2026, verrouillée sur le nouveau chemin.

    > « une agence, un bailleur ou un mandataire qui n'avaient pas de visibilité
    >   n'en gagnent aucune »

    La consultation des lots est confinée à la branche « aucun rattachement ».
    Un compte qui EN A un décide comme avant, sur lui seul — même s'il détient
    par ailleurs un lot dans un autre bâtiment.

    C'est le test que la première écriture du correctif échouait : elle décidait
    sur `batiments_de_l_utilisateur()` en toutes circonstances, et ce profil-là
    gagnait l'accès au bâtiment de son lot.
    """
    with Session(engine) as session:
        user = Utilisateur(
            nom="Mixte", prenom="Cas", email="rattache-et-proprietaire@test.fr",
            roles_json="propriétaire",
            statut=StatutUtilisateur.copropriétaire_bailleur,
            batiment_id=batiments[0], actif=True,
        )
        session.add(user)
        lot = Lot(batiment_id=batiments[1], numero="C7")
        session.add(lot)
        session.commit()
        session.refresh(user)
        session.refresh(lot)
        session.add(UserLot(user_id=user.id, lot_id=lot.id, actif=True))
        session.commit()
        mes_batiments.invalider_cache()
        try:
            #  Cas zéro : sans ce lot effectivement rattaché, le test ne prouve rien.
            assert batiments[1] in mes_batiments.batiments_de_l_utilisateur(user), (
                "le lot n'est pas remonté — ce test ne mesure plus le cas qu'il décrit"
            )
            assert perimetre_visible([f"bat:{batiments[0]}"], user) is True
            assert perimetre_visible([f"bat:{batiments[1]}"], user) is False
        finally:
            for ul in session.exec(
                select(UserLot).where(UserLot.user_id == user.id)
            ).all():
                purger_ligne(session, UserLot, ul.id)
            purger_ligne(session, Lot, lot.id)
            purger_ligne(session, Utilisateur, user.id)
            session.commit()
            mes_batiments.invalider_cache()


def test_un_compte_sans_rattachement_ni_lot_ne_voit_rien_de_cible(batiments):
    """Le cas visé par l'arbitrage : ni rattachement, ni lot, donc pas résident."""
    technique = _utilisateur("mandataire", None, None)
    assert perimetre_visible([f"bat:{batiments[0]}"], technique) is False
    #  ⚠️ Ce qui reste ouvert, et qui ne relève PAS de ce lot : un contenu à portée
    #  globale (« résidence ») est visible de tous, y compris de ce compte — la
    #  branche `a_portee_globale` court-circuite avant toute question de bâtiment,
    #  et c'est le comportement d'avant comme d'après.
    assert perimetre_visible(["résidence"], technique) is True