r"""Le manuel ne RECOPIE plus de valeur technique — il n'en cite aucune.

## 🔴 Ce fichier remplace deux contrôles, et le remplacement EST la décision

Jusqu'au 02/09/2026, `test_manuel_chiffres.py` et `test_manuel_concordance.py`
vérifiaient que les valeurs recopiées dans le manuel **correspondaient** à celles
du code : « 10 pièces jointes », « 5 Mo par photo, 15 Mo par document », « PDF,
Word, Excel ou texte », les cinq descriptions de catégories de ticket. Ils
existaient parce que ces copies avaient divergé quatre fois, dont une pendant
deux semaines — le manuel promettait deux fois moins de photos que
l'application n'en accepte.

La refonte de #651 a fait le choix inverse : **le manuel ne cite plus ces valeurs
du tout**. Il est passé de 3 111 à environ 1 100 lignes, sur arbitrage —
*« beaucoup trop complexe et trop long ; seule la partie Démarrer est
suffisante »*. Le détail vit dans l'application, où il ne peut pas se périmer.

Les deux anciens contrôles ont donc perdu leur objet, et un contrôle dont la
cible a disparu est **vert en ne mesurant plus rien**. Les supprimer sans rien
mettre à la place aurait laissé la porte ouverte : rien n'aurait empêché la
première section « pratique » de réintroduire « 15 Mo » un an plus tard.

## Ce que celui-ci vérifie

Non plus la concordance d'une copie, mais **l'absence de copie**. C'est plus fort
et plus simple : on n'a rien à tenir à jour, et le seul moyen de le faire échouer
est d'écrire dans le manuel une valeur dont le code est la source.

⚠️ Il ne prétend pas lire la prose — c'est impossible sans se tromper, et un
contrôle qui crie sur du légitime finit désarmé. Il cherche des **formes
précises** : un nombre suivi d'une unité technique, une extension de fichier, une
énumération de catégories. « 3 minutes pour démarrer » n'en est pas une : aucune
constante du code ne dit combien de temps prend une lecture.
"""
from __future__ import annotations

import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_MANUEL = _RACINE / "docs" / "manuel-utilisateur.html"

#: Ce qui trahit une valeur RECOPIÉE depuis le code, avec ce qu'elle vaut.
#:
#: Chaque motif nomme sa source : c'est elle qui décide, et le manuel n'a pas à
#: la répéter. Une entrée sans source ne serait qu'une interdiction de vocabulaire.
INTERDITS = {
    "une taille de fichier": (
        re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:Mo|Ko|MB|KB)\b"),
        "la source est `MAX_SIZE_MB` / `MAX_SIZE_MB_DOC` (api/app/routers/uploads.py) ; "
        "l'écran l'affiche déjà au bon endroit, au moment de joindre un fichier",
    ),
    "un nombre de pièces jointes": (
        re.compile(r"\b\d+\s*(?:photos|documents|fichiers|pi[eè]ces jointes)\b", re.IGNORECASE),
        "la source est `MAX_FICHIERS` ; le manuel l'a annoncé faux pendant deux semaines",
    ),
    "une liste d'extensions acceptées": (
        re.compile(r"\.(?:pdf|docx?|xlsx?|txt)\b", re.IGNORECASE),
        "la source est la liste des types acceptés côté serveur",
    ),
    "un délai en jours": (
        re.compile(r"\b\d+\s*jours?\b", re.IGNORECASE),
        "les délais (archivage, relance, rétention) sont administrables : "
        "les écrire ici les fige à la valeur d'un jour donné",
    ),
}


def _corps() -> str:
    """Le manuel SANS son CSS ni ses icônes.

    Le CSS est plein de `.5rem` et de `24px`, et les tracés d'icônes de nombres :
    les scanner ferait échouer le contrôle sur du décor, et un contrôle qui crie
    sur du légitime finit désarmé.
    """
    texte = _MANUEL.read_text(encoding="utf-8")
    texte = texte[texte.index("</style>"):]
    return re.sub(r"<svg.*?</svg>", "", texte, flags=re.S)


def test_le_manuel_ne_cite_aucune_valeur_dont_le_code_est_la_source():
    corps = _corps()
    fautes = []
    for quoi, (motif, source) in INTERDITS.items():
        for trouve in set(motif.findall(corps)):
            fautes.append(f"  « {trouve} » — {quoi} : {source}")
    assert not fautes, (
        "Le manuel recopie des valeurs dont le code est la source :\n"
        + "\n".join(sorted(fautes))
        + "\n\nUne valeur recopiée diverge — c'est arrivé quatre fois ici. "
        "Le manuel dit ce qu'on peut faire ; l'application dit avec quelles limites."
    )


def test_le_controle_lit_bien_le_manuel():
    """Cas zéro. Un fichier introuvable ou un corps vide rendrait la même
    liste vide qu'un manuel irréprochable.
    """
    corps = _corps()
    #  Plancher calé sur le manuel refondu (~15 900 caractères de corps), pas sur
    #  l'ancien de 3 000 lignes : un plancher trop haut ferait échouer le contrôle
    #  sur sa propre réussite, et un plancher à zéro ne distinguerait rien.
    assert len(corps) > 10_000, f"corps de {len(corps)} caractères : rien n'a été lu"
    assert "ecran-card" in corps, "la grille des écrans est absente : ce n'est pas le manuel"
    #  Et les motifs doivent mordre quand il y a de quoi mordre.
    assert INTERDITS["une taille de fichier"][0].search("jusqu'à 15 Mo par fichier")
    assert INTERDITS["un nombre de pièces jointes"][0].search("5 photos maximum")
    assert not INTERDITS["un délai en jours"][0].search("3 minutes pour démarrer")
