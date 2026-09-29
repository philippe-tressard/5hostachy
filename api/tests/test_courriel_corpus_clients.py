"""Le CORPUS des transferts — un cas par client de messagerie et par terminal (#1471).

Demandé le 30/09/2026 : *« rendre la détection plus robuste quel que soit le
type de terminal et le lecteur mail qui expédie le mail »*. Le premier transfert
réel avait été refusé deux fois : chaque client écrit le transfert à sa façon,
et le découpage n'en connaissait que trois.

Chaque cas transfère le MÊME fil — la réponse du syndic (29/09/2026, 14:31 à
Paris) qui cite le message de Jean Dupont (29/09/2026, 08:43) — tel que ce
client l'écrit. Un client de plus = une ligne de plus dans `CAS`, et le
découpage doit la passer. Noms et adresses fictifs (`standards/14`).
"""

from __future__ import annotations

import email
from datetime import datetime
from email.message import EmailMessage

import pytest

from app.utils.courriel_decodage import _corps_lisible, _sans_citation, transfert_dans
from app.utils.courriel_fil import messages_du_fil

SYNDIC = "gestion@syndic.test"
JEAN = "jean.dupont@exemple.test"
TEXTE_SYNDIC = "Nous lançons un ordre de service à l'électricien."
TEXTE_JEAN = "Le portillon électrique ne fonctionne plus."
#: Les deux envois, en UTC (Paris = UTC+2 en septembre).
A_14_31 = datetime(2026, 9, 29, 12, 31)
A_08_43 = datetime(2026, 9, 29, 6, 43)


def _cas(id_, corps, *, sujet="TR: RE: Portail", syndic=A_14_31, jean=A_08_43):
    return pytest.param(sujet, corps, syndic, jean, id=id_)


