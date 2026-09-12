"""Le « Saisi pour » **se substitue à l'auteur** — pour le nom lu et pour la copie.

## La demande (12/09/2026, à l'écran)

> Pour un ticket dont le « Saisi pour » possède un résident inscrit ou une
> personne extérieure, ce dernier se substitue à l'auteur :
>   • pour le nom qui apparaît dans les publications du fil d'actualité,
>   • pour « Envoyer une copie à XXX » dans la catégorie DIFFUSION.

## Pourquoi c'est la suite d'un arbitrage déjà pris

`copie_auteur.py` est né le 31/08/2026 sur ces mots : *« c'est bien le
propriétaire du ticket, pas celui qui fait un commentaire »*. La question était
déjà la bonne ; la réponse s'arrêtait à l'auteur parce que rien d'autre
n'existait alors. Le « Saisi pour » la complète : quand le conseil syndical
enregistre le signalement d'un résident qui a téléphoné, l'auteur est celui qui
a **tapé**, et le propriétaire celui qui **a le problème**.

## Ce que ce test verrouille

🔴 **Le nom lu et le destinataire servi sont la MÊME personne.** C'est tout
l'enjeu : un écran qui annonce « Envoyer une copie à Martin » et qui envoie à
Dupont ment, et personne ne s'en aperçoit — le courriel part ailleurs, en
silence. Les deux viennent donc de `proprietaire()`, et d'elle seule.

⚠️ Le nom peut exister SANS adresse : une personne extérieure dont on ne connaît
que le nom. L'écran doit alors annoncer ce nom et n'envoyer aucune copie. Les
confondre ferait soit taire le nom, soit promettre un envoi qui n'a pas lieu.
"""
from __future__ import annotations

import pathlib

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.core import Utilisateur
from app.utils.copie_auteur import copie_demandee, proprietaire


class _Ticket:
    """Un porteur des seuls champs que `proprietaire` regarde.

    ⚠️ Volontairement PAS le modèle SQLModel : ce test porte sur la règle, pas
    sur la table. Un objet nu montre exactement de quoi la fonction dépend — et
    il échouerait si elle se mettait à lire autre chose.
    """

    def __init__(self, auteur_id=None, sp_user=None, sp_nom=None, sp_email=None):
        self.auteur_id = auteur_id
        self.saisi_pour_user_id = sp_user
        self.saisi_pour_nom = sp_nom
        self.saisi_pour_email = sp_email


@pytest.fixture()
def session():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        s.add(Utilisateur(id=1, prenom="Alice", nom="Martin", email="alice@x.fr",
                          mot_de_passe_hash="x", role="conseil_syndical"))
        s.add(Utilisateur(id=2, prenom="Bruno", nom="Dupont", email="bruno@x.fr",
                          mot_de_passe_hash="x", role="propriétaire"))
        s.commit()
        yield s


def test_sans_saisi_pour_le_proprietaire_est_l_AUTEUR(session):
    """Le cas courant, et celui des publications, événements et annonces : ces
    objets n'ont aucun champ « Saisi pour », et traversent la fonction sans que
    rien ne change pour eux."""
    nom, email = proprietaire(session, _Ticket(auteur_id=1))
    assert nom == "Alice MARTIN"
    assert email == "alice@x.fr"


def test_un_resident_INSCRIT_se_substitue_a_l_auteur(session):
    """🔴 Le cœur de la demande. Alice (CS) saisit pour Bruno : c'est Bruno que
    le fil nomme, et Bruno qui reçoit la copie."""
    nom, email = proprietaire(session, _Ticket(auteur_id=1, sp_user=2))
    assert nom == "Bruno DUPONT"
    assert email == "bruno@x.fr"


def test_une_personne_EXTERIEURE_se_substitue_aussi(session):
    """Le second cas : personne d'inscrit, seulement un nom et une adresse
    saisis. Ils priment sur l'auteur de la même façon."""
    nom, email = proprietaire(
        session, _Ticket(auteur_id=1, sp_nom="Paul EXTERNE", sp_email="paul@dehors.fr")
    )
    assert nom == "Paul EXTERNE"
    assert email == "paul@dehors.fr"


def test_un_nom_SANS_adresse_reste_un_nom(session):
    """⚠️ Le cas qui distingue les deux questions : on sait QUI, on ne sait pas
    OÙ. L'écran doit nommer cette personne — la taire au motif qu'on ne peut pas
    lui écrire reviendrait à afficher l'auteur, donc quelqu'un d'autre."""
    nom, email = proprietaire(session, _Ticket(auteur_id=1, sp_nom="Paul EXTERNE"))
    assert nom == "Paul EXTERNE"
    assert email is None


def test_un_saisi_pour_INTROUVABLE_retombe_sur_l_auteur(session):
    """Le compte a été supprimé depuis la saisie. On ne laisse pas le ticket sans
    propriétaire : l'auteur reprend la place, et la copie part quand même."""
    nom, email = proprietaire(session, _Ticket(auteur_id=1, sp_user=999))
    assert nom == "Alice MARTIN"
    assert email == "alice@x.fr"


def test_la_COPIE_part_au_saisi_pour_et_non_a_l_auteur(session):
    """🔴 Le test qui relie les deux moitiés : ce que l'écran annonce et ce que
    le serveur envoie doivent désigner la même personne.

    Vérifié sur la version fautive : avant le 12/09, cette copie partait à
    `alice@x.fr` — l'adresse de celle qui avait tapé."""
    bcc = copie_demandee(session, _Ticket(auteur_id=1, sp_user=2), [], demandee=True)
    assert bcc == ["bruno@x.fr"]


def test_la_copie_n_est_pas_DOUBLEE_quand_le_proprietaire_est_deja_servi(session):
    """La déduplication vaut pour le propriétaire comme elle valait pour
    l'auteur : un résident déjà destinataire principal ne reçoit pas deux fois le
    même courriel."""
    bcc = copie_demandee(
        session, _Ticket(auteur_id=1, sp_user=2), ["BRUNO@X.FR"], demandee=True
    )
    assert bcc is None


def test_le_FIL_et_la_COPIE_lisent_la_MEME_fonction():
    """⚠️ Garde-fou statique, et c'est lui qui empêche la dérive silencieuse : si
    le fil recalculait le nom de son côté, l'écran pourrait annoncer une personne
    et le courriel partir à une autre — sans qu'aucun test de valeur ne le voie,
    puisque les deux seraient « corrects » séparément."""
    flux = (pathlib.Path(__file__).resolve().parents[1]
            / "app" / "routers" / "flux" / "tickets.py").read_text(encoding="utf-8")
    assert "proprietaire(" in flux, (
        "le fil des tickets doit nommer le propriétaire par `copie_auteur.proprietaire`"
    )
    assert "auteur_nom(ctx.session, tk.auteur_id)" not in flux, (
        "le fil ne doit plus nommer l'auteur directement : le « Saisi pour » prime"
    )
