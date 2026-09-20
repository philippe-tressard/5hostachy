"""Ce qu'on ne journalise pas n'a pas eu lieu.

## Le constat (#1040, audit du 19/09/2026)

**Aucun événement de sécurité n'était journalisé**, et aucune fonction d'audit
n'existait : zéro `logger` dans `routers/auth.py`, `auth_mot_de_passe.py`,
`admin/utilisateurs.py`, `auth/deps.py`, `auth/jwt.py`.

Un compte compromis, une élévation de rôle ou une attaque par force brute — que
le rate limit freine sans la **signaler** — ne laissaient donc aucune trace
exploitable après coup. On peut constater qu'un mot de passe a changé ; on ne
pouvait pas savoir **qui** l'a changé, **quand**, ni combien de tentatives
avaient précédé.

Seuls journaux de sécurité existants : les refus de téléversement et les
violations CSP.

## Ce que ces tests verrouillent

1. La fonction d'audit existe, elle est **unique**, et elle porte les trois
   champs qui rendent une ligne exploitable : quoi, qui, sur qui.
2. Chaque geste sensible l'appelle — connexion refusée, mot de passe changé ou
   réinitialisé, rôle ajouté ou retiré, bannissement. La liste est **déclarée**
   ici : un geste qui cesse d'exister fait échouer le test, plutôt que de laisser
   une exigence protéger une fonction disparue.
3. 🔴 **Aucune donnée personnelle dans le journal.** #777 a montré l'inverse :
   des adresses e-mail journalisées en clair sur échec d'envoi. Un journal de
   sécurité nomme un **identifiant**, jamais une adresse, jamais un mot de passe
   — sans quoi la trace devient elle-même la fuite (`standards/14`).

⚠️ Ces tests lisent l'arbre syntaxique, pas le texte : un appel réparti sur
plusieurs lignes ou renommé à l'import est vu pareil.
"""
import ast
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1] / "app"

#: La fonction d'audit, et le module qui la porte.
MODULE = RACINE / "utils" / "journal_securite.py"
FONCTION = "journaliser_securite"

#: Les gestes qui DOIVENT laisser une trace : (fichier, fonction du routeur).
#: Une entrée dont la fonction a disparu fait échouer `test_les_gestes_declares_existent`.
GESTES_SENSIBLES = {
    ("routers/auth.py", "login"): "une connexion refusée — sans elle, une attaque "
    "par force brute est freinée par le rate limit mais jamais signalée",
    ("routers/auth_mot_de_passe.py", "change_password"): "un mot de passe changé par "
    "son porteur",
    ("routers/auth_mot_de_passe.py", "reset_password"): "un mot de passe réinitialisé "
    "par jeton — le chemin qu'emprunterait quelqu'un qui a pris la boîte mail",
    ("routers/admin/utilisateurs.py", "ajouter_role"): "une élévation de rôle : c'est "
    "le geste qui donne des droits, et rien ne nommait l'admin qui l'a fait",
    ("routers/admin/utilisateurs.py", "retirer_role"): "un retrait de rôle",
    ("routers/admin/utilisateurs.py", "ban_communaute"): "un bannissement",
}


def _arbre(chemin: Path) -> ast.Module:
    return ast.parse(chemin.read_text(encoding="utf-8"))


def _fonction(arbre: ast.Module, nom: str):
    for n in ast.walk(arbre):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom:
            return n
    return None


def test_la_fonction_d_audit_existe_et_porte_ce_qu_il_faut():
    """Quoi, qui, sur qui — une ligne sans ces trois champs ne sert à rien.

    Le cas ZÉRO de tous les autres tests : s'ils cherchaient un appel à une
    fonction disparue, ils échoueraient en nommant les appelants, et on
    corrigerait les appelants. C'est la fonction qu'il faut regarder d'abord.
    """
    assert MODULE.exists(), (
        f"{MODULE.relative_to(RACINE.parent)} a disparu : les gestes sensibles "
        f"n'ont plus où écrire."
    )
    fn = _fonction(_arbre(MODULE), FONCTION)
    assert fn is not None, f"`{FONCTION}` a disparu de {MODULE.name}"

    params = [a.arg for a in fn.args.args] + [a.arg for a in fn.args.kwonlyargs]
    for attendu in ("evenement", "acteur_id", "cible_id"):
        assert attendu in params, (
            f"`{FONCTION}` ne prend plus `{attendu}` : une ligne de journal qui ne dit "
            f"pas QUOI, QUI et SUR QUI ne permet de reconstituer aucun enchaînement."
        )


