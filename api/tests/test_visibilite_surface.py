"""La surface publique de `app.utils.visibility` se DÉRIVE, elle ne se recopie pas.

## Pourquoi (20/08/2026, #547)

`visibility.py` a franchi les 500 lignes en recevant un correctif de sécurité, et
la règle de modularité (rang 1) impose de découper. Il est devenu un paquet de
trois fragments — `socle`, `objets`, `documents` — derrière un `__init__.py` qui
réexporte, pour que ses **seize importateurs** ne changent pas d'une ligne.

🔴 **La liste des réexports a été écrite à la main, et elle était fausse.** Elle
portait les dix fonctions et oubliait `CODES_PUBLIC_CIBLE`, une **constante** : le
regard cherchait des `def`. La suite de tests ne démarrait plus — `ImportError` à
la collecte —, ce qui est la bonne façon d'échouer, mais seulement parce qu'un
test importait ce nom-là. Un nom public qu'aucun test n'importe encore serait
parti en silence, et le premier module qui en aurait eu besoin l'aurait
simplement redéfini chez lui.

C'est `standards/02` : une liste tenue en parallèle de ce qu'elle décrit diverge.
Ici, la source de vérité est le **code des fragments** ; ce fichier compare, et
c'est tout.

## Ce que ce test ne fait PAS

Il ne vérifie pas que les règles sont justes — `test_documents_acces.py`,
`test_visibilite_ouverte.py` et `test_perimetres_arbre.py` s'en chargent. Il
vérifie qu'aucune n'est devenue **inatteignable** en changeant de fichier.
"""
from __future__ import annotations

import ast
import pathlib

import app.utils.visibility as visibility

PAQUET = pathlib.Path(visibility.__file__).parent


def _noms_publics(fichier: pathlib.Path) -> set[str]:
    """Les noms de premier niveau qu'un fragment définit et n'a pas préfixés de `_`.

    Lecture de l'ARBRE, pas du texte : un motif textuel confondrait une
    définition avec une mention en commentaire — et ce paquet en est plein.
    """
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    noms: set[str] = set()
    for noeud in arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not noeud.name.startswith("_"):
                noms.add(noeud.name)
        elif isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name) and not cible.id.startswith("_"):
                    noms.add(cible.id)
        elif isinstance(noeud, ast.AnnAssign):
            if isinstance(noeud.target, ast.Name) and not noeud.target.id.startswith("_"):
                noms.add(noeud.target.id)
    return noms


def _fragments() -> list[pathlib.Path]:
    return sorted(f for f in PAQUET.glob("*.py") if f.name != "__init__.py")


def test_le_paquet_a_bien_des_fragments():
    """Cas zéro : sans fragment lu, tout le reste passerait au vert sans rien voir.

    Un renommage du paquet, un découpage en sous-répertoires, un fichier qui
    devient un module unique — chacun rendrait ce fichier muet, et un fichier de
    test muet se lit comme « rien à signaler » (`standards/04` §2).
    """
    fragments = _fragments()
    assert len(fragments) >= 2, (
        f"{len(fragments)} fragment(s) trouvé(s) dans {PAQUET} : le paquet a-t-il "
        "changé de forme ? Ce fichier ne mesurerait plus rien."
    )


def test_tout_nom_public_d_un_fragment_est_reexporte():
    """🔴 Le défaut réel : `CODES_PUBLIC_CIBLE` manquait à la liste.

    Un nom public défini dans un fragment mais absent de `__init__` n'est pas
    « privé » : il est **perdu**. Rien ne le dit, et le prochain qui en a besoin
    le réécrit chez lui — une deuxième règle de visibilité, exactement ce que ce
    module existe pour empêcher.
    """
    attendus: set[str] = set()
    for fragment in _fragments():
        attendus |= _noms_publics(fragment)

    manquants = sorted(n for n in attendus if not hasattr(visibility, n))
    assert not manquants, (
        f"nom(s) public(s) non réexporté(s) par `visibility/__init__.py` : {manquants}. "
        "Un nom perdu se réécrit ailleurs, et une règle de visibilité en double "
        "est une règle qui divergera."
    )


def test___all___dit_exactement_ce_que_le_paquet_expose():
    """⚠️ Et `__all__` doit dire la même chose que les imports, ni plus ni moins.

    Un `__all__` en retard ferait mentir `from … import *` et la lecture rapide du
    module ; un `__all__` en avance nommerait un symbole absent, et
    `from … import *` lèverait à l'exécution, pas ici.
    """
    attendus: set[str] = set()
    for fragment in _fragments():
        attendus |= _noms_publics(fragment)

    declares = set(visibility.__all__)
    assert declares == attendus, (
        f"absents d'`__all__` : {sorted(attendus - declares)} · "
        f"déclarés mais non définis : {sorted(declares - attendus)}"
    )
