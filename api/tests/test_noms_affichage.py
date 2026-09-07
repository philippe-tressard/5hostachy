"""« Prénom NOM » — la règle d'affichage d'une personne, et son jumeau front.

## Pourquoi ce test (31/08/2026)

Le fil affichait « Jean-Sébastien CourT » : la casse telle qu'elle avait été
tapée. Arbitré à l'écran — *« l'affichage devrait être Prénom NOM => Nom en
majuscule »*.

La règle est écrite **deux fois** : `app/utils/noms.py` et
`front/src/lib/noms.ts`. Ce n'est pas un oubli — les contextes de construction
Docker sont `./api` et `./front`, rien de la racine n'entre dans les images
(mémoire `project_partage_front_api_impossible`). Le seul motif viable est
*copie + concordance exécutée*.

⚠️ **Ce fichier est la moitié Python de l'attente.** L'autre moitié est
`front/scripts/check-noms.mjs`, qui transpile le TypeScript, l'exécute sur les
MÊMES cas, et vérifie qu'ils sont écrits ici. Les deux implémentations sont
alors tenues par une seule attente, et l'une ne peut plus se corriger sans
l'autre — c'est ce qui a manqué à `perimetreLabel` pendant neuf jours.

Toute modification des cas ci-dessous doit être reportée dans `check-noms.mjs`,
qui échoue sinon.
"""
from __future__ import annotations

from app.utils.noms import nom_affiche

#  🔒 LES CAS DE CONCORDANCE — lus tels quels par `front/scripts/check-noms.mjs`.
#  Ne pas en changer la forme sans changer son extracteur : il échoue s'il n'en
#  lit plus assez, plutôt que de conclure au vert sur zéro cas.
CAS = [
    #  (prénom, nom, rendu attendu)
    ("Jean-Sébastien", "CourT", "Jean-Sébastien COURT"),
    ("Christine", "Longuève", "Christine LONGUÈVE"),
    ("Marie", "de La Tour", "Marie DE LA TOUR"),
    ("  Paul  ", "  Durand  ", "Paul DURAND"),
    ("Anne", "", "Anne"),
    ("", "Martin", "MARTIN"),
    ("", "", ""),
]


def test_le_nom_passe_en_capitales_le_prenom_non():
    """Le cas signalé à l'écran, et ses voisins."""
    for prenom, nom, attendu in CAS:
        assert nom_affiche(prenom, nom) == attendu, (
            f"nom_affiche({prenom!r}, {nom!r}) rend "
            f"{nom_affiche(prenom, nom)!r} au lieu de {attendu!r}"
        )


def test_l_absence_ne_produit_JAMAIS_None_ni_espace_orphelin():
    """Une personne à demi connue s'affiche quand même, et proprement.

    C'est le cas qui se perd : `f"{prenom} {nom}"` sur un nom vide laisse un
    espace en fin de chaîne, invisible dans le code et visible dans une liste
    triée ou une comparaison.
    """
    assert nom_affiche(None, None) == ""
    assert nom_affiche(None, "Martin") == "MARTIN"
    assert nom_affiche("Anne", None) == "Anne"
    for prenom, nom, _ in CAS:
        assert nom_affiche(prenom, nom) == nom_affiche(prenom, nom).strip()


def test_la_regle_INVERSE_existe_toujours_et_reste_distincte():
    """⚠️ `_nom_presentable` fait l'inverse, et les confondre casse les courriels.

    « DUPONT » → « Dupont » sert à s'ADRESSER à quelqu'un ; `nom_affiche` sert à
    l'IDENTIFIER dans une liste. Si l'une venait à déléguer à l'autre, les
    courriels se mettraient à hurler — ce test le refuse.
    """
    from app.utils.destinataires import _nom_presentable

    assert _nom_presentable("DUPONT") == "Dupont"
    assert nom_affiche("Jean", "dupont") == "Jean DUPONT"
