r"""Répondre à un ticket par courriel — la décision, éprouvée sur des messages forgés.

## 🔴 Ce que ce fichier protège (#703)

**SMTP n'authentifie pas l'expéditeur.** N'importe qui peut écrire à
`noreply@5hostachy.fr` en mettant l'adresse du syndic dans le `From:`. Sans
vérification, son message deviendrait un commentaire officiel sur un ticket,
visible des résidents, **signé du syndic**.

C'est le seul endroit du site où un texte venu de l'extérieur, écrit par un
inconnu, peut atterrir dans une donnée que d'autres liront comme officielle. La
moitié des cas ci-dessous sont donc des messages **hostiles** : c'est la seule
manière de vérifier un filtre.

## Pourquoi la décision est PURE, et testée ici sans IMAP

`courriel_ingestion.examiner` ne touche ni au réseau ni à la base : elle reçoit
des en-têtes et rend un verdict. On peut donc lui présenter le message qu'on
veut, y compris ceux qu'aucune boîte réelle ne produirait.

Le dépôt a payé l'inverse : *« je testais la décision, pas le tuyau qui la
nourrit »* (check-reliability, 11/08/2026). Ici les deux sont séparés — et
`traiter()` est éprouvée en base, sans IMAP non plus.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    Notification,
    StatutTicket,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.models.courriel import RelanceCourriel
from app.utils.courriel_boite import traiter
from app.utils.courriel_entrant import (
    adresse_de_reponse,
    domaine_de,
    jeton_dans,
    nouveau_jeton,
)
from app.utils.courriel_ingestion import ACCEPTE, IGNORE, REFUSE, RELANCE, examiner
from tests.purge_test import purger_ligne

_AUTH_OK = "mx.ovh.net; spf=pass smtp.mailfrom=syndic.fr; dkim=pass; dmarc=pass"


def _entetes(jeton: str, *, de: str = "gestion@syndic.fr", auth: str | None = _AUTH_OK) -> dict:
    entetes = {"From": de, "To": adresse_de_reponse(jeton, "5hostachy.fr"), "Subject": "Re: ticket"}
    if auth is not None:
        entetes["Authentication-Results"] = auth
    return entetes


# ── Le jeton ──────────────────────────────────────────────────────────────────

def test_deux_jetons_ne_se_ressemblent_pas():
    """Un jeton dérivé de l'identifiant se devinerait ; celui-ci se tire au sort.

    Vérifié sur un lot, pas sur deux : deux tirages identiques par malchance sont
    improbables, mais un générateur cassé rendrait la même valeur à chaque appel
    et deux comparaisons suffiraient à le manquer une fois sur deux.
    """
    jetons = {nouveau_jeton() for _ in range(200)}
    assert len(jetons) == 200
    assert all(len(j) == 32 and all(c in "0123456789abcdef" for c in j) for j in jetons)


def test_le_jeton_se_relit_dans_les_en_tetes_qui_le_portent():
    jeton = nouveau_jeton()
    adresse = adresse_de_reponse(jeton, "5hostachy.fr")
    assert jeton_dans(adresse) == jeton
    assert jeton_dans(f'Conseil syndical <{adresse.upper()}>') == jeton
    assert jeton_dans(None, "", "autre@ailleurs.fr") is None
    #  Une adresse trop courte n'est pas un jeton tronqué acceptable.
    assert jeton_dans("tickets+abc@5hostachy.fr") is None


def test_le_domaine_vient_de_l_adresse_d_envoi_ou_de_rien():
    assert domaine_de("noreply@5hostachy.fr") == "5hostachy.fr"
    assert domaine_de("Nom <NOREPLY@5Hostachy.FR>") == "5hostachy.fr"
    assert domaine_de("") == "", "sans domaine, on ne fabrique pas d'adresse"
    assert domaine_de("adresse-sans-arobase") == ""


# ── 🔴 L'authentification ─────────────────────────────────────────────────────

def test_un_message_authentifie_est_accepte():
    v = examiner(_entetes(nouveau_jeton()), recu_le=datetime(2026, 9, 3))
    assert v.decision == ACCEPTE


@pytest.mark.parametrize("auth, ce_qui_manque", [
    (None, "aucun en-tête de vérification"),
    ("mx.ovh.net; spf=pass; dkim=fail; dmarc=fail", "DKIM et DMARC"),
    ("mx.ovh.net; spf=softfail; dkim=pass; dmarc=pass", "SPF"),
    ("mx.ovh.net; dmarc=pass", "SPF et DKIM"),
    ("", "en-tête vide"),
])
def test_un_message_NON_authentifie_est_refuse(auth, ce_qui_manque):
    """🔴 Le cœur du fichier — cinq façons d'usurper, cinq refus.

    Le cas `None` est le plus important et le moins évident : un message sans
    `Authentication-Results` n'a pas *échoué*, il n'a **pas été vérifié**. Le
    traiter comme un succès reviendrait à faire confiance à tout message dont
    l'attaquant aurait simplement omis l'en-tête.
    """
    v = examiner(_entetes(nouveau_jeton(), auth=auth), recu_le=datetime(2026, 9, 3))
    assert v.decision == REFUSE, f"accepté alors que manque {ce_qui_manque}"
    assert v.motif, "un refus sans motif est un silence"


def test_un_message_sans_rapport_est_IGNORE_et_non_refuse():
    """La nuance qui évite de noyer le conseil syndical.

    Un prospectus arrivé dans la boîte n'est pas une tentative d'usurpation :
    le confondre avec un refus produirait une notification par publicité reçue,
    et le filtre deviendrait lui-même la nuisance. On finirait par ne plus le lire.
    """
    v = examiner({"From": "pub@ailleurs.fr", "To": "noreply@5hostachy.fr"},
                 recu_le=datetime(2026, 9, 3))
    assert v.decision == IGNORE


def test_le_sujet_ne_rattache_JAMAIS_un_ticket():
    """Un sujet se réécrit, se traduit, se tronque — et se falsifie.

    C'était la troisième voie envisagée, et elle est écartée : accepter
    « Re: [#TK-0042] » donnerait le moyen d'écrire sur n'importe quel ticket en
    connaissant son numéro, qui figure dans tous les courriels déjà envoyés.
    """
    v = examiner({"From": "faux@ailleurs.fr", "To": "noreply@5hostachy.fr",
                  "Subject": "Re: [#TK-0042] fuite", "Authentication-Results": _AUTH_OK},
                 recu_le=datetime(2026, 9, 3))
    assert v.decision == IGNORE


# ── La date plancher ──────────────────────────────────────────────────────────

def test_les_messages_anterieurs_au_2_septembre_sont_ignores():
    """Arbitrage du 02/09/2026 : sans plancher, la première relève déverserait
    des mois d'archives dans les tickets.
    """
    v = examiner(_entetes(nouveau_jeton()), recu_le=datetime(2026, 8, 31))
    assert v.decision == IGNORE
    v = examiner(_entetes(nouveau_jeton()), recu_le=datetime(2026, 9, 2, 0, 1))
    assert v.decision == ACCEPTE


def test_la_date_est_examinee_AVANT_le_reste():
    """Un vieux message NON authentifié ne doit pas notifier le conseil syndical.

    Si l'ordre était inversé, la première relève d'une boîte de plusieurs mois
    produirait une notification par ancien message douteux — un réveil brutal
    pour une fonction qu'on vient d'activer.
    """
    v = examiner(_entetes(nouveau_jeton(), auth=None), recu_le=datetime(2026, 1, 1))
    assert v.decision == IGNORE


# ── Ce qui est écrit en base ──────────────────────────────────────────────────

@pytest.fixture()
def scene():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        syndic = Utilisateur(
            email=f"syndic-{uuid.uuid4().hex[:8]}@syndic.fr", mot_de_passe_hash="x",
            prenom="G", nom="S", roles_json="résident", actif=True,
        )
        cs = Utilisateur(
            email=f"cs-{uuid.uuid4().hex[:8]}@exemple.test", mot_de_passe_hash="x",
            prenom="C", nom="S", roles_json="conseil_syndical", actif=True,
        )
        session.add(syndic); session.add(cs); session.commit()
        session.refresh(syndic); session.refresh(cs)
        ticket = Ticket(
            numero=f"TK-{uuid.uuid4().hex[:6]}", titre="Fuite", description="…",
            categorie="panne", auteur_id=cs.id, statut=StatutTicket.ouvert,
            jeton_courriel=nouveau_jeton(),
        )
        session.add(ticket); session.commit(); session.refresh(ticket)
        yield session, ticket, syndic, cs
        for evol in session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == ticket.id)
        ).all():
            purger_ligne(session, TicketEvolution, evol.id)
        for notif in session.exec(
            select(Notification).where(Notification.destinataire_id == cs.id)
        ).all():
            purger_ligne(session, Notification, notif.id)
        purger_ligne(session, Ticket, ticket.id)
        purger_ligne(session, Utilisateur, syndic.id)
        purger_ligne(session, Utilisateur, cs.id)
        session.commit()


def _evolutions(session, ticket):
    return session.exec(
        select(TicketEvolution).where(TicketEvolution.ticket_id == ticket.id)
    ).all()


def _notifs(session, user):
    return session.exec(
        select(Notification).where(Notification.destinataire_id == user.id)
    ).all()


def test_une_reponse_authentifiee_rejoint_le_fil(scene):
    session, ticket, syndic, _cs = scene
    decision = traiter(
        session, _entetes(ticket.jeton_courriel, de=syndic.email),
        "Nous intervenons jeudi.", datetime(2026, 9, 3),
    )
    assert decision == ACCEPTE
    evols = _evolutions(session, ticket)
    assert len(evols) == 1
    assert evols[0].contenu == "Nous intervenons jeudi."
    assert evols[0].auteur_id == syndic.id, "l'entrée doit être signée de son auteur réel"


def test_un_message_USURPE_n_ecrit_RIEN_et_previent_le_conseil(scene):
    """🔴 Le scénario complet, de bout en bout.

    Quelqu'un se fait passer pour le syndic. Deux choses doivent arriver, et les
    deux comptent autant : **rien** dans le ticket, et **quelqu'un est prévenu**.
    Le silence est ce qui rend un filtre dangereux — un filtre qu'on n'entend
    jamais finit par être cru parfait.
    """
    session, ticket, syndic, cs = scene
    decision = traiter(
        session, _entetes(ticket.jeton_courriel, de=syndic.email, auth=None),
        "Le problème est réglé, fermez le ticket.", datetime(2026, 9, 3),
    )
    assert decision == REFUSE
    assert _evolutions(session, ticket) == [], "un message usurpé a été écrit dans le fil"
    notifs = _notifs(session, cs)
    assert notifs, "personne n'a été prévenu : le refus est silencieux"
    assert ticket.numero in notifs[0].titre
    #  Le corps doit porter la RAISON, pas seulement l'alerte : une notification
    #  qui dit « un message a été refusé » sans dire pourquoi renvoie le lecteur
    #  à la boîte pour comprendre, et il n'ira pas.
    assert syndic.email in notifs[0].corps
    assert "attribué avec certitude" in notifs[0].corps


def test_un_expediteur_authentifie_SANS_COMPTE_ne_signe_rien(scene):
    """`TicketEvolution.auteur_id` est obligatoire : pas de compte, pas d'entrée.

    L'alternative — un compte de service — ferait signer « 5Hostachy » un texte
    écrit par un tiers. Le conseil syndical est prévenu et recopie s'il veut.
    """
    session, ticket, _syndic, cs = scene
    decision = traiter(
        session, _entetes(ticket.jeton_courriel, de="inconnu@syndic.fr"),
        "Bonjour, c'est noté.", datetime(2026, 9, 3),
    )
    assert decision == REFUSE
    assert _evolutions(session, ticket) == []
    assert any("compte" in n.corps for n in _notifs(session, cs))


def test_un_jeton_FORGE_ne_touche_a_aucun_ticket(scene):
    """Deviner un jeton ne mène nulle part — et ne réveille personne."""
    session, ticket, syndic, cs = scene
    decision = traiter(
        session, _entetes(nouveau_jeton(), de=syndic.email),
        "Fermez ce ticket.", datetime(2026, 9, 3),
    )
    assert decision == IGNORE
    assert _evolutions(session, ticket) == []
    assert _notifs(session, cs) == [], "un jeton forgé ne doit pas produire de bruit"


def test_la_citation_du_message_precedent_n_entre_pas_dans_le_fil(scene):
    """Sans ça, chaque échange recopierait tout l'échange dans le ticket."""
    session, ticket, syndic, _cs = scene
    traiter(
        session, _entetes(ticket.jeton_courriel, de=syndic.email),
        "C'est noté.\n\nLe 2 septembre, Conseil syndical a écrit :\n> Bonjour,\n> merci de…",
        datetime(2026, 9, 3),
    )
    evols = _evolutions(session, ticket)
    assert len(evols) == 1
    assert evols[0].contenu == "C'est noté."


# ── 🔴 La relance GROUPÉE : un envoi, N tickets, aucune réponse à ventiler ────

def test_une_reponse_a_une_relance_groupee_va_au_CONSEIL_et_dans_aucun_fil(scene):
    """🔴 La stratégie du 03/09/2026, éprouvée de bout en bout.

    Question posée : *« quelle stratégie si un retour de mail traite de plusieurs
    tickets relancés ? »*. Avant ce lot, la relance partait SANS `Reply-To` — un
    seul message pour N dossiers n'a pas de jeton de ticket — et la réponse du
    syndic était ignorée **en silence**. Le seul cas où l'on perdait une
    information qu'on avait soi-même sollicitée.

    Deux choses doivent arriver, et les deux comptent autant :

    - **rien dans les fils** : « pour le TK-123 on intervient jeudi, le TK-456 est
      clos » recopié dans quatre fils serait faux dans trois d'entre eux ;
    - **le conseil reçoit le texte ENTIER, avec la liste des dossiers** — il est
      déjà en copie de la relance, c'est le bon récepteur.
    """
    import json as _json

    session, ticket, syndic, cs = scene
    #  Un second ticket : une relance GROUPÉE en porte plusieurs, et le test ne
    #  distinguerait rien s'il n'y en avait qu'un.
    second = Ticket(
        numero=f"TK-{uuid.uuid4().hex[:6]}", titre="Autre", description="…",
        categorie="panne", auteur_id=cs.id, statut=StatutTicket.ouvert,
        jeton_courriel=nouveau_jeton(),
    )
    session.add(second)
    session.commit()
    session.refresh(second)
    vises = [ticket, second]
    relance = RelanceCourriel(
        jeton=nouveau_jeton(),
        tickets_json=_json.dumps([t.id for t in vises]),
    )
    session.add(relance)
    session.commit()

    decision = traiter(
        session, _entetes(relance.jeton, de=syndic.email),
        "Pour le premier on intervient jeudi ; le second est clos.",
        datetime(2026, 9, 3),
    )
    try:
        #  RELANCE et non REFUSE (04/09/2026) : rien n'a été refusé — la
        #  réponse est reçue, conservée et notifiée, seulement pas ventilée.
        #  Le journal disait « refusées=1 » sur un traitement réussi.
        assert decision == RELANCE, "une réponse groupée ne s'écrit pas dans un fil"
        for t in vises:
            assert _evolutions(session, t) == [], (
                f"la réponse a été recopiée dans le fil de {t.numero} — elle parle "
                "de plusieurs dossiers, elle y serait fausse"
            )
        notifs = _notifs(session, cs)
        assert notifs, "personne n'a été prévenu : la réponse est perdue"
        corps = notifs[0].corps
        assert "intervient jeudi" in corps, "le texte du syndic n'est pas transmis"
        for t in vises:
            assert t.numero in corps, (
                "la notification ne dit pas quels dossiers étaient relancés — le "
                "conseil ne saurait pas où reporter"
            )
    finally:
        session.delete(relance)
        for evol in session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == second.id)
        ).all():
            session.delete(evol)
        session.delete(second)
        session.commit()


