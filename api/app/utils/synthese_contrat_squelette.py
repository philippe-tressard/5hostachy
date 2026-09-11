"""Le SQUELETTE d'une synthèse de contrat : ce qu'on demande, ce qu'on rend.

Ce module ne connaît **ni le réseau, ni la base, ni la configuration** : il
transforme du texte en objet, et un objet en HTML. C'est ce qui le rend
éprouvable seul — `api/tests/test_synthese_contrat.py` l'exerce entièrement sans
joindre le moindre service.

Séparé de `synthese_contrat.py` le 11/09/2026, quand le fichier unique a dépassé
le plafond de modularité (rang 1, 500 lignes). La coupe suit le SUJET, pas le
compteur : d'un côté ce que la synthèse EST, de l'autre comment on va la
chercher. Même couture que `fiche_arrivant` / `fiche_arrivant_css` et
`manuel_pdf` / `manuel_pdf_css`.

🔴 **Les deux décisions qui vivent ICI**, et qui ne se rediscutent pas au cas
par cas :

**1. Le modèle rend des DONNÉES, ce module rend le HTML.** La réponse attendue
est un objet dont les clés sont celles de `SQUELETTE` ; `rendre_html()` compose
le balisage à partir d'elles, en échappant chaque valeur. Deux conséquences, et
la seconde est la vraie raison :

- le squelette est tenu par **construction** — une section absente le reste, une
  section inventée est ignorée, l'ordre et les numéros sont ceux du squelette et
  de rien d'autre ;
- **aucun balisage écrit par le modèle n'atteint la page.** Le champ `notes` est
  rendu par `{@html safeHtml(...)}` côté écran : laisser le modèle produire du
  HTML reviendrait à faire transiter du balisage d'origine externe jusqu'à un
  `{@html}`. DOMPurify le nettoierait, et ce serait quand même la mauvaise
  frontière — on ne désinfecte pas ce qu'on peut ne jamais laisser entrer.

**2. Ce qui n'est pas dans le document ne s'invente pas.** La consigne l'impose
section par section, et `NON_PRECISE` est la réponse attendue. Sur un contrat,
une valeur plausible et fausse coûte plus cher qu'une case vide : c'est le
raisonnement que ce dépôt applique déjà à `_appliquer_perimetre`, qui refuse de
désigner « le premier » bâtiment quand plusieurs sont visés.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape
from typing import Any, Literal

#: Ce que le modèle doit écrire quand le contrat ne dit rien. Une seule écriture :
#: la consigne l'emploie, le rendu la reconnaît pour griser la ligne.
NON_PRECISE = "Non précisé au contrat"

#: 🔴 La CITATION qui fonde chaque section — clé `"<section>_citation"`.
#:
#: Elle vient de la pratique du conseil syndical : ses synthèses manuelles
#: portent, sous plusieurs rubriques, l'extrait du contrat qui les fonde
#: («&nbsp;…se renouvellera par tacite reconduction…&nbsp;»). Ce n'est pas
#: décoratif — c'est ce qui permet de VÉRIFIER une ligne sans rouvrir le PDF,
#: et c'est le meilleur garde-fou contre une affirmation inventée : un extrait
#: faux se repère, une reformulation fausse ne se repère pas.
SUFFIXE_CITATION = "_citation"

class SyntheseIndisponible(Exception):
    """Ce qui empêche la génération, dit en français à qui a cliqué.

    Toujours une phrase qui nomme le geste suivant. « Erreur 400 » n'en est pas
    une : c'est ce que l'écran afficherait sinon, et le conseil syndical ne peut
    rien en faire.
    """

@dataclass(frozen=True)
class Rubrique:
    """Une section du squelette : sa clé, son titre affiché, ce qu'on en attend.

    ⚠️ Le titre ne porte PAS son numéro. Il est posé au rendu, depuis la position
    dans `SQUELETTE` — réordonner les sections renumérote donc toute la synthèse,
    et deux sections ne peuvent pas porter le même chiffre. Un numéro écrit dans
    le libellé serait une seconde source de vérité, libre de mentir dès le
    premier déplacement.
    """

    cle: str
    titre: str
    consigne: str
    #: Comment la section se rend, et donc ce que le modèle doit renvoyer :
    #:
    #: | `forme`    | attendu du modèle          | rendu              |
    #: |------------|----------------------------|--------------------|
    #: | `"texte"`  | une chaîne                 | un ou des `<p>`    |
    #: | `"liste"`  | un tableau de chaînes      | `<ul><li>`         |
    #: | `"champs"` | un objet libellé → valeur  | `<ul>` de `libellé : valeur` |
    forme: Literal["texte", "liste", "champs"] = "texte"
    #: Pour `forme="champs"` : les libellés attendus, dans l'ordre de rendu.
    #: Ils sont FIXES — un libellé absent de la réponse ressort « non précisé »,
    #: un libellé inventé par le modèle est ignoré. C'est la même garantie que
    #: pour les sections elles-mêmes, un cran plus bas.
    champs: tuple[str, ...] = ()


#: 🔴 LE SQUELETTE — source unique, et le seul endroit à modifier pour changer la
#: forme d'une synthèse. Il sert À LA FOIS de consigne au modèle, de schéma de
#: lecture de sa réponse et de plan du HTML rendu. Le recopier ailleurs (dans le
#: prompt, dans un gabarit d'affichage) rouvrirait la divergence que ce dépôt a
#: déjà payée quatre fois — c'est `standards/02` §2.
#:
#: 🔴 **Les sept titres sont ceux du conseil syndical** (11/09/2026), donnés avec
#: une synthèse déjà rédigée à la main — celle du contrat d'entretien ROSARIO —
#: et la consigne *« respecte uniquement les titres »*. Ils ne se réécrivent donc
#: pas « pour faire mieux » : ce sont les intitulés sous lesquels la copropriété
#: lit ses contrats depuis avant ce produit. Ce qu'ils contiennent, en revanche,
#: dépend du contrat et n'est pas imposé.
SQUELETTE: tuple[Rubrique, ...] = (
    Rubrique(
        "fournisseur",
        "Identification du fournisseur",
        "Qui est le prestataire, tel que le contrat le désigne.",
        forme="champs",
        champs=(
            "Prestataire",
            "Adresse",
            "SIRET",
            "Représentant",
            "Assurance",
        ),
    ),
    Rubrique(
        "dates",
        "Dates clés / Validité",
        "Quand le contrat prend effet, combien de temps il dure, comment il se rompt.",
        forme="champs",
        champs=(
            "Date de signature",
            "Durée",
            "Préavis",
        ),
    ),
    Rubrique(
        "objet",
        "Objet du contrat",
        "Ce que le contrat couvre. Une entrée par volet de la mission.",
        forme="liste",
    ),
    Rubrique(
        "inclus",
        "Prestations incluses",
        "Ce que le forfait comprend. Une entrée par prestation, avec SA FRÉQUENCE "
        "quand le contrat la donne (« Ramassage détritus : 3×/semaine ») et le "
        "périmètre concerné quand il varie (bâtiments, parking, espaces verts, "
        "ordures ménagères).",
        forme="liste",
    ),
    Rubrique(
        "exclus",
        "Prestations non incluses",
        "Ce qui est exclu, sur devis, ou facturé en sus. Une entrée par exclusion.",
        forme="liste",
    ),
    Rubrique(
        "finances",
        "Conditions financières",
        "Montants et leurs assiettes : mensuel HT, suppléments, TVA, TTC, révision "
        "des prix, ce qui est inclus dans le forfait et ce qui est facturé à part. "
        "Reprendre les chiffres du contrat à l'unité près.",
        forme="liste",
    ),
    Rubrique(
        "attention",
        "Points d'attention pour la copropriété",
        "Ce qui mérite un examen du conseil syndical : coût au regard du périmètre, "
        "préavis court, reconduction difficile à dénoncer, supplément particulier, "
        "prestation manquante, absence de clause de révision. S'appuyer UNIQUEMENT "
        "sur le document.",
        forme="liste",
    ),
)

def consignes() -> str:
    """Le texte envoyé avec les PDF — DÉRIVÉ du squelette, jamais retapé."""
    lignes = [
        "Tu analyses le ou les contrats joints pour le conseil syndical d'une copropriété.",
        "",
        "Réponds UNIQUEMENT par un objet JSON, sans texte autour et sans bloc de code.",
        "Il porte exactement les clés suivantes :",
        "",
    ]
    for r in SQUELETTE:
        if r.forme == "champs":
            attendu = "objet dont les clés sont exactement : " + ", ".join(
                f'"{c}"' for c in r.champs
            )
        elif r.forme == "liste":
            attendu = "tableau de chaînes"
        else:
            attendu = "chaîne"
        lignes.append(f'- "{r.cle}" ({attendu}) — {r.titre} : {r.consigne}')
        lignes.append(
            f'- "{r.cle}{SUFFIXE_CITATION}" (chaîne) — un extrait VERBATIM du contrat, '
            "recopié mot pour mot, qui fonde cette section. Chaîne vide si aucune "
            "phrase du document ne la fonde."
        )
    lignes += [
        "",
        "Règles impératives :",
        f'- Ce que le document ne dit pas s\'écrit exactement "{NON_PRECISE}". '
        "N'invente aucune date, aucun montant, aucun délai, aucune fréquence.",
        "- N'écris aucune balise HTML ni Markdown : du texte brut dans chaque valeur.",
        "- Reprends les termes du contrat plutôt que de les reformuler quand ils sont "
        "précis (montants, préavis, fréquences, articles).",
        "- Rédige en français, au présent, sans formule d'introduction ni de conclusion.",
    ]
    return "\n".join(lignes)

def extraire_objet(texte: str) -> dict[str, Any]:
    """L'objet JSON contenu dans la réponse, même entouré de bavardage.

    ⚠️ La consigne demande du JSON nu et ce n'est PAS une garantie : un modèle
    encadre volontiers sa réponse d'un bloc ``` ou d'une phrase. Échouer là-dessus
    donnerait une erreur incompréhensible pour un défaut cosmétique — on retire
    donc la clôture, puis on retient le plus grand objet accolé.
    """
    nu = texte.strip()
    nu = re.sub(r"^```(?:json)?\s*", "", nu)
    nu = re.sub(r"\s*```$", "", nu).strip()
    try:
        objet = json.loads(nu)
    except json.JSONDecodeError:
        debut, fin = nu.find("{"), nu.rfind("}")
        if debut == -1 or fin <= debut:
            raise SyntheseIndisponible(
                "Le service n'a pas renvoyé une synthèse lisible. Réessayer dans un instant."
            ) from None
        try:
            objet = json.loads(nu[debut : fin + 1])
        except json.JSONDecodeError:
            raise SyntheseIndisponible(
                "Le service n'a pas renvoyé une synthèse lisible. Réessayer dans un instant."
            ) from None
    if not isinstance(objet, dict):
        raise SyntheseIndisponible(
            "Le service n'a pas renvoyé une synthèse lisible. Réessayer dans un instant."
        )
    return objet


def _lignes(valeur: Any) -> list[str]:
    """Les entrées d'une rubrique en liste, quelle que soit la forme reçue.

    Une chaîne est acceptée là où un tableau est demandé : le modèle s'y trompe
    régulièrement, et refuser la réponse entière pour cela ferait perdre les dix
    autres rubriques. On coupe alors sur les retours à la ligne et les puces.
    """
    if isinstance(valeur, list):
        return [str(v).strip() for v in valeur if str(v).strip()]
    if isinstance(valeur, str):
        brut = [re.sub(r"^[-•*]\s*", "", l).strip() for l in valeur.splitlines()]
        return [l for l in brut if l]
    return []


def _non_precise() -> str:
    return f"<em>{escape(NON_PRECISE)}</em>"


def _citation(objet: dict[str, Any], rubrique: Rubrique) -> str:
    """L'extrait du contrat qui fonde la section, en exergue — ou rien.

    Les guillemets sont posés ICI et non demandés au modèle : à lui de les
    écrire, la moitié des sections en porterait deux paires et l'autre aucune.
    On retire donc ceux qu'il aurait mis quand même.
    """
    brut = objet.get(f"{rubrique.cle}{SUFFIXE_CITATION}")
    if not isinstance(brut, str):
        return ""
    texte = brut.strip().strip('"').strip("«»").strip()
    if not texte or texte == NON_PRECISE:
        return ""
    return f"<blockquote>«\u00a0{escape(texte)}\u00a0»</blockquote>"


def rendre_html(objet: dict[str, Any]) -> str:
    """Le HTML de la synthèse — composé ICI, à partir du squelette.

    Chaque valeur passe par `escape()` : ce qui vient du modèle est du TEXTE, et
    il le reste jusqu'au bout. Les balises employées sont celles que
    `sanitize.ts` admet — un rendu qui en emploierait d'autres serait nettoyé à
    l'affichage sans que rien ne le signale, et c'est ce que vérifie
    `test_synthese_contrat.py` en LISANT la liste dans `sanitize.ts`.

    ⚠️ Le numéro de section vient de la POSITION dans `SQUELETTE`, jamais du
    libellé : réordonner les sections renumérote, et deux sections ne peuvent pas
    porter le même chiffre.
    """
    morceaux: list[str] = []
    for rang, r in enumerate(SQUELETTE, start=1):
        valeur = objet.get(r.cle)
        morceaux.append(f"<h3>{rang}. {escape(r.titre)}</h3>")

        if r.forme == "champs":
            #  Les libellés sont ceux du squelette, dans SON ordre : un libellé
            #  que le modèle aurait inventé n'est pas rendu, un libellé qu'il
            #  aurait omis ressort « non précisé ». Même garantie que pour les
            #  sections, un cran plus bas.
            fourni = valeur if isinstance(valeur, dict) else {}
            entrees = []
            for libelle in r.champs:
                brut = fourni.get(libelle)
                texte = str(brut).strip() if brut is not None else ""
                rendu = escape(texte) if texte and texte != NON_PRECISE else _non_precise()
                entrees.append(f"<li><strong>{escape(libelle)}</strong> : {rendu}</li>")
            morceaux.append(f"<ul>{''.join(entrees)}</ul>")

        elif r.forme == "liste":
            entrees = _lignes(valeur)
            if not entrees or (len(entrees) == 1 and entrees[0] == NON_PRECISE):
                morceaux.append(f"<p>{_non_precise()}</p>")
            else:
                puces = "".join(f"<li>{escape(e)}</li>" for e in entrees)
                morceaux.append(f"<ul>{puces}</ul>")

        else:
            texte = str(valeur).strip() if valeur is not None else ""
            if not texte or texte == NON_PRECISE:
                morceaux.append(f"<p>{_non_precise()}</p>")
            else:
                paragraphes = [p.strip() for p in texte.split("\n") if p.strip()]
                morceaux += [f"<p>{escape(p)}</p>" for p in paragraphes]

        morceaux.append(_citation(objet, r))
    return "".join(morceaux)
