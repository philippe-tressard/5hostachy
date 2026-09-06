# SPDX-FileCopyrightText: 2026 Philippe Tressard
# SPDX-License-Identifier: MIT
"""La table des sens du ciblage : ce que `NULL`, `[]` et le défaut veulent dire (#789).

## Pourquoi ce fichier existe

Le ciblage se stocke dans deux colonnes JSON — `perimetre_cible` (où) et
`public_cible` (à qui) — et **les défauts divergent d'un modèle à l'autre** :

| Colonne | Défaut `None` | Défaut écrit en dur |
|---|---|---|
| `perimetre_cible` | Sondage, TicketEvolution, Document | AnnonceHall, PetiteAnnonce, Idee, Ticket, Publication (`'["résidence"]'`) |
| `public_cible` | Sondage, PetiteAnnonce, Idee | Publication (`'["résidents"]'`) |

Personne n'avait vérifié si ces écarts avaient un sens. C'était la question de
#789, et la réponse est : **non, ils sont équivalents** — `NULL`, `[]` et le
défaut produisent le même verdict d'accès et le même affichage.

🔴 **Mais l'équivalence n'est vraie que par accident, et ce test la rend
délibérée.** Rien dans le code ne l'imposait : trois écritures pour un même sens
finissent par se traiter différemment quelque part, et le jour où cela arrive, le
symptôme est un objet qui apparaît ou disparaît d'une liste — sans message, sans
journal, sans test rouge.

## ⚠️ Ce que ce fichier NE dit pas

Il ne dit pas que les défauts de modèle sont bons. `'["résidence"]'` écrit dans
cinq modèles est **la valeur en dur** que `code_par_defaut()` existe pour
éviter — le même défaut que quatre lecteurs venaient de se voir retirer
(#789, v3.104.2). Sur une copropriété qui renomme ce nœud, une ligne créée
aujourd'hui porterait un code obsolète là où `NULL` aurait suivi.

Les aligner sur `None` est l'étape suivante, et elle n'est **pas** faite ici :
changer un défaut modifie ce qui s'écrit en base pour les nouvelles lignes, et
cela se décide en sachant ce qu'on remplace. C'est précisément ce que ce test
établit.

## Ce qui est vérifiable ici, et ce qui ne l'est pas

Le **public cible** se décide sans base : sa règle ne lit que `user.statut`.
Le **périmètre** interroge l'arbre des périmètres ; sur une base de test non
migrée il est illisible, et la règle refuse alors tout — « INCONNU, jamais OK ».
Les tests qui en dépendent le disent et s'abstiennent plutôt que de conclure.
"""
from __future__ import annotations

import pytest

from app.models.core import RoleUtilisateur, StatutUtilisateur, Utilisateur
from app.utils.visibility import public_cible_visible
from app.utils.visibility.socle import _codes_json_pour_acces


def _resident(statut: StatutUtilisateur) -> Utilisateur:
    """Un utilisateur sans rôle privilégié : c'est sur LUI que le ciblage agit.

    ⚠️ Prendre un CS ou un admin rendrait tous ces tests verts sans rien prouver —
    ils sortent avant que la règle ne s'applique.
    """
    return Utilisateur(
        email="x@exemple.test",
        mot_de_passe_hash="x",
        prenom="Test",
        nom="Aulnay",
        role=RoleUtilisateur.résident,
        statut=statut,
    )


#  Les trois écritures de « aucune restriction de public », telles qu'elles
#  existent réellement en base selon le modèle qui a créé la ligne.
ABSENCE_DE_PUBLIC = [
    pytest.param(None, id="NULL (Sondage, PetiteAnnonce, Idee)"),
    pytest.param("[]", id="[] (liste vidée par une correction)"),
    pytest.param('["résidents"]', id='["résidents"] (Publication)'),
]

TOUS_LES_STATUTS = [
    StatutUtilisateur.copropriétaire_résident,
    StatutUtilisateur.copropriétaire_bailleur,
    StatutUtilisateur.locataire,
    StatutUtilisateur.syndic,
    StatutUtilisateur.mandataire,
]


@pytest.mark.parametrize("brut", ABSENCE_DE_PUBLIC)
@pytest.mark.parametrize("statut", TOUS_LES_STATUTS)
def test_les_trois_ecritures_de_l_absence_de_public_sont_equivalentes(brut, statut):
    """`NULL`, `[]` et `["résidents"]` disent tous « tout le monde ».

    🔴 C'est l'invariant que #789 cherchait. Trois modèles écrivent l'un, un
    quatrième écrit l'autre, et une correction qui vide la liste produit le
    troisième : les trois doivent rendre le même verdict, pour **chaque** statut.
    """
    assert public_cible_visible(brut, _resident(statut)) is True


def test_un_public_restreint_n_est_PAS_equivalent():
    """⚠️ Le cas qui empêche le test précédent d'être vrai par vacuité.

    Sans lui, une règle qui rendrait toujours `True` passerait au vert partout.
    """
    locataire = _resident(StatutUtilisateur.locataire)
    assert public_cible_visible('["copropriétaires"]', locataire) is False
    assert public_cible_visible('["locataires"]', locataire) is True


def test_un_public_illisible_ne_donne_jamais_l_acces():
    """Une donnée abîmée ne doit pas élargir. `standards/04` : INCONNU ≠ OK."""
    locataire = _resident(StatutUtilisateur.locataire)
    assert public_cible_visible("{ceci n'est pas du JSON", locataire) is False
    assert public_cible_visible('["code_inconnu"]', locataire) is False


#  ── Périmètre : les deux écritures de « aucune restriction géographique » ─────

@pytest.mark.parametrize(
    "brut",
    [
        pytest.param(None, id="NULL (Sondage, TicketEvolution, Document)"),
        pytest.param("[]", id="[] (périmètre vidé)"),
        pytest.param("", id="chaîne vide (colonne jamais renseignée)"),
    ],
)
def test_l_absence_de_perimetre_ne_restreint_rien(brut):
    """`NULL`, `[]` et `""` rendent tous `[]` — « aucune restriction ».

    C'est la moitié vérifiable sans base : `_codes_json_pour_acces` ne consulte
    pas l'arbre. La seconde moitié — `["résidence"]` équivaut-il à l'absence ? —
    dépend de l'arbre des périmètres et n'est donc pas éprouvée ici ; elle l'est
    par les tests de visibilité, qui disposent d'un arbre.
    """
    assert _codes_json_pour_acces(brut) == []


def test_un_perimetre_illisible_rend_INCONNU_et_non_une_liste_vide():
    """🔴 La distinction qui vaut une faille.

    `[]` signifie « aucune restriction », donc **visible de tous**. Rendre `[]`
    sur une donnée illisible transformerait une corruption en ouverture. La
    fonction rend `None`, et chaque appelant refuse.

    C'est la nuance que `parse_json_perimetres` n'a PAS — elle retombe sur le
    défaut, ce qui convient à un badge et jamais à une décision d'accès. Les deux
    lectures coexistent pour cette raison, et #789 l'a confirmé plutôt que de les
    unifier.
    """
    assert _codes_json_pour_acces("{pas du JSON") is None
    assert _codes_json_pour_acces('"une chaîne, pas une liste"') is None
    assert _codes_json_pour_acces("42") is None
