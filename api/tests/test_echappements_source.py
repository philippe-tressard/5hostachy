r"""Le français du source s'écrit en clair, jamais en séquences d'échappement.

## Le défaut, tel qu'il était

Le 02/09/2026, **249 séquences `\uXXXX`** dormaient dans 15 fichiers versionnés —
modèles d'e-mail, contenus envoyés en WhatsApp, messages d'erreur rendus à
l'écran, séparateurs de section, docstrings. On y lisait, en toutes lettres :

    'Catégorie : {{ item.categorie }} · Priorité : …'
    raise HTTPException(403, "Vous n'êtes pas associé à ce lot.")

Python et JavaScript les décodent : **rien n'était cassé à l'exécution**. C'est
précisément ce qui rend le défaut durable — aucun test ne pouvait le trouver par
son effet, et il n'a aucun symptôme.

## Ce qu'il coûte

Le seul contrôle qui existe sur un texte envoyé aux résidents est **la
relecture**. Un libellé faux, un lien mort, une faute dans un modèle d'e-mail ne
se voient qu'à l'œil. Un texte écrit en séquences n'est pas relu : il est sauté.
Et la même écriture a déjà produit un défaut **fonctionnel** ici — un `\b` dans
un littéral de gabarit, qui a rendu `lint:titres` incapable de mesurer quoi que
ce soit depuis son écriture.

⚠️ Ces séquences ne viennent pas d'une frappe : elles viennent d'un outillage qui
écrit du source (`ascii()`, `json.dumps` sans `ensure_ascii=False`, un heredoc
qui avale les antislashs). C'est pourquoi une consigne ne suffit pas — la main
qui écrit le fichier ne les voit pas non plus.

## La règle, et pourquoi elle a exactement cette frontière

**Un caractère qu'on peut lire s'écrit en clair. Un caractère qu'on ne peut pas
voir reste échappé.** La frontière est la CATÉGORIE Unicode, jamais une liste :

- `Zs` (espaces insécables) : les écrire en clair les rendrait indiscernables
  d'une espace ordinaire, et la typographie française en dépend ;
- `Mn` (accents combinants, sélecteur de variante) : invisibles isolément, et
  employés ici dans des classes de regex où la forme échappée est la seule
  lisible ;
- `Cc` / `Cf` / `Cs` : non imprimables par définition.

Tout le reste — lettres accentuées, tirets, apostrophes, symboles — est visible,
donc s'écrit visiblement.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

BS = chr(92)

RACINE = Path(__file__).resolve().parents[2]

#: Où le source vit. `scripts/` en fait partie : le défaut y était aussi
#: (`setup-rpi5.sh`), et un contrôle qui ne regarde que `api/` aurait été vert
#: sur un dépôt fautif — « la portée du contrôle fait partie du contrôle ».
ARBRES = ("api", "front/src", "front/scripts", "scripts")
SUFFIXES = (".py", ".ts", ".svelte", ".mjs", ".js", ".sh")
IGNORES = ("node_modules", ".svelte-kit", "__pycache__", "build", "dist")

#: 🔴 AUCUNE EXCEPTION, et ce n'est pas un oubli.
#:
#: La première rédaction en déclarait trois — les fichiers qui PARLENT du
#: défaut et doivent donc le citer. Le contrôle les a refusées : un fichier qui
#: montre la séquence l'écrit forcément avec DEUX antislashs, et le motif
#: ci-dessous ne compte que les séquences réelles. L'exception était superflue
#: avant d'exister.
#:
#: C'est la bonne façon de ne pas avoir de liste : une frontière qui rend
#: l'exception inutile, jamais une liste qu'on cesse de relire.

#: Une séquence réelle : précédée d'un nombre PAIR d'antislashs. Sans cette
#: garde, un antislash littéral suivi de `u2014` serait compté à tort — et trois
#: occurrences de cette forme existent, dans les tests qui parlent du sujet.
_SEQUENCE = re.compile(r"(?<!\\)(?:\\\\)*\\u([0-9a-fA-F]{4})")

#: Les emoji hors du plan de base — `\\U0001f4c5`, huit chiffres — sont couverts
#: depuis le 03/09/2026 (#734) : 73 séquences réécrites en clair dans 18 fichiers
#: vivants, avec la même preuve d'équivalence par AST.
_EMOJI = re.compile(r"(?<!\\)(?:\\\\)*\\U000([0-9a-fA-F]{5})")

#: 🔴 `api/alembic/` EN EST EXCLU, et c'est la seule exception du fichier.
#:
#: Une migration déjà appliquée ne se réécrit jamais (`CLAUDE.md`). Le job Ruff
#: porte déjà la même exclusion, avec le même motif : *« les corriger pour
#: satisfaire un linter réécrirait l'historique du schéma — le remède serait pire
#: que le défaut »*. Les emoji y sont d'ailleurs le cas le moins grave : ils se
#: lisent comme « un emoji », là où une lettre échappée casse le mot lui-même.
#:
#: ⚠️ L'exclusion est VÉRIFIÉE, pas supposée : `test_l_exclusion_alembic_sert_encore`
#: échoue si ces migrations cessaient d'en porter — une exception qui ne sert plus
#: fait croire la règle plus poreuse qu'elle ne l'est.
SANS_EMOJI = ("api/alembic",)


def _visible(point: str) -> bool:
    """Un caractère imprimable, qui a donc sa place en clair dans le source."""
    return unicodedata.category(chr(int(point, 16)))[0] not in "ZMC"


def _fichiers():
    for arbre in ARBRES:
        base = RACINE / arbre
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if f.suffix not in SUFFIXES:
                continue
            if any(part in IGNORES for part in f.parts):
                continue
            yield f


def lignes_fautives(texte: str, court: str = "<texte>") -> list[str]:
    """La décision, PURE : ce qu'un contenu porte de fautif.

    Séparée de la lecture des fichiers exprès — c'est le seul moyen de
    l'éprouver sur un contenu connu, sans écrire sur le disque. Le dépôt a déjà
    payé l'inverse : « je testais la décision, pas le tuyau qui la nourrit ».
    """
    trouves = []
    emoji = not any(court.startswith(a) for a in SANS_EMOJI)
    for ligne_no, ligne in enumerate(texte.splitlines(), 1):
        for m in _SEQUENCE.finditer(ligne):
            if _visible(m.group(1)):
                c = chr(int(m.group(1), 16))
                trouves.append(
                    f"  {court}:{ligne_no} — la lettre « {c} » écrite en séquence"
                )
        if emoji:
            for m in _EMOJI.finditer(ligne):
                c = chr(int(m.group(1), 16))
                trouves.append(
                    f"  {court}:{ligne_no} — l'emoji « {c} » écrit en séquence"
                )
    return trouves


def _releve() -> dict[str, list[str]]:
    """Chemin relatif POSIX -> lignes fautives, fichier par fichier."""
    par_fichier: dict[str, list[str]] = {}
    for f in _fichiers():
        court = f.relative_to(RACINE).as_posix()
        fautes = lignes_fautives(f.read_text(encoding="utf-8", errors="replace"), court)
        if fautes:
            par_fichier[court] = fautes
    return par_fichier


def test_aucune_lettre_francaise_ecrite_en_sequence_d_echappement():
    fautifs = [x for lignes in _releve().values() for x in lignes]
    assert not fautifs, (
        f"{len(fautifs)} séquence(s) d'échappement pour des caractères "
        "IMPRIMABLES :\n" + "\n".join(fautifs[:40])
        + "\n\nCe texte ne sera pas relu, donc pas vérifié. L'écrire en clair.\n"
        "Si l'outil qui produit le fichier échappe tout seul : "
        "`json.dumps(..., ensure_ascii=False)`, et jamais `ascii()`."
    )


def test_le_controle_regarde_bien_quelque_chose():
    """Cas zéro. Un scan qui ne lit aucun fichier rend la même liste vide.

    C'est la seule façon de distinguer « rien trouvé » de « rien lu » — le faux
    vert que ce dépôt a produit assez de fois pour en faire une règle.
    """
    fichiers = list(_fichiers())
    assert len(fichiers) > 400, (
        f"seulement {len(fichiers)} fichier(s) examiné(s) : le scan ne voit "
        "presque rien, et son verdict ne vaut rien."
    )
    #  Et la décision doit voir une faute quand il y en a une, sans se laisser
    #  prendre par un antislash littéral ni par un invisible légitime.
    assert lignes_fautives("Cat" + BS + "u00e9gorie") != []
    assert lignes_fautives("un antislash " + BS + BS + "u2014 littéral") == []
    assert lignes_fautives("Article" + BS + "u00a0: 3") == []
    assert lignes_fautives("Date " + BS + "U0001f4c5") != []
    assert lignes_fautives("Date " + BS + "U0001f4c5", "api/alembic/versions/x.py") == []


def test_l_exclusion_alembic_sert_encore():
    """Une exception qui ne correspond plus à rien se retire.

    Le jour où plus aucune migration ne porterait d'emoji échappé, cette
    exclusion ferait croire la règle plus poreuse qu'elle ne l'est — et
    couvrirait autre chose sans qu'on s'en aperçoive.
    """
    porteuses = [
        f.relative_to(RACINE).as_posix()
        for f in (RACINE / "api" / "alembic").rglob("*.py")
        if _EMOJI.search(f.read_text(encoding="utf-8", errors="replace"))
    ]
    assert porteuses, (
        "plus aucune migration ne porte d'emoji échappé : retirer `SANS_EMOJI`, "
        "l'exclusion ne protège plus rien."
    )


def test_les_invisibles_restent_autorises():
    """L'exception de catégorie est vérifiée, pas supposée.

    Si `_visible` se mettait à refuser l'insécable, 71 lignes de typographie
    française deviendraient fautives d'un coup — et la tentation serait de les
    « corriger » en espaces ordinaires, ce qui casserait le rendu.
    """
    for point in ("00a0", "202f", "0300", "fe0f"):
        assert not _visible(point), point + " devrait rester échappé"
    for point in ("00e9", "2014", "2019", "2500", "20ac"):
        assert _visible(point), point + " devrait s'écrire en clair"
