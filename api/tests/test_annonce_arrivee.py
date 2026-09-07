"""L'annonce de bienvenue ne publie AUCUNE donnée personnelle (#821).

Demandé le 07/09/2026 : une actualité pour informer d'un nouvel arrivant, avec
le bâtiment et l'étage — *« par contre sois vigilant de ne pas communiquer des
infos personnelles comme l'email »*.

## 🔴 Pourquoi c'est un test et pas une intention

« Faire attention aux données personnelles » ne survit pas au premier
enrichissement du gabarit : celui qui ajoutera une ligne dans six mois n'aura
pas cette phrase sous les yeux, et rien ne lèvera.

Le test construit donc une annonce à partir d'un compte dont **tous** les champs
sensibles portent une valeur reconnaissable, et vérifie qu'aucune ne se retrouve
dans le titre ou le corps. C'est le seul contrôle qui tienne : il mesure ce qui
SORT, pas ce qu'on a eu l'intention de ne pas mettre.

⚠️ Il vise aussi l'annonce SANS bâtiment et SANS étage : c'est le cas le plus
courant à l'inscription, et un gabarit qui suppose ces valeurs produirait
« vient d'emménager au  » ou « Bienvenue à X — ».
"""
from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    Batiment,
    Copropriete,
    Publication,
    RoleUtilisateur,
    StatutUtilisateur,
    Utilisateur,
)
from app.utils.annonce_arrivee import (
    CHAMPS_INTERDITS,
    corps_annonce,
    creer_annonce_arrivee,
    libelle_etage,
    titre_annonce,
)
from tests.purge_test import purger_ligne

#: Des valeurs qu'on reconnaît à l'œil dans une chaîne — c'est tout leur intérêt.
SENSIBLES = {
    "email": "ne-doit-pas-sortir@exemple.test",
    "telephone": "0600000000",
    "hashed_password": "CONDENSAT-SECRET",
    "nom_proprietaire": "PROPRIO-A-NE-PAS-CITER",
}


@pytest.fixture()
def arrivant():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        copro = Copropriete(nom=f"Copro-{uuid.uuid4().hex[:4]}", adresse="1 rue Test")
        session.add(copro)
        session.commit()
        bat = Batiment(numero="3", copropriete_id=copro.id)
        session.add(bat)
        session.commit()
        session.refresh(bat)

        u = Utilisateur(
            prenom="Alix",
            nom="RIVANT",
            role=RoleUtilisateur.résident,
            statut=StatutUtilisateur.locataire,
            actif=True,
            batiment_id=bat.id,
            etage=2,
            **{k: v for k, v in SENSIBLES.items() if k != "email"},
            email=SENSIBLES["email"],
        )
        session.add(u)
        session.commit()
        session.refresh(u)
        yield u, bat
        session.rollback()
        for pub in session.exec(
            select(Publication).where(Publication.auteur_id == u.id)
        ).all():
            purger_ligne(session, Publication, pub.id)
        session.commit()
        u2 = session.get(Utilisateur, u.id)
        u2.batiment_id = None
        session.commit()
        purger_ligne(session, Utilisateur, u.id)
        purger_ligne(session, Batiment, bat.id)
        purger_ligne(session, Copropriete, copro.id)
        session.commit()


def test_l_annonce_ne_contient_AUCUNE_donnee_personnelle(arrivant):
    """Le contrôle qui compte : ce qui SORT, pas ce qu'on a voulu ne pas mettre."""
    user, _ = arrivant
    with Session(engine) as session:
        u = session.get(Utilisateur, user.id)
        pub = creer_annonce_arrivee(
            session, u, nom_complet="Alix RIVANT", ancien="Mme BERNAERT"
        )
        session.commit()

        texte = f"{pub.titre}\n{pub.contenu}"
        for champ in CHAMPS_INTERDITS:
            valeur = SENSIBLES[champ]
            assert valeur not in texte, (
                f"L'annonce publie `{champ}` — « {valeur} ». Une annonce de "
                "voisinage n'a besoin d'aucune de ces données."
            )
        #  Et le contraire : ce qui DOIT y être, y est.
        assert "Alix RIVANT" in texte
        assert "Bâtiment 3" in texte
        assert "2ᵉ étage" in texte
        assert "Mme BERNAERT" in texte


def test_le_gabarit_tient_SANS_batiment_ni_etage():
    """Le cas le plus courant à l'inscription — et celui qui casse un gabarit naïf.

    Sans garde, on obtient « Bienvenue à X — » et « vient d'emménager au  ».
    """
    titre = titre_annonce("Alix RIVANT", "")
    assert titre == "Bienvenue à Alix RIVANT", titre
    assert not titre.rstrip().endswith("—")

    corps = corps_annonce("Alix RIVANT", "", None, "")
    assert "dans la résidence" in corps
    assert "  " not in corps.replace("\n", ""), corps
    assert "succède" not in corps


def test_ne_sait_pas_n_est_PAS_publie_comme_un_nom():
    """Le formulaire pose « Ne sait pas » quand l'arrivant coche la case.

    Publier la valeur telle quelle donnerait « succède à Ne sait pas » — une
    phrase qui a l'air d'un défaut d'affichage, et qui en est un.
    """
    for valeur in ("Ne sait pas", "ne sait pas", "INCONNU"):
        assert "succède" not in corps_annonce("Alix RIVANT", "Bâtiment 3", 2, valeur)
    assert "succède" in corps_annonce("Alix RIVANT", "Bâtiment 3", 2, "Mme BERNAERT")


def test_l_etage_se_lit_en_francais():
    """Zéro et les négatifs ne sont pas des étages comme les autres."""
    assert libelle_etage(None) == ""
    assert libelle_etage(0) == "rez-de-chaussée"
    assert libelle_etage(1) == "1ᵉʳ étage"
    assert libelle_etage(2) == "2ᵉ étage"
    assert libelle_etage(-1) == "sous-sol"


def test_l_ARRIVANT_est_l_auteur_de_sa_propre_annonce(arrivant):
    """🔴 Sinon il ne pourrait ni la lire ni la corriger.

    Une présentation de soi qu'on ne peut pas modifier est le défaut de
    `project_auteur_toujours_visible`, appliqué à sa propre arrivée.
    """
    user, bat = arrivant
    with Session(engine) as session:
        u = session.get(Utilisateur, user.id)
        pub = creer_annonce_arrivee(session, u, nom_complet="Alix RIVANT", ancien="")
        session.commit()
        assert pub.auteur_id == u.id
        assert pub.batiment_id == bat.id
        assert pub.perimetre_cible == f'["bat:{bat.id}"]'
        #  Jamais sur le groupe : une annonce nominative ne quitte pas l'application.
        assert pub.partager_whatsapp is False


def test_relancer_l_accueil_ne_publie_PAS_une_seconde_annonce(arrivant):
    """`accueil-arrivant` est rejouable par un membre du conseil."""
    user, _ = arrivant
    with Session(engine) as session:
        u = session.get(Utilisateur, user.id)
        creer_annonce_arrivee(session, u, nom_complet="Alix RIVANT", ancien="")
        session.commit()
        seconde = creer_annonce_arrivee(session, u, nom_complet="Alix RIVANT", ancien="")
        session.commit()

        assert seconde is None
        toutes = session.exec(
            select(Publication).where(Publication.auteur_id == u.id)
        ).all()
        assert len(toutes) == 1, f"{len(toutes)} annonces pour une arrivée"
