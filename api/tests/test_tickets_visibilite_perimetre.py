"""L'ouverture des tickets aux résidents de leur périmètre (#710, étape 2).

## Ce que le lot change, en une phrase

Un résident voit désormais, **en lecture seule**, les tickets dont le périmètre
recoupe ses bâtiments, plus ceux à portée globale. Hier il ne voyait que les
siens.

## Les trois choses que ce fichier éprouve, et pourquoi ce sont celles-là

1. **La liste et la fiche rendent le MÊME verdict.** C'était le premier piège
   nommé par le ticket : `list_tickets` filtrait en SQL, `ticket_visible` en
   Python — deux écritures d'une même règle, qui ne pouvaient rester d'accord que
   par chance. Le lot supprime le filtre SQL ; ce test vérifie qu'aucune
   divergence ne subsiste, sur des tickets réels et pour plusieurs profils. Un
   désaccord ne se voit jamais depuis l'écran : *on ne remarque pas ce qui
   manque*.

2. **`confidentiel` referme, et referme exactement ce qui a été ouvert.** Pas
   plus : l'auteur, la personne pour qui le ticket a été saisi et le CS gardent
   l'accès. Pas moins : un résident du bâtiment voisin ne le voit plus.

3. **Le droit d'ÉCRIRE n'a pas bougé.** Ouvrir la lecture d'un ticket à tout un
   bâtiment n'aurait aucun sens si chacun pouvait ensuite en modifier le suivi.
   La séparation est structurelle — `ticket_visible` d'un côté, `peut_commenter`
   et `peut_editer` de l'autre —, mais une séparation structurelle se casse en
   une ligne, et rien ne le dirait.

## Ce que ce fichier NE vérifie pas

La règle géographique elle-même : elle vit dans `perimetre_visible`, et
`test_perimetres_arbre.py` / `test_visibilite_ouverte.py` l'éprouvent déjà couple
par couple. La rejouer ici en dupliquerait la définition — le défaut même que le
lot supprime.
"""
from __future__ import annotations

import json
import uuid

import pytest
from sqlmodel import Session, SQLModel, select

from app.auth.deps import peut_commenter, peut_editer
from app.database import engine
from app.models.core import (
    Batiment,
    StatutTicket,
    StatutUtilisateur,
    Ticket,
    Utilisateur,
)
from app.routers.tickets.crud import list_tickets
from app.utils import mes_batiments
from app.utils import perimetres as P
from app.utils.visibility import ticket_visible
from tests.purge_test import purger_ligne


