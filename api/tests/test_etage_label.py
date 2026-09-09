"""Le libellé d'un étage ne dérive pas entre le serveur et le front (08/09/2026).

## Ce qui a mené ici

Le libellé était écrit **treize fois** en tout. Sept ont été réunies le matin du
08/09 derrière `front/src/lib/utils.ts::etageLabel` (#835) ; le contrôle posé
alors ne cherchait que les **comparaisons à zéro** — la forme corrigée du
défaut — et laissait donc passer les six écritures qui n'avaient jamais tenté de
traiter le rez-de-chaussée. Dont celle-ci, côté serveur :

    etage_html = f"Étage {m['etage']}" if m.get("etage") else ""

🔴 Deux défauts en une ligne, et le second est le plus grave : `if m.get("etage")`
est un **test de vérité**, et `0` est faux en Python. Un conseiller du
rez-de-chaussée n'avait donc **aucun étage** sur la fiche d'accueil remise aux
nouveaux arrivants — pas un étage faux, un étage **absent**. Le seul cas où
l'information manquait est celui où elle est la plus simple à donner.

⚠️ La table est écrite deux fois — `app/utils/etages.py` et
`front/src/lib/utils.ts` — parce que les contextes de build sont `./api` et
`./front` : le partage d'un fichier est impossible, seule la copie l'est. C'est
ce test qui rend la copie tenable.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from app.utils.etages import etage_label

_UTILS_TS = (
    pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "utils.ts"
)


@pytest.mark.parametrize(
    "etage,attendu",
    [
        (0, "RDC"),
        (1, "1er"),
        (2, "2ème"),
        (12, "12ème"),
        (-1, "SS 1"),
        (-2, "SS 2"),
    ],
)
def test_les_libelles(etage, attendu):
    assert etage_label(etage) == attendu


def test_le_RDC_n_est_PAS_traite_comme_une_absence():
    """🔴 Le défaut exact de la fiche arrivant.

    `0` est un étage. Un test de vérité le confond avec « pas de valeur », et
    l'information disparaît là où elle est la plus simple.
    """
    assert etage_label(0) == "RDC"
    assert etage_label(0), "le RDC rend une chaîne vide — il serait masqué"


@pytest.mark.parametrize("brut,attendu", [("0", "RDC"), ("3", "3ème"), ("-1", "SS 1")])
def test_une_valeur_en_CHAINE_est_lue(brut, attendu):
    """🔴 La donnée n'est pas toujours un entier, et je l'avais supposé.

    La fiche arrivant construit ses dictionnaires depuis la base ET depuis un
    import, où l'étage arrive parfois en chaîne. Neuf tests existants l'ont dit
    immédiatement — `'<' not supported between instances of 'str' and 'int'`.
    Sans eux, la fiche aurait levé en production, à la génération du document.
    """
    assert etage_label(brut) == attendu


def test_une_valeur_ILLISIBLE_est_rendue_telle_quelle():
    """⚠️ Jamais effacée : perdre l'information serait pire que la montrer brute,
    et c'est précisément le défaut que cette fonction corrige. Même règle que
    `lotTypeLabel` devant un type de lot inconnu.
    """
    assert etage_label("mezzanine") == "mezzanine"
    assert etage_label("") == ""


def test_None_rend_une_chaine_VIDE_pas_un_tiret():
    """L'appelant décide de ce qu'il affiche à la place. Trois sites l'entourent
    déjà d'une condition ; y mettre « — » leur imposerait un tiret dans un tiret.
    """
    assert etage_label(None) == ""


def test_la_fiche_arrivant_ne_teste_plus_la_VERITE_de_l_etage():
    """🔴 Le garde-fou du point d'appel, pas seulement de la règle.

    La fonction peut être parfaite : c'est le `if` de l'appelant qui masquait le
    rez-de-chaussée. C'est la leçon du 06/09 — *« je testais la décision, pas le
    tuyau qui la nourrit »* — et elle vaut ici mot pour mot.
    """
    source = (
        pathlib.Path(__file__).resolve().parents[1] / "app" / "utils" / "fiche_arrivant.py"
    ).read_text(encoding="utf-8")
    assert 'if m.get("etage")' not in source, (
        "le test de vérité est revenu : un conseiller du rez-de-chaussée "
        "n'aurait de nouveau aucun étage sur la fiche."
    )
    assert "etage_label(" in source, "la fiche n'emploie plus la source unique"


def test_le_FRONT_rend_EXACTEMENT_la_meme_chose():
    """🔴 Le garde-fou de la copie assumée.

    ⚠️ On ne peut pas exécuter du TypeScript ici : ce test lit les quatre
    littéraux de `etageLabel` dans sa source et les confronte à ceux du serveur.
    C'est grossier, et c'est ce qui empêche l'un des deux de dériver en silence —
    un « SS » devenu « -1 » d'un côté ne se verrait sur aucun écran de l'autre.
    """
    source = _UTILS_TS.read_text(encoding="utf-8")
    debut = source.index("export function etageLabel")
    corps = source[debut : source.index("\n}", debut)]

    #  Cas zéro : une extraction qui ne trouve rien conclurait au vert sur zéro
    #  comparaison (`standards/04` §2).
    assert len(corps) > 100, "extraction de `etageLabel` cassée"

    for attendu, motif in (
        ("RDC", r"'RDC'"),
        ("SS", r"`SS \$\{Math\.abs\(etage\)\}`"),
        ("1er", r"'1er'"),
        ("ème", r"`\$\{etage\}ème`"),
    ):
        assert re.search(motif, corps), (
            f"le front n'écrit plus « {attendu} » comme le serveur :\n{corps}"
        )


def test_les_BORNES_de_l_etage_ne_derivent_pas_non_plus():
    """Les mêmes deux nombres, des deux côtés (09/09/2026).

    Elles étaient écrites en clair dans `min="-2" max="50"` sur deux écrans et
    dans un `if` de `auth.py`. Un troisième champ s'est ajouté — l'étage d'un lot
    — et une quatrième copie allait suivre. Elles vivent maintenant dans
    `app/utils/etages.py` et `front/src/lib/utils.ts`, pour la même raison que le
    libellé : les contextes de build interdisent le partage, seule la copie est
    possible, et c'est ce test qui la rend tenable.
    """
    from app.utils.etages import ETAGE_MAX, ETAGE_MIN

    source = _UTILS_TS.read_text(encoding="utf-8")
    for nom, attendu in (("ETAGE_MIN", ETAGE_MIN), ("ETAGE_MAX", ETAGE_MAX)):
        trouve = re.search(rf"export const {nom} = (-?\d+);", source)
        assert trouve, (
            f"`{nom}` est introuvable dans `front/src/lib/utils.ts` : la borne "
            "serveur n'a plus de pendant, et les deux peuvent diverger sans que "
            "rien ne le dise."
        )
        assert int(trouve.group(1)) == attendu, (
            f"`{nom}` vaut {trouve.group(1)} côté front et {attendu} côté serveur : "
            "l'écran accepterait une valeur que l'API refuse, ou l'inverse."
        )
