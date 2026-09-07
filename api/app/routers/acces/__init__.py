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

## ⚠️ Ce qui n'a PAS été fusionné, et pourquoi

Les deux modules d'import se ressemblent beaucoup. Ils ne sont pas fusionnés :
les fichiers sources n'ont ni les mêmes colonnes ni les mêmes règles
d'appariement — le vigik porte un code, la télécommande un numéro de série et un
drapeau « chez le locataire ». Les fondre demanderait un paramétrage qui coûterait
plus cher que les deux fichiers.

🔴 Ce qu'ils partagent **vraiment**, en revanche, est dans `commun` :
`_normaliser`, qui rapproche un nom du fichier Excel d'un nom en base. Deux copies
auraient divergé sur un accent, et le même résident aurait été reconnu d'un côté
et pas de l'autre.

⚠️ C'est la distinction de `standards/02` §4 : *deux morceaux qui se ressemblent
par hasard* (les deux imports) contre *une même règle écrite deux fois* (la
normalisation). Seule la seconde se factorise.

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
