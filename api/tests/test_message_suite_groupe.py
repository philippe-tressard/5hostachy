"""`message_suite` seule — le message d'une Suite sur le groupe, composé UNE fois (#1569).

`routers/tickets/suite_groupe.py` n'est nommé par aucun test (relevé du 02/10/2026,
#1569) : `test_suite_groupe.py` le tient de bout en bout — de vraies Suites, le
message tel que le canal le compose —, mais jamais par son nom. Ce fichier-ci
éprouve la fonction ISOLÉE, cas limites en main, sur une vraie base :

1. le titre selon la nature (« (suite) » pour une actualité, « 🔧 » pour une affaire) ;
2. le lien de la fiche, TOUJOURS présent, bâti sur l'adresse du site ;
3. le rappel de l'historique : le message initial compte, la Suite enregistrée ne
   se compte pas elle-même, une parole vide ne compte pas ;
4. le texte : le message en cours puis le rappel — le rappel seul quand il n'y a
   pas de message ;
5. l'urgence suit la priorité de l'affaire.

Que les trois appelants (affaire, actualité, aperçu) passent bien par ici est
tenu par l'arbre syntaxique, en bas de fichier.
"""

from __future__ import annotations

import ast
import itertools
import pathlib
from datetime import timedelta

import pytest

from app.models.core import Ticket, TicketEvolution
from app.routers.tickets.suite_groupe import MessageSuite, message_suite
from app.utils import horloge
from app.utils.liens import lien_ticket
from tests.aides_base import compte

SITE = "https://residence.exemple.test"
ROUTEURS = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "tickets"


@pytest.fixture()
def auteur(session):
    return compte(session, prefixe="suite")


_numero = itertools.count(1)


def _ticket(session, auteur, titre="Fuite au 3e", **champs) -> Ticket:
    champs.setdefault("categorie", "panne")
    champs.setdefault("statut", "ouvert")
    #  Le périmètre est posé : son défaut se lit dans l'arbre de la base de
    #  l'application, que ce test n'ouvre pas.
    t = Ticket(
        numero=f"S-{next(_numero):04d}",
        titre=titre,
        description="Message initial.",
        auteur_id=auteur.id,
        perimetre_cible='["résidence"]',
    )
    for cle, valeur in champs.items():
        setattr(t, cle, valeur)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _parole(session, ticket, auteur, contenu, rang: int, type_="commentaire") -> TicketEvolution:
    e = TicketEvolution(
        ticket_id=ticket.id,
        type=type_,
        contenu=contenu,
        auteur_id=auteur.id,
        cree_le=horloge.maintenant() + timedelta(minutes=rang),
    )
    session.add(e)
    session.commit()
    return e


def _suite(session, ticket, contenu="Le plombier passe demain.", *, enregistree=False):
    return message_suite(session, ticket, contenu, site_url=SITE, suite_enregistree=enregistree)


# ── Titre ───────────────────────────────────────────────────────────────────


def test_le_titre_d_une_affaire_porte_la_cle_a_molette(session, auteur):
    assert _suite(session, _ticket(session, auteur)).titre == "🔧 Fuite au 3e"


def test_le_titre_d_une_actualite_porte_suite(session, auteur):
    t = _ticket(session, auteur, "Fête des voisins", categorie="actualite", statut="publie")
    assert _suite(session, t).titre == "Fête des voisins (suite)"


# ── Lien ────────────────────────────────────────────────────────────────────


def test_le_lien_est_celui_de_la_fiche_sur_l_adresse_du_site(session, auteur):
    t = _ticket(session, auteur)
    assert _suite(session, t).lien == SITE + lien_ticket(t.id) == f"{SITE}/tickets/{t.id}"


def test_le_lien_est_present_meme_sans_aucun_message(session, auteur):
    """Y compris pour le message restreint d'une actualité ciblée, qui ne porte que lui."""
    t = _ticket(session, auteur)
    assert _suite(session, t, "").lien == f"{SITE}/tickets/{t.id}"


# ── Rappel de l'historique ──────────────────────────────────────────────────


def test_a_l_apercu_seul_le_message_initial_est_compte(session, auteur):
    suite = _suite(session, _ticket(session, auteur))
    assert "Déjà 1 message(s)" in suite.contenu


