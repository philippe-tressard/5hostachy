"""Une CORRECTION : ce que c'est, comment elle s'écrit, et pourquoi le fil l'ignore.

## Le défaut, signalé à l'écran le 01/09/2026

> *« pourquoi cet évènement a été mis à jour, il n'a eu qu'une édition »*

Le fil affichait une carte **« Mise à jour — Correction : Périmètre »** pour un
événement dont on venait de rectifier le périmètre. Une seule édition, une ligne
de nouvelle.

🔴 **Une correction n'est pas une nouvelle.** Elle dit qu'on s'est trompé, pas
qu'il s'est passé quelque chose. Elle appartient à l'**Historique** de l'objet —
qui a corrigé quoi, et quand — et pas au fil de la copropriété, qui répond à
« qu'est-ce qui est arrivé ? ».

C'est la suite directe de la décision du même jour : *« l'édition ne change pas
la date de modification »* et *« ne modifie pas la mise à jour dans le fil
d'actualité »*. Une correction ne remontait déjà plus une carte ; elle n'en crée
plus non plus.

## Ce que ce module remplace

Le préfixe `« Correction : »` était écrit **quatre fois** — `calendrier.py`,
`publications/crud.py`, `tickets/correction.py`, et deux commentaires de modèle
qui le décrivent. Le fil aurait eu besoin d'un cinquième, pour le RECONNAÎTRE.

⚠️ C'est une convention de données, pas un type : le modèle ne connaît que
`commentaire` et `etat`, et le commentaire de `calendrier_historique.py` le dit —
*« le troisième que l'on serait tenté d'ajouter (« correction ») n'existe nulle
part : une correction est un `commentaire` préfixé »*. Tant que c'est vrai, la
chaîne doit exister à **un** endroit, sinon écrire et reconnaître divergent — et
c'est la RECONNAISSANCE qui se tromperait en silence, en laissant passer dans le
fil ce qu'elle ne sait plus lire.
"""
from __future__ import annotations

from typing import Any, Iterable

#: La marque d'une correction, dans le contenu d'une entrée d'historique.
#: 🔴 Écrite ICI et nulle part ailleurs.
PREFIXE_CORRECTION = "Correction : "

#: ⚠️ Les tickets distinguent l'auteur du conseil syndical : « Correction auteur :
#: … ». Ce n'est pas un caprice — l'Historique dit QUI a corrigé, et un résident
#: qui rectifie son propre ticket ne fait pas la même chose qu'un membre du CS.
#: La reconnaissance doit donc accepter la famille, pas la seule chaîne exacte.
PREFIXE_CORRECTION_AUTEUR = "Correction auteur : "

_MARQUES = (PREFIXE_CORRECTION, PREFIXE_CORRECTION_AUTEUR)

#: Ce qui sépare deux champs corrigés dans la même entrée.
SEPARATEUR_CORRECTION = " ; "


def contenu_correction(champs: Iterable[str]) -> str:
    """« Correction : Périmètre ; Description » — le contenu d'une entrée.

    Les trois écrivains (événement, publication, ticket) l'assemblaient
    séparément avec la même expression.
    """
    return PREFIXE_CORRECTION + SEPARATEUR_CORRECTION.join(champs)


def est_correction(entree: Any) -> bool:
    """Cette entrée d'historique est-elle une correction ?

    ⚠️ Une entrée qui porte un changement d'état n'en est **jamais** une, même si
    son contenu commence par la marque : une transition est un fait, et le fil
    doit la montrer. C'est le cas qui se perd si l'on ne regarde que le texte.
    """
    if getattr(entree, "nouveau_statut", None) or getattr(entree, "ancien_statut", None):
        return False
    contenu = getattr(entree, "contenu", None) or ""
    return contenu.startswith(_MARQUES)


def _selftest() -> None:
    """Les cas qui se ressemblent, et celui qui se perd."""

    class E:
        def __init__(self, contenu=None, ancien_statut=None, nouveau_statut=None):
            self.contenu = contenu
            self.ancien_statut = ancien_statut
            self.nouveau_statut = nouveau_statut

    assert contenu_correction(["Périmètre"]) == "Correction : Périmètre"
    assert contenu_correction(["Périmètre", "Lieu"]) == "Correction : Périmètre ; Lieu"
    #  1. Le cas nominal.
    assert est_correction(E("Correction : Périmètre"))
    #  2. Un vrai commentaire n'en est pas une.
    assert not est_correction(E("Le nettoyage est reporté."))
    #  3. Une entrée vide non plus.
    assert not est_correction(E())
    assert not est_correction(E(""))
    #  4. 🔴 Celui qui se perd : une TRANSITION reste une nouvelle, même si son
    #     contenu porte la marque.
    assert not est_correction(E("Correction : Périmètre", "ouvert", "en_cours"))
    #  5. La variante des tickets — elle serait passée dans le fil sans ceci.
    assert est_correction(E("Correction auteur : Description"))
    #  6. Un texte qui commence par le mot sans être une entrée de correction.
    assert not est_correction(E("Corrections à prévoir sur la façade"))
    print("OK corrections : 9 cas verifies.")


if __name__ == "__main__":
    _selftest()
