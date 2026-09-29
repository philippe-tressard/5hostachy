"""Le découpage d'un fil TRANSFÉRÉ en messages — `utils/courriel_fil` (29/09/2026).

Le cas qui l'a fait naître est un vrai fil du conseil, transféré depuis Mail
(Apple) : une réponse du syndic (Outlook), qui cite un message d'un membre du
conseil (Gmail, bloc « De : / Envoyé : »), qui cite le premier message (« Le …
a écrit : », coupé sur deux lignes par Gmail). Noms et adresses sont fictifs :
un fil réel porte des données personnelles, et un dépôt git les garde pour
toujours (`standards/14`).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.utils.courriel_decodage import transfert_dans
from app.utils.courriel_fil import (
    FilIllisible,
    cle_du_fil,
    date_citee,
    empreinte,
    messages_du_fil,
    repere_ecrit,
    titre_du_fil,
)

SUJET = "TR: RE: Demande d'intervention urgente"

FIL = """TK-109008

Début du message réexpédié :

De: Gestion Syndic <gestion@syndic.test>
Objet: RE: Demande d'intervention urgente
Date: 29 septembre 2026 à 10:12:34 UTC+2
À: Jean Dupont <jean.dupont@exemple.test>
Cc: Membre Conseil <conseil@exemple.test>

Bonjour Monsieur Dupont,

Nous nous chargeons de lancer un ordre de service à l'électricien.

Cordialement

Gestion Syndic
Tel standard : 01 00 00 00 00


De : Jean Dupont <jean.dupont@exemple.test>
Envoyé : mardi 29 septembre 2026 08:43
À : Gestion Syndic <gestion@syndic.test>
Cc : Membre Conseil <conseil@exemple.test>; Autre <autre@exemple.test>;
 Encore <encore@exemple.test>
Objet : Re: Demande d'intervention urgente

Bonjour Madame,

A ce jour l'entreprise ne répond pas à notre demande d'intervention urgente.

Cordialement

Le sam. 26 sept. 2026, 08:58, Jean Dupont <
jean.dupont@exemple.test> a écrit :

> Bonjour Monsieur,
>
> Le portillon électrique ne fonctionne plus.
>
> Bien cordialement
"""


def _messages(texte=FIL, sujet=SUJET):
    return messages_du_fil(transfert_dans(sujet, texte))


def test_le_fil_de_l_exemple_donne_trois_messages_du_plus_recent_au_plus_ancien():
    syndic, jean, premier = _messages()
    assert (syndic.nom, syndic.adresse) == ("Gestion Syndic", "gestion@syndic.test")
    assert (jean.nom, jean.adresse) == ("Jean Dupont", "jean.dupont@exemple.test")
    assert (premier.nom, premier.adresse) == ("Jean Dupont", "jean.dupont@exemple.test")
    #  En UTC : 10:12:34 UTC+2, puis deux heures de Paris (CEST).
    assert syndic.envoye_le == datetime(2026, 9, 29, 8, 12, 34)
    assert jean.envoye_le == datetime(2026, 9, 29, 6, 43)
    assert premier.envoye_le == datetime(2026, 9, 26, 6, 58)


def test_chaque_message_ne_porte_que_son_texte():
    syndic, jean, premier = _messages()
    assert "ordre de service" in syndic.texte and "Madame" not in syndic.texte
    assert jean.texte.startswith("Bonjour Madame,") and "portillon" not in jean.texte
    assert "Encore" not in jean.texte, "la liste des destinataires continue sur deux lignes"
    assert premier.texte.startswith("Bonjour Monsieur,") and ">" not in premier.texte
    assert "Le portillon électrique ne fonctionne plus." in premier.texte


def test_la_note_de_qui_transfere_porte_le_repere_et_pas_un_message():
    transfert = transfert_dans(SUJET, FIL)
    assert transfert.note == "TK-109008"
    assert transfert.objet == "RE: Demande d'intervention urgente"
    assert repere_ecrit(SUJET, transfert.note) == "TK-109008"
    assert repere_ecrit("TR: Affaire #TK-121048 — Porte", "") == "TK-121048"
    assert repere_ecrit(SUJET, "Pour info") is None


def test_un_transfert_lu_depuis_le_HTML_garde_ses_chevrons_et_se_lit_quand_meme():
    cite = "\n".join(f"> {ligne}" if ligne else ">" for ligne in FIL.splitlines()[2:])
    assert len(_messages(cite)) == 3


@pytest.mark.parametrize(
    "ecrit, utc",
    [
        ("mardi 29 septembre 2026 08:43", datetime(2026, 9, 29, 6, 43)),
        ("29 sept. 2026 à 15 h 47", datetime(2026, 9, 29, 13, 47)),
        ("sam. 26 sept. 2026, 08:58", datetime(2026, 9, 26, 6, 58)),
        ("jeudi 1er octobre 2026 09:05", datetime(2026, 10, 1, 7, 5)),
        ("29/09/2026 08:43", datetime(2026, 9, 29, 6, 43)),
        ("Tue, 29 Sep 2026 10:12:34 +0200", datetime(2026, 9, 29, 8, 12, 34)),
        ("Tuesday, September 29, 2026 8:43 PM", datetime(2026, 9, 29, 18, 43)),
        ("15 décembre 2026 à 10:00", datetime(2026, 12, 15, 9, 0)),  # heure d'hiver
    ],
)
def test_les_dates_des_clients_de_messagerie_se_lisent(ecrit, utc):
    assert date_citee(ecrit) == utc


@pytest.mark.parametrize("ecrit", ["", "hier soir", "29 septembre 2026", "Brumaire 12 2026 10:00"])
def test_une_date_illisible_n_est_pas_devinee(ecrit):
    assert date_citee(ecrit) is None


def test_un_message_sans_date_lisible_refuse_TOUT_le_fil():
    """Verser la moitié d'un fil écrirait un historique faux qui a l'air juste."""
    fil = FIL.replace("Envoyé : mardi 29 septembre 2026 08:43", "Envoyé : hier soir")
    with pytest.raises(FilIllisible, match="Jean Dupont"):
        _messages(fil)


def test_une_phrase_du_corps_qui_commence_par_Le_n_est_pas_un_en_tete():
    fil = FIL.replace(
        "Nous nous chargeons", "Le prestataire a écrit : il passe demain.\n\nNous nous chargeons"
    )
    assert len(_messages(fil)) == 3


def test_le_titre_et_la_cle_du_fil_oublient_les_prefixes_et_le_repere():
    assert titre_du_fil("TR: RE: Demande d'intervention urgente TK-109008") == (
        "Demande d'intervention urgente"
    )
    cles = {
        cle_du_fil(o)
        for o in (
            "RE: Demande d'intervention urgente",
            "TR : Re: demande d’intervention URGENTE",
            "Fwd: Demande d'intervention urgente — Affaire #TK-109008",
        )
    }
    assert cles == {"demande d intervention urgente"}
    assert cle_du_fil("RE: Info") is None, "un objet trop court ne reconnaît aucun fil"


def test_l_empreinte_reconnait_un_message_cite_autrement():
    """Deux transferts du même fil ne coupent pas les lignes aux mêmes endroits."""
    _s, _j, premier = _messages()
    autre = FIL.replace(
        "> Le portillon électrique ne fonctionne plus.",
        "> Le portillon\n> électrique  ne fonctionne plus.",
    )
    assert empreinte(_messages(autre)[2]) == empreinte(premier)
    assert empreinte(_messages()[1]) != empreinte(premier)