def test_a_l_apercu_chaque_parole_du_fil_s_ajoute(session, auteur):
    t = _ticket(session, auteur)
    _parole(session, t, auteur, "Un", 1)
    _parole(session, t, auteur, "Deux", 2)

    assert "Déjà 3 message(s)" in _suite(session, t).contenu


def test_a_l_envoi_la_suite_enregistree_ne_se_compte_pas_elle_meme(session, auteur):
    t = _ticket(session, auteur)
    _parole(session, t, auteur, "Un", 1)
    _parole(session, t, auteur, "La Suite qui part", 2)

    assert "Déjà 2 message(s)" in _suite(session, t, enregistree=True).contenu


def test_a_l_envoi_sans_aucune_parole_la_suite_enregistree_n_efface_pas_le_message_initial(
    session, auteur
):
    """Cas limite : fil vide, `suite_enregistree` vrai — le message initial compte quand même."""
    assert (
        "Déjà 1 message(s)" in _suite(session, _ticket(session, auteur), enregistree=True).contenu
    )


def test_une_parole_sans_texte_ne_compte_pas(session, auteur):
    """Un changement d'état muet n'est pas un message : le groupe ne le lirait pas."""
    t = _ticket(session, auteur)
    _parole(session, t, auteur, None, 1, type_="etat")
    _parole(session, t, auteur, "", 2, type_="etat")
    _parole(session, t, auteur, "Un vrai message", 3)

    assert "Déjà 2 message(s)" in _suite(session, t).contenu


def test_le_fil_d_une_autre_affaire_ne_compte_pas(session, auteur):
    t = _ticket(session, auteur)
    autre = _ticket(session, auteur, "Autre affaire")
    _parole(session, autre, auteur, "Ailleurs", 1)

    assert "Déjà 1 message(s)" in _suite(session, t).contenu


# ── Texte ───────────────────────────────────────────────────────────────────


def test_le_texte_est_le_message_en_cours_puis_le_rappel(session, auteur):
    contenu = _suite(session, _ticket(session, auteur), "Le plombier passe demain.").contenu

    message, _, rappel = contenu.partition("\n\n")
    assert message == "Le plombier passe demain."
    assert rappel.startswith("📜 Déjà ")
    assert "l'historique complet est sur l'application" in rappel


def test_sans_message_le_texte_se_reduit_au_rappel(session, auteur):
    contenu = _suite(session, _ticket(session, auteur), "").contenu

    assert contenu.startswith("📜 Déjà 1 message(s)")
    assert "\n\n" not in contenu


def test_le_message_initial_de_l_affaire_n_est_jamais_celui_du_groupe(session, auteur):
    """Signalé le 28/09/2026 : c'est la Suite qui part, jamais l'ouverture de l'affaire."""
    t = _ticket(session, auteur)
    assert t.description not in _suite(session, t, "Autre chose.").contenu


# ── Urgence ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "priorite,attendue", [("haute", True), ("normale", False), ("basse", False), (None, False)]
)
def test_l_urgence_suit_la_priorite_de_l_affaire(session, auteur, priorite, attendue):
    t = _ticket(session, auteur)
    if priorite is not None:
        t.priorite = priorite
    assert _suite(session, t).urgente is attendue


def test_le_message_est_immuable(session, auteur):
    suite = _suite(session, _ticket(session, auteur))
    assert isinstance(suite, MessageSuite)
    with pytest.raises(Exception):
        suite.titre = "autre"  # type: ignore[misc]


# ── Le verrou annoncé par l'en-tête du module ───────────────────────────────


@pytest.mark.parametrize("module", ["evolutions", "actualite", "apercu"])
def test_les_trois_appelants_composent_la_suite_par_ce_module(module):
    """Les deux envois et l'aperçu importent et appellent `message_suite` — ils ne
    la recomposent pas (l'aperçu montrait la description de l'affaire, un mensonge)."""
    arbre = ast.parse((ROUTEURS / f"{module}.py").read_text(encoding="utf-8"))
    importe = any(
        isinstance(n, ast.ImportFrom)
        and n.module == "suite_groupe"
        and any(a.name == "message_suite" for a in n.names)
        for n in ast.walk(arbre)
    )
    appelle = any(
        isinstance(n, ast.Call) and getattr(n.func, "id", None) == "message_suite"
        for n in ast.walk(arbre)
    )
    assert importe and appelle, f"{module}.py ne passe plus par suite_groupe.message_suite"
