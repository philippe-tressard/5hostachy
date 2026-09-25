"""Un réglage propre à un usage de l'assistant vit DANS son bloc (#1324).

Signalé à l'écran le 25/09/2026 : la case « Envoyer le document du contrat au
service » était rendue à côté de `BlocUsageIA`, donc hors de son `<details>` —
le bloc « Synthèse de contrat » replié la laissait visible sous lui, seul des
trois. Elle passe désormais par l'emplacement `option` du bloc.

Ce test lit l'écran : dans la boucle des usages, rien d'autre que le bloc.
"""

from __future__ import annotations

import pathlib
import re

_ONGLET = (
    pathlib.Path(__file__).resolve().parents[2]
    / "front"
    / "src"
    / "lib"
    / "components"
    / "OngletIA.svelte"
)


def corps_de_la_boucle(source: str) -> str:
    """Le corps de `{#each usages …}`, commentaires retirés."""
    m = re.search(r"\{#each usages as usage \(usage\.code\)\}(.*?)\{/each\}", source, re.S)
    assert m, "la boucle des usages est introuvable — le contrôle ne mesure rien"
    return re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S).strip()


def test_la_boucle_des_usages_ne_rend_que_le_bloc():
    corps = corps_de_la_boucle(_ONGLET.read_text(encoding="utf-8"))
    assert corps.startswith("<BlocUsageIA") and corps.endswith("</BlocUsageIA>"), (
        "La boucle des usages rend autre chose que BlocUsageIA : un réglage posé "
        "À CÔTÉ du bloc reste visible quand il est replié. Le passer par "
        '<svelte:fragment slot="option">.'
    )


def test_le_controle_refuse_la_forme_d_avant():
    avant = (
        "{#each usages as usage (usage.code)}<BlocUsageIA {usage} />"
        "{#if usage.code === 'synthese_contrat'}<label>x</label>{/if}{/each}"
    )
    corps = corps_de_la_boucle(avant)
    assert not corps.endswith("</BlocUsageIA>")