CAS = [
    _cas(
        "apple-mail-fr",  # Mail sur Mac, iPhone, iPad
        "Envoyé de mon iPhone\n\nDébut du message réexpédié :\n\n"
        f"De: Gestion Syndic <{SYNDIC}>\nObjet: RE: Portail\n"
        "Date: 29 septembre 2026 à 14:31:05 UTC+2\n"
        f"À: Jean Dupont <{JEAN}>\n\n{TEXTE_SYNDIC}\n\n"
        f"Le 29 sept. 2026 à 08:43, Jean Dupont <{JEAN}> a écrit :\n\n> {TEXTE_JEAN}\n"
        "> \n> Envoyé de mon iPhone\n",
        syndic=datetime(2026, 9, 29, 12, 31, 5),
    ),
    _cas(
        "apple-mail-en",
        "Begin forwarded message:\n\n"
        f"From: Gestion Syndic <{SYNDIC}>\nSubject: RE: Portail\n"
        "Date: September 29, 2026 at 2:31:05 PM GMT+2\n"
        f"To: Jean Dupont <{JEAN}>\n\n{TEXTE_SYNDIC}\n\n"
        f"On Sep 29, 2026, at 08:43, Jean Dupont <{JEAN}> wrote:\n\n> {TEXTE_JEAN}\n",
        sujet="Fwd: RE: Portail",
        syndic=datetime(2026, 9, 29, 12, 31, 5),
    ),
    _cas(
        "gmail-fr",  # web, Android, iOS
        "---------- Message transféré ---------\n"
        f"De : Gestion Syndic <{SYNDIC}>\nDate: mar. 29 sept. 2026 à 14:31\n"
        f"Subject: RE: Portail\nTo: Jean Dupont <{JEAN}>\n\n\n{TEXTE_SYNDIC}\n\n"
        f"Le mar. 29 sept. 2026 à 08:43, Jean Dupont <{JEAN}> a\nécrit :\n\n"
        f"> {TEXTE_JEAN}\n",
        sujet="Fwd: RE: Portail",
    ),
    _cas(
        "gmail-en",
        "---------- Forwarded message ---------\n"
        f"From: Gestion Syndic <{SYNDIC}>\nDate: Tue, Sep 29, 2026 at 2:31 PM\n"
        f"Subject: RE: Portail\nTo: Jean Dupont <{JEAN}>\n\n{TEXTE_SYNDIC}\n\n"
        f"On Tue, Sep 29, 2026 at 8:43 AM Jean Dupont <{JEAN}> wrote:\n\n> {TEXTE_JEAN}\n",
        sujet="Fwd: RE: Portail",
    ),
    _cas(
        "outlook-windows-fr",  # Outlook, nouvel Outlook, Mail pour Windows
        "________________________________\n"
        f"De : Gestion Syndic <{SYNDIC}>\nEnvoyé : mardi 29 septembre 2026 14:31\n"
        f"À : Jean Dupont <{JEAN}>\nObjet : RE: Portail\n\n{TEXTE_SYNDIC}\n\n"
        f"De : Jean Dupont <{JEAN}>\nEnvoyé : mardi 29 septembre 2026 08:43\n"
        f"À : Gestion Syndic <{SYNDIC}>\nObjet : Portail\n\n{TEXTE_JEAN}\n",
    ),
    _cas(
        "outlook-en",
        "-----Original Message-----\n"
        f"From: Gestion Syndic <{SYNDIC}>\nSent: Tuesday, September 29, 2026 2:31 PM\n"
        f"To: Jean Dupont <{JEAN}>\nSubject: RE: Portail\n\n{TEXTE_SYNDIC}\n\n"
        f"From: Jean Dupont <{JEAN}>\nSent: Tuesday, September 29, 2026 8:43 AM\n"
        f"To: Gestion Syndic <{SYNDIC}>\nSubject: Portail\n\n{TEXTE_JEAN}\n",
        sujet="FW: RE: Portail",
    ),
    _cas(
        "outlook-ancien-mailto",
        f"De : Gestion Syndic [mailto:{SYNDIC}]\nEnvoyé : mardi 29 septembre 2026 14:31\n"
        f"À : Jean Dupont\nObjet : RE: Portail\n\n{TEXTE_SYNDIC}\n\n"
        f"De : Jean Dupont [mailto:{JEAN}]\nEnvoyé : mardi 29 septembre 2026 08:43\n"
        f"Objet : Portail\n\n{TEXTE_JEAN}\n",
    ),
    _cas(
        "outlook-mobile",  # Outlook pour iOS et Android
        "Obtenir Outlook pour Android\n________________________________\n"
        f"De : Gestion Syndic <{SYNDIC}>\n"
        "Envoyé : Tuesday, September 29, 2026 2:31:00 PM\n"
        f"À : Jean Dupont <{JEAN}>\nObjet : RE: Portail\n\n{TEXTE_SYNDIC}\n\n"
        f"De : Jean Dupont <{JEAN}>\nEnvoyé : mardi, septembre 29, 2026 8:43:00 AM\n"
        f"Objet : Portail\n\n{TEXTE_JEAN}\n",
    ),
    _cas(
        "courrier-windows-10",
        "Envoyé à partir de Courrier pour Windows 10\n\n"
        f"De : Gestion Syndic<mailto:{SYNDIC}>\n"
        "Envoyé le :mardi 29 septembre 2026 14:31\n"
        f"À : Jean Dupont<mailto:{JEAN}>\nObjet :RE: Portail\n\n{TEXTE_SYNDIC}\n\n"
        f"De : Jean Dupont<mailto:{JEAN}>\nEnvoyé le :mardi 29 septembre 2026 08:43\n"
        f"Objet :Portail\n\n{TEXTE_JEAN}\n",
    ),
    _cas(
        "thunderbird-fr",  # l'objet et la date AVANT l'expéditeur
        "\n\n-------- Message transféré --------\n"
        "Sujet : \tRE: Portail\nDate : \tTue, 29 Sep 2026 14:31:00 +0200\n"
        f"De : \tGestion Syndic <{SYNDIC}>\nPour : \tJean Dupont <{JEAN}>\n\n\n\n"
        f"{TEXTE_SYNDIC}\n\nLe 29/09/2026 à 08:43, Jean Dupont a écrit :\n> {TEXTE_JEAN}\n",
        sujet="Fwd: RE: Portail",
    ),
    _cas(
        "thunderbird-en",
        "-------- Forwarded Message --------\n"
        "Subject: \tRE: Portail\nDate: \tTue, 29 Sep 2026 14:31:00 +0200\n"
        f"From: \tGestion Syndic <{SYNDIC}>\nTo: \tJean Dupont <{JEAN}>\n\n"
        f"{TEXTE_SYNDIC}\n\nOn 29/09/2026 08:43, Jean Dupont wrote:\n> {TEXTE_JEAN}\n",
        sujet="Fwd: RE: Portail",
    ),
    _cas(
        "yahoo-fr",
        "----- Message transféré -----\n"
        f"De : Gestion Syndic <{SYNDIC}>\nÀ : Jean Dupont <{JEAN}>\n"
        "Envoyé : mardi 29 septembre 2026 à 14:31:00 UTC+2\nObjet : RE: Portail\n\n"
        f"{TEXTE_SYNDIC}\n\n"
        f"Le mardi 29 septembre 2026 à 08:43:00 UTC+2, Jean Dupont <{JEAN}> a écrit :\n\n"
        f"{TEXTE_JEAN}\n",
        sujet="Fwd: RE: Portail",
    ),
    _cas(
        "orange-webmail",  # « Message du … » sans ligne « Date : »
        "\n\n> Message du 29/09/26 14:31\n"
        f'> De : "Gestion Syndic" <{SYNDIC}>\n'
        f'> A : "Jean Dupont" <{JEAN}>\n> Copie à : \n> Objet : RE: Portail\n>\n'
        f"> {TEXTE_SYNDIC}\n>\n> > Message du 29/09/26 08:43\n"
        f'> > De : "Jean Dupont" <{JEAN}>\n> > A : "Gestion Syndic" <{SYNDIC}>\n'
        f"> > Objet : Portail\n> >\n> > {TEXTE_JEAN}\n",
    ),
    _cas(
        "free-zimbra",
        "----- Mail transféré -----\n"
        f'De: "Gestion Syndic" <{SYNDIC}>\nÀ: "Jean Dupont" <{JEAN}>\n'
        "Envoyé: Mardi 29 Septembre 2026 14:31:00\nObjet: RE: Portail\n\n"
        f"{TEXTE_SYNDIC}\n\n----- Mail original -----\n"
        f'De: "Jean Dupont" <{JEAN}>\nÀ: "Gestion Syndic" <{SYNDIC}>\n'
        f"Envoyé: Mardi 29 Septembre 2026 08:43:00\nObjet: Portail\n\n{TEXTE_JEAN}\n",
    ),
    _cas(
        "samsung-email",  # le fuseau du téléphone, écrit
        "\n\n-------- Message d'origine --------\n"
        f"De : Gestion Syndic <{SYNDIC}>\nDate : 29/09/2026 14:31 (GMT+02:00)\n"
        f"À : Jean Dupont <{JEAN}>\nObjet : RE: Portail\n\n{TEXTE_SYNDIC}\n\n"
        "-------- Message d'origine --------\n"
        f"De : Jean Dupont <{JEAN}>\nDate : 29/09/2026 08:43 (GMT+02:00)\n"
        f"Objet : Portail\n\n{TEXTE_JEAN}\n",
    ),
    _cas(
        "proton",
        "------- Forwarded Message -------\n"
        f"From: Gestion Syndic <{SYNDIC}>\n"
        "Date: On Tuesday, September 29th, 2026 at 2:31 PM\n"
        f"Subject: RE: Portail\nTo: Jean Dupont <{JEAN}>\n\n{TEXTE_SYNDIC}\n\n"
        "------- Original Message -------\n"
        f"On Tuesday, September 29th, 2026 at 8:43 AM, Jean Dupont <{JEAN}> wrote:\n\n"
        f"> {TEXTE_JEAN}\n",
        sujet="Fwd: RE: Portail",
    ),
    _cas(
        "date-iso-et-pointee",
        "-------- Message d'origine --------\n"
        f"De : Gestion Syndic <{SYNDIC}>\nDate : 2026-09-29 14:31\n"
        f"Objet : RE: Portail\n\n{TEXTE_SYNDIC}\n\n"
        f"De : Jean Dupont <{JEAN}>\nEnvoyé : 29.09.2026 08:43\n"
        f"Objet : Portail\n\n{TEXTE_JEAN}\n",
    ),
]


