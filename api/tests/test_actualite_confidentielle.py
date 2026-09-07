"""Actualité confidentielle : ce qu'elle **empêche**, en dehors de la lecture.

Qui voit quoi est verrouillé par `test_visibilite_ouverte.py`, qui rejoue tous
les couples (publication × profil). Ce fichier-ci couvre les deux autres moitiés
du lot #347, qui ne sont pas des règles d'accès mais des règles d'**émission** :

1. **l'affiche de hall est interdite** — une affiche est punaisée dans un hall et
   lue par n'importe qui, il n'y a aucun contrôle d'accès derrière ;
2. **le message WhatsApp ne porte ni le titre ni le contenu** — le groupe est
   commun à toute la copropriété ; le message garde le périmètre (c'est lui qui
   fait venir les bons résidents) et le lien, qui renvoie vers l'application où
   la règle d'accès s'applique.

La différence de traitement entre les deux n'est pas une nuance de degré : sur
WhatsApp le lecteur doit se connecter pour lire, sur une affiche non.
"""
from __future__ import annotations

import json

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models.core import AnnonceHall, Publication, Utilisateur
from app.routers.publications.commun import appliquer_confidentialite
from app.utils.whatsapp import TITRE_CONFIDENTIEL, construire_message

VRAI_TITRE = "Dégât des eaux chez M. Durand"
VRAI_CONTENU = "<p>Le sinistre concerne l'appartement du 3ᵉ étage.</p>"

CONFIG = {
    "whatsapp_enabled": "1",
    "whatsapp_footer": "— Conseil Syndical",
    "site_url": "https://exemple.test/",
}


#: L'objet passé à `appliquer_confidentialite` reste **détaché**, et c'est
#: délibéré : la fonction consulte l'arborescence des périmètres, qui ouvre sa
#: propre session. Sur `sqlite:///:memory:` les deux partagent la même connexion,
#: et la fermeture de la seconde annule la transaction de la première — une ligne
#: insérée sans `commit` disparaît alors sous les pieds du test.
#:
#: 🔴 Mais l'AFFICHE, elle, est bien écrite en base, et elle portait
#: `publication_id = 90_347` — un identifiant inventé, sur une publication qui
#: n'existait pas. Sous `foreign_keys=ON` la base le refuse (#546), et elle a
#: raison : ce n'était pas le sujet du test, c'était un accident de montage.
#:
#: La publication est donc COMMITTÉE (le grief du commentaire d'origine portait
#: sur les lignes non committées, pas sur les autres), et l'objet détaché reprend
#: son identifiant. Le test mesure la même chose, sur un état qui peut exister.


def _publication(*, perimetre: list[str], confidentiel: bool,
                 annonce_hall: bool = False, porteurs=None) -> Publication:
    return Publication(
        id=porteurs["publication"] if porteurs else None,
        titre=VRAI_TITRE, contenu=VRAI_CONTENU,
        auteur_id=porteurs["auteur"] if porteurs else None,
        perimetre_cible=json.dumps(perimetre, ensure_ascii=False),
        public_cible='["résidents"]',
        confidentiel=confidentiel, annonce_hall=annonce_hall,
    )


@pytest.fixture
def session_affiches():
    """Une session, un auteur et une publication RÉELS — purgés à la sortie.

    ⚠️ La fixture rend `(session, porteurs)` là où elle ne rendait que la
    session : les porteurs sont désormais montés, donc leurs identifiants sont
    attribués par la base et ne peuvent plus être écrits en dur.
    """
    import uuid

    from tests.purge_test import purger_ligne

    with Session(engine) as session:
        auteur = Utilisateur(
            email=f"affiche-{uuid.uuid4().hex[:8]}@exemple.test",
            mot_de_passe_hash="x", prenom="A", nom="H", actif=True,
        )
        session.add(auteur)
        session.commit()
        session.refresh(auteur)
        pub = Publication(titre=VRAI_TITRE, contenu=VRAI_CONTENU, auteur_id=auteur.id)
        session.add(pub)
        session.commit()
        session.refresh(pub)
        porteurs = {"auteur": auteur.id, "publication": pub.id}
        try:
            yield session, porteurs
        finally:
            session.rollback()
            #  La purge passe par le code de production : elle emporte l'affiche
            #  avec la publication, sans que la fixture ait à connaître le graphe.
            purger_ligne(session, Publication, pub.id)
            purger_ligne(session, Utilisateur, auteur.id)


def _affiche(session: Session, porteurs) -> AnnonceHall:
    affiche = AnnonceHall(titre=VRAI_TITRE, message=VRAI_CONTENU,
                          publication_id=porteurs["publication"],
                          auteur_id=porteurs["auteur"])
    session.add(affiche)
    session.commit()
    return affiche


# ── 1. L'affiche de hall ──────────────────────────────────────────────────────

def test_confidentiel_retire_l_option_affiche_de_hall(batiments, session_affiches):
    """Cocher les deux est contradictoire : c'est la confidentialité qui gagne."""
    session, porteurs = session_affiches
    pub = _publication(perimetre=[f"bat:{batiments[0]}"], confidentiel=True,
                       annonce_hall=True, porteurs=porteurs)
    appliquer_confidentialite(pub, session)
    assert pub.annonce_hall is False


def test_une_affiche_deja_generee_est_archivee(batiments, session_affiches):
    """La symétrie exigée par l'arbitrage : le blocage vaut dans les deux sens.

    Passer en confidentiel une actualité **déjà retenue** pour le hall doit l'en
    retirer. L'affiche existante est **archivée** et non supprimée : le PDF a été
    envoyé au CS et fait foi (archiver ≠ supprimer, `standards/11`).
    """
    session, porteurs = session_affiches
    affiche = _affiche(session, porteurs)
    pub = _publication(perimetre=[f"bat:{batiments[0]}"], confidentiel=True,
                       annonce_hall=True, porteurs=porteurs)

    appliquer_confidentialite(pub, session)
    session.commit()

    assert pub.annonce_hall is False
    assert affiche.archivee is True


