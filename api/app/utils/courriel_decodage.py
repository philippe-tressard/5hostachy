"""Du MIME au texte lisible — le DÉCODAGE d'une réponse par courriel.

Extrait de `courriel_boite.py` le 09/09/2026, sur refus du contrôle de
modularité : ce fichier était à 500 lignes pile et devait recevoir la
distinction passager/persistant (#858).

La coupe suit une couture qui existait déjà. `courriel_boite` est le **tuyau** —
il ouvre la boîte, lit, applique un verdict. Ces trois fonctions-ci ne connaissent
ni IMAP, ni la base, ni le ticket : on leur donne un message `email.message`, elles
rendent du texte. Elles s'éprouvent sur des messages écrits à la main, y compris
mal formés, sans réseau.

⚠️ Elles gardent leur préfixe `_` : ce n'est pas une surface publique, c'est le
même module vu de plus près. Deux appelants seulement, tous deux dans
`courriel_boite`.
"""
from __future__ import annotations

from email.header import decode_header, make_header

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


def _corps_lisible(message) -> str:
    """Le texte de la réponse, en clair.

    On préfère la partie `text/plain` : elle existe presque toujours, et elle
    évite d'avoir à assainir du HTML écrit par un tiers avant de l'afficher. Le
    HTML n'est PAS retenu en repli — un fil de ticket qui accepterait du balisage
    venu d'un courriel ouvrirait une porte que `lint:html` ne surveille pas.
    """
    if message.is_multipart():
        for partie in message.walk():
            if partie.get_content_type() == "text/plain":
                charge = partie.get_payload(decode=True) or b""
                return charge.decode(partie.get_content_charset() or "utf-8", "replace")
        return ""
    if message.get_content_type() != "text/plain":
        return ""
    charge = message.get_payload(decode=True) or b""
    return charge.decode(message.get_content_charset() or "utf-8", "replace")


def _sans_citation(texte: str) -> str:
    """La réponse, sans le message cité en dessous.

    Une réponse par courriel recopie tout l'échange précédent. Le laisser
    entrerait dans le ticket une copie du ticket, à chaque échange, et le fil
    deviendrait illisible en trois messages.
    """
    lignes = []
    for ligne in texte.splitlines():
        nue = ligne.strip()
        if nue.startswith(">") or nue.startswith("-- "):
            break
        if nue.startswith("Le ") and nue.endswith("écrit :"):
            break
        lignes.append(ligne)
    return "\n".join(lignes).strip()[:MAX_CORPS]
