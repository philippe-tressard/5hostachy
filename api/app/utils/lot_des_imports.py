"""Le LOT d'une ligne d'import de badges, retrouvé sans aucun compte (#1194).

## Pourquoi le lot, et pas le propriétaire

Un badge appartient au lot (`utils/porteurs_acces`). Tant qu'on l'attribuait à
une personne, une ligne ne se résolvait que si son propriétaire avait un compte
— et la plupart n'en ont pas : sur la sauvegarde du 23/09, 124 lignes de
télécommandes et 129 de Vigik attendaient une inscription qui ne viendra
peut-être jamais. Le lot, lui, se lit dans les fichiers du syndic.

| Badge | Ce que son fichier donne | Comment on retrouve le lot |
|---|---|---|
| Vigik | bâtiment + appartement | directement — 180 lignes sur 182 |
| télécommande | le seul nom du copropriétaire | ce nom, dans le **fichier des lots**, désigne un copropriétaire ; son **premier** parking (à défaut, son premier lot) |

## 🔴 Ce que ce module remplace

La règle du Vigik était écrite **deux fois** : `_etape_lot_par_adresse` dans le
routeur des imports, `_resoudre_lot_vigik` dans l'appariement à l'inscription.
La télécommande n'en avait aucune, faute de colonnes.

## ⚠️ Ce qu'il ne fait pas : deviner la PERSONNE

Un nom qui désigne deux copropriétaires ne rattache rien : la ligne reste à
préciser à l'écran. Le nom COMPLET départage d'abord — « DUBREUIL FRANCOIS »
parmi trois DUBREUIL —, puis le NOM DE FAMILLE (le premier mot : « PARIS »
désigne « PARIS Francis » et non la « BANQUE NATIONALE DE PARIS », signalé le
23/09/2026), puis un nom inclus dans un seul, puis un mot commun à un seul. Un badge rattaché au mauvais copropriétaire montrerait son code aux
voisins.

Plusieurs PARKINGS, en revanche, ne bloquent plus (arbitré le 23/09/2026 :
« si plusieurs parkings, prendre le 1er ») : les porteurs sont les mêmes —
ceux du copropriétaire —, seul le numéro affiché change, et il se corrige.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from sqlmodel import Session, select

from app.models.copropriete import Lot
from app.models.core import LotImport
from app.utils.auto_match_service import _cle_de_nom
from app.utils.import_xlsx import normaliser
from app.utils.valeurs import valeur

#: Les mots d'un nom qui ne désignent personne en particulier. Sans eux,
#: « Madame X » et « Madame Y » seraient le même copropriétaire.
_MOTS_VIDES = {
    "madame", "monsieur", "mademoiselle", "epoux", "epouse", "indivision",
    "succession", "consorts", "veuve", "societe", "mme", "des", "les", "ste", "sci", "cie",
}


def _mots(nom: str | None) -> set[str]:
    #  Trois lettres suffisent : « LUC », « ROY » départagent, et les écarter
    #  rendait « BERNARD Luc » indiscernable de « BERNARD » tout court.
    return {m for m in _cle_de_nom(nom).split() if len(m) >= 3 and m not in _MOTS_VIDES}


def _famille(nom: str | None) -> str:
    """Le nom de famille d'un fichier du syndic : son premier mot significatif."""
    for m in _cle_de_nom(nom).split():
        if len(m) >= 3 and m not in _MOTS_VIDES:
            return m
    return ""


def _par_adresse(session: Session) -> Callable[[object], int | None]:
    """Vigik : le lot par son bâtiment et son appartement."""
    from app.utils.import_vigiks import _build_lot_index

    index = _build_lot_index(session)

    def trouver(imp) -> int | None:
        if not imp.batiment_raw or not imp.appartement_raw:
            return None
        return index.get((normaliser(imp.batiment_raw), normaliser(imp.appartement_raw)))

    return trouver


def _par_coproprietaire(session: Session, nature: str) -> Callable[[object], int | None]:
    """Télécommande : le nom du fichier → un copropriétaire du fichier des lots → son lot."""
    natures = {lot.id: valeur(lot.type) for lot in session.exec(select(Lot)).all()}
    numeros = {lot.id: lot.numero for lot in session.exec(select(Lot)).all()}
    lots_de: dict[str, set[int]] = defaultdict(set)
    mots_de: dict[str, set[str]] = {}
    famille_de: dict[str, str] = {}
    for li in session.exec(select(LotImport).where(LotImport.lot_id != None)).all():  # noqa: E711
        copro = li.no_coproprietaire or li.nom_coproprietaire
        if not copro:
            continue
        mots_de.setdefault(copro, _mots(li.nom_coproprietaire))
        famille_de.setdefault(copro, _famille(li.nom_coproprietaire))
        lots_de[copro].add(li.lot_id)

    def premier(lots: set[int]) -> int | None:
        """Le premier parking par numéro, à défaut le premier lot."""
        ordre = sorted(lots, key=lambda i: (natures.get(i) != nature, _cle_numero(numeros.get(i))))
        return ordre[0] if ordre else None

    def trouver(imp) -> int | None:
        mots = _mots(imp.nom_proprietaire)
        if not mots:
            return None
        famille = _famille(imp.nom_proprietaire)
        #  Du plus sûr au plus large ; le premier palier qui désigne UN
        #  copropriétaire l'emporte, un palier ambigu arrête la recherche.
        paliers = (
            lambda c: mots_de[c] == mots,
            lambda c: len(mots) == 1 and famille_de[c] == famille,
            lambda c: mots <= mots_de[c],
            lambda c: bool(mots_de[c] & mots),
        )
        for garder in paliers:
            candidats = [c for c in mots_de if garder(c)]
            if len(candidats) == 1:
                return premier(lots_de[candidats[0]])
            if candidats:
                return None
        return None

    return trouver


def _cle_numero(numero: str | None) -> tuple:
    """« 9 » avant « 10 » : un numéro de lot se trie comme un nombre quand il en est un."""
    n = (numero or "").strip()
    return (0, int(n), "") if n.isdigit() else (1, 0, n)


def trouveur_de_lot(type_acces, session: Session) -> Callable[[object], bool]:
    """Rend l'étape qui pose le lot d'une ligne, et dit si elle l'a posé.

    Les index sont bâtis UNE fois : l'appariement parcourt des centaines de
    lignes, et relire tous les lots pour chacune le rendrait quadratique.
    """
    if type_acces.acces_suit_le_lot:
        trouver = _par_adresse(session)
    else:
        trouver = _par_coproprietaire(session, type_acces.types_lot[0])

    def etape(imp) -> bool:
        if imp.lot_id:
            return False
        lot_id = trouver(imp)
        if lot_id:
            imp.lot_id = lot_id
        return bool(lot_id)

    return etape


__all__ = ["trouveur_de_lot"]
