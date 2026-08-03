"""Garde-fou : aucun endpoint ne doit rester exposé sans consommateur.

Le 03/08/2026, la bascule des pièces jointes vers `POST /uploads/fichier` a laissé
`POST /uploads/ticket/{id}` et `POST /uploads/evenement/{id}` sans un seul
appelant — repérés à l'œil, pas par un contrôle. Un endpoint orphelin n'est pas
qu'un déchet :

  - il reste une **surface d'attaque** authentifiée que plus personne ne teste ;
  - il **ment** sur le fonctionnement réel du produit à qui lit le code ;
  - il fige un schéma (`photos_urls` alimenté après création) que la nouvelle
    logique ne respecte plus, donc il diverge en silence.

Le contrôle est statique : il lit les décorateurs `@router.<méthode>("…")` sans
importer l'application (pas de base, pas d'effet de bord), puis cherche un
consommateur dans le front **et** dans les scripts d'infra — `maintenance.sh` et
`check-reliability.sh` sont des clients aussi légitimes qu'une page Svelte.

Les deux sens sont vérifiés, conformément au principe « un contrôle qui ne peut
pas s'exécuter renvoie INCONNU » :
  - une route orpheline non déclarée fait échouer le test ;
  - une entrée de la liste d'exceptions qui a retrouvé un consommateur le fait aussi,
    sinon la liste se remplit et ne protège plus rien.
"""
import ast
import pathlib
import re

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]
ROUTEURS = RACINE / "api" / "app" / "routers"

#: Routes légitimement absentes du front, avec la raison. Toute entrée ajoutée
#: ici est une décision consciente : si la raison ne tient pas en une ligne,
#: c'est probablement que la route doit être supprimée.
SANS_CONSOMMATEUR_FRONT = {
    "/admin/db/checkpoint":
        "voie in-process obligatoire contre la corruption SQLite (CLAUDE.md, "
        "règle d'or) — appelée à la main pendant un incident, jamais par le front",
    "/admin/notifications":
        "API d'administration exposée pour l'exploitation, sans écran dédié",
    "/admin/notifications/{notif_id}/lue":
        "idem /admin/notifications",
    "/acces/admin/imports/{import_id}/refuser-locataire":
        "pendant de `resoudre` documenté dans specs/architecture/api.md, "
        "conservé pour l'exploitation manuelle des imports Vigik",
    "/lots/admin/diag-couples":
        "diagnostic ponctuel des couples de lots, appelé au cas par cas",
    "/lots/admin/propager-couples":
        "remédiation associée à /lots/admin/diag-couples",
}


def _routes() -> list[tuple[str, str, str]]:
    """(fichier, méthode, chemin complet) de chaque endpoint déclaré."""
    trouvees: list[tuple[str, str, str]] = []
    for fichier in sorted(ROUTEURS.glob("*.py")):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        prefixe = ""
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call) and getattr(noeud.func, "id", "") == "APIRouter":
                for kw in noeud.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        prefixe = kw.value.value
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in noeud.decorator_list:
                if (
                    isinstance(deco, ast.Call)
                    and isinstance(deco.func, ast.Attribute)
                    and deco.func.attr in {"get", "post", "patch", "put", "delete"}
                    and deco.args
                    and isinstance(deco.args[0], ast.Constant)
                ):
                    trouvees.append(
                        (fichier.name, deco.func.attr.upper(), (prefixe + deco.args[0].value) or "/")
                    )
    return trouvees


def _sources_consommatrices() -> str:
    """Tout ce qui peut appeler l'API : le front, et les scripts d'infra."""
    morceaux = [
        p.read_text(encoding="utf-8", errors="ignore")
        for p in (RACINE / "front" / "src").rglob("*")
        if p.suffix in {".ts", ".js", ".svelte"}
    ]
    morceaux += [
        p.read_text(encoding="utf-8", errors="ignore")
        for p in RACINE.glob("*.sh")
    ]
    return "\n".join(morceaux)


def _motif(chemin: str) -> re.Pattern:
    """`/tickets/{id}/evolutions` → motif tolérant à `${…}` et aux concaténations."""
    segments = [re.escape(s) for s in re.split(r"\{[^}]+\}", chemin)]
    return re.compile(r"[^\s'\"`]*".join(segments))


@pytest.fixture(scope="module")
def orphelines() -> set[str]:
    sources = _sources_consommatrices()
    assert len(sources) > 100_000, (
        "sources consommatrices introuvables ou quasi vides : le contrôle ne peut "
        "pas s'exécuter, il ne doit donc pas passer au vert"
    )
    return {chemin for _, _, chemin in _routes() if not _motif(chemin).search(sources)}


def test_aucun_endpoint_orphelin_non_declare(orphelines):
    """Une route sans appelant doit être supprimée — ou justifiée explicitement."""
    inattendues = sorted(orphelines - set(SANS_CONSOMMATEUR_FRONT))
    assert not inattendues, (
        "Endpoints sans aucun consommateur (front ni script d'infra) :\n  "
        + "\n  ".join(inattendues)
        + "\n\nSupprimer l'endpoint ET son client TypeScript, ou l'inscrire dans "
          "SANS_CONSOMMATEUR_FRONT avec sa raison."
    )


def test_la_liste_blanche_ne_pourrit_pas(orphelines):
    """Une exception qui a retrouvé un appelant n'a plus lieu d'être.

    Sans ce sens-là, la liste d'exceptions grossit à chaque incident et finit par
    couvrir des routes redevenues normales : le contrôle reste vert en ne
    contrôlant plus rien.
    """
    perimees = sorted(set(SANS_CONSOMMATEUR_FRONT) - orphelines)
    assert not perimees, (
        "Ces routes ont désormais un consommateur : les retirer de "
        "SANS_CONSOMMATEUR_FRONT :\n  " + "\n  ".join(perimees)
    )


def test_les_routes_sont_bien_detectees():
    """Le détecteur lui-même : s'il ne trouve plus rien, tout paraît consommé."""
    routes = _routes()
    assert len(routes) > 200, f"seulement {len(routes)} routes détectées — parseur cassé ?"
