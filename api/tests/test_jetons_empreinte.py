"""Un jeton se stocke par son EMPREINTE, jamais en clair (#1389, 27/09/2026).

Les trois familles — rafraîchissement, mot de passe oublié, vérification
d'adresse — étaient écrites telles quelles et cherchées par égalité : une copie
de la base (sauvegarde, export hors site) donnait des jetons utilisables.

Ce fichier tient trois choses :

1. **Aucune écriture ni recherche en clair** dans `app/` : tout `Modele(token=…)`
   et tout `Modele.token == …` passe par `empreinte(…)`. Lu dans l'arbre
   syntaxique, pas par motif textuel — un nom de variable ne prouve rien.
2. **Le jeton brut n'est jamais en base** après un parcours réel.
3. **La migration 0231** convertit l'existant, sans re-hacher une empreinte, et
   un lien envoyé AVANT elle reste valide APRÈS.
"""

from __future__ import annotations

import ast
import importlib.util
import pathlib
from datetime import datetime

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from app.auth.empreinte_jeton import empreinte, est_empreinte
from app.models.core import EmailVerificationToken, PasswordResetToken, RefreshToken

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


#  ── La migration 0231 ───────────────────────────────────────────────────────


def _migration():
    chemin = RACINE / "alembic" / "versions" / "0231_jetons_par_empreinte.py"
    spec = importlib.util.spec_from_file_location("m0231", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_la_migration_convertit_sans_rehacher_et_les_liens_restent_valides():
    cle = "cle-de-test-" + "x" * 32
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    deja = empreinte("deja-converti", cle)
    #  Des lignes d'AVANT la migration : jetons bruts, plus une empreinte déjà posée.
    #  Pas de compte : SQLite n'impose pas les clés étrangères sur ce moteur.
    fin = datetime(2030, 1, 1)
    with Session(moteur) as s:
        s.add(RefreshToken(user_id=1, token="eyJ.session.ouverte", expires_at=fin))
        s.add(PasswordResetToken(user_id=1, token="lien-mot-de-passe", expires_at=fin))
        s.add(EmailVerificationToken(user_id=1, token="lien-verification", expires_at=fin))
        s.add(EmailVerificationToken(user_id=1, token=deja, expires_at=fin))
        s.commit()

    m = _migration()
    with moteur.begin() as conn:
        assert m.convertir(conn, cle) == 3
    with moteur.begin() as conn:
        assert m.convertir(conn, cle) == 0, "rejouée, la migration re-hache des empreintes"

    with Session(moteur) as s:
        stockes = [t.token for t in s.exec(select(EmailVerificationToken)).all()]
        assert deja in stockes, "une empreinte déjà posée a été modifiée"
        #  Le lien envoyé AVANT la migration porte le brut : il doit se retrouver.
        for modele, brut in (
            (RefreshToken, "eyJ.session.ouverte"),
            (PasswordResetToken, "lien-mot-de-passe"),
            (EmailVerificationToken, "lien-verification"),
        ):
            assert s.exec(select(modele).where(modele.token == empreinte(brut, cle))).first()
            assert not s.exec(select(modele).where(modele.token == brut)).first()
