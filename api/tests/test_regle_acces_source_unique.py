"""Garde-fou : la règle d'accès géographique ne s'écrit qu'à UN endroit.

## Ce qu'on protège, et pourquoi ce test existe

> « Les règles d'accès de sécurité doivent être centralisées et non pas
>   introduites dans du code. » — l'utilisateur, 02/09/2026

Deux notions distinctes, chacune avec **une** source :

| Notion | Source unique | Question à laquelle elle répond |
|---|---|---|
| « quels bâtiments sont les siens » | `utils/mes_batiments.batiments_de_l_utilisateur` | rattachement **et** lots actifs |
| « ce contenu le concerne-t-il » | `utils/visibility.perimetre_visible` | l'intersection, et les deux cas zéro |

Le jour de sa rédaction, ces deux règles venaient d'être remaniées deux fois en
quelques heures, sur deux arbitrages successifs. C'est exactement la situation où
une décision se recopie « juste ici, pour ce cas-là » : le remaniement rend la
règle familière, et une copie faite en la comprenant paraît sans danger.

## Ce que ce test vérifie

Que **personne d'autre** ne dérive « mes bâtiments » à la main. Le motif cherché
est la lecture directe de `user.batiment_id` dans un module qui décide — routeurs
et utilitaires —, hors des exceptions nommées ci-dessous.

⚠️ Il ne peut pas vérifier qu'un appelant emploie la règle **correctement** :
c'est le rôle de `test_visibilite_ouverte.py` et `test_perimetres_arbre.py`. Il
attrape la forme, qui est ce qui se recopie.

📖 Même patron que `test_destinataires_source_unique.py`, et pour la même raison :
la duplication d'une règle de sécurité ne produit **aucun signal** — un accès
donné à trop de monde ne fait pas de bruit, personne ne se plaint de voir quelque
chose.
"""
from __future__ import annotations

import ast
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1] / "app"
SOURCE_BATIMENTS = RACINE / "utils" / "mes_batiments.py"
SOURCE_ACCES = RACINE / "utils" / "visibility" / "socle.py"

#: Les fichiers autorisés à lire `user.batiment_id` en direct, avec leur RAISON.
#:
#: 🔴 Une tolérance sans raison devient un dépotoir. Le second test ci-dessous
#: échoue si l'une d'elles cesse de servir : une exception qui ne sert plus fait
#: croire que la règle est plus poreuse qu'elle ne l'est.
EXCEPTIONS = {
    "utils/mes_batiments.py":
        "la source unique elle-même : c'est ici que le rattachement est lu.",
    "routers/auth.py":
        "AFFICHAGE seul — compose le libellé « Bât. N » du profil, ne décide rien.",
    "routers/admin/profils.py":
        "ADMINISTRATION — pose le rattachement demandé, ne lit aucun accès.",
    "routers/admin/arrivants.py":
        "DESTINATAIRES d'une notification, pas un accès : choisit les membres du "
        "CS du bâtiment de l'arrivant. Relève de `utils/destinataires`, et son "
        "rapprochement est un sujet à part.",
    "routers/delegations.py":
        "AFFICHAGE — expose le bâtiment du mandant dans la fiche de délégation.",
}

#: Les répertoires qui DÉCIDENT. `models/` est exclu : y déclarer le champ n'est
#: pas le lire, et `seed/` pose des données, il ne décide de rien.
SURVEILLES = ["routers", "utils"]


def _fichiers_surveilles() -> list[Path]:
    trouves = []
    for coin in SURVEILLES:
        trouves += sorted((RACINE / coin).rglob("*.py"))
    return trouves


