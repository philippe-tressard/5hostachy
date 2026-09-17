"""Le FORMAT de l'usage « description » — ce qu'on demande, et comment on relit.

## Pourquoi ce fichier est séparé d'`assistant_description.py` (17/09/2026)

Même ligne de coupe que `synthese_format.py` / `synthese_contrat.py` : **ici on
décrit ce qu'on attend du modèle et on relit sa réponse**, là-bas on lit une
configuration et on passe l'appel. Ce fichier ne connaît ni la base, ni le
réseau : ce sont des chaînes et un `dict`, vérifiables sans rien monter.

## 🔴 Deux textes, deux propriétaires

| Texte | Qui le tient | Où |
|---|---|---|
| `CONSIGNE_DEFAUT` | **l'administrateur** — c'est le prompt de l'usage, modifiable dans Admin → Assistant IA | en base, initialisé une fois depuis ici (migration 0194) |
| `FORMAT_REPONSE` | **le code** — il impose la forme JSON que `lire_reponse` sait relire | ajouté à l'appel, jamais exposé à l'édition |

Séparer les deux est ce qui permet à l'administrateur de réécrire librement le
ton, la langue ou les interdits sans pouvoir casser la lecture de la réponse :
un prompt qui aurait perdu la phrase « rends du JSON » ferait échouer chaque
appel, sans qu'aucun écran ne dise pourquoi.
"""
from __future__ import annotations

import json
import re

#: Le prompt d'ORIGINE de l'usage — celui que l'administrateur relit et adapte.
#: Rédigé le 17/09/2026 sur les quatre consignes de Philippe : langage simple,
#: législation française, réponse synthétique, destinée aux copropriétaires et
#: locataires.
CONSIGNE_DEFAUT = """Tu retravailles le titre et la description d'une publication destinée aux
copropriétaires et aux locataires d'une copropriété.

- Rédige dans un langage simple, courtois et neutre, sans être offensant.
- Respecte la législation française relative aux contenus publiés : aucune
  mise en cause nominative, aucune donnée personnelle qui n'était pas déjà
  dans le texte, aucun propos diffamatoire ou discriminatoire.
- La réponse est synthétique et compréhensible par tous.
- Conserve tous les faits, dates, montants, lieux et noms fournis ; n'en
  invente aucun et n'en supprime aucun.
- Si le titre manque, propose-en un court à partir de la description. Si la
  description manque, propose-en une à partir du titre seul.
- Le contexte transmis (catégorie, périmètre, état, date…) sert à comprendre
  le texte ; il ne se réécrit pas et ne se recopie pas dans la description.
- La description est du HTML simple (`<p>`, `<ul><li>`, `<strong>`), le titre
  est du texte brut."""

#: 🔴 Le FORMAT — tenu par le code, jamais par le prompt. `lire_reponse` en
#: dépend : la clé du titre et celle de la description sont celles-ci, et une
#: réponse qui ne les porte pas est un échec lisible, pas un texte tronqué.
FORMAT_REPONSE = """Réponds UNIQUEMENT par un objet JSON, sans texte avant ni après, sans bloc de
code, avec exactement ces deux clés :
{"titre": "<le titre, texte brut, ou null si aucun titre n'est demandé>",
 "description": "<la description, HTML simple>"}"""

#: Ce que l'écran peut envoyer au plus. Un texte au-delà n'est pas une
#: description, et il coûte des jetons pour rien.
MAX_CARACTERES_DESCRIPTION = 20_000
MAX_CARACTERES_CONTEXTE = 500
MAX_CARACTERES_PRECISION = 500


def construire_message(
    *,
    entite: str,
    titre: str | None,
    description: str | None,
    contexte: dict[str, str],
    precision: str | None,
    avec_titre: bool,
) -> str:
    """Le message posé au modèle — la matière, jamais la consigne.

    Chaque élément est ANNONCÉ par son nom : sans cela, le modèle lit une seule
    masse de texte et ne peut pas savoir que « bât. 2 » est un périmètre et non
    une phrase de la description.

    ⚠️ Le contexte est déclaré « à ne pas réécrire » ici aussi, pas seulement
    dans le prompt : le prompt est modifiable, et l'administrateur peut en
    retirer la phrase sans savoir qu'elle protégeait ce point.
    """
    blocs = [f"Nature de la publication : {entite}."]
    if contexte:
        lignes = "\n".join(f"- {k} : {v}" for k, v in contexte.items() if v)
        if lignes:
            blocs.append(
                "Contexte, à comprendre et à ne pas réécrire ni recopier :\n" + lignes
            )
    if avec_titre:
        blocs.append("Titre actuel :\n" + (titre.strip() if titre and titre.strip() else "(aucun)"))
    else:
        blocs.append("Aucun titre n'est demandé : réponds avec \"titre\": null.")
    blocs.append(
        "Description actuelle :\n"
        + (description.strip() if description and description.strip() else "(aucune)")
    )
    if precision and precision.strip():
        blocs.append("Précision demandée par l'auteur pour cette réécriture : " + precision.strip())
    return "\n\n".join(blocs)


_BLOC_CODE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class ReponseIllisible(ValueError):
    """Le modèle n'a pas rendu le JSON attendu — l'appelant en fait une `ErreurLLM`."""


def lire_reponse(texte: str) -> dict[str, str | None]:
    """Le titre et la description, relus dans ce que le modèle a rendu.

    Tolère un bloc de code autour du JSON — beaucoup de modèles en posent un
    malgré la consigne — et du texte parasite avant ou après l'objet. Ne
    tolère PAS un objet sans `description` : c'est la seule clé qui ne peut
    pas manquer, et la remplacer par le texte brut ferait passer une réponse
    en prose pour une proposition.
    """
    brut = (texte or "").strip()
    m = _BLOC_CODE.match(brut)
    if m:
        brut = m.group(1)
    debut, fin = brut.find("{"), brut.rfind("}")
    if debut < 0 or fin <= debut:
        raise ReponseIllisible("Réponse du modèle sans objet JSON.")
    try:
        charge = json.loads(brut[debut : fin + 1])
    except ValueError as exc:
        raise ReponseIllisible("Réponse du modèle illisible — JSON invalide.") from exc
    if not isinstance(charge, dict) or not isinstance(charge.get("description"), str):
        raise ReponseIllisible("Réponse du modèle sans description.")
    titre = charge.get("titre")
    if titre is not None and not isinstance(titre, str):
        titre = str(titre)
    return {
        "titre": titre.strip() if isinstance(titre, str) and titre.strip() else None,
        "description": charge["description"].strip(),
    }


def _normaliser(texte: str | None) -> str:
    """Pour dire si un champ a CHANGÉ : les espaces et les fins de ligne ne
    comptent pas, un éditeur riche en ajoute sans que personne les ait tapés."""
    return re.sub(r"\s+", " ", (texte or "")).strip()


def a_change(avant: str | None, apres: str | None) -> bool:
    return _normaliser(avant) != _normaliser(apres)


__all__ = [
    "CONSIGNE_DEFAUT",
    "FORMAT_REPONSE",
    "MAX_CARACTERES_CONTEXTE",
    "MAX_CARACTERES_DESCRIPTION",
    "MAX_CARACTERES_PRECISION",
    "ReponseIllisible",
    "a_change",
    "construire_message",
    "lire_reponse",
]
