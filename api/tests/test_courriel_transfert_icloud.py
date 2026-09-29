"""Le transfert du webmail iCloud — le premier transfert RÉEL (29/09/2026).

Sa partie `text/plain` tenait sur UNE ligne : « Début du message réexpédié :
De : … Objet : … » bout à bout, sans un saut. Aucun en-tête ne s'y repérait, et
le message a été refusé deux fois. Sa partie HTML, elle, était intacte — c'est
elle que la relève lit désormais (`courriel_decodage._aplati`).

Et la redirection d'OVH avait doublé un point : « Le sam. 26 sept.. 2026 » —
la date du plus ancien message ne se lisait plus.

La structure reproduit la source brute, balise pour balise là où elle compte ;
noms, adresses et téléphones sont fictifs (`standards/14`).
"""

from __future__ import annotations

import email
from datetime import datetime
from email.message import EmailMessage

from app.utils.courriel_decodage import _corps_lisible, transfert_dans
from app.utils.courriel_fil import messages_du_fil, repere_ecrit

SUJET = "TR\xa0: RE: Demande d'intervention urgente TK-109008"

#: La partie texte telle qu'iCloud l'écrit : tout le fil sur une ligne.
TEXTE_APLATI = (
    "Membre Conseil / conseil@exemple.test / 06 00 00 00 00 Début du message "
    "réexpédié : De : Gestion Syndic <gestion@syndic.test> Objet : RE: Demande "
    "d'intervention urgente Date : 29 sept. 2026 à 14 h 31 À : Jean Dupont "
    "<jean.dupont@exemple.test> Bonjour Monsieur Dupont, Nous nous chargeons de "
    "lancer un ordre de service à l'électricien. Cordialement De : Jean Dupont "
    "<jean.dupont@exemple.test> Envoyé : mardi 29 septembre 2026 08:43 Objet : Re: "
    "Demande d'intervention urgente Bonjour Madame, A ce jour l'entreprise ne répond "
    "pas. Le sam. 26 sept.. 2026, 08:58, Jean Dupont < jean.dupont@exemple.test > a "
    "écrit : Bonjour Monsieur, Le portillon électrique ne fonctionne plus."
)

HTML = (
    '<html><body><div><div><div><br></div><div style="white-space: pre-wrap" '
    'class="x-apple-signature">Membre Conseil / <a href="mailto:conseil@exemple.test">'
    "conseil@exemple.test</a>  / 06 00 00 00 00</div></div><div><br></div>"
    '<blockquote type="cite"><div>Début du message réexpédié :</div><div><br></div>'
    '<div><b style="color: initial">De :&nbsp;</b>Gestion Syndic '
    "&lt;gestion@syndic.test&gt;</div>"
    '<div><b style="color: initial">Objet :&nbsp;</b><b>RE: Demande d\'intervention '
    "urgente</b></div>"
    '<div><b style="color: initial">Date :&nbsp;</b>29 sept. 2026 à 14 h 31</div>'
    '<div><b style="color: initial">À :&nbsp;</b>Jean Dupont '
    "&lt;jean.dupont@exemple.test&gt;</div><div><br></div><div><br></div>"
    '<div lang="FR"><div class="WordSection1">'
    '<p class="MsoNormal"><span>Bonjour Monsieur Dupont,</span></p>'
    '<p class="MsoNormal"><span>Nous nous chargeons de lancer un ordre de service à '
    "l'électricien.</span></p>"
    '<p class="MsoNormal"><span>&nbsp;</span></p>'
    '<div><div><p class="MsoNormal"><b><span>Cordialement</span></b></p>'
    '<p class="MsoNormal"><b><span>Gestion Syndic</span></b></p>'
    '<p class="MsoNormal"><img src="cid:logo@exemple.test">'
    '<a href="mailto:gestion@syndic.test">gestion@syndic.test</a></p>'
    '<p class="MsoNormal">Tel standard&nbsp;: 01 00 00 00 00</p></div></div>'
    '<div style="border:none;border-top:solid #E1E1E1 1.0pt"><p class="MsoNormal">'
    "<b><span>De&nbsp;:</span></b><span> Jean Dupont &lt;jean.dupont@exemple.test&gt; "
    "<br> <b>Envoyé&nbsp;:</b> mardi 29 septembre 2026 08:43<br> <b>À&nbsp;:</b> "
    "Gestion Syndic &lt;gestion@syndic.test&gt;<br> <b>Objet&nbsp;:</b> Re: Demande "
    "d'intervention urgente</span></p></div>"
    '<p class="MsoNormal">&nbsp;</p><p class="MsoNormal">Bonjour Madame,&nbsp;</p>'
    '<p class="MsoNormal">A ce jour l\'entreprise ne répond pas à notre demande '
    "d'intervention urgente.&nbsp;</p>"
    '<p class="MsoNormal">Le sam. 26 sept.. 2026, 08:58, Jean Dupont &lt;'
    '<a href="mailto:jean.dupont@exemple.test">jean.dupont@exemple.test</a>&gt; a '
    "écrit&nbsp;:</p>"
    '<blockquote style="border-left:solid #CCCCCC 1.0pt">'
    '<p class="MsoNormal">Bonjour Monsieur,&nbsp;</p>'
    '<p class="MsoNormal">Le portillon électrique ne fonctionne plus.</p>'
    "</blockquote></div></div></blockquote></div></body></html>"
)


def _message_icloud() -> email.message.Message:
    """Un multipart/alternative à deux parties, relu depuis ses OCTETS."""
    m = EmailMessage()
    m["From"] = "Membre Conseil <conseil@exemple.test>"
    m["Subject"] = SUJET
    m.set_content(TEXTE_APLATI)
    m.add_alternative(HTML, subtype="html")
    return email.message_from_bytes(m.as_bytes())


def test_la_partie_texte_APLATIE_cede_la_place_au_HTML():
    corps = _corps_lisible(_message_icloud())
    assert "Début du message réexpédié" in corps
    assert len(corps.splitlines()) > 10, "le HTML garde les lignes"


def test_le_transfert_iCloud_donne_ses_trois_messages():
    transfert = transfert_dans(SUJET, _corps_lisible(_message_icloud()))
    assert transfert is not None and transfert.adresse == "gestion@syndic.test"
    assert repere_ecrit(SUJET, transfert.note) == "TK-109008"
    syndic, jean, premier = messages_du_fil(transfert)
    assert syndic.envoye_le == datetime(2026, 9, 29, 12, 31)
    assert "ordre de service" in syndic.texte and "Madame" not in syndic.texte
    assert jean.envoye_le == datetime(2026, 9, 29, 6, 43)
    assert "ne répond pas" in jean.texte and "portillon" not in jean.texte
    #  « sept.. » : le point doublé par la redirection d'OVH.
    assert premier.envoye_le == datetime(2026, 9, 26, 6, 58)
    assert "Le portillon électrique ne fonctionne plus." in premier.texte


def test_une_reponse_courte_garde_sa_partie_texte():
    """Seul un texte APLATI cède : une réponse d'une ligne reste lue en texte."""
    m = EmailMessage()
    m.set_content("Oui, jeudi 10 h.")
    m.add_alternative("<p>Oui, jeudi 10 h.</p><p>Signature</p>", subtype="html")
    assert _corps_lisible(email.message_from_bytes(m.as_bytes())).strip() == "Oui, jeudi 10 h."
