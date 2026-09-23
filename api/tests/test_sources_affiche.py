"""Ce qu'une affiche de hall peut reprendre — et surtout ce qu'elle ne peut PAS.

## Ce qui a été demandé (10/09/2026)

*« Permet la génération d'une affiche à partir de n'importe quelle publication
incluse dans le fil d'actualité, quel que soit le type »*, puis : *« je ne vois
pas la présélection de toutes les publications, tickets etc. »*.

Le sélecteur ne proposait que des `Publication`. Le fil, lui, agrège trois
familles — deux depuis le 23/09/2026 : une actualité EST une affaire de
catégorie « Actualité » (#1091, lot 4), et se reprend comme telle.

## 🔴 Pourquoi ce test, et pas seulement le code

L'ouverture porte un risque qui n'existait pas avant : **une affiche de hall est
lue par tout le monde**, y compris par des gens à qui l'objet d'origine est
fermé. Reprendre un ticket confidentiel — refermé sur son auteur et le conseil
syndical — le publierait au mur du hall. Rien à l'écran ne le rattraperait, et le
défaut ne se verrait qu'une fois l'affiche imprimée et posée.

C'est une règle de sécurité, donc elle se teste, et elle se teste sur le
**comportement** : ce que la fonction rend, pas ce qu'elle déclare.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.core import Ticket
from app.models.evenement import Evenement
from app.utils.sources_affiche import FENETRE_JOURS, prefill_source, sources_disponibles


@pytest.fixture()
def session():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        yield s


_numero = [0]


def _ticket(session, titre, **kw):
    #  `numero` est attribué par le routeur (compteur annuel) : ici on le pose,
    #  la contrainte NOT NULL n'ayant rien à voir avec ce qu'on mesure.
    _numero[0] += 1
    t = Ticket(titre=titre, description=titre, auteur_id=1,
               numero=f"T-{_numero[0]:04d}", **kw)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _actualite(session, titre, **kw):
    """Une affaire de catégorie « Actualité » — ce qu'était une publication."""
    kw.setdefault("perimetre_cible", '["résidence"]')
    return _ticket(session, titre, categorie="actualite", statut="publie", **kw)


def _evenement(session, titre, **kw):
    e = Evenement(titre=titre, description=titre, debut=datetime.utcnow(), auteur_id=1, **kw)
    session.add(e)
    session.commit()
    session.refresh(e)
    return e


def test_actualites_affaires_et_evenements_sont_proposes(session):
    """C'est la demande : tout ce que le fil agrège, le sélecteur le propose.

    L'actualité est une affaire depuis le 23/09/2026 : elle vient par la famille
    des affaires, mais se présente toujours comme une actualité.
    """
    _actualite(session, "Une actualité")
    _ticket(session, "Un ticket")
    _evenement(session, "Un événement")

    familles = {s.titre: s.famille for s in sources_disponibles(session)}
    assert familles == {
        "Une actualité": "Actualité", "Un ticket": "Affaire", "Un événement": "Événement",
    }, f"obtenu {familles}"


def test_un_contenu_CONFIDENTIEL_n_est_jamais_proposé(session):
    """🔴 Le point de sécurité de ce lot.

    Une affiche de hall est lue par TOUT LE MONDE. Un ticket refermé sur son
    auteur et le CS ne peut pas devenir une affiche : ce serait publier au mur ce
    qu'on a explicitement fermé.
    """
    _actualite(session, "Actualité confidentielle", confidentiel=True)
    _ticket(session, "Ticket confidentiel", confidentiel=True)
    _actualite(session, "Actualité ouverte")

    titres = {s.titre for s in sources_disponibles(session)}
    assert titres == {"Actualité ouverte"}, f"obtenu {titres}"


def test_une_publication_RESERVEE_AU_CS_n_est_pas_proposée(session):
    """🛡️ Confirmé à l'écran : « les publications confidentielles ne sont bien
    sûr pas affichées, ou celles qui sont réservées au Conseil Syndical ».

    ⚠️ DEUX mécanismes, pas un : `confidentiel` restreint la lecture au périmètre
    visé, `public_cible` désigne à qui l'on parle. Ils se combinent en ET (#347),
    et ne filtrer que le premier laissait passer une publication marquée 🛡️.
    """
    import json

    _actualite(session, "Pour le CS", public_cible=json.dumps(["conseil_syndical"]))
    _actualite(session, "Pour tout le monde")

    assert {s.titre for s in sources_disponibles(session)} == {"Pour tout le monde"}


