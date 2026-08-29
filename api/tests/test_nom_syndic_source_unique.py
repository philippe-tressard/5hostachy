"""Garde-fou : le nom du syndic a UNE source, celle du contrat (#535).

## Le doublon que ce test ferme

Le nom du syndic existait **deux fois** — `SyndicInfo.nom_syndic` (texte libre)
et `Copropriete.syndic_contrat_id → ContratEntretien → Prestataire.nom` — et rien
ne disait que c'était le même.

🔴 **Changer de syndic dans Prestataires ne mettait à jour ni l'annuaire ni la
fiche arrivant**, celle qu'on remet aux nouveaux résidents et qu'ils n'ont aucun
moyen de vérifier.

⚠️ C'est le même défaut que #490 a corrigé pour l'assurance, **sur la ligne d'à
côté du même modèle** : la conversion s'était arrêtée à mi-chemin. Ce test existe
pour qu'elle ne reparte pas en arrière.

## Ce qui est vérifié

  1. le contrat FAIT FOI dès qu'il existe ;
  2. la saisie sert de REPLI, et seulement là où le contrat est absent ;
  3. `source_du_nom` dit laquelle a répondu — sans quoi l'écran laisserait
     corriger un texte que personne ne lit ;
  4. aucun module hors `utils/syndic.py` ne LIT `SyndicInfo.nom_syndic` pour en
     déduire un affichage. C'est ce point qui attrape la réapparition du doublon.
"""
import ast
import pathlib
import types

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
SOURCE = APP / "utils" / "syndic.py"

#: L'administration ÉCRIT ce champ (c'est le repli) : c'est son métier.
#: Déclaré ici avec son motif — une exception non écrite est un oubli qui
#: ressemble à une décision.
EXCEPTIONS = {
    "routers/admin/annuaire.py": "écrit la saisie de repli, ne la lit pas pour afficher",
    "models/core.py": "définit la colonne",
}


class _Session:
    """Une session minimale : `syndic.py` ne fait que `exec(...).first()` et `get`."""

    def __init__(self, copro=None, contrat=None, presta=None, info=None):
        self._suite = [copro, info]
        self._contrat, self._presta = contrat, presta
        self._i = 0

    def exec(self, _requete):
        valeur = self._suite[min(self._i, len(self._suite) - 1)]
        self._i += 1
        return types.SimpleNamespace(first=lambda: valeur)

    def get(self, modele, ident):
        return self._presta if "Prestataire" in modele.__name__ else self._contrat


def _monde(nom_contrat=None, nom_saisi=None, contrat_designe=True):
    copro = types.SimpleNamespace(id=1, syndic_contrat_id=7 if contrat_designe else None)
    contrat = types.SimpleNamespace(id=7, prestataire_id=3) if nom_contrat else None
    presta = types.SimpleNamespace(id=3, nom=nom_contrat) if nom_contrat else None
    info = types.SimpleNamespace(nom_syndic=nom_saisi) if nom_saisi is not None else None
    return copro, contrat, presta, info


def _appeler(fn, nom_contrat=None, nom_saisi=None, monkeypatch=None):
    """Appelle `fn` en neutralisant `contrat_de_reference`, qui fait une requête."""
    from app.utils import syndic as mod

    copro, contrat, presta, info = _monde(nom_contrat, nom_saisi)
    import app.routers.copropriete as rc

    original = rc.contrat_de_reference
    rc.contrat_de_reference = lambda s, c, section: contrat
    try:
        return getattr(mod, fn)(_Session(copro, contrat, presta, info))
    finally:
        rc.contrat_de_reference = original


# ── Le contrat fait foi ──────────────────────────────────────────────────────

def test_le_contrat_fait_foi_quand_il_existe():
    assert _appeler("nom_du_syndic", nom_contrat="Cabinet Nouveau", nom_saisi="Ancien Syndic") == "Cabinet Nouveau"


def test_la_source_est_nommee_pour_l_ecran():
    """Un champ de saisie sans effet doit le dire, sinon on corrige dans le vide."""
    assert _appeler("source_du_nom", nom_contrat="Cabinet Nouveau", nom_saisi="Ancien") == "contrat"


# ── Le repli, et rien de plus ────────────────────────────────────────────────

def test_la_saisie_sert_de_repli_sans_contrat():
    assert _appeler("nom_du_syndic", nom_contrat=None, nom_saisi="Cabinet Saisi") == "Cabinet Saisi"
    assert _appeler("source_du_nom", nom_contrat=None, nom_saisi="Cabinet Saisi") == "saisie"


def test_ni_l_un_ni_l_autre_rend_une_chaine_vide():
    """Jamais `None` : les appelants l'écrivent dans un e-mail et dans un PDF.

    `None` s'y afficherait « None » sur le document remis au résident — c'est le
    genre de détail qui ne casse rien et se voit sur papier.
    """
    assert _appeler("nom_du_syndic", nom_contrat=None, nom_saisi=None) == ""
    assert _appeler("source_du_nom", nom_contrat=None, nom_saisi=None) == "aucune"


def test_un_contrat_sans_nom_de_prestataire_retombe_sur_la_saisie():
    """Le contrat existe mais son prestataire n'a pas de nom : on ne rend pas vide."""
    assert _appeler("nom_du_syndic", nom_contrat="", nom_saisi="Cabinet Saisi") == "Cabinet Saisi"


# ── Personne ne relit la colonne pour afficher ───────────────────────────────

def test_aucun_module_ne_lit_la_colonne_pour_afficher():
    """C'est ce point qui attrape la réapparition du doublon.

    Un troisième écran qui lirait `SyndicInfo.nom_syndic` en direct rouvrirait
    exactement l'écart que ce lot ferme — et il serait vert partout ailleurs.
    """
    coupables = {}
    for chemin in sorted(APP.rglob("*.py")):
        if "__pycache__" in chemin.parts or chemin == SOURCE:
            continue
        rel = chemin.relative_to(APP).as_posix()
        if rel in EXCEPTIONS:
            continue
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        lus = [
            n.lineno
            for n in ast.walk(arbre)
            if isinstance(n, ast.Attribute)
            and n.attr == "nom_syndic"
            and isinstance(n.ctx, ast.Load)
        ]
        if lus:
            coupables[rel] = lus
    assert not coupables, (
        f"`nom_syndic` relu hors de `utils/syndic.py` : {coupables}.\n"
        "Appeler `nom_du_syndic(session)` — le contrat fait foi, la saisie n'est "
        "qu'un repli. Deux sources qui répondent en même temps sont le doublon "
        "que #535 ferme."
    )


def test_les_exceptions_declarees_servent_encore():
    mortes = []
    for rel, motif in EXCEPTIONS.items():
        chemin = APP / rel
        if not chemin.exists():
            mortes.append(f"{rel} (absent — {motif})")
        elif "nom_syndic" not in chemin.read_text(encoding="utf-8"):
            mortes.append(f"{rel} (ne touche plus au champ — {motif})")
    assert not mortes, f"Exceptions à retirer : {mortes}"
