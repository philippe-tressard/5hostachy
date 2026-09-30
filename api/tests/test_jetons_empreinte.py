"""Un jeton se stocke par son EMPREINTE, jamais en clair (#1389, 27/09/2026).

Les trois familles — rafraîchissement, mot de passe oublié, vérification
d'adresse — étaient écrites telles quelles et cherchées par égalité : une copie
de la base (sauvegarde, export hors site) donnait des jetons utilisables.

Ce fichier tient deux choses :

1. **Aucune écriture ni recherche en clair** dans `app/` : tout `Modele(token=…)`
   et tout `Modele.token == …` passe par `empreinte(…)`. Lu dans l'arbre
   syntaxique, pas par motif textuel — un nom de variable ne prouve rien.
2. **L'empreinte est stable, liée à la clé, et reconnaissable** — un jeton brut
   n'en a jamais la forme.

⚠️ Qu'aucun jeton brut ne soit en base après un parcours réel (connexion, lien
de réinitialisation) n'est vérifié ici par aucune exécution : cette ligne le
promettait jusqu'au 30/09/2026 sans qu'aucun test ne le fasse (#1496).
"""

from __future__ import annotations

import ast
import pathlib


from app.auth.empreinte_jeton import empreinte, est_empreinte

RACINE = pathlib.Path(__file__).resolve().parents[1]
APP = RACINE / "app"
MODELES = {"RefreshToken", "PasswordResetToken", "EmailVerificationToken"}


def _appel_empreinte(noeud: ast.AST) -> bool:
    return (
        isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Name)
        and noeud.func.id == "empreinte"
    )


def _ecarts() -> list[str]:
    ecarts = []
    for chemin in APP.rglob("*.py"):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        rel = chemin.relative_to(RACINE).as_posix()
        for n in ast.walk(arbre):
            #  Modele(token=…)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in MODELES:
                for kw in n.keywords:
                    if kw.arg == "token" and not _appel_empreinte(kw.value):
                        ecarts.append(f"{rel}:{n.lineno} {n.func.id}(token=…) en clair")
            #  Modele.token == …
            if isinstance(n, ast.Compare) and isinstance(n.left, ast.Attribute):
                gauche = n.left
                if (
                    gauche.attr == "token"
                    and isinstance(gauche.value, ast.Name)
                    and gauche.value.id in MODELES
                    and not all(_appel_empreinte(c) for c in n.comparators)
                ):
                    ecarts.append(f"{rel}:{n.lineno} {gauche.value.id}.token == … en clair")
    return ecarts


def test_aucun_jeton_ecrit_ni_cherche_en_clair():
    ecarts = _ecarts()
    assert not ecarts, "jetons hors de `empreinte` :\n" + "\n".join(ecarts)


def test_le_controle_voit_bien_les_trois_familles():
    """Cas zéro : un contrôle qui ne trouverait aucun point d'usage serait vert à vide."""
    sources = "\n".join(p.read_text(encoding="utf-8") for p in APP.rglob("*.py"))
    for modele in MODELES:
        assert f"{modele}(" in sources, f"{modele} n'est plus construit nulle part"


def test_l_empreinte_est_stable_a_cle_et_reconnaissable():
    assert empreinte("abc", "k" * 32) == empreinte("abc", "k" * 32)
    assert empreinte("abc", "k" * 32) != empreinte("abc", "z" * 32), "sans clé, pas un HMAC"
    assert est_empreinte(empreinte("abc", "k" * 32))
    #  Aucun jeton brut n'a la forme d'une empreinte : c'est ce qui rend 0231 rejouable.
    assert not est_empreinte("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig")
    assert not est_empreinte("Qx3_kz8-" * 5 + "abc")