def test_une_actualite_RESERVEE_AU_PERIMETRE_n_est_pas_proposee(session):
    """🔒 Un hall se lit sans badge d'accès : ce que l'Accès referme sur un
    bâtiment n'y va pas. La génération directe le refusait déjà ; la liste des
    reprenables, non — deux écritures d'une même règle, et l'une laissait
    passer ce que l'autre refusait (#1091, lot 4)."""
    import json

    _actualite(session, "Bâtiment 1 seulement", reserve_perimetre=True,
               perimetre_cible=json.dumps(["bat:1"]))
    _actualite(session, "Pour tout le monde")

    assert {s.titre for s in sources_disponibles(session)} == {"Pour tout le monde"}


def test_le_prefill_REFUSE_ce_qui_n_est_pas_proposé(session):
    """La liste et le pré-remplissage appliquent la MÊME règle.

    Sans cela, l'écran cacherait l'élément et l'API le servirait quand même — le
    contrôle vivrait alors dans l'affichage, ce qui n'a jamais protégé personne
    (`standards/03` §1).
    """
    ferme = _ticket(session, "Ticket confidentiel", confidentiel=True)
    assert prefill_source(session, "ticket", ferme.id) is None

    ouvert = _ticket(session, "Ticket ouvert")
    champs = prefill_source(session, "ticket", ouvert.id)
    assert champs is not None
    assert champs["titre"] == "Ticket ouvert"


def test_une_actualite_archivee_reste_dehors(session):
    _actualite(session, "Archivée", archive_manuel=True)
    _actualite(session, "Publiée")

    assert {s.titre for s in sources_disponibles(session)} == {"Publiée"}


def test_les_EPINGLES_viennent_en_tête(session):
    """Épingler dit « ceci reste d'actualité » — c'est exactement ce qu'on
    affiche au hall. Trier par date seule le noyait."""
    _actualite(session, "Récente")
    ancienne = _actualite(session, "Ancienne épinglée", epingle=True)
    ancienne.cree_le = datetime.utcnow() - timedelta(days=180)
    session.add(ancienne)
    session.commit()

    assert [s.titre for s in sources_disponibles(session)][0] == "Ancienne épinglée"


def test_hors_fenêtre_du_fil_un_ticket_disparaît(session):
    vieux = _ticket(session, "Vieux ticket")
    vieux.cree_le = datetime.utcnow() - timedelta(days=FENETRE_JOURS + 5)
    session.add(vieux)
    session.commit()

    assert sources_disponibles(session) == []


def test_la_FENETRE_ne_diverge_pas_de_celle_du_fil():
    """🔴 La valeur est recopiée depuis `routers/flux` — l'importer créerait un
    cycle. Deux copies divergent au premier ajustement, et le sélecteur
    proposerait alors des éléments que le fil n'affiche plus (ou l'inverse)."""
    import re
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "routers" / "flux" / "__init__.py"
              ).read_text(encoding="utf-8")
    trouve = re.search(r"_FENETRE_JOURS\s*=\s*(\d+)", source)
    assert trouve, "Cas zéro : _FENETRE_JOURS introuvable dans routers/flux — contrôle inopérant."
    assert int(trouve.group(1)) == FENETRE_JOURS, (
        f"le fil retient {trouve.group(1)} jours, les sources d'affiche {FENETRE_JOURS}"
    )


# ── Le PÉRIMÈTRE, famille par famille ───────────────────────────────────────


def test_le_perimetre_est_repris_dans_chaque_famille(session):
    """🔴 Deux parseurs, et ils ne sont pas interchangeables.

    Un événement porte `perimetre` en TEXTE (« parking,cave ») ; publications et
    tickets portent `perimetre_cible` en JSON. Appeler le parseur JSON sur du
    texte ne lève pas — il retombe sur le périmètre par DÉFAUT. L'affiche
    héritait alors de « résidence » au lieu du bâtiment visé, et rien ne le
    disait : un défaut qui rend une valeur plausible ne se voit qu'à l'usage
    (signalé à l'écran le 11/09/2026).
    """
    import json

    pub = _actualite(session, "Actualité", perimetre_cible=json.dumps(["bat:1"]))
    tk = _ticket(session, "Ticket", perimetre_cible=json.dumps(["bat:3"]))
    ev = _evenement(session, "Événement", perimetre="parking,cave")

    assert prefill_source(session, "ticket", pub.id)["perimetre_cible"] == ["bat:1"]
    assert prefill_source(session, "ticket", tk.id)["perimetre_cible"] == ["bat:3"]
    assert prefill_source(session, "evenement", ev.id)["perimetre_cible"] == ["parking", "cave"], (
        "l'événement retombe sur le périmètre par défaut — c'est le parseur JSON "
        "appliqué à une chaîne texte"
    )
