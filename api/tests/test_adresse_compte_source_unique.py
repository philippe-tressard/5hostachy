"""« Le compte de cette adresse » s'écrit UNE fois : `app/auth/adresse_compte.py` (#1550).

## Le défaut (audit du 02/10/2026)

La question s'écrivait de DEUX façons, qui divergeaient sur le cas limite — la
casse de l'adresse stockée (`standards/02` §1 bis) :

=====================================  =========================================
Écriture A — insensible à la casse     Écriture B — sensible
=====================================  =========================================
inscription, connexion, admin, profil  renvoi du lien de vérification, mot de
transfert d'un courriel                passe oublié, recherche d'un locataire
=====================================  =========================================

Un compte dont l'adresse stockée portait une majuscule se CONNECTAIT (A), mais
ne pouvait ni recevoir un nouveau lien de vérification ni réinitialiser son mot
de passe (B) : un 204 muet, « pas d'énumération de comptes » — et la personne
concluait que le courriel n'arrivait pas.

La normalisation elle-même — minuscules, espaces retirés — était recopiée dans
trois validateurs et une demi-douzaine de modules.

## Ce que ce fichier refuse, hors du module source

1. une COMPARAISON sur la colonne `Utilisateur.email` (`==`, `!=`, `in`), une
   fonction SQL qui l'enveloppe (`func.lower(Utilisateur.email)`), ou une
   méthode de recherche (`.ilike`, `.like`, `.in_`…) — la recherche passe par
   `compte_par_adresse` ;
2. la normalisation recopiée (`.strip().lower()` dans les deux ordres) sur une
   adresse — elle passe par `normaliser_adresse`.

Lu dans l'arbre syntaxique, pas par motif : un appel sur plusieurs lignes est vu
pareil. ⚠️ `Utilisateur.email.isnot(None)` n'est pas une recherche par adresse
(on sélectionne les comptes joignables) : il reste permis.
"""

from __future__ import annotations

import ast

from tests.aides_sources import modules_app

#: Le seul module qui pose la question et porte la forme d'une adresse.
SOURCE = "auth/adresse_compte.py"

#: Les normalisations qui ne sont PAS celle d'une adresse de compte — déclarées,
#: sinon une exception non écrite ressemble à une décision (CLAUDE.md, règle 1).
EXCEPTIONS_NORMALISATION = {
    "utils/courriel_authenticite.py": "le DOMAINE d'une adresse (`rpartition('@')` puis "
    "`rstrip('.')`) — une autre forme, comparée à des domaines DNS, jamais à un compte",
}

#: Les méthodes SQLAlchemy qui CHERCHENT par la valeur de la colonne.
_METHODES_DE_RECHERCHE = {
    "ilike",
    "like",
    "in_",
    "contains",
    "startswith",
    "endswith",
    "__eq__",
    "is_",
}
#: Les fonctions SQL qui l'enveloppent pour comparer.
_FONCTIONS_SQL = {"lower", "upper", "trim"}


def _est_colonne(n: ast.AST) -> bool:
    return (
        isinstance(n, ast.Attribute)
        and n.attr == "email"
        and isinstance(n.value, ast.Name)
        and n.value.id == "Utilisateur"
    )


def _enveloppe_colonne(n: ast.AST) -> bool:
    """`func.lower(Utilisateur.email)`, `func.lower(func.trim(Utilisateur.email))`."""
    return (
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in _FONCTIONS_SQL
        and any(_est_colonne(a) or _enveloppe_colonne(a) for a in n.args)
    )


def _est_normalisation(n: ast.AST) -> bool:
    """`x.strip().lower()` ou `x.lower().strip()`."""
    if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
        return False
    interieur = n.func.value
    return (
        n.func.attr in ("lower", "strip")
        and isinstance(interieur, ast.Call)
        and isinstance(interieur.func, ast.Attribute)
        and {n.func.attr, interieur.func.attr} == {"lower", "strip"}
    )


def _parle_d_adresse(texte: str) -> bool:
    texte = texte.lower()
    return "mail" in texte or "adresse" in texte