def _lit_le_batiment_dun_utilisateur(fichier: Path) -> bool:
    """`x.batiment_id` où `x` est une INSTANCE d'utilisateur — pas un lot, pas un membre.

    On travaille sur l'AST, pas sur le texte : un commentaire qui EXPLIQUE la
    règle est légitime, et un contrôle qui le refuserait pousserait à supprimer
    les explications plutôt que les copies.

    ⚠️ `Utilisateur.batiment_id` — la CLASSE, dans un `select()` — est hors
    portée, et c'est délibéré : c'est une référence de colonne, pas une décision
    prise sur un utilisateur donné. La distinction n'est pas cosmétique — le
    premier essai de ce contrôle a signalé `routers/telemetry.py`, qui projette
    la colonne dans un tableau de bord d'administration. Un contrôle qui crie sur
    du légitime finit désarmé dans la semaine.

    Ce que ça laisse passer, et qu'il faut savoir : un
    `.where(Utilisateur.batiment_id == …)` qui filtrerait une liste **est** une
    décision d'accès, et ce test ne le verra pas. Il n'y en a aucun aujourd'hui —
    aucune liste n'est restreinte par bâtiment côté requête —, et le jour où il y
    en aura un, c'est `test_autorisation.py` (dépendance obligatoire sur chaque
    endpoint) qui reste le filet.
    """
    porteurs = {"user", "utilisateur", "u", "acteur", "mandant", "self"}
    for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
        if not isinstance(noeud, ast.Attribute) or noeud.attr != "batiment_id":
            continue
        cible = noeud.value
        nom = cible.id if isinstance(cible, ast.Name) else None
        if nom in porteurs:
            return True
    return False


def test_les_deux_sources_existent_toujours():
    """🔴 CAS ZÉRO — un chemin qui ne désigne plus rien rendrait tout le reste vert.

    Si le paquet est renommé ou la fonction déplacée, ce fichier doit échouer
    bruyamment : INCONNU, jamais OK (`standards/04` §2).
    """
    for source in (SOURCE_BATIMENTS, SOURCE_ACCES):
        assert source.is_file(), f"{source} introuvable — ce test ne mesure plus rien."
    assert "def batiments_de_l_utilisateur" in SOURCE_BATIMENTS.read_text(encoding="utf-8")
    assert "def perimetre_visible" in SOURCE_ACCES.read_text(encoding="utf-8")
    surveilles = _fichiers_surveilles()
    assert len(surveilles) >= 50, (
        f"{len(surveilles)} fichier(s) surveillé(s) — l'arborescence a bougé, et "
        "ce contrôle ne couvre plus ce qu'il prétend couvrir."
    )


def test_personne_ne_derive_mes_batiments_a_la_main():
    """Le rattachement d'un utilisateur se lit dans UN fichier, et se déclare ici."""
    fautifs = []
    for fichier in _fichiers_surveilles():
        rel = fichier.relative_to(RACINE).as_posix()
        if rel in EXCEPTIONS or rel.startswith("utils/visibility/"):
            continue
        if _lit_le_batiment_dun_utilisateur(fichier):
            fautifs.append(rel)

    assert not fautifs, (
        "Le rattachement d'un utilisateur est lu hors de sa source unique : "
        + ", ".join(fautifs)
        + "\n  Une règle d'accès recopiée ne produit AUCUN signal quand elle "
        "diverge — personne ne se plaint de voir quelque chose.\n"
        "  Employer `utils/visibility.perimetre_visible` pour décider, ou "
        "`utils/mes_batiments.batiments_de_l_utilisateur` pour la seule notion "
        "de « ses bâtiments ». Si l'usage n'est vraiment pas une décision "
        "d'accès, l'ajouter à EXCEPTIONS **avec sa raison**."
    )


def test_aucune_exception_ne_survit_a_son_objet():
    """Une tolérance qui ne sert plus fait croire la règle plus poreuse qu'elle n'est."""
    inutiles = []
    for rel in EXCEPTIONS:
        fichier = RACINE / rel
        if not fichier.is_file():
            inutiles.append(f"{rel} (le fichier n'existe plus)")
        elif not _lit_le_batiment_dun_utilisateur(fichier):
            inutiles.append(f"{rel} (ne lit plus `batiment_id`)")

    assert not inutiles, (
        "Exception(s) devenue(s) inutile(s), à retirer de EXCEPTIONS : "
        + ", ".join(inutiles)
    )
