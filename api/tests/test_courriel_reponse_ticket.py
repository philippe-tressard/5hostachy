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
    GenreCivilite,
    MembreSyndic,
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


def test_le_sujet_rattache_en_REPLI_quand_le_jeton_manque():
    """🔴 REVIREMENT du 05/09/2026 — et il a une raison, pas une lassitude.

    Ce test disait l'inverse : « le sujet ne rattache JAMAIS un ticket », parce
    qu'un sujet se réécrit et se falsifie. Le raisonnement était bon, sur une
    hypothèse fausse — *que l'adresse à jeton achemine*. Elle n'achemine pas :
    *« cette adresse pour le suivi du syndic ne semble pas marcher »*.

    Une voie sûre qui ne transporte rien ne protège personne : elle perd la
    réponse du syndic, en silence. Le sujet devient donc un REPLI — jamais le
    premier choix (voir le test suivant), et payé par un contrôle que le jeton
    n'exigeait pas (`correspondant_du_ticket`).
    """
    v = examiner({"From": "gestion@syndic.fr", "To": "noreply@5hostachy.fr",
                  "Subject": "Re: Ticket #TK-482910 — Fuite au 3e",
                  "Authentication-Results": _AUTH_OK},
                 recu_le=datetime(2026, 9, 3))
    assert v.decision == ACCEPTE
    assert v.numero == "TK-482910"
    assert v.jeton is None


def test_le_jeton_PRIME_toujours_sur_le_sujet():
    """L'adresse prouve, le sujet désigne : le second ne doit jamais l'emporter.

    Un fil transféré porte souvent l'ancien sujet et la nouvelle adresse. Lire
    les deux ferait dépendre le rattachement de l'ordre des tests.
    """
    jeton = nouveau_jeton()
    v = examiner({"From": "gestion@syndic.fr",
                  "To": f"tickets+{jeton}@5hostachy.fr",
                  "Subject": "Re: Ticket #TK-000001 — un AUTRE dossier",
                  "Authentication-Results": _AUTH_OK},
                 recu_le=datetime(2026, 9, 3))
    assert v.jeton == jeton
    assert v.numero is None, "le sujet ne doit même pas être lu quand le jeton est là"


def test_un_numero_sans_le_mot_ticket_ne_rattache_rien():
    """Le motif exige « Ticket » devant : sinon une référence quelconque —
    facture, commande, lot — rattacherait un message au hasard.
    """
    v = examiner({"From": "quelquun@ailleurs.fr", "To": "noreply@5hostachy.fr",
                  "Subject": "Re: votre facture TK-482910",
                  "Authentication-Results": _AUTH_OK},
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
