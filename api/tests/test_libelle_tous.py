"""« Tous », jamais « tous les résidents », dans un texte SERVI (#1305).

Depuis v2.49.3 (#1279), le choix sans restriction s'écrit « Tous »
(`LIBELLE_TOUS`) : un copropriétaire bailleur, un mandataire ou le syndic n'est
pas un résident, et « tous les résidents » promettait moins que la règle.
L'expression survivait dans un profil documentaire, quatre descriptions de
périmètre, un libellé d'administration et le message WhatsApp d'une publication
ciblée — `ux-patterns` §2 bis disait qu'aucun contrôle ne la tenait.

Portée : ce qui se LIT à l'écran ou dans un message. Les commentaires et
docstrings (« visible de tous les résidents », au sens du code) ne sont pas des
textes servis.
"""

from __future__ import annotations

import ast
import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_API = _RACINE / "api" / "app"
_FRONT = _RACINE / "front" / "src"
MOTIF = re.compile(r"tous\s+les\s+résidents", re.IGNORECASE)

#: Les constantes qui portent l'ANCIEN texte, lues par la migration 0226 pour le
#: remplacer en base : elles le contiennent exprès. Le test échoue si l'une ne
#: sert plus.
EXCEPTIONS = {"LIBELLE_TOUS_ANCIEN", "PASSAGES_TOUS_LES_RESIDENTS"}


def chaines_servies_python(source: str) -> list[tuple[int, str]]:
    """Les littéraux de chaîne d'un module, docstrings exclues. PURE."""
    arbre = ast.parse(source)
    docstrings = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            corps = noeud.body
            if (
                corps
                and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
            ):
                docstrings.add(id(corps[0].value))
    exemptes = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Assign) and any(
            isinstance(c, ast.Name) and c.id in EXCEPTIONS for c in noeud.targets
        ):
            exemptes |= {id(n) for n in ast.walk(noeud.value)}
    return [
        (n.lineno, n.value)
        for n in ast.walk(arbre)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and id(n) not in docstrings | exemptes
    ]


def texte_servi_svelte(source: str) -> str:
    """Le balisage d'un composant, commentaires HTML retirés. PURE."""
    fin = source.rfind("</script>")
    balisage = source[fin:] if fin >= 0 else source
    return re.sub(r"<!--.*?-->", "", balisage, flags=re.S)


def fautes_python(source: str) -> list[int]:
    return [ligne for ligne, s in chaines_servies_python(source) if MOTIF.search(s)]


def fautes_svelte(source: str) -> bool:
    return bool(
        MOTIF.search(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", texte_servi_svelte(source))))
    )


def test_le_controle_voit_les_formes_d_avant():
    """Cas zéro : les formes relevées par #1305 sont refusées, les commentaires non."""
    assert fautes_python('PROFIL = {"libelle": "Tous les résidents"}\n') == [1]
    assert fautes_python('D = ("parking. Concerne "\n     "tous les résidents.")\n') == [1]
    assert fautes_python('"""Visible de tous les résidents."""\n# tous les résidents\n') == []
    assert fautes_svelte("<script>\n</script>\n<label>Concerne tous les résidents</label>")
    assert fautes_svelte("</script>visible de <strong\n>tous les résidents</strong\n>")
    assert not fautes_svelte("</script><!-- tous les résidents --><p>Tous</p>")
    assert fautes_python('LIBELLE_TOUS_ANCIEN = "Tous les résidents"\n') == []


def test_aucun_texte_servi_ne_dit_tous_les_residents():
    fautes = []
    servies = set()
    for f in _API.rglob("*.py"):
        source = f.read_text(encoding="utf-8")
        servies |= {e for e in EXCEPTIONS if re.search(rf"^{e}\s*=", source, re.M)}
        for ligne in fautes_python(source):
            fautes.append(f"{f.relative_to(_RACINE)}:{ligne}")
    for f in _FRONT.rglob("*.svelte"):
        if fautes_svelte(f.read_text(encoding="utf-8")):
            fautes.append(str(f.relative_to(_RACINE)))
    assert servies == EXCEPTIONS, f"exception(s) qui ne servent plus : {EXCEPTIONS - servies}"
    assert not fautes, "« tous les résidents » dans un texte servi — écrire « Tous » :\n  " + (
        "\n  ".join(fautes)
    )
