"""Le nom du site se lit par `nom_site()`, et le nom de CETTE copropriété n'est
écrit nulle part dans le code.

## 🔴 Ce que ce test empêche (14/09/2026, #779)

« 5Hostachy » était écrit **dix-sept fois** dans `api/app/`, en repli de
`site_nom`, plus une dix-huitième sous une autre valeur (« Ma Résidence », dans
le moteur d'envoi). Deux défauts, dont un silencieux :

1. **C'est un nom propre.** Le produit doit servir une autre copropriété — le
   dépôt le répète (« ni AFUL, ni quatre bâtiments »). Sa configuration vide, ses
   résidents auraient lu le nom de celle-ci en pied de courriel.
2. **Sept des dix-huit écritures ne se repliaient pas.** `cfg.get(cle, defaut)`
   ne rend le défaut que si la clé est **absente** : une `site_nom` présente et
   vide — ce qu'un champ de configuration effacé produit — passait telle quelle,
   et le courriel annonçait une résidence sans nom.

⚠️ La divergence était **invisible à la lecture** : les deux formes se
ressemblent, et chaque fichier était cohérent avec lui-même.
"""

import re
from pathlib import Path

import pytest

from app.utils.liens import NOM_SITE_PAR_DEFAUT, nom_site

APP = Path(__file__).resolve().parents[1] / "app"

#: Le fichier qui a le droit de nommer le repli : celui qui le définit.
_SOURCE = APP / "utils" / "liens.py"


def _sources() -> list[Path]:
    return [p for p in APP.rglob("*.py") if "__pycache__" not in p.parts]


def test_cas_zero_le_releve_lit_quelque_chose():
    """Un relevé vide annoncerait « aucun nom en dur » sans avoir rien ouvert."""
    fichiers = _sources()
    assert len(fichiers) > 100, f"{len(fichiers)} fichier(s) lus — le relevé est cassé"


def test_aucun_nom_de_copropriete_en_dur():
    """Le nom de cette copropriété ne s'écrit pas dans le code.

    ⚠️ On cherche la chaîne **entre guillemets**, pas le mot : les docstrings et
    les commentaires racontent l'incident et doivent pouvoir le nommer. C'est la
    leçon de `lint:html`, dont la première version comptait les mentions dans les
    commentaires qui expliquaient la règle.
    """
    motif = re.compile(r"""["']5Hostachy["']""")
    fautifs = []
    for p in _sources():
        texte = p.read_text(encoding="utf-8")
        for numero, ligne in enumerate(texte.splitlines(), 1):
            nue = ligne.strip()
            if nue.startswith("#") or nue.startswith("#:"):
                continue
            if motif.search(ligne):
                fautifs.append(f"{p.relative_to(APP)}:{numero}")
    assert not fautifs, (
        "Le nom de la copropriété est écrit dans le code :\n  "
        + "\n  ".join(fautifs)
        + "\n→ employer `nom_site(cfg.get('site_nom'))` (`app.utils.liens`)."
    )


def test_aucun_repli_de_nom_recopie():
    """Le repli lui-même ne se recopie pas — c'est ainsi qu'il a divergé."""
    fautifs = []
    for p in _sources():
        if p == _SOURCE:
            continue
        for numero, ligne in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            nue = ligne.strip()
            if nue.startswith("#"):
                continue
            #  ⚠️ On vise le REPLI, pas la clé : `("site_nom", "site_url")` est une
            #  liste de clés à lire, et la première version du motif la comptait —
            #  dix faux positifs, tous légitimes. Un contrôle qui crie sur du code
            #  juste se fait désarmer.
            if re.search(r"""get\(\s*["']site_nom["']\s*,\s*["']""", ligne) or re.search(
                r"""get\(\s*["']site_nom["']\s*\)\s*or\s*["']""", ligne
            ):
                fautifs.append(f"{p.relative_to(APP)}:{numero}")
    assert not fautifs, (
        "Un repli de nom de site est recopié :\n  "
        + "\n  ".join(fautifs)
        + "\n→ `nom_site(...)` porte le repli, et lui seul."
    )


@pytest.mark.parametrize(
    "valeurs,attendu",
    [
        (("Les Quatre Saisons",), "Les Quatre Saisons"),
        #  L'espace de fin n'est pas une valeur différente — même règle que `base_site`.
        (("  Résidence du Parc  ",), "Résidence du Parc"),
        #  🔴 LE CAS QUI ÉTAIT FAUX SEPT FOIS : présente, et vide.
        (("",), NOM_SITE_PAR_DEFAUT),
        (("   ",), NOM_SITE_PAR_DEFAUT),
        ((None,), NOM_SITE_PAR_DEFAUT),
        ((), NOM_SITE_PAR_DEFAUT),
        #  La cascade : une configuration spécifique passe avant la générale.
        ((None, "Générale"), "Générale"),
        (("Spécifique", "Générale"), "Spécifique"),
        (("", "Générale"), "Générale"),
    ],
)
def test_nom_site(valeurs, attendu):
    assert nom_site(*valeurs) == attendu


def test_le_repli_ne_nomme_aucune_copropriete_reelle():
    """Un repli doit être NEUTRE : il s'affiche chez quelqu'un d'autre."""
    assert "hostachy" not in NOM_SITE_PAR_DEFAUT.lower()