def test_l_affiche_survit_a_une_actualite_qui_reste_publique(batiments, session_affiches):
    """Le contrôle sait aussi ne RIEN faire — sinon il archiverait tout."""
    session, porteurs = session_affiches
    affiche = _affiche(session, porteurs)
    pub = _publication(perimetre=[f"bat:{batiments[0]}"], confidentiel=False,
                       annonce_hall=True, porteurs=porteurs)

    appliquer_confidentialite(pub, session)
    session.commit()

    assert pub.annonce_hall is True
    assert affiche.archivee is False


def test_un_perimetre_qui_concerne_tout_le_monde_decoche_la_case(batiments, session_affiches):
    """Un cadenas qui ne ferme rien est pire qu'aucun cadenas.

    « Copropriété entière » — et tout nœud à portée globale — reste visible de
    tous quel que soit ce drapeau : `perimetre_visible` sort avant même de
    regarder le bâtiment. Conserver la case cochée afficherait un 🔒 sur une
    publication que tout le monde lit.
    """
    session, porteurs = session_affiches
    from app.utils.perimetres import code_par_defaut

    pub = _publication(perimetre=[code_par_defaut()], confidentiel=True)
    appliquer_confidentialite(pub, session)
    assert pub.confidentiel is False

    vide = _publication(perimetre=[], confidentiel=True)
    appliquer_confidentialite(vide, session)
    assert vide.confidentiel is False


def test_un_perimetre_de_batiment_conserve_la_case(batiments, session_affiches):
    """Le pendant du précédent : là, la confidentialité mord vraiment."""
    session, porteurs = session_affiches
    pub = _publication(perimetre=[f"bat:{batiments[1]}"], confidentiel=True)
    appliquer_confidentialite(pub, session)
    assert pub.confidentiel is True


# ── 2. Le message WhatsApp ────────────────────────────────────────────────────

@pytest.fixture
def message_confidentiel() -> str:
    return construire_message(
        VRAI_TITRE, VRAI_CONTENU, urgente=False, perimetre_cible='["bat:3"]',
        config=CONFIG, public_cible='["résidents"]', pub_id=42, confidentiel=True,
    )


def test_le_message_whatsapp_porte_le_titre_mais_JAMAIS_le_contenu(message_confidentiel):
    """🔴 ARBITRAGE RENVERSÉ le 29/08/2026 (#623), après celui de #347.

    #347 masquait le titre, au motif que « Dégât des eaux chez M. Durand » en dit
    déjà l'essentiel au groupe entier. Le raisonnement était juste, mais il
    traitait le titre comme une donnée SUBIE. Le nouvel arbitrage le traite comme
    une donnée **écrite** : le titre part, et son auteur est averti à l'écran de
    n'y rien mettre de confidentiel.

    ⚠️ Ce qui n'a pas bougé, et qui est le cœur de la protection : le **contenu**
    ne part jamais. C'est lui qui porte le détail — « l'appartement du 3ᵉ étage ».
    Les deux assertions ci-dessous ne sont pas redondantes : la première dit ce
    qui a changé, la seconde ce qui ne doit pas changer avec.
    """
    assert VRAI_TITRE in message_confidentiel
    assert "3ᵉ étage" not in message_confidentiel
    assert "sinistre concerne" not in message_confidentiel


def test_le_titre_de_repli_ne_sert_QUE_aux_actualites_sans_titre():
    """`TITRE_CONFIDENTIEL` n'est plus le titre des confidentielles.

    Il reste comme repli — une actualité sans titre ne doit pas produire un
    message qui commence par un tiret. Ce test empêche qu'on le supprime en
    croyant l'arbitrage clos, et qu'on obtienne alors un message décapité.
    """
    message = construire_message(
        "", VRAI_CONTENU, urgente=False, perimetre_cible='["bat:3"]',
        config=CONFIG, public_cible='["résidents"]', pub_id=42, confidentiel=True,
    )
    assert TITRE_CONFIDENTIEL in message


def test_le_message_whatsapp_garde_le_perimetre_et_le_lien(message_confidentiel):
    """C'est tout l'objet du message : faire venir les bons résidents."""
    assert "bat:3" in message_confidentiel
    assert "https://exemple.test/actualites#pub-42" in message_confidentiel


def test_une_actualite_ordinaire_garde_son_message_complet():
    """Le contrôle sait rougir dans l'autre sens : rien n'a changé sans la case."""
    message = construire_message(
        VRAI_TITRE, VRAI_CONTENU, urgente=False, perimetre_cible='["bat:3"]',
        config=CONFIG, public_cible='["résidents"]', pub_id=42, confidentiel=False,
    )
    assert VRAI_TITRE in message
    assert "3ᵉ étage" in message
    assert TITRE_CONFIDENTIEL not in message


def test_le_public_restreint_garde_son_vrai_titre():
    """Les deux usages du message court ne se confondent pas.

    Une publication à public restreint (locataires, CS…) affiche son titre : le
    groupe voit de quoi il s'agit, seul le contenu est retenu. C'est la
    confidentialité — l'axe bâtiment — qui retire aussi le titre.
    """
    message = construire_message(
        VRAI_TITRE, VRAI_CONTENU, urgente=False, perimetre_cible='["bat:3"]',
        config=CONFIG, public_cible='["locataires"]', pub_id=42, confidentiel=False,
    )
    assert VRAI_TITRE in message
    assert "3ᵉ étage" not in message
