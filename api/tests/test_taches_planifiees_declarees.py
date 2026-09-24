"""Une tâche planifiée qui disparaît doit prévenir quelqu'un.

## Le constat (#1047, audit du 19/09/2026)

Sept tâches tournent en permanence, enregistrées à trois endroits — et **aucun
test ne citait un seul identifiant**. Trois fichiers de test les concernaient
(`test_taches_planifiees.py`, `test_sante_taches_forme.py`, `test_taches_sante.py`) :
ils vérifiaient des formes, jamais la liste.

Un `add_job` supprimé par mégarde laisse donc l'application démarrer normalement.
La sauvegarde ne se fait plus, et on l'apprend le jour d'une restauration.
« Une tâche planifiée qui disparaît ne prévient personne » (`standards/07` §5).

## Ce que ce test vérifie, et ce qu'il ne peut pas voir

Il confronte `utils/taches.TACHES_PERMANENTES` aux `scheduler.add_job(...)` du
code, **dans les deux sens** : une tâche déclarée sans enregistrement, et un
enregistrement sans déclaration.

⚠️ Il lit le **code**, pas l'exécution : un `add_job` qu'une condition saute au
démarrage lui paraît présent. C'est pourquoi la table sert **aussi** au
démarrage — `verifier_taches_enregistrees` compare ce qui tourne vraiment, dans
le process, et journalise l'écart. Aucun des deux contrôles ne suffit seul
(`standards/04` §12 — un contrôle borné dit ce qu'il ne couvre pas).
"""

import ast
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1] / "app"

from app.utils.taches import TACHES_PERMANENTES  # noqa: E402


def _ids_enregistres() -> set[str]:
    """Les identifiants littéraux passés à un `scheduler.add_job(...)`."""
    ids = set()
    for fichier in sorted(RACINE.rglob("*.py")):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)):
                continue
            if noeud.func.attr != "add_job":
                continue
            for mot in noeud.keywords:
                if mot.arg == "id" and isinstance(mot.value, ast.Constant):
                    ids.add(mot.value.value)
    return ids


def test_chaque_tache_declaree_est_enregistree():
    """Une tâche qui quitte le code sans quitter la table serait invisible."""
    manquantes = sorted(set(TACHES_PERMANENTES) - _ids_enregistres())
    assert not manquantes, (
        "Tâche(s) déclarée(s) qu'aucun `add_job` n'enregistre :\n"
        + "\n".join(f"  • {m} — on perd : {TACHES_PERMANENTES[m]}" for m in manquantes)
        + "\n\nSoit l'enregistrement a disparu (et il faut le remettre), soit la tâche "
        "n'existe plus (et il faut retirer sa ligne de `utils/taches.py`)."
    )


def test_aucune_tache_permanente_non_declaree():
    """L'autre sens : ce qui tourne sans être déclaré n'a pas de coût écrit.

    Le jour où elle tombe, personne ne sait ce qu'on vient de perdre — c'est
    précisément ce qui rendait la disparition indolore.
    """
    #  Les rattrapages sont créés à la volée, de type `date` : leur nombre dépend
    #  de l'état du système, et les déclarer rendrait le contrôle rouge sur une
    #  installation saine.
    non_declarees = sorted(
        i for i in _ids_enregistres() - set(TACHES_PERMANENTES) if not i.startswith("rattrapage")
    )
    assert not non_declarees, (
        f"Tâche(s) enregistrée(s) sans déclaration : {non_declarees}\n"
        f"Les inscrire dans `utils/taches.TACHES_PERMANENTES` **avec ce qu'on perd** "
        f"si elles cessent de tourner — c'est cette phrase qui permet de trancher, "
        f"en cas d'écart, s'il faut intervenir tout de suite."
    )


def test_la_table_n_est_pas_vide():
    """Cas zéro : une table vide rend les deux tests ci-dessus verts.

    Ils ne comparent que des ensembles ; vider la table les satisfait tous les
    deux en ayant supprimé la seule liste qui dise ce qui doit tourner.
    """
    assert len(TACHES_PERMANENTES) >= 5, (
        f"`TACHES_PERMANENTES` n'en porte plus que {len(TACHES_PERMANENTES)} : "
        f"le dépôt en enregistre {len(_ids_enregistres())}. Une table vide rendrait "
        f"ce contrôle vert sans rien mesurer."
    )


def test_le_controle_au_demarrage_existe_et_est_appele():
    """Le test statique ne voit pas un `add_job` qu'une condition saute.

    C'est la raison d'être du contrôle au démarrage : sans lui, ce fichier
    donnerait l'illusion d'une couverture qu'il n'a pas.
    """
    taches = (RACINE / "utils" / "taches.py").read_text(encoding="utf-8")
    assert "def verifier_taches_enregistrees" in taches, (
        "`verifier_taches_enregistrees` a disparu : il ne reste plus que l'analyse "
        "statique, aveugle à ce qui est sauté à l'exécution."
    )
    main = (RACINE / "main.py").read_text(encoding="utf-8")
    assert "verifier_taches_enregistrees(" in main, (
        "`main.py` n'appelle plus `verifier_taches_enregistrees` : le contrôle "
        "existe et ne s'exécute pas, ce qui ne sert à rien."
    )
