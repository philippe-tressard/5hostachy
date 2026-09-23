"""Toute Suite d'AFFAIRE s'ouvre avec les pastilles d'état en tête (#1094).

Deux écrans ouvrent une Suite sur une affaire : la carte (`CarteTicket`) et la
fiche (`HistoriqueTicket`). La carte passait `statutOptions`, la fiche non : le
même geste montrait les pastilles ici et pas là (23/09/2026). La forme est celle
qu'a imposée #426 — on touche une pastille pour faire avancer, on n'y touche
pas pour une simple parole.

Ce test lit chaque `<EvolForm … entite={TICKET} …>` du front qui n'est pas une
CORRECTION (`editMode`) et exige `statutOptions`.
"""
from __future__ import annotations

import pathlib
import re

_FRONT = pathlib.Path(__file__).resolve().parents[2] / "front" / "src"

#: Ce qui emprunte `EvolForm` sur une affaire SANS être une Suite — déclaré, avec
#: sa raison ; le test échoue si l'exception cesse de servir.
_PAS_UNE_SUITE = {
    "lib/components/FilMessagesTicket.svelte":
        "« Répondre » poste un MESSAGE (`POST …/messages`), qui ne change aucun état",
}
_BALISE = re.compile(r"<EvolForm\b(.*?)>", re.S)


def _suites_sans_pastilles(texte: str) -> int:
    manques = 0
    for attributs in _BALISE.findall(texte):
        if "entite={TICKET}" in attributs and "editMode" not in attributs:
            if "statutOptions=" not in attributs:
                manques += 1
    return manques


def test_chaque_suite_d_affaire_porte_les_pastilles():
    fichiers = [p for p in _FRONT.rglob("*.svelte")]
    trouvees = sum(
        1 for p in fichiers for a in _BALISE.findall(p.read_text(encoding="utf-8"))
        if "entite={TICKET}" in a and "editMode" not in a
    )
    #  Cas zéro : la carte et la fiche, au moins.
    assert trouvees >= 2, f"{trouvees} Suite(s) d'affaire relevée(s) — le motif de lecture est cassé."
    fautes = {p.relative_to(_FRONT).as_posix() for p in fichiers if _suites_sans_pastilles(p.read_text(encoding="utf-8"))}
    assert not fautes - set(_PAS_UNE_SUITE), f"Suite d'affaire sans pastilles d'état (#1094) : {sorted(fautes - set(_PAS_UNE_SUITE))}"
    inutiles = set(_PAS_UNE_SUITE) - fautes
    assert not inutiles, f"Exception qui ne sert plus — la retirer : {sorted(inutiles)}"


def test_le_releve_voit_une_suite_sans_pastilles():
    assert _suites_sans_pastilles("<EvolForm\n  entite={TICKET}\n  titre='x'\n/>") == 1
    assert _suites_sans_pastilles("<EvolForm entite={TICKET} statutOptions={X} />") == 0
    assert _suites_sans_pastilles("<EvolForm entite={TICKET} editMode={true} />") == 0
