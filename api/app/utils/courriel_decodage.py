"""Du MIME au texte lisible — le DÉCODAGE d'une réponse par courriel.

Extrait de `courriel_boite.py` le 09/09/2026, sur refus du contrôle de
modularité : ce fichier était à 500 lignes pile et devait recevoir la
distinction passager/persistant (#858).

La coupe suit une couture qui existait déjà. `courriel_boite` est le **tuyau** —
il ouvre la boîte, lit, applique un verdict. Ces fonctions-ci ne connaissent
ni IMAP, ni la base, ni le ticket : on leur donne un message `email.message`, elles
rendent du texte. Elles s'éprouvent sur des messages écrits à la main, y compris
mal formés, sans réseau.

⚠️ Les trois premières gardent leur préfixe `_` : ce n'est pas une surface
publique, c'est le même module vu de plus près.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from email.header import decode_header, make_header
from html.parser import HTMLParser

#: Un corps de réponse dépasse rarement quelques lignes utiles ; au-delà c'est la
#: citation du message précédent. Tronqué pour ne pas recopier tout un fil dans le
#: ticket à chaque échange. Vient avec `_sans_citation`, sa seule lectrice.
MAX_CORPS = 4000


def _texte(valeur) -> str:
    """Un en-tête décodé, quel que soit son encodage MIME."""
    if not valeur:
        return ""
    try:
        return str(make_header(decode_header(valeur)))
    except Exception:
        return str(valeur)


class _TexteDuHtml(HTMLParser):
    """Le TEXTE d'un corps HTML — jamais son balisage.

    Les blocs deviennent des lignes, `<br>` un saut de ligne, et une ligne citée
    (`<blockquote>`) est préfixée de « > » comme dans un courriel en texte brut :
    `_sans_citation` la reconnaît alors sans règle de plus.
    """

    _BLOCS = {"p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "blockquote"}
    _MUETS = {"style", "script", "head", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lignes: list[str] = [""]
        self.cite = 0
        self.muet = 0

    def _saut(self):
        if self.lignes[-1].strip():
            self.lignes.append("")

    def handle_starttag(self, tag, attrs):
        if tag in self._MUETS:
            self.muet += 1
        elif tag == "br":
            self.lignes.append("")
        elif tag in self._BLOCS:
            self._saut()
            if tag == "blockquote":
                self.cite += 1

    def handle_endtag(self, tag):
        if tag in self._MUETS:
            self.muet = max(0, self.muet - 1)
        elif tag in self._BLOCS:
            self._saut()
            if tag == "blockquote":
                self.cite = max(0, self.cite - 1)

    def handle_data(self, data):
        if self.muet:
            return
        morceau = re.sub(r"\s+", " ", data.replace("\xa0", " "))
        if not morceau.strip():
            return
        if not self.lignes[-1] and self.cite:
            self.lignes[-1] = "> "
        self.lignes[-1] += morceau.lstrip() if not self.lignes[-1].strip() else morceau


def _html_en_texte(html: str) -> str:
    lecteur = _TexteDuHtml()
    lecteur.feed(html)
    lecteur.close()
    return "\n".join(ligne.strip() for ligne in lecteur.lignes).strip()


def _charge(partie) -> str:
    brut = partie.get_payload(decode=True) or b""
    return brut.decode(partie.get_content_charset() or "utf-8", "replace")


def _corps_lisible(message) -> str:
    """Le texte de la réponse, en clair.

    On préfère la partie `text/plain` : elle existe presque toujours. À défaut, le
    `text/html` est réduit à son TEXTE — jamais conservé comme balisage : un fil
    de ticket qui accepterait du HTML venu d'un courriel ouvrirait une porte que
    `lint:html` ne surveille pas.

    🔴 **Ce repli manquait jusqu'au 28/09/2026.** L'application Mail d'Orange
    n'envoie QUE du HTML : son corps était lu vide, et la réponse d'un membre du
    conseil a été ignorée sans un mot.
    """
    parties = list(message.walk()) if message.is_multipart() else [message]
    for partie in parties:
        if partie.get_content_type() == "text/plain":
            return _charge(partie)
    for partie in parties:
        if partie.get_content_type() == "text/html":
            return _html_en_texte(_charge(partie))
    return ""


#: Un séparateur de réponse : une ligne faite de tirets ou de soulignés seuls
#: (« ---------------- » d'Orange, « ________ » d'Outlook).
_SEPARATEUR = re.compile(r"^[-_]{8,}$")
#: L'en-tête d'un message cité à la manière d'Outlook : « De : … <adresse> »
#: suivi, dans les lignes qui viennent, d'« Envoyé : » ou « Date : ».
_DE = re.compile(r"^\*?(De|From)\s*:\*?\s*.*@", re.I)
_DATE_CITEE = re.compile(r"^\*?(Envoyé|Sent|Date)\s*:", re.I)


def _sans_citation(texte: str) -> str:
    """La réponse, sans le message cité en dessous.

    Une réponse par courriel recopie tout l'échange précédent. Le laisser
    entrerait dans le ticket une copie du ticket, à chaque échange, et le fil
    deviendrait illisible en trois messages.
    """
    source = texte.splitlines()
    lignes = []
    for n, ligne in enumerate(source):
        nue = ligne.strip()
        if nue.startswith(">") or nue.startswith("-- ") or _SEPARATEUR.match(nue):
            break
        if nue.startswith("Le ") and nue.endswith("écrit :"):
            break
        if _DE.match(nue) and any(_DATE_CITEE.match(s.strip()) for s in source[n + 1 : n + 4]):
            break
        lignes.append(ligne)
    return "\n".join(lignes).strip()[:MAX_CORPS]


# ── Un TRANSFERT : le message d'un autre, sous une note ───────────────────────

#: « TR : », « Fwd: », « Fw: » en tête de l'objet.
_OBJET_TRANSFERT = re.compile(r"^\s*(tr|fwd?|transf\.?)\s*:", re.I)
#: La ligne qui ouvre le message transféré (Apple, Gmail, Outlook, Orange).
_MARQUE_TRANSFERT = re.compile(
    r"^(D[ée]but du message r[ée]exp[ée]di[ée]\s*:?"
    r"|-{2,}\s*(Message transf[ée]r[ée]|Forwarded message|Original Message|Message d'origine)"
    r"\s*-*)$",
    re.I,
)
_ADRESSE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


@dataclass(frozen=True)
class Transfert:
    """Un message transféré : la note de qui transfère, puis le message d'origine."""

    note: str
    #: L'en-tête « De : » du message d'origine, tel qu'écrit (« Nom <adresse> »).
    de: str
    adresse: str
    corps: str


