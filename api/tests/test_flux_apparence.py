"""Garde-fou : toute rubrique du fil a une couleur, un fond et un libellé (08/08/2026).

Le fil d'activité émet quinze types. Les trois tables d'apparence du front n'en
couvraient que **dix** : `prestataire`, `document`, `diagnostic`, `faq` et
`annuaire` — les cinq rubriques ajoutées depuis — retombaient sur les valeurs par
défaut, soit **gris de bordure sur fond gris** (contraste 1,15:1, illisible), avec
le nom technique brut en guise de libellé (« PRESTATAIRE »).

Personne ne l'avait vu, et c'est le point : **une pastille grise ressemble à une
pastille**. Le défaut a été signalé par l'utilisateur, pas par un contrôle — c'est
la question 1 du bilan mémoire (`mep-precheck`, P10), donc le contrôle manquant
est la vraie leçon.

Ce test est **inter-langages**, comme `test_liens_front.py` : le producteur des
types est en Python, leur apparence en TypeScript, et rien ne reliait les deux.
Ajouter une rubrique au fil sans son apparence échoue désormais en CI.
"""
import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_FLUX_API = _RACINE / "api" / "app" / "routers" / "flux"
_FLUX_TS = _RACINE / "front" / "src" / "lib" / "flux.ts"

#: `type="…"` dans la construction d'un FluxItem — c'est la seule façon dont une
#: rubrique déclare son type, et elle est littérale partout.
_TYPE_EMIS = re.compile(r'type="([a-z_]+)"')


def _types_emis() -> set[str]:
    """Les types que le backend produit réellement — la PORTÉE du contrôle."""
    fichiers = [f for f in sorted(_FLUX_API.rglob("*.py")) if "__pycache__" not in f.parts]
    assert len(fichiers) >= 10, (
        f"Seulement {len(fichiers)} module(s) sous {_FLUX_API} — la portée du "
        "contrôle est cassée, ne pas lire ce test comme vert."
    )
    types = set()
    for f in fichiers:
        types |= set(_TYPE_EMIS.findall(f.read_text(encoding="utf-8")))
    #  Plancher : un motif cassé rendrait un ensemble vide, et toutes les
    #  inclusions ci-dessous seraient vraies à vide (`standards/04` §2, cas zéro).
    assert len(types) >= 12, (
        f"Seulement {len(types)} type(s) détecté(s) : {sorted(types)} — le "
        "détecteur est cassé, ne pas lire ce test comme vert."
    )
    return types


def _table(nom: str) -> set[str]:
    """Les clés d'une des trois tables d'apparence de `flux.ts`."""
    source = _FLUX_TS.read_text(encoding="utf-8")
    debut = source.index(f"export const {nom}")
    corps = source[debut : source.index("};", debut)]
    #  ⚠️ Plusieurs clés peuvent tenir sur UNE ligne (`TYPE_LABELS` en met trois).
    #  Un motif ancré en début de ligne n'en voyait qu'une sur trois et déclarait
    #  absentes des entrées présentes — faux échec du détecteur, trouvé à sa
    #  première exécution. Une clé suit donc un début de ligne, une accolade ou
    #  une virgule ; les `:` des valeurs (`var(--…)`) ne sont jamais dans ce cas.
    return set(re.findall(r"(?:^|[,{])\s*([a-z_]+):", corps, re.M))


def test_chaque_type_emis_a_une_couleur_un_fond_et_un_libelle():
    emis = _types_emis()
    manques = {}
    for nom in ("TYPE_LABELS", "TYPE_COLORS", "TYPE_BG"):
        absents = emis - _table(nom)
        if absents:
            manques[nom] = sorted(absents)
    assert not manques, (
        "Des rubriques du fil n'ont pas d'apparence déclarée dans "
        f"front/src/lib/flux.ts : {manques}.\n"
        "Sans elles, la pastille s'affiche en gris sur fond gris (illisible) et "
        "porte le nom technique brut. Ajouter les trois entrées — couleur, fond "
        "et libellé — en vérifiant le contraste (AA = 4.5:1)."
    )


def test_aucune_apparence_orpheline():
    """Vérification EN SENS INVERSE : une entrée pour un type qui n'existe plus.

    Sans elle, les tables grossissent à chaque rubrique retirée et personne ne le
    sait — c'est la même exigence que la liste d'exceptions de
    `test_endpoints_orphelins` (`standards/02` §5).
    """
    emis = _types_emis()
    for nom in ("TYPE_LABELS", "TYPE_COLORS", "TYPE_BG"):
        orphelines = _table(nom) - emis
        assert not orphelines, (
            f"{nom} déclare l'apparence de {sorted(orphelines)}, que le backend "
            "n'émet plus. Retirer ces entrées — ou la rubrique a-t-elle été "
            "supprimée sans nettoyer son apparence ?"
        )


def _contraste(avant_plan: str, arriere_plan: str) -> float:
    def luminance(hexa: str) -> float:
        hexa = hexa.lstrip("#")
        canaux = [int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canaux]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    a, b = luminance(avant_plan), luminance(arriere_plan)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def _valeurs(nom: str) -> dict[str, str]:
    source = _FLUX_TS.read_text(encoding="utf-8")
    debut = source.index(f"export const {nom}")
    corps = source[debut : source.index("};", debut)]
    return dict(re.findall(r"(?:^|[,{])\s*([a-z_]+):\s*'([^']+)'", corps, re.M))


def test_chaque_pastille_est_lisible():
    """Contraste texte/fond au niveau AA — c'est la plainte d'origine.

    Six des sept couleurs historiques échouaient : l'ambre à 2,07, l'émeraude à
    2,41. Un contrôle sur la seule PRÉSENCE des entrées aurait laissé passer une
    pastille jaune pâle sur blanc cassé, tout aussi illisible que le gris.
    """
    couleurs, fonds = _valeurs("TYPE_COLORS"), _valeurs("TYPE_BG")
    assert len(couleurs) >= 12, f"TYPE_COLORS n'a que {len(couleurs)} entrées — détecteur cassé"

    trop_pales = []
    for type_, couleur in couleurs.items():
        #  `var(--color-primary)` = #1E3A5F, la couleur de charte : résolue ici
        #  plutôt qu'exclue, sinon la seule entrée non littérale échapperait au
        #  contrôle — exactement le genre de trou qui laisse passer un défaut.
        if couleur.startswith("var("):
            couleur = "#1E3A5F"
        fond = fonds.get(type_)
        if not fond or fond.startswith("var("):
            continue
        rapport = _contraste(couleur, fond)
        if rapport < 4.5:
            trop_pales.append(f"{type_} : {couleur} sur {fond} = {rapport:.2f}:1")

    assert not trop_pales, (
        "Pastilles sous le seuil de lisibilité AA (4.5:1) :\n  "
        + "\n  ".join(trop_pales)
        + "\nUtiliser une teinte foncée (700/800) sur un fond clair (50)."
    )
