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
| télécommande | le seul nom du copropriétaire | ce nom, dans le **fichier des lots**, désigne un copropriétaire ; s'il a **un** parking, c'est lui |

## 🔴 Ce que ce module remplace

La règle du Vigik était écrite **deux fois** : `_etape_lot_par_adresse` dans le
routeur des imports, `_resoudre_lot_vigik` dans l'appariement à l'inscription.
La télécommande n'en avait aucune, faute de colonnes.

## ⚠️ Ce qu'il ne fait pas : deviner

Un nom qui désigne deux copropriétaires, ou un copropriétaire qui a deux
parkings, ne rattache rien : la ligne reste à préciser à l'écran. Un badge
rattaché au mauvais lot montrerait son code aux voisins — mieux vaut une ligne
de plus à choisir.
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
    "succession", "consorts", "veuve", "societe",
}


def _mots(nom: str | None) -> set[str]:
    return {m for m in _cle_de_nom(nom).split() if len(m) > 3 and m not in _MOTS_VIDES}


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
    lots_de: dict[str, set[int]] = defaultdict(set)
    mots_de: dict[str, set[str]] = {}
    for li in session.exec(select(LotImport).where(LotImport.lot_id != None)).all():  # noqa: E711
        copro = li.no_coproprietaire or li.nom_coproprietaire
        if not copro:
            continue
        mots_de.setdefault(copro, _mots(li.nom_coproprietaire))
        if natures.get(li.lot_id) == nature:
            lots_de[copro].add(li.lot_id)

    def trouver(imp) -> int | None:
        mots = _mots(imp.nom_proprietaire)
        if not mots:
            return None
        candidats = {c for c, m in mots_de.items() if m & mots}
        if len(candidats) != 1:
            return None
        lots = lots_de.get(candidats.pop(), set())
        return next(iter(lots)) if len(lots) == 1 else None

    return trouver


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