def ecarts_du_source(source: str, rel: str = "<extrait>") -> list[str]:
    """Les recherches et normalisations d'adresse écrites hors de la source."""
    arbre = ast.parse(source)
    ecarts: list[str] = []

    def visiter(noeud: ast.AST, fonction: str) -> None:
        for n in ast.iter_child_nodes(noeud):
            nom = n.name if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) else fonction
            if isinstance(n, ast.Compare) and any(
                _est_colonne(x) or _enveloppe_colonne(x) for x in [n.left, *n.comparators]
            ):
                ecarts.append(f"app/{rel}:{n.lineno} Utilisateur.email comparé")
                continue  # un seul écart par comparaison : `func.lower(…)` est dedans
            if _enveloppe_colonne(n):
                ecarts.append(f"app/{rel}:{n.lineno} {ast.unparse(n.func)}(Utilisateur.email)")
            elif (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and _est_colonne(n.func.value)
                and n.func.attr in _METHODES_DE_RECHERCHE
            ):
                ecarts.append(f"app/{rel}:{n.lineno} Utilisateur.email.{n.func.attr}(…)")
            elif _est_normalisation(n) and (
                _parle_d_adresse(ast.unparse(n)) or _parle_d_adresse(nom)
            ):
                ecarts.append(f"app/{rel}:{n.lineno} adresse normalisée à la main")
            visiter(n, nom)

    visiter(arbre, "")
    return ecarts


def test_aucune_recherche_ni_normalisation_d_adresse_hors_de_la_source():
    ecarts = []
    for module in modules_app():
        if module.rel == SOURCE:
            continue
        trouves = ecarts_du_source(module.source, module.rel)
        if module.rel in EXCEPTIONS_NORMALISATION:
            trouves = [e for e in trouves if "normalisée à la main" not in e]
        ecarts.extend(trouves)
    assert not ecarts, (
        "« Le compte de cette adresse » se demande à `app.auth.adresse_compte` "
        "(`compte_par_adresse`, `normaliser_adresse`) — deux écritures ont divergé sur "
        "la casse (#1550) :\n" + "\n".join(f"  • {e}" for e in ecarts)
    )


def test_le_releve_voit_chaque_ecriture():
    """Cas zéro : un relevé qui ne verrait rien serait vert à vide."""
    cas = {
        "select(Utilisateur).where(Utilisateur.email == x)": 1,
        "select(Utilisateur).where(func.lower(Utilisateur.email) == x)": 1,
        "q = func.lower(Utilisateur.email)": 1,
        "select(Utilisateur).where(Utilisateur.email.ilike(x))": 1,
        "def lowercase_email(cls, v):\n    return v.strip().lower()": 1,
        "nue = body.email.lower().strip()": 1,
        #  Ce qui reste permis : sélectionner les comptes joignables, et une
        #  normalisation qui ne parle pas d'adresse.
        "select(Utilisateur.id).where(Utilisateur.email.isnot(None))": 0,
        "cle = nom.strip().lower()": 0,
    }
    for extrait, attendu in cas.items():
        assert len(ecarts_du_source(extrait)) == attendu, extrait


def test_les_exceptions_servent_encore():
    """Une exception qui ne sert plus garde une porte qui n'est plus là."""
    par_rel = {m.rel: m for m in modules_app()}
    for rel in EXCEPTIONS_NORMALISATION:
        assert rel in par_rel, f"{rel} a disparu : retirer l'exception"
        assert any(
            "normalisée à la main" in e for e in ecarts_du_source(par_rel[rel].source, rel)
        ), f"{rel} ne normalise plus d'adresse à la main : retirer l'exception"


def test_la_source_pose_bien_la_question():
    """Témoin : la source cherche par la colonne — sinon le refus ailleurs ne prouve rien."""
    source = next((m for m in modules_app() if m.rel == SOURCE), None)
    assert source is not None, f"app/{SOURCE} a disparu : la question n'a plus de lieu"
    assert ecarts_du_source(source.source, SOURCE), (
        f"app/{SOURCE} ne cherche plus par `Utilisateur.email` : qui le fait ?"
    )
