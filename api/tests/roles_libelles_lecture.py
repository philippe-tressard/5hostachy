"""Lire `front/src/lib/roles.ts` — la mécanique partagée par les garde-fous.

## Pourquoi ce module (08/09/2026)

`test_roles_libelles.py` a dépassé son plafond de modularité en recevant le
troisième garde-fou de la série (les libellés ABRÉGÉS, #828). Le refus disait
vrai : ce fichier mêlait deux choses de nature différente — les règles à
vérifier, et **comment lire un fichier TypeScript depuis Python**.

🔴 Et la lecture était elle-même dupliquée. `_teintes_par_table` et
`_tables_indexees_par_statut` étaient **le même algorithme** — parcourir les
littéraux d'objet, compter par TABLE et non par ligne, retenir celles qui
dépassent le seuil — à un seul détail près : ce qu'on exige de la **valeur**.
L'une voulait `'badge-…'`, l'autre n'importe quelle chaîne.

Ce qui varie est donc un motif, c'est-à-dire une **donnée**, et non une raison
d'écrire le parcours deux fois. `tables_par_cle` le prend en paramètre.
"""
from __future__ import annotations

import re
from pathlib import Path

#: La source unique des libellés et des teintes, côté front.
ROLES_TS = Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "roles.ts"

#:  Le SEUIL qui distingue une table recopiée d'une homonymie.
#:
#:  🔴 Le comptage se fait par TABLE et non par ligne, et c'est tout le contrôle.
#:  La première version signalait chaque ligne isolément : elle a trouvé
#:  `KANBAN_COLORS` dans `reporting.ts`, où `syndic: 'badge-orange'` désigne la
#:  **colonne du kanban** qui traite le sujet, pas un rôle d'utilisateur. Le mot
#:  est le même, la notion non.
#:
#:  Une table recopiée en porte cinq à onze ; une homonymie en porte une. Deux
#:  est le seuil qui les sépare, et il est **mesuré sur le relevé réel** — pas
#:  choisi pour faire passer le contrôle. Une dérogation nominative pour
#:  `reporting.ts` aurait, elle, laissé passer une vraie table dans ce fichier.
SEUIL_TABLE = 2

#: Ce qu'on exige de la VALEUR — le seul point où les deux contrôles diffèrent.
VALEUR_TEINTE = r"'badge-"
VALEUR_CHAINE = r"['\"]"


def table_ts(source: str, nom: str) -> dict[str, str]:
    """Extrait `export const <nom>: Record<string, string> = { … };` du fichier TS."""
    debut = source.index(f"export const {nom}")
    corps = source[source.index("{", debut) + 1 : source.index("};", debut)]
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r"^\t(\S+?):\s*'([^']*)',", corps, re.MULTILINE)
    }


def tables_par_cle(source: str, cles: set[str], valeur: str) -> list[tuple[int, list[str]]]:
    """Les tables de ce fichier qui associent PLUSIEURS de `cles` à `valeur`.

    Rend `(ligne de départ, entrées trouvées)` pour chaque table dépassant
    `SEUIL_TABLE`. Les commentaires sont ignorés : un contrôle qui se déclenche
    sur la prose qui l'explique finit désarmé.
    """
    lignes = source.splitlines()
    motif = re.compile(
        r"^\s*(" + "|".join(re.escape(c) for c in cles) + r")\s*:\s*" + valeur
    )
    tables: list[tuple[int, list[str]]] = []
    debut, trouvees = None, []
    for numero, ligne in enumerate(lignes, 1):
        nue = ligne.strip()
        if nue.startswith(("//", "*", "/*", "<!--", "#")):
            continue
        if re.search(r"=\s*\{\s*$", ligne):
            debut, trouvees = numero, []
            continue
        if debut is not None and re.match(r"^\s*\}", ligne):
            if len(trouvees) >= SEUIL_TABLE:
                tables.append((debut, trouvees))
            debut, trouvees = None, []
            continue
        if debut is not None and motif.search(ligne):
            trouvees.append(nue[:60])
    return tables


def fichiers_du_front(sauf: str) -> list[tuple[str, str]]:
    """Les `.svelte` et `.ts` du front, hors `sauf` — (chemin relatif, source)."""
    #  `parents[1]` = `front/src` : les chemins relatifs se comptent depuis
    #  `front/`, ce qui donne « src/lib/roles.ts » — la forme sous laquelle les
    #  appelants nomment la source à exclure.
    front = ROLES_TS.parents[1]
    trouves = []
    for fichier in front.rglob("*"):
        if fichier.suffix not in (".svelte", ".ts") or not fichier.is_file():
            continue
        relatif = fichier.relative_to(front.parent).as_posix()
        if relatif == sauf:
            continue
        trouves.append((relatif, fichier.read_text(encoding="utf-8")))
    return trouves
