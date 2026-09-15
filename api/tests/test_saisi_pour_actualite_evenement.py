"""« Saisi pour » sur les actualités et les événements — la même notion partout.

## Ce que ce fichier protège

Le ticket porte « Saisi pour » depuis l'origine. L'actualité et l'événement l'ont
reçu le 15/09/2026, à la demande : *« ajouter la section Saisi pour, présente
dans les formulaires de tickets, pour actualité et calendrier »*.

Trois entités, une seule notion. Ce qui est vérifié ici est **ce qui les rend
identiques**, parce que c'est précisément ce qui diverge en silence :

1. **les trois colonnes**, sur les trois modèles — deux sur trois laisserait un
   nom d'ancien destinataire survivre à un résident désigné depuis ;
2. **le DROIT étendu** — poser `saisi_pour_user_id` suffit à ce que la personne
   nommée puisse corriger, parce que `est_auteur` lit par `getattr` sans
   connaître le type. C'est voulu (`ux-patterns` §15) et c'est le genre de
   conséquence qu'on découvre autrement en production ;
3. **l'effacement** — revenir à « En mon nom » doit vider, pas ne rien faire.
   C'est la dette qui a tenu ce champ fermé en édition sur les tickets jusqu'au
   18/08/2026 : `None` y était indistinguable d'un champ non transmis ;
4. **le libellé affiché**, composé à un seul endroit.

## ⚠️ Ce qu'il ne vérifie PAS

Le rendu à l'écran. La mention en lecture seule n'existe aujourd'hui que sur la
**fiche** d'un ticket (`tickets/[id]`), et ni l'actualité ni l'événement n'ont de
fiche : leurs cartes ne la portent pas encore. C'est un manque assumé et nommé,
pas un oubli — le formulaire de correction, lui, montre bien au nom de qui
l'objet a été déposé.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.auth.deps import est_auteur, peut_editer
from app.models.core import Publication, RoleUtilisateur, Ticket, Utilisateur
from app.models.evenement import Evenement
from app.utils.saisi_pour import CHAMPS, affichage

#: Les trois entités qui portent la notion. Le paramétrage est ce qui empêche
#: qu'on en ajoute une quatrième sans lui appliquer les mêmes exigences.
PORTEUSES = (Ticket, Publication, Evenement)


@pytest.fixture()
def session():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        yield s


def _utilisateur(session, prenom="Jean", nom="Dupont", roles="residant"):
    u = Utilisateur(
        email=f"{prenom.lower()}.{nom.lower()}@exemple.test",
        mot_de_passe_hash="x", prenom=prenom, nom=nom, roles_json=roles, actif=True,
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


# ── 1. Les trois colonnes, sur les trois entités ─────────────────────────────

@pytest.mark.parametrize("modele", PORTEUSES, ids=lambda m: m.__name__)
def test_les_trois_colonnes_sont_presentes(modele):
    """Deux sur trois ne suffit pas : elles voyagent ensemble ou pas du tout."""
    manquantes = [c for c in CHAMPS if c not in modele.model_fields]
    assert not manquantes, (
        f"{modele.__name__} ne porte pas {manquantes}. Les trois champs décrivent "
        "UNE notion : n'en réécrire que deux laisserait le nom d'une personne "
        "extérieure survivre au résident inscrit désigné depuis."
    )


@pytest.mark.parametrize("modele", (Publication, Evenement), ids=lambda m: m.__name__)
def test_aucune_cle_etrangere_declaree_sur_les_colonnes_ajoutees(modele):
    """🔴 SQLite ne sait pas ajouter une contrainte à une table existante.

    Ces colonnes arrivent par `add_column` : les déclarer `foreign_key` dans le
    modèle ferait diverger une base neuve (`create_all`) d'une base migrée. Le
    pendant — la contrainte dans la migration — est refusé par
    `test_migrations.py` ; celui-ci garde l'autre moitié du défaut.

    ⚠️ `Ticket` est hors périmètre : sa colonne est née avec la table, elle porte
    donc légitimement sa clé.
    """
    colonne = modele.__table__.columns["saisi_pour_user_id"]
    assert not colonne.foreign_keys, (
        f"{modele.__name__}.saisi_pour_user_id déclare une clé étrangère. Une base "
        "migrée ne l'aura pas — les deux schémas divergeraient en silence."
    )


# ── 2. 🔴 Le droit étendu — la conséquence qui ne se voit pas ────────────────

@pytest.mark.parametrize("modele", PORTEUSES, ids=lambda m: m.__name__)
def test_la_personne_nommee_peut_CORRIGER_ce_qui_parle_d_elle(session, modele):
    """*« Un membre du CS qui dépose au nom d'un résident ne le dépossède pas. »*

    `est_auteur` lit `saisi_pour_user_id` par `getattr`, sans connaître le type :
    poser la colonne SUFFIT à étendre le droit. Ce test rend la conséquence
    visible — sinon elle ne se lit nulle part, et un lot futur pourrait la
    retirer sans que rien ne bronche.
    """
    membre_cs = _utilisateur(session, "Claire", "Martin", roles="conseil_syndical")
    resident = _utilisateur(session, "Paul", "Durand")

    objet = modele(auteur_id=membre_cs.id, saisi_pour_user_id=resident.id)
    assert est_auteur(objet, resident) is True
    assert peut_editer(objet, resident) is True
    #  Et l'auteur réel garde évidemment son droit.
    assert peut_editer(objet, membre_cs) is True


@pytest.mark.parametrize("modele", PORTEUSES, ids=lambda m: m.__name__)
def test_un_TIERS_ne_gagne_aucun_droit(session, modele):
    """Cas zéro du précédent : sans lui, un test qui rendrait VRAI sur tout le
    monde passerait pour une réussite."""
    auteur = _utilisateur(session, "Claire", "Martin", roles="conseil_syndical")
    nomme = _utilisateur(session, "Paul", "Durand")
    tiers = _utilisateur(session, "Luc", "Bernard")

    objet = modele(auteur_id=auteur.id, saisi_pour_user_id=nomme.id)
    assert est_auteur(objet, tiers) is False
    assert peut_editer(objet, tiers) is False


def test_un_objet_sans_saisi_pour_n_ouvre_rien(session):
    """⚠️ `None == None` rendrait VRAI sur tout objet sans « saisi pour ».

    La garde existe dans `est_auteur` ; ce test l'éprouve sur les entités neuves,
    parce que c'est exactement le cas limite qu'une colonne nullable ajoute.
    """
    auteur = _utilisateur(session, "Claire", "Martin", roles="conseil_syndical")
    autre = _utilisateur(session, "Paul", "Durand")
    for modele in (Publication, Evenement):
        objet = modele(auteur_id=auteur.id)
        assert est_auteur(objet, autre) is False, modele.__name__


# ── 3. L'effacement : revenir à « En mon nom » doit VIDER ────────────────────

def test_un_champ_remis_a_vide_est_TRANSMIS_par_le_schema():
    """🔴 La PRÉSENCE décide d'écrire, pas la non-nullité.

    `model_dump(exclude_unset=True)` — ce qu'emploient les deux routeurs — garde
    un `null` transmis et écarte un champ tu. Sans cette distinction, choisir
    « En mon nom » serait un geste sans effet, en silence : c'est la dette qui a
    tenu ce champ fermé en édition sur les tickets pendant des semaines.
    """
    from app.routers.calendrier import EvenementUpdate
    from app.schemas_publications import PublicationUpdate

    for schema in (PublicationUpdate, EvenementUpdate):
        efface = schema(saisi_pour_user_id=None, saisi_pour_nom=None, saisi_pour_email=None)
        envoye = efface.model_dump(exclude_unset=True)
        assert set(CHAMPS) <= set(envoye), (
            f"{schema.__name__} n'a pas transmis les champs remis à vide : "
            f"{sorted(envoye)}"
        )

        muet = schema(titre="Sans rapport")
        assert not (set(CHAMPS) & set(muet.model_dump(exclude_unset=True))), (
            f"{schema.__name__} transmet « Saisi pour » alors que personne n'y a "
            "touché : une correction de titre effacerait la mention."
        )


# ── 4. Le libellé affiché, composé à un seul endroit ─────────────────────────

def test_le_resident_inscrit_PRIME_sur_le_nom_libre(session):
    """C'est le compte qui fait foi : c'est lui qui porte le droit de correction.

    ⚠️ Le pendant front (`$lib/saisiPour.modeDepuis`) applique la même
    priorité. Deux écritures d'une même règle doivent dire la même chose jusque
    dans leurs cas limites, sinon les comparer ne prouve rien.
    """
    resident = _utilisateur(session, "Paul", "Durand")
    objet = Publication(auteur_id=1, saisi_pour_user_id=resident.id,
                        saisi_pour_nom="Nom qui traîne")
    assert affichage(session, objet) == "Paul DURAND"


def test_le_nom_libre_sert_quand_personne_n_est_inscrit(session):
    objet = Evenement(auteur_id=1, saisi_pour_nom="  Mme Voisine  ")
    assert affichage(session, objet) == "Mme Voisine"


@pytest.mark.parametrize("valeurs", [{}, {"saisi_pour_nom": "   "}, {"saisi_pour_nom": ""}])
def test_sans_rien_l_affichage_est_NONE_et_pas_une_chaine_vide(session, valeurs):
    """L'écran teste la PRÉSENCE pour décider d'afficher la mention.

    Une chaîne vide est présente : elle afficherait « Saisi pour » suivi de rien.
    """
    assert affichage(session, Publication(auteur_id=1, **valeurs)) is None


def test_un_identifiant_qui_ne_designe_personne_ne_fait_pas_tomber(session):
    """Un compte supprimé depuis laisse un identifiant orphelin — la colonne n'a
    pas de clé étrangère, donc rien ne l'empêche. L'affichage retombe sur le nom
    libre, ou sur `None` : il ne lève pas."""
    objet = Publication(auteur_id=1, saisi_pour_user_id=999_999)
    assert affichage(session, objet) is None
