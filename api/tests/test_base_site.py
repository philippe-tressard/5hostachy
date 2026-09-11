"""L'adresse du site est normalisée en UN endroit, et nulle part ailleurs.

## L'incident (11/09/2026, signalé à l'écran)

Un e-mail de ticket adressé au syndic portait le lien
`https://5hostachy.fr//tickets/34` — **double barre, 404**. La valeur en base
valait `https://5hostachy.fr/`, et tous les modèles écrivent
`{{ app.url }}/tickets/{{ ticket.id }}`.

## Pourquoi ce test, et pas juste un `rstrip` de plus

Le défaut n'était pas dans le modèle d'e-mail : `site_url` était lu à une
vingtaine d'endroits dans l'API, dont **onze** ne retiraient pas la barre finale.
Les autres le faisaient chacun dans leur coin, par un `rstrip("/")` recopié — la
forme canonique de la duplication. Corriger le chemin signalé aurait laissé les
dix autres, et le défaut serait revenu par celui qu'on n'a pas relu.

Ce test refuse donc qu'une douzième copie apparaisse : toute lecture de
`site_url` destinée à fabriquer une URL passe par `base_site`.

⚠️ Il ne regarde pas `rstrip` — un test qui cherche le REMÈDE passe à côté de la
douzième copie qui l'écrit autrement (`.strip('/')`, une f-string, un `removesuffix`).
Il regarde la LECTURE de la clé, qui est le geste commun à toutes les formes.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.utils.liens import DEFAUT_SITE, base_site

RACINE = Path(__file__).resolve().parents[1] / "app"

#: Les fichiers autorisés à lire `site_url` sans passer par `base_site`.
#:
#: Chacun a son motif, et un motif qui cesse d'être vrai fait échouer le test :
#: une exception reconduite « au cas où » protège un fichier qui n'en a plus
#: besoin et masque la prochaine vraie copie.
EXCEPTIONS: dict[str, str] = {
    #  🔴 VIDE, et c'est le but : `base_site` est le seul chemin. Le motif
    #  ci-dessous ne relève que les lectures de VALEUR, jamais les ensembles de
    #  clés à charger — il n'y avait donc pas de cas légitime à excuser.
    #  Si l'un apparaît, il s'écrit ici AVEC son motif : une exception non écrite
    #  n'est pas une exception, c'est un oubli qui ressemble à une décision.
}

#: Une lecture de VALEUR — `get("site_url")` ou `cfg["site_url"]`. Un ensemble de
#: clés à charger (`{"site_nom", "site_url"}`) n'en est pas une : c'est la requête
#: qui rapporte la ligne, et la valeur sera lue ailleurs. Viser la notion, pas la
#: chaîne (`standards/04` §40).
#: 🔴 DEUX formes de lecture, parce qu'une 23ᵉ copie s'est cachée derrière la
#: seconde : `session.get(ConfigSite, "site_url")` lit la même valeur que
#: `cfg.get("site_url")`, et `utils/reponses.py` y écrivait son propre `rstrip`.
#: Un contrôle qui ne connaît qu'une écriture de la notion laisse passer l'autre
#: (`standards/04` §40 — viser la NOTION, pas la forme déjà rencontrée).
LECTURE = re.compile(
    r"""(?:\.get\(|\[)\s*["']site_url["']|session\.get\(\s*ConfigSite\s*,\s*["']site_url["']"""
)


def _fichiers():
    for f in sorted(RACINE.rglob("*.py")):
        rel = f.relative_to(RACINE).as_posix()
        yield rel, f


def _portees(src: str):
    """Chaque fonction du module, avec son texte — la lecture et sa normalisation
    n'étant pas forcément sur la même LIGNE (`utils/reponses.py` lit la ligne de
    configuration puis appelle `base_site` deux lignes plus bas). Le module
    lui-même compte comme une portée, pour le code hors fonction."""
    arbre = ast.parse(src)
    lignes = src.splitlines()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield n.name, ("\n").join(lignes[n.lineno - 1 : n.end_lineno]), n.lineno


def test_aucune_lecture_de_site_url_hors_de_base_site():
    fautifs = []
    for rel, f in _fichiers():
        if rel in EXCEPTIONS:
            continue
        src = f.read_text(encoding="utf-8")
        #  Les commentaires ne sont pas du code : ce fichier-ci en parle
        #  abondamment, et un contrôle qui lit son propre récit se déclenche sur
        #  lui-même (`standards/04` §39).
        for nom, corps, debut in _portees(src):
            code = ("\n").join(
                l for l in corps.splitlines() if not l.lstrip().startswith("#")
            )
            if not LECTURE.search(code):
                continue
            #  Une clause SQL qui SÉLECTIONNE la ligne de configuration n'est pas
            #  une lecture de valeur : c'est la requête qui la rapporte.
            code_utile = ("\n").join(
                l for l in code.splitlines()
                if "cle.in_" not in l and "ConfigSite.cle" not in l
            )
            if not LECTURE.search(code_utile):
                continue
            if "base_site(" in code_utile:
                continue
            fautifs.append(f"{rel}:{debut}  fonction `{nom}`")
    assert not fautifs, (
        "site_url lu sans passer par `base_site` — la barre finale repassera :\n  "
        + ("\n  ").join(fautifs)
    )


def test_les_exceptions_declarees_servent_TOUTES():
    """Une exception qui ne sert plus se retire — sinon elle masque la suivante."""
    inutiles = []
    for rel, motif in EXCEPTIONS.items():
        f = RACINE / rel
        if not f.exists():
            inutiles.append(f"{rel} — le fichier a disparu ({motif})")
            continue
        if not LECTURE.search(f.read_text(encoding="utf-8")):
            inutiles.append(f"{rel} — ne lit plus site_url ({motif})")
    assert not inutiles, "Exceptions périmées :\n  " + "\n  ".join(inutiles)


@pytest.mark.parametrize(
    "valeur, attendu",
    [
        ("https://5hostachy.fr/", "https://5hostachy.fr"),
        ("https://5hostachy.fr", "https://5hostachy.fr"),
        ("https://5hostachy.fr///", "https://5hostachy.fr"),
        ("  https://5hostachy.fr/  ", "https://5hostachy.fr"),
        #  Un sous-chemin est légitime (le produit peut vivre sous /copro) : on
        #  n'enlève que la barre FINALE, jamais un segment.
        ("https://exemple.fr/copro/", "https://exemple.fr/copro"),
    ],
)
def test_la_barre_finale_disparait_sans_toucher_au_reste(valeur, attendu):
    assert base_site(valeur) == attendu


@pytest.mark.parametrize("vide", [None, "", "   ", "/", "///"])
def test_une_valeur_vide_rend_le_DEFAUT_jamais_une_chaine_vide(vide):
    """⚠️ Une chaîne vide produirait `"/tickets/34"` — un lien sans domaine, qui
    part quand même dans l'e-mail et n'ouvre rien. Une adresse manifestement
    fausse se voit ; un lien muet se clique."""
    assert base_site(vide) == DEFAUT_SITE


def test_le_lien_complet_ne_porte_JAMAIS_de_double_barre():
    """Le fait signalé, reproduit : c'est cette chaîne-là qui rendait 404."""
    lien = f"{base_site('https://5hostachy.fr/')}/tickets/34"
    assert lien == "https://5hostachy.fr/tickets/34"
    assert "//tickets" not in lien


def test_la_normalisation_est_branchee_a_l_ENREGISTREMENT():
    """Normaliser à la lecture suffit à réparer les liens, mais laisse la donnée
    sale en base — et le prochain lecteur qui l'oubliera repartira de là."""
    src = (RACINE / "routers" / "config.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)
    noms = {
        n.targets[0].id
        for n in ast.walk(arbre)
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
    }
    assert "_NORMALISEURS" in noms
    assert "_NORMALISEURS[cle](valeur)" in src, "la table est déclarée mais jamais appliquée"
