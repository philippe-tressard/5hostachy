"""Le cookie d'accès ne se lit qu'à UNE porte : `auth/deps.py` (#1595).

## Le défaut (audit du 02/10/2026)

`routers/telemetry_collecte.py` décodait `access_token` lui-même —
`request.cookies.get("access_token")` puis `decode_token(...)` — sans la chaîne
de `_get_current_user` : ni `actif`, ni l'empreinte du mot de passe (#1063).
Une session invalidée restait donc reconnue par ce second lecteur jusqu'à
120 minutes. `standards/03` §1 : **un doublon de dépendance d'auth hors du
module central est un défaut de sécurité** — un durcissement de la règle
centrale ne l'atteint pas.

## Ce que le contrôle refuse, hors de `auth/deps.py`

1. une lecture du cookie : `request.cookies.get("access_token")`,
   `request.cookies["access_token"]`, ou un paramètre nommé `access_token`
   (la forme `Cookie()` de FastAPI) ;
2. un appel à `decode_token`, sauf la porte déclarée ci-dessous.

⚠️ ÉCRIRE le cookie (`set_cookie`, `delete_cookie`) reste permis : c'est la
connexion qui l'émet, et ce n'est pas une lecture.
"""

from __future__ import annotations

import ast

from tests.aides_sources import modules_app

COOKIE = "access_token"
PORTE = "auth/deps.py"

#: Les autres appelants de `decode_token`, avec leur raison. Une entrée qui ne
#: sert plus fait échouer le dernier test : une exception sans objet n'est pas
#: une décision, c'est un trou laissé ouvert.
DECODAGES_DECLARES = {
    #  Le jeton de RAFRAÎCHISSEMENT, qui n'est pas le cookie d'accès : il se
    #  vérifie contre sa ligne en base (empreinte, rotation, rejeu — #1389).
    "routers/auth.py",
}


def _lit_le_cookie(noeud: ast.AST) -> bool:
    """`…cookies.get("access_token")`, `…cookies["access_token"]`, ou `access_token=` en paramètre."""
    if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute):
        cible = noeud.func
        if (
            cible.attr == "get"
            and isinstance(cible.value, ast.Attribute)
            and cible.value.attr == "cookies"
            and noeud.args
            and isinstance(noeud.args[0], ast.Constant)
            and noeud.args[0].value == COOKIE
        ):
            return True
    if isinstance(noeud, ast.Subscript) and isinstance(noeud.value, ast.Attribute):
        if noeud.value.attr == "cookies" and isinstance(noeud.slice, ast.Constant):
            return noeud.slice.value == COOKIE
    if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
        arguments = noeud.args.args + noeud.args.kwonlyargs
        return any(a.arg == COOKIE for a in arguments)
    return False


def _decode(noeud: ast.AST) -> bool:
    if not isinstance(noeud, ast.Call):
        return False
    f = noeud.func
    return getattr(f, "id", None) == "decode_token" or getattr(f, "attr", None) == "decode_token"


def _modules_qui(predicat) -> set[str]:
    return {m.rel for m in modules_app() if any(predicat(n) for n in ast.walk(m.arbre))}


def test_le_controle_reconnait_la_porte():
    """Cas zéro : la porte elle-même lit le cookie et le décode — sinon le
    contrôle ne reconnaîtrait aucune forme, et serait vert sur tout."""
    assert PORTE in _modules_qui(_lit_le_cookie), "le témoin ne lit plus le cookie : forme perdue"
    assert PORTE in _modules_qui(_decode), "le témoin ne décode plus : forme perdue"


def test_le_cookie_d_acces_ne_se_lit_qu_a_sa_porte():
    lecteurs = _modules_qui(_lit_le_cookie) - {PORTE}
    assert not lecteurs, (
        f"Le cookie d'accès est lu hors de `{PORTE}` : {sorted(lecteurs)}.\n"
        "Passer par une dépendance de `auth/deps.py` : un lecteur à part saute "
        "la vérification d'`actif` et de l'empreinte du mot de passe (#1063, #1595)."
    )


def test_decode_token_ne_s_appelle_qu_aux_portes_declarees():
    appelants = _modules_qui(_decode) - {PORTE, "auth/jwt.py"}
    inattendus = appelants - DECODAGES_DECLARES
    assert not inattendus, (
        f"`decode_token` appelé hors de sa porte : {sorted(inattendus)}. "
        "Décoder soi-même un jeton, c'est réécrire la règle d'authentification "
        "à côté de `auth/deps.py` (`standards/03` §1)."
    )
    orphelines = DECODAGES_DECLARES - appelants
    assert not orphelines, f"exception(s) sans objet, à retirer : {sorted(orphelines)}"
