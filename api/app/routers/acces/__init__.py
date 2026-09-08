"""Router accès — badges Vigik, télécommandes, et les imports qui les alimentent.

`acces.py` faisait **981 lignes**. Découpé le 06/09/2026, au fil de l'eau :
enrichir la lecture des badges pour qu'elle dise enfin **qui les porte** (#805)
l'avait fait passer de 962 à 981, et c'est le garde-fou de modularité qui a
refusé le lot.

C'est le deuxième découpage de la journée, après `bailleur/` — et la règle a
fonctionné deux fois de la même façon : on ne découpe pas parce qu'un fichier est
gros, on découpe **quand on y touche**.

## La règle de découpage : un domaine, un module

| Module | Ce qui y change | Lignes |
|---|---|---|
| `resident` | ce qu'un porteur fait de ses badges, plus les deux lectures du CS | 407 |
| `imports_telecommandes` | l'import Excel des télécommandes et son appariement | 384 |
| `imports_vigik` | idem pour les badges Vigik | 276 |
| `commun` | la normalisation des noms, employée par les DEUX imports | 50 |

## 🔴 Ce qu'on a cru ne PAS pouvoir fusionner — et qui a fini par diverger

Cette note affirmait, du 06/09 au 08/09/2026, que fondre les deux modules
d'import « demanderait un paramétrage qui coûterait plus cher que les deux
fichiers », au nom de `standards/02` §4 : *deux morceaux qui se ressemblent par
hasard*.

**C'était faux, et un défaut en production l'a établi** (#847). Deux morceaux qui
se ressemblent par hasard ne divergent pas sur la même ligne : ils n'ont pas la
même ligne. Ceux-ci en avaient une — le report de `chez_locataire` sur l'objet
créé — et seul le côté télécommande la portait. Un badge Vigik remis à un
locataire arrivait donc marqué « chez le propriétaire », et se reproposait au
transfert vers le locataire suivant.

Le cycle des deux imports vit désormais dans `socle_imports`, avec l'objet
`TypeImportAcces` qui porte les **six** différences réelles. Ce qui reste
séparé est ce qui diffère vraiment :

| Ce qui reste séparé | Pourquoi |
|---|---|
| `utils/import_telecommandes.py`, `utils/import_vigiks.py` | ni les mêmes colonnes ni les mêmes règles de lecture de l'Excel |
| `_etape_lot_par_adresse` (vigik) | le fichier Vigik porte bâtiment + appartement ; celui des télécommandes ne les a pas |
| `refuser-locataire` (télécommande) | asymétrie **déclarée** dans `test_symetrie_imports_acces.py` |

⚠️ La leçon n'est pas « fusionner davantage ». Elle est que **le seul fichier
qui parlait du sujet disait que le problème n'existait pas** — le même motif que
les quatre copies des destinataires CS (`CLAUDE.md`), dont l'une affirmait être
« le seul endroit où cette règle s'écrit ».

## Ordre de montage

`resident` en premier : ses chemins sont les plus courts (`/mes-vigiks`,
`/declarer-badge`) et les plus spécifiques (`/admin/vigiks` avant les
`/admin/imports-vigik/{id}` des autres modules). Les 31 chemins sont identiques
au caractère près à ceux d'avant le découpage — trois routes d'écriture en moins,
supprimées sur arbitrage le même jour (#805).
"""
from fastapi import APIRouter

from . import imports_telecommandes, imports_vigik, resident

router = APIRouter(prefix="/acces", tags=["acces"])

router.include_router(resident.router)
router.include_router(imports_vigik.router)
router.include_router(imports_telecommandes.router)