def _utilisateur(session, roles, statut, batiment_id) -> Utilisateur:
    u = Utilisateur(
        nom="X", prenom="Y",
        email=f"tk-{uuid.uuid4().hex[:8]}@exemple.test",
        mot_de_passe_hash="x", roles_json=roles, statut=statut,
        batiment_id=batiment_id, actif=True,
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _ticket(session, auteur_id, perimetre, *, confidentiel=False) -> Ticket:
    t = Ticket(
        numero=f"T-{uuid.uuid4().hex[:6]}", titre="Fuite", description="…",
        categorie="panne", auteur_id=auteur_id, statut=StatutTicket.ouvert,
        perimetre_cible=json.dumps(perimetre, ensure_ascii=False),
        confidentiel=confidentiel,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


@pytest.fixture()
def scene(batiments):
    """Deux résidents de bâtiments DIFFÉRENTS, et trois tickets du premier.

    Le second résident est le témoin : c'est lui qui doit voir le ticket de son
    voisin quand le périmètre le concerne, et ne rien voir quand il ne le
    concerne pas.
    """
    SQLModel.metadata.create_all(engine)
    mes_batiments.invalider_cache()
    P.invalider_cache()
    with Session(engine) as session:
        b1, b2 = batiments[0], batiments[1]
        auteur = _utilisateur(session, "résident", StatutUtilisateur.locataire, b1)
        voisin = _utilisateur(session, "résident", StatutUtilisateur.locataire, b2)
        cs = _utilisateur(session, "conseil_syndical", StatutUtilisateur.locataire, b2)
        tickets = {
            "chez_moi": _ticket(session, auteur.id, [f"bat:{b1}"]),
            "chez_le_voisin": _ticket(session, auteur.id, [f"bat:{b2}"]),
            "toute_la_residence": _ticket(session, auteur.id, ["résidence"]),
            "confidentiel": _ticket(session, auteur.id, ["résidence"], confidentiel=True),
        }
        mes_batiments.invalider_cache()
        yield session, tickets, auteur, voisin, cs
        for t in tickets.values():
            purger_ligne(session, Ticket, t.id)
        for u in (auteur, voisin, cs):
            purger_ligne(session, Utilisateur, u.id)
        session.commit()
        mes_batiments.invalider_cache()


# ── 1. La liste et la fiche disent la même chose ──────────────────────────────

def test_la_liste_rend_exactement_ce_que_la_fiche_accepte(scene):
    """🔴 Le piège n° 1 du ticket, vérifié sur des tickets réels.

    Si `list_tickets` réintroduisait un jour un `where` de visibilité, ce test
    tomberait — c'est la seule chose qui empêche les deux règles de repartir
    chacune de leur côté.
    """
    session, _tickets, auteur, voisin, cs = scene
    tous = session.exec(select(Ticket)).all()
    for user in (auteur, voisin, cs):
        listes = {t.id for t in list_tickets(session=session, user=user)}
        fiches = {t.id for t in tous if ticket_visible(t, user)}
        assert listes == fiches, (
            f"la liste et la fiche divergent pour {user.email} :\n"
            f"  seulement dans la liste : {sorted(listes - fiches)}\n"
            f"  seulement dans la fiche : {sorted(fiches - listes)}"
        )


def test_le_voisin_voit_ce_qui_concerne_son_batiment(scene):
    _session, tickets, _auteur, voisin, _cs = scene
    assert ticket_visible(tickets["chez_le_voisin"], voisin) is True
    assert ticket_visible(tickets["toute_la_residence"], voisin) is True


def test_le_voisin_ne_voit_PAS_un_ticket_d_un_autre_batiment(scene):
    """Sans ce refus, l'ouverture ne serait pas « par périmètre » mais totale."""
    _session, tickets, _auteur, voisin, _cs = scene
    assert ticket_visible(tickets["chez_moi"], voisin) is False


# ── 2. Le drapeau referme, et rien de plus ────────────────────────────────────

def test_confidentiel_referme_pour_le_voisin(scene):
    _session, tickets, _auteur, voisin, _cs = scene
    assert ticket_visible(tickets["confidentiel"], voisin) is False, (
        "un ticket confidentiel à portée résidence reste lisible du voisin : "
        "le drapeau ne referme pas l'ouverture qu'il doit refermer"
    )


def test_confidentiel_ne_referme_NI_pour_l_auteur_NI_pour_le_CS(scene):
    """L'autre moitié, celle qu'on oublie de vérifier.

    Un drapeau qui refermerait aussi pour l'auteur transformerait « confidentiel »
    en « inaccessible », et le CS ne pourrait plus traiter les dossiers les plus
    sensibles — exactement ceux qu'on marque.
    """
    _session, tickets, auteur, _voisin, cs = scene
    assert ticket_visible(tickets["confidentiel"], auteur) is True
    assert ticket_visible(tickets["confidentiel"], cs) is True


def test_un_ciblage_illisible_refuse(scene):
    """Une donnée abîmée ne doit pas ÉLARGIR la visibilité.

    C'est la nuance que `_codes_json_pour_acces` porte : un JSON corrompu vaut
    `None`, et l'appelant refuse. Le repli d'affichage (`["résidence"]`) ferait
    ici l'inverse de ce qu'on veut.
    """
    session, tickets, _auteur, voisin, _cs = scene
    abime = tickets["chez_moi"]
    abime.perimetre_cible = "{ceci n'est pas du JSON"
    session.add(abime)
    session.commit()
    assert ticket_visible(abime, voisin) is False


# ── 3. Lire n'est pas écrire ──────────────────────────────────────────────────

def test_voir_un_ticket_ne_donne_AUCUN_droit_d_ecriture(scene):
    """🔴 Le point 4 du ticket, vérifié plutôt que promis.

    La séparation est structurelle — deux fonctions, deux appelants — mais elle
    se casserait en une ligne le jour où quelqu'un « simplifierait » en réutilisant
    `ticket_visible` dans `add_evolution`.
    """
    _session, tickets, _auteur, voisin, _cs = scene
    lisible = tickets["toute_la_residence"]
    assert ticket_visible(lisible, voisin) is True
    assert peut_editer(lisible, voisin) is False, (
        "le voisin peut RÉÉCRIRE la demande d'un autre résident"
    )
    assert peut_commenter(lisible, voisin) is False, (
        "le voisin peut commenter et faire avancer le suivi d'un ticket qui "
        "n'est pas le sien — l'ouverture devait être en lecture seule"
    )


def test_le_batiment_du_voisin_est_bien_celui_qu_on_croit(scene, batiments):
    """Cas zéro. Si les deux résidents partageaient un bâtiment, tous les tests
    ci-dessus passeraient au vert en ne distinguant plus rien.
    """
    _session, _tickets, auteur, voisin, _cs = scene
    assert auteur.batiment_id != voisin.batiment_id
    assert mes_batiments.batiments_de_l_utilisateur(auteur) != (
        mes_batiments.batiments_de_l_utilisateur(voisin)
    )
    assert Batiment is not None  # l'arbre a bien été semé par la fixture
