"""La composition du conseil et du syndic ne s'écrit qu'à UN endroit (09/09/2026).

## Le défaut

`routers/admin/annuaire.py` (l'écran) et `routers/admin/arrivants.py` (la fiche
d'accueil remise aux nouveaux résidents) construisaient la même liste, avec le
même tri, les mêmes caches et les mêmes clés — **trente et une lignes identiques
au caractère près**. Le second l'annonçait : *« même logique que
GET /admin/annuaire »*, ce qui est la signature d'une copie qui se sait copie et
que personne ne rapproche.

Elles avaient déjà divergé :

* `est_gestionnaire_site` s'écrivait `site_manager_user_id is not None and …` d'un
  côté, `site_manager_user_id and …` de l'autre — deux réponses différentes pour
  l'identifiant `0` ;
* l'une rendait `id`, l'autre `batiment_id`.

C'est la forme la plus coûteuse de duplication d'un **rendu** : les deux sorties
décrivent le même objet — le conseil syndical — et personne ne les compare, parce
qu'elles vivent sur deux écrans différents (`standards/11` §14).

## Ce que ce fichier verrouille

Le **tri** et la composition, par leur marqueur le plus distinctif : la sentinelle
`9999` qui range les membres sans bâtiment en dernier. Un fichier qui la réécrit
vient de recopier le tri, et le tri est la moitié de la composition.
"""
from __future__ import annotations

import ast
import pathlib

RACINE = pathlib.Path(__file__).resolve().parents[1] / "app"
SOURCE = "utils/annuaire.py"

#: La sentinelle du tri : « pas de bâtiment » se range après tous les bâtiments.
SENTINELLE = 9999


def _fichiers():
    return [p for p in RACINE.rglob("*.py") if "__pycache__" not in p.parts]


def _emploie_la_sentinelle(source: str) -> bool:
    """Cherche la VALEUR dans le code, jamais le texte : la prose la cite."""
    return any(
        isinstance(n, ast.Constant) and n.value == SENTINELLE
        for n in ast.walk(ast.parse(source))
    )


def test_le_tri_du_conseil_n_est_ecrit_qu_une_fois():
    fautifs = [
        p.relative_to(RACINE).as_posix()
        for p in _fichiers()
        if p.relative_to(RACINE).as_posix() != SOURCE
        and _emploie_la_sentinelle(p.read_text(encoding="utf-8"))
    ]
    assert not fautifs, (
        "Ces fichiers rangent eux-mêmes les membres du conseil : "
        + ", ".join(sorted(fautifs))
        + ". Employer `membres_du_conseil` de `app.utils.annuaire` — deux tris "
        "d'une même liste finissent par se contredire, et sur deux écrans que "
        "personne ne compare."
    )


def test_cas_zero_la_source_emploie_bien_la_sentinelle():
    """🔴 Sans elle, le balayage ne cherche plus rien et reste vert.

    C'est le cas zéro de `standards/04` §2 : un contrôle dont le motif ne
    correspond plus à rien ne refuse plus rien, et il ne le dit pas.
    """
    assert _emploie_la_sentinelle((RACINE / SOURCE).read_text(encoding="utf-8")), (
        f"`{SOURCE}` n'emploie plus la sentinelle {SENTINELLE} : ce contrôle ne "
        "reconnaît plus le tri qu'il protège, et laisserait passer une copie."
    )
    assert len(_fichiers()) > 50, "le parcours ne décrit plus `app/`."


def test_les_deux_ecrans_rendent_la_MEME_composition():
    """Le fait, pas la forme : les deux appelants passent-ils par la source ?

    Un test qui ne regarderait que la sentinelle resterait vert si l'un des deux
    reconstituait la liste autrement — mêmes clés, autre tri.
    """
    import inspect

    from app.routers.admin import annuaire, arrivants

    for module, fonction in (
        (annuaire, "annuaire"),
        (arrivants, "get_fiche_arrivant"),
    ):
        source = inspect.getsource(getattr(module, fonction))
        assert "membres_du_conseil" in source, (
            f"`{module.__name__}.{fonction}` ne passe plus par "
            "`membres_du_conseil` : il a repris sa propre composition."
        )
        assert "membres_du_syndic" in source, (
            f"`{module.__name__}.{fonction}` ne passe plus par `membres_du_syndic`."
        )
