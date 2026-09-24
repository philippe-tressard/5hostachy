"""Un événement se classe sur sa TENUE, pas sur sa date de saisie (#524).

## Le défaut

Le fil affichait et surtout **classait** l'AG du **22 juin 2026** au **1er mars
2026**, jour de sa saisie :

    AG 2026 : debut = 2026-06-22 18:00   cree_le = 2026-03-01 20:16

Conséquence : l'assemblée **descendait dans le fil à mesure qu'elle approchait**,
et sortait de la fenêtre de chargement avant d'avoir eu lieu.

## Pourquoi une table, et pas un `if`

🔴 Toutes les entités n'ont pas la même « bonne » date, et c'est le fond du
sujet. Une règle unique serait fausse pour au moins un type :

| Objet | Ce qui le classe | Pourquoi |
|---|---|---|
| **événement** | `meta.debut` | on cherche « quoi ENSUITE » |
| publication | l'annonce | on cherche « quoi de NEUF » |
| ticket | la clôture, sinon la dernière activité | idem |

D'où `DATE_QUI_CLASSE`, une table déclarative : le jour où une entité veut une
autre date, elle le **dit**, et la fonction ne bouge pas. Même forme que
l'archivage (#515) et que les périodes par nœud (#542).

## Ce que ce fichier vérifie, et comment

`flux.ts` n'est pas exécutable depuis Python. Le contrôle porte donc sur le
**texte du module** — ce qui suffit à attraper les deux régressions qui comptent :
la table vidée, et la fonction qui cesserait de la consulter.

⚠️ C'est un contrôle plus faible qu'un test d'exécution, et il est écrit en le
sachant. Il vaut mieux que rien : sans lui, vider `DATE_QUI_CLASSE` ramènerait
l'ancien comportement **en silence**, sur le tri de la page la plus regardée du
site.
"""

from __future__ import annotations

import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]
MODULE = _RACINE / "front" / "src" / "lib" / "flux.ts"


def _source() -> str:
    return MODULE.read_text(encoding="utf-8")


def test_le_module_existe():
    """🔴 Cas zéro : un chemin qui ne désigne plus rien rendrait tout vert.

    C'est la forme d'échec la plus coûteuse d'un contrôle textuel — il ne trouve
    rien, ne compare rien, et le dit en vert (`standards/04` §2).
    """
    assert MODULE.is_file(), f"{MODULE} introuvable : ce fichier ne mesure plus rien."
    assert "dateDeReference" in _source(), "la fonction a changé de nom : le contrôle est aveugle."


def test_la_fonction_CONSULTE_la_table():
    """⚠️ Une table déclarée mais jamais lue est pire qu'une absence de table.

    Elle donne l'apparence d'une règle configurable, et le comportement de
    l'ancien code. C'est le même motif que la table des périodes par nœud, dont
    le câblage recopié était aveugle aux deux points d'appel (#542).
    """
    src = _source()
    fonction = re.search(
        r"export function dateDeReference\(item: FluxItem\): number \{(.*?)\n\}", src, re.S
    )
    assert fonction, "`dateDeReference` est introuvable ou a changé de signature."
    assert "DATE_QUI_CLASSE[item.type]" in fonction.group(1), (
        "`dateDeReference` ne consulte plus la table : les déclarations ne "
        "servent à rien, et le comportement est celui d'avant #524."
    )


#  Les deux tests de l'ÉVÉNEMENT — sa date de tenue, lue par les deux règles —
#  sont partis le 23/09/2026 avec lui : c'est une affaire (#1092).