def test_un_message_authentifie_qui_repond_SANS_jeton_ne_se_perd_plus(scene):
    """Le second trou que la question a mis au jour.

    Un message authentifié qui cite une référence — donc qui répond visiblement à
    un envoi du site — mais qu'aucun jeton ne rattache était traité comme un
    prospectus : `IGNORE`, en silence. La règle qui évite de notifier le conseil
    pour chaque publicité était trop large, et elle avalait les vraies réponses :
    un fil transféré, un client qui réécrit le destinataire, une passerelle qui
    perd le `To`.
    """
    session, _ticket, syndic, cs = scene
    entetes = {
        "From": syndic.email,
        "To": "noreply@5hostachy.fr",
        "In-Reply-To": "<TK-000000.abc@5hostachy.fr>",
        "Authentication-Results": _AUTH_OK,
    }
    decision = traiter(session, entetes, "C'est noté.", datetime(2026, 9, 3))
    assert decision == REFUSE
    notifs = _notifs(session, cs)
    assert notifs, "une réponse authentifiée non rattachable disparaît encore"
    assert "rien ne permet de dire à quel ticket" in notifs[0].corps


def test_un_prospectus_ne_reveille_toujours_personne(scene):
    """La contrepartie, sans laquelle le remède serait pire que le mal.

    Si tout message non rattachable notifiait le conseil, la boîte deviendrait
    une source d'alertes sur des publicités — et le filtre finirait par ne plus
    être lu. Un message sans référence ET sans jeton reste ignoré.
    """
    session, _ticket, _syndic, cs = scene
    decision = traiter(
        session,
        {"From": "pub@ailleurs.fr", "To": "noreply@5hostachy.fr",
         "Authentication-Results": _AUTH_OK},
        "Profitez de nos offres !", datetime(2026, 9, 3),
    )
    assert decision == IGNORE
    assert _notifs(session, cs) == []