def transfert_dans(sujet: str, texte: str) -> Transfert | None:
    """Le message transféré, si ce courriel en est un — sinon None.

    L'objet décide d'abord : une RÉPONSE à un transfert (« RE: TR : … ») cite la
    marque de transfert dans son historique, et n'est pas un transfert.
    """
    if not _OBJET_TRANSFERT.match(sujet or ""):
        return None
    lignes = texte.splitlines()
    for n, ligne in enumerate(lignes):
        if not _MARQUE_TRANSFERT.match(ligne.strip().strip("*")):
            continue
        de, fin = "", n + 1
        #  Le bloc d'en-têtes du message d'origine, jusqu'à la première ligne vide
        #  qui le suit.
        while fin < len(lignes) and (not lignes[fin].strip() or ":" in lignes[fin]):
            nue = lignes[fin].strip().strip("*")
            if not nue and de:
                break
            if _DE.match(nue):
                de = nue.split(":", 1)[1].strip().strip("*").strip()
            fin += 1
        adresse = _ADRESSE.search(de)
        if not adresse:
            return None
        return Transfert(
            note="\n".join(lignes[:n]).strip(),
            de=de,
            adresse=adresse.group(0).lower(),
            corps="\n".join(lignes[fin:]).strip(),
        )
    return None
