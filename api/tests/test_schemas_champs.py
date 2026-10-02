"""Un champ passé à un schéma qui ne le déclare pas est **perdu en silence**.

## 🔴 Le défaut, évité de justesse (02/09/2026)

Le lot #515 ajoutait `archivee` aux tickets :

    return TicketRead(
        ...
        archivee=est_archivable("ticket", ticket, seuil_jours=...),
    )

Le champ **n'avait pas été ajouté à `TicketRead`**. Pydantic v2 ignore les clés
inconnues : aucune exception, aucun avertissement. L'API aurait servi des tickets
sans `archivee`, le front aurait lu `undefined`, et **aucun ticket ne se serait
jamais archivé**.

Ce qui est passé au vert malgré tout :

  - les **970 tests** — aucun ne lisait ce champ ;
  - **svelte-check** — le type front déclarait `archivee?: boolean`, optionnel ;
  - **Ruff** — c'est un appel valide.

Le seul signe était la sortie de `git diff --stat`, où `schemas.py` n'apparaissait
pas. C'est mince, et ça ne tient pas lieu de contrôle.

## Ce que ce fichier vérifie

Pour chaque appel `<Nom>Read(...)` dans `app/`, que **chaque mot-clé** est un
champ déclaré du schéma correspondant.

⚠️ Il travaille sur l'AST, et ne suit que les appels dont le nom se résout dans
`app.schemas` ou dans un `*_schemas.py` voisin d'un routeur (#1566) : un constructeur homonyme défini ailleurs n'est pas concerné.

⚠️ Il ne vérifie PAS l'inverse — un champ déclaré et jamais rempli. Celui-là ne se
perd pas en silence : il prend sa valeur par défaut, ce qui est souvent voulu
(`Optional[...] = None`). Le distinguer demanderait de savoir ce qui est facultatif,
et un contrôle qui crie sur du légitime finit désarmé.
"""

from __future__ import annotations

import ast
import importlib

import app.schemas as schemas
from tests.aides_sources import modules_app


def _modules_de_schemas() -> list:
    """`app.schemas` et les modules de schémas VOISINS d'un routeur (`routers/**/*_schemas.py`).

    Un schéma propre à un seul routeur vit à côté de lui, plus dans `app/schemas.py`
    (#1566) : sans eux, `MessageRead(...)`, `DocumentRead(...)`… sortaient du contrôle.
    """
    modules = [schemas]
    for m in modules_app("routers", minimum=50):
        if m.rel.endswith("_schemas.py"):
            modules.append(importlib.import_module("app." + m.rel[: -len(".py")].replace("/", ".")))
    return modules


def _schemas_connus() -> dict[str, set[str]]:
    """Les modèles Pydantic de ces modules, et leurs champs déclarés."""
    connus: dict[str, set[str]] = {}
    for module in _modules_de_schemas():
        for nom in dir(module):
            champs = getattr(getattr(module, nom), "model_fields", None)
            if isinstance(champs, dict):
                connus.setdefault(nom, set()).update(champs)
    return connus


def _appels_fautifs(connus: dict[str, set[str]]) -> list[str]:
    fautifs = []
    for m in modules_app():
        for noeud in ast.walk(m.arbre):
            if not isinstance(noeud, ast.Call) or not isinstance(noeud.func, ast.Name):
                continue
            champs = connus.get(noeud.func.id)
            if champs is None:
                continue
            for kw in noeud.keywords:
                #  `**quelque_chose` : on ne peut rien en dire, et prétendre le
                #  contraire serait pire que se taire.
                if kw.arg is None:
                    continue
                if kw.arg not in champs:
                    fautifs.append(
                        f"{m.rel}:{noeud.lineno} — "
                        f"{noeud.func.id}({kw.arg}=…) : ce champ n'existe pas dans le schéma"
                    )
    return fautifs


def test_le_cas_zero_le_relevé_porte_sur_quelque_chose():
    """🔴 Sans schémas connus, tout le reste serait vert sans rien lire."""
    connus = _schemas_connus()
    assert len(connus) >= 20, (
        f"{len(connus)} schéma(s) Pydantic trouvé(s) dans `app.schemas` et les `*_schemas.py` "
        "des routeurs — le module a-t-il été découpé ? Ce contrôle ne mesure plus rien."
    )
    #  Un schéma déplacé à côté de son routeur (#1566) reste couvert.
    voisins = {"MessageRead", "DocumentRead", "NotificationRead", "CommandeAccesRead"}
    assert voisins <= set(connus), "un schéma voisin de son routeur n'est plus relevé."
    assert "TicketRead" in connus, "TicketRead introuvable : le contrôle a perdu sa cible."
    assert "archivee" in connus["TicketRead"], (
        "TicketRead ne déclare plus `archivee` — c'est le champ qui a motivé ce "
        "contrôle, et son absence ferait que plus aucun ticket ne s'archive."
    )


def test_aucun_champ_passe_a_un_schema_qui_ne_le_declare_pas():
    """Pydantic ignore les clés inconnues : sans ce test, la perte est muette."""
    fautifs = _appels_fautifs(_schemas_connus())
    assert not fautifs, (
        "Champ(s) passé(s) à un schéma qui ne les déclare pas :\n  "
        + "\n  ".join(fautifs)
        + "\n\n  Pydantic les IGNORE en silence : le champ n'atteint jamais l'API, "
        "et le front lit `undefined`.\n  Ajouter le champ au schéma, ou retirer "
        "l'argument."
    )
