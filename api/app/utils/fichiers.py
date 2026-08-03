"""Nom d'un fichier téléversé sur disque — écrit une seule fois.

Deux routeurs construisaient ce nom chacun de leur côté (`uploads.py`,
`documents.py`) : même préfixe UUID, même assainissement, deux écritures. La
règle est de sécurité (elle protège `/app/uploads`, servi en statique) : elle
n'a pas à exister en double.

L'extension est un **paramètre** et non une déduction du nom fourni, parce que
les deux appelants n'ont pas la même contrainte :

  - `uploads.py` sert des fichiers en statique → l'extension décide du
    `Content-Type` renvoyé au navigateur, elle doit donc venir du type MIME
    validé, jamais de l'appelant ;
  - `documents.py` sert par un endpoint authentifié qui impose lui-même le
    `media_type` → il conserve l'extension d'origine, utile au diagnostic.
"""
import os
import re
import unicodedata
import uuid

#: Racine réelle des fichiers téléversés. Résolue une fois : c'est elle qui borne
#: `chemins_locaux`, donc elle ne doit pas dépendre d'un lien symbolique traversé
#: au moment de l'appel.
RACINE_UPLOADS = os.path.realpath("/app/uploads")

# Assez long pour rester lisible dans une URL, assez court pour ne pas buter sur
# la limite de longueur de nom de fichier une fois le préfixe UUID ajouté.
_LONGUEUR_MAX_RADICAL = 60
_LONGUEUR_MAX_EXTENSION = 8


def radical_assaini(nom_origine: str | None) -> str:
    """Nom fourni par l'appelant → radical sûr : sans chemin, sans extension, ASCII.

    Les accents sont translittérés plutôt que remplacés par des `_` : « été.pdf »
    donne « ete » et non « _t_ ». Tout ce qui n'est ni lettre, ni chiffre, ni
    `-`/`_` disparaît — séparateurs de chemin compris, d'où l'absence de
    traversée possible.
    """
    brut = os.path.basename(nom_origine or "")
    radical = os.path.splitext(brut)[0]
    radical = unicodedata.normalize("NFKD", radical).encode("ascii", "ignore").decode()
    radical = re.sub(r"[^A-Za-z0-9_\-]", "_", radical)[:_LONGUEUR_MAX_RADICAL]
    return radical.strip("_") or "fichier"


def extension_assainie(nom_origine: str | None) -> str:
    """Extension du nom fourni, ramenée à `.xxx` alphanumérique minuscule.

    Réservée aux fichiers qui ne sont PAS servis en statique. Pour les autres,
    passer l'extension déduite du type MIME validé.
    """
    brute = os.path.splitext(os.path.basename(nom_origine or ""))[1]
    ext = re.sub(r"[^a-z0-9]", "", brute.lower())[:_LONGUEUR_MAX_EXTENSION]
    return f".{ext}" if ext else ""


def chemins_locaux(urls: list[str]) -> list[str]:
    """URLs internes `/uploads/…` → chemins locaux existants, pour les joindre à un e-mail.

    Écrite deux fois à l'identique (`tickets.py`, `publications.py`) et attendue
    une troisième pour le calendrier. Trois vérifications, toutes nécessaires :
    l'URL doit être l'une des nôtres, le chemin résolu doit rester SOUS la racine
    des téléversements (sans quoi `/uploads/../../etc/passwd` sortirait du bac à
    sable et partirait en pièce jointe), et le fichier doit exister — une URL
    orpheline ne doit pas faire échouer l'envoi.
    """
    chemins: list[str] = []
    for url in urls:
        if not isinstance(url, str) or not url.startswith("/uploads/"):
            continue
        chemin = os.path.realpath("/app" + url)
        if not chemin.startswith(RACINE_UPLOADS + os.sep):
            continue
        if os.path.isfile(chemin):
            chemins.append(chemin)
    return chemins


def nom_stocke(nom_origine: str | None, extension: str) -> str:
    """`{uuid}_{radical}{extension}` — collision impossible, nom d'origine lisible.

    Le préfixe UUID rend l'URL non devinable ; le radical conserve un nom
    parlant, sans quoi une pièce jointe s'affiche « a3f8…c2.pdf » partout où on
    la référence.
    """
    ext = extension if (not extension or extension.startswith(".")) else f".{extension}"
    return f"{uuid.uuid4().hex}_{radical_assaini(nom_origine)}{ext}"