@pytest.mark.parametrize("sujet, corps, syndic_le, jean_le", CAS)
def test_chaque_client_de_messagerie_se_decoupe(sujet, corps, syndic_le, jean_le):
    transfert = transfert_dans(sujet, corps)
    assert transfert is not None, "le transfert n'est pas reconnu"
    assert transfert.adresse == SYNDIC
    syndic, jean = messages_du_fil(transfert)
    assert (syndic.adresse, syndic.envoye_le) == (SYNDIC, syndic_le)
    assert TEXTE_SYNDIC in syndic.texte and TEXTE_JEAN not in syndic.texte
    assert (jean.nom, jean.envoye_le) == ("Jean Dupont", jean_le)
    assert TEXTE_JEAN in jean.texte
    for m in (syndic, jean):
        assert "iPhone" not in m.texte and "Outlook pour" not in m.texte


# ── Le transfert en PIÈCE JOINTE (Outlook, Thunderbird) ───────────────────────


def test_un_transfert_en_PIECE_JOINTE_se_lit_comme_un_transfert_en_ligne():
    """« Transférer en tant que pièce jointe » : le message d'origine est une
    partie `message/rfc822`, avec ses propres en-têtes — il était ignoré."""
    origine = EmailMessage()
    origine["From"] = f"Gestion Syndic <{SYNDIC}>"
    origine["Date"] = "Tue, 29 Sep 2026 14:31:00 +0200"
    origine["Subject"] = "RE: Portail"
    origine.set_content(
        f"{TEXTE_SYNDIC}\n\nLe 29 sept. 2026 à 08:43, Jean Dupont <{JEAN}> a écrit :\n"
        f"> {TEXTE_JEAN}\n"
    )
    transfert = EmailMessage()
    transfert["Subject"] = "TR: RE: Portail"
    transfert.set_content("TK-109008")
    transfert.add_attachment(origine)
    corps = _corps_lisible(email.message_from_bytes(transfert.as_bytes()))
    lu = transfert_dans("TR: RE: Portail", corps)
    assert lu is not None and lu.note == "TK-109008" and lu.adresse == SYNDIC
    syndic, jean = messages_du_fil(lu)
    assert syndic.envoye_le == A_14_31 and TEXTE_SYNDIC in syndic.texte
    assert jean.envoye_le == A_08_43 and TEXTE_JEAN in jean.texte


def test_une_reponse_ne_lit_pas_le_message_joint_comme_son_texte():
    """Le texte d'une réponse reste le sien : le message joint vient APRÈS, et la
    citation s'arrête à son en-tête."""
    joint = EmailMessage()
    joint["From"] = f"Jean Dupont <{JEAN}>"
    joint["Date"] = "Tue, 29 Sep 2026 08:43:00 +0200"
    joint.set_content(TEXTE_JEAN)
    reponse = EmailMessage()
    reponse.set_content("Bien reçu, nous passons jeudi.")
    reponse.add_attachment(joint)
    corps = _corps_lisible(email.message_from_bytes(reponse.as_bytes()))
    assert _sans_citation(corps) == "Bien reçu, nous passons jeudi."


@pytest.mark.parametrize(
    "signature",
    [
        "Envoyé de mon iPhone",
        "Envoyé depuis mon mobile Huawei",
        "Sent from my iPhone",
        "Obtenir Outlook pour Android",
        "Get Outlook for iOS",
        "Envoyé à partir de Courrier pour Windows",
    ],
)
def test_une_signature_d_appareil_n_entre_pas(signature):
    assert _sans_citation(f"Nous passons jeudi.\n\n{signature}") == "Nous passons jeudi."
