"""Une entrée d'Historique notifie **ce qu'elle raconte**, pas l'événement porteur.

## Pourquoi ce garde-fou (18/08/2026)

Le lot de la veille a ouvert la section Diffusion du suivi d'un événement, et l'a
câblée sur l'objet **porteur** au lieu de l'**entrée**. Résultat, signalé à
l'écran :

  • le groupe WhatsApp recevait la description de l'événement à chaque
    commentaire — donc le MÊME message, indéfiniment, jamais le suivi ;
  • aucune photo ne partait (`image_url=None` en dur), ni aucun lien ;
  • l'e-mail attachait les pièces de l'événement, jamais celles de l'entrée.

⚠️ **Aucun de ces trois défauts ne lève.** Le message part, l'e-mail arrive, les
journaux sont verts : ils sont simplement faux. C'est très exactement la classe
d'erreur qui a produit `'evenement' is undefined` le 28/07/2026 — un envoi en
tâche de fond n'a d'autre trace que ce qu'on est allé lui demander.

C'est aussi un défaut **prévisible** : ajouter un canal à une entité existante
invite à reprendre l'appel qui marche déjà, et l'appel qui marche parle de
l'objet. Le test décrit donc l'invariant, pas la correction : *ce qui part
raconte l'entrée*.

Il vérifie **le fait** — les arguments réellement empilés dans les tâches de
fond — et non le code de retour de l'endpoint (`standards/04` §14).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import ConfigSite, Evenement, RoleUtilisateur, TypeEvenement, Utilisateur
from app.routers.calendrier_courriels import notifier_canaux

COMMENTAIRE = "Le prestataire est passé, la vanne est remplacée."
DESCRIPTION_EVENEMENT = "<p>Coupure d'eau programmée dans le bâtiment C.</p>"


@pytest.fixture()
def contexte():
    """Un CS, un événement décrit, et WhatsApp activé en configuration."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = Utilisateur(
            email=f"cs-{uuid.uuid4().hex[:8]}@exemple.test",
            mot_de_passe_hash="x",
            prenom="Camille",
            nom="Sorel",
            role=RoleUtilisateur.conseil_syndical,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        ev = Evenement(
            titre="Remplacement de vanne",
            description=DESCRIPTION_EVENEMENT,
            type=TypeEvenement.travaux,
            debut=datetime(2026, 8, 20, 9, 0),
            perimetre='["bat:3"]',
            photos_urls='["/uploads/evenements/avant.jpg"]',
            fichiers_urls='["/uploads/evenements/devis.pdf"]',
            auteur_id=user.id,
        )
        session.add(ev)

        #  WhatsApp doit être *actif* : sinon `notifier_canaux` s'abstient et le
        #  test passerait sur une absence d'envoi — un vert qui ne prouve rien
        #  (`standards/04` §2, cas zéro).
        for cle, valeur in (
            ("whatsapp_enabled", "1"),
            ("whatsapp_api_url", "http://bridge.test"),
            ("whatsapp_api_key", "k"),
            ("whatsapp_group_jid", "g@g.us"),
            ("site_url", "https://5hostachy.test"),
        ):
            if not session.get(ConfigSite, cle):
                session.add(ConfigSite(cle=cle, valeur=valeur))
        session.commit()
        session.refresh(ev)

        yield session, ev, user

        session.delete(session.get(Evenement, ev.id))
        session.delete(session.get(Utilisateur, user.id))
        session.commit()


def _taches(bt: BackgroundTasks) -> list:
    return list(bt.tasks)


def _tache_whatsapp(bt: BackgroundTasks):
    for t in _taches(bt):
        if t.func.__name__ == "envoyer_whatsapp_avec_log":
            return t
    return None


def _tache_email(bt: BackgroundTasks):
    for t in _taches(bt):
        if t.func.__name__ == "send_email_group":
            return t
    return None


SUIVI = {"commentaire": COMMENTAIRE, "etat": "Prestataire"}
FICHIERS_SUIVI = '["/uploads/evenements/apres.jpg"]'


def test_whatsapp_du_suivi_porte_le_commentaire_et_pas_la_description(contexte):
    """Le défaut d'origine : `ev.description` partait à chaque commentaire."""
    session, ev, user = contexte
    bt = BackgroundTasks()
    notifier_canaux(
        ev, user, session, bt,
        whatsapp=True, suivi=SUIVI, fichiers_suivi=FICHIERS_SUIVI,
    )
    tache = _tache_whatsapp(bt)
    assert tache is not None, "aucun envoi WhatsApp empilé — le test ne prouverait rien"
    _titre, contenu, *_ = tache.args
    assert COMMENTAIRE in contenu, "le suivi n'est pas dans le message"
    assert "Coupure d'eau programmée" not in contenu, (
        "le message porte la description de l'ÉVÉNEMENT : le groupe recevrait le "
        "même texte à chaque entrée d'Historique."
    )
    assert "Prestataire" in contenu, "l'état atteint doit ouvrir le message"