def test_le_syndic_peut_repondre_PLUSIEURS_FOIS_a_la_meme_relance(scene):
    """Signalé le 03/09/2026 : *« le syndic peut peut-être faire plusieurs mails »*.

    C'est le cas normal, pas l'exception : un message par dossier, ou une
    précision le lendemain. Le jeton ne s'épuise donc pas — il n'est ni consommé,
    ni daté, ni à usage unique.

    ⚠️ Et chaque réponse produit sa PROPRE notification. Dédoublonner serait le
    défaut inverse : la deuxième réponse est une information neuve, et la taire
    au motif qu'on a déjà prévenu ferait exactement ce que ce lot corrige —
    perdre une réponse qu'on a sollicitée.
    """
    import json as _json

    session, ticket, syndic, cs = scene
    relance = RelanceCourriel(
        jeton=nouveau_jeton(), tickets_json=_json.dumps([ticket.id])
    )
    session.add(relance)
    session.commit()
    try:
        for texte in ("Le premier point est réglé.", "Pour le second, on passe lundi."):
            assert traiter(
                session, _entetes(relance.jeton, de=syndic.email), texte,
                datetime(2026, 9, 3),
            ) == RELANCE

        corps = [n.corps for n in _notifs(session, cs)]
        assert len(corps) == 2, (
            f"{len(corps)} notification(s) pour deux réponses : la seconde a été "
            "dédoublonnée, donc perdue"
        )
        assert any("réglé" in c for c in corps)
        assert any("lundi" in c for c in corps)
        assert _evolutions(session, ticket) == [], "toujours rien dans les fils"
    finally:
        session.delete(relance)
        session.commit()