def test_chaque_geste_sensible_laisse_une_trace():
    """La liste est déclarée, et elle est vérifiée dans les deux sens."""
    manquants = []
    for (fichier, fonction), pourquoi in GESTES_SENSIBLES.items():
        chemin = RACINE / fichier
        fn = _fonction(_arbre(chemin), fonction)
        if fn is None:
            continue  # vu par le test suivant
        appels = {
            n.func.id
            for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        if FONCTION not in appels:
            manquants.append(f"app/{fichier}::{fonction} — {pourquoi}")
    assert not manquants, (
        f"Ces gestes ne laissent aucune trace ({FONCTION} n'y est pas appelé) :\n"
        + "\n".join(f"  • {m}" for m in manquants)
        + "\n\nCe qu'on ne journalise pas n'a pas eu lieu (`standards/07` §1)."
    )


def test_les_gestes_declares_existent():
    """Une exigence qui protège une fonction disparue protège un souvenir."""
    perimes = []
    for fichier, fonction in GESTES_SENSIBLES:
        chemin = RACINE / fichier
        if not chemin.exists() or _fonction(_arbre(chemin), fonction) is None:
            perimes.append(f"app/{fichier}::{fonction}")
    assert not perimes, (
        f"GESTES_SENSIBLES cite {perimes}, qui n'existe(nt) plus : renommer l'entrée "
        f"ou la retirer, sinon la liste garde une porte qui n'est plus là."
    )


def test_le_journal_ne_porte_aucune_donnee_personnelle():
    """🔴 La trace ne doit pas devenir la fuite.

    #777 a montré le défaut inverse — des adresses e-mail journalisées en clair
    sur échec d'envoi. Un journal de sécurité nomme un identifiant ; l'adresse,
    le mot de passe et le jeton restent dehors, y compris tronqués : un condensé
    partiel d'adresse reste une donnée personnelle (`standards/14`).
    """
    source = MODULE.read_text(encoding="utf-8")
    arbre = ast.parse(source)
    fn = _fonction(arbre, FONCTION)
    assert fn is not None

    corps = ast.unparse(fn)
    for interdit in ("email", "mot_de_passe", "password", "token", "jeton"):
        assert interdit not in corps, (
            f"`{FONCTION}` manipule `{interdit}` : un journal de sécurité nomme un "
            f"IDENTIFIANT, jamais une adresse, un mot de passe ou un jeton — sinon la "
            f"trace devient la fuite (#777)."
        )

    #: Et les appelants ne lui passent pas non plus une adresse.
    fautes = []
    for fichier, fonction in GESTES_SENSIBLES:
        fn_appelante = _fonction(_arbre(RACINE / fichier), fonction)
        if fn_appelante is None:
            continue
        for n in ast.walk(fn_appelante):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)):
                continue
            if n.func.id != FONCTION:
                continue
            #  ⚠️ Les littéraux sont EXCLUS, et ce n'est pas une tolérance : le nom
            #  de l'événement est `"mot_de_passe_change"`, et ce contrôle le
            #  refusait — il confondait le NOM de la chose avec la chose. Ce qui
            #  fuite est une VALEUR : une variable, un attribut, une f-string.
            valeurs = [
                a
                for a in list(n.args) + [k.value for k in n.keywords]
                if not (isinstance(a, ast.Constant) and isinstance(a.value, str))
            ]
            for valeur in valeurs:
                texte = ast.unparse(valeur)
                if any(x in texte for x in ("email", "password", "mot_de_passe", "token")):
                    fautes.append(f"app/{fichier}::{fonction} — {texte[:90]}")
    assert not fautes, (
        "Une adresse ou un mot de passe est passé au journal :\n" + "\n".join(fautes)
    )