def test_whatsapp_du_suivi_porte_sa_photo_et_un_lien(contexte):
    """`image_url` valait `None` en dur, et aucun lien n'était posé."""
    session, ev, user = contexte
    bt = BackgroundTasks()
    notifier_canaux(
        ev, user, session, bt,
        whatsapp=True, suivi=SUIVI, fichiers_suivi=FICHIERS_SUIVI,
    )
    tache = _tache_whatsapp(bt)
    assert tache is not None
    #  (titre, contenu, urgente, perimetre_cible, image_url, config)
    image_url = tache.args[4]
    assert image_url == "/uploads/evenements/apres.jpg", (
        f"photo du suivi non transmise (reçu {image_url!r}) — elle n'était pas "
        "refusée par le bridge, elle n'était jamais proposée."
    )
    lien = tache.kwargs.get("lien", "")
    assert lien.startswith("https://5hostachy.test"), f"lien absent ou relatif : {lien!r}"
    assert f"ev-{ev.id}" in lien, "le lien ne désigne pas CET événement"


def test_le_courriel_du_suivi_choisit_les_pieces_du_suivi(contexte, monkeypatch):
    """Les pièces attachées étaient celles de l'événement, jamais celles de l'entrée.

    ⚠️ Le test intercepte `chemins_locaux` au lieu de lire la liste finale, et ce
    n'est pas un raccourci : cette fonction résout `/app/uploads/…` sur le disque,
    un chemin qui n'existe sur aucun poste de développement. Elle y rend donc
    **toujours** `[]` — et l'assertion « le devis n'est pas joint » serait vraie
    quoi qu'on écrive dans le routeur. Un cas zéro, c'est-à-dire un test qui ne
    peut plus échouer (`standards/04` §2).

    Ce qu'on vérifie est la DÉCISION — quelle liste part à la résolution —, et
    c'est exactement là que se trouvait le défaut.
    """
    session, ev, user = contexte
    vus: list[list[str]] = []
    monkeypatch.setattr(
        "app.routers.calendrier_courriels.chemins_locaux",
        lambda urls: vus.append(list(urls)) or [],
    )
    bt = BackgroundTasks()
    notifier_canaux(
        ev, user, session, bt,
        cs=True, suivi=SUIVI, fichiers_suivi=FICHIERS_SUIVI,
    )
    assert vus, "`chemins_locaux` n'a pas été appelée — aucun courriel n'a été préparé"
    demandes = vus[0]
    assert demandes == ["/uploads/evenements/apres.jpg"], (
        f"le courriel du suivi demande {demandes!r} — ce sont les pièces de "
        "l'ÉVÉNEMENT, pas celles de l'entrée d'Historique."
    )


def test_le_courriel_d_une_creation_garde_les_pieces_de_l_affaire(contexte, monkeypatch):
    """L'autre moitié de l'invariant : sans suivi, l'affaire entière part."""
    session, ev, user = contexte
    vus: list[list[str]] = []
    monkeypatch.setattr(
        "app.routers.calendrier_courriels.chemins_locaux",
        lambda urls: vus.append(list(urls)) or [],
    )
    bt = BackgroundTasks()
    notifier_canaux(ev, user, session, bt, cs=True)
    assert vus, "aucun courriel préparé"
    assert vus[0] == [
        "/uploads/evenements/avant.jpg",
        "/uploads/evenements/devis.pdf",
    ]


def test_une_creation_continue_de_raconter_l_evenement(contexte):
    """L'invariant vaut dans les DEUX sens : sans suivi, rien ne change.

    Un correctif qui ne regarde qu'un cas déplace le défaut au lieu de le
    supprimer — c'est ce qui est arrivé deux fois à la galerie des annonces, où
    la condition a changé de victime sans disparaître (#338).
    """
    session, ev, user = contexte
    bt = BackgroundTasks()
    notifier_canaux(ev, user, session, bt, whatsapp=True)
    tache = _tache_whatsapp(bt)
    assert tache is not None
    titre, contenu, *_ = tache.args
    assert "Coupure d'eau programmée" in contenu
    assert ev.titre in titre
    assert tache.args[4] == "/uploads/evenements/avant.jpg", (
        "la création perdrait sa photo — elle en avait une"
    )


def test_le_perimetre_de_l_evenement_est_transmis(contexte):
    """Le message annonçait « Copropriété » quel que soit le périmètre réel.

    `perimetre_cible` valait `None` en dur, à côté d'`image_url`. Le bâtiment C
    devenait donc toute la copropriété dans l'en-tête du message.
    """
    session, ev, user = contexte
    bt = BackgroundTasks()
    notifier_canaux(ev, user, session, bt, whatsapp=True, suivi=SUIVI)
    tache = _tache_whatsapp(bt)
    assert tache is not None
    assert json.loads(tache.args[3]) == ["bat:3"]
