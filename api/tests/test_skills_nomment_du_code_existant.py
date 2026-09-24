"""Une skill ne nomme que du code qui existe (#1035).

## 🔴 Pourquoi — la consigne périmée régénère le défaut

Les deux skills chargées **avant d'écrire dans `front/src/`** enseignaient des
motifs que le code avait supprimés — dont trois qu'un linter refuse. Ce n'est
pas une imprécision de documentation : c'est la première cause de récidive que
`standards/02` §5 nomme.

Le précédent est daté : `svelte-patterns` a produit `renderContent` (#429) en
enseignant un motif d'assainissement remplacé depuis. Le code était corrigé, la
skill non — et la skill est ce qu'on lit **avant** d'écrire.

## Ce que ce contrôle vérifie

Trois familles de noms, choisies parce qu'elles se vérifient sans ambiguïté :

| Forme citée | Doit exister |
|---|---|
| `Quelquechose.svelte` | un fichier de ce nom sous `front/src` |
| `lint:quelquechose` | un script de ce nom dans `front/package.json` |
| `$lib/x.ts` ou `lib/x.ts` | le fichier correspondant |

⚠️ **Une mention historique n'est pas une faute.** Une skill a le droit — et le
devoir — de dire « `PhotosUpload` a été remplacé par `FichiersUpload` » : c'est
ce qui empêche le nom mort de revenir. Le contrôle ignore donc toute ligne qui
porte un marqueur d'historique (`supprimé`, `retiré`, `n'existe plus`,
`remplacé`, `renommé`…).

C'est la distinction qui rend ce contrôle tenable : il ne cherche pas les noms
morts, il cherche **les noms morts présentés comme vivants**.

## Ce qu'il ne fait pas

Il ne vérifie pas que la skill enseigne le **bon** motif — seulement qu'elle ne
renvoie pas vers un fichier absent. Une skill peut être à jour sur les noms et
périmée sur le fond ; c'est ce que l'audit de cohérence mesure, et il ne
s'automatise pas.
"""

from __future__ import annotations

import json
import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_SKILLS = _RACINE / ".claude" / "skills"
_FRONT = _RACINE / "front"

#: Les skills qui parlent du front, donc celles dont les noms se vérifient ici.
#: ⚠️ La portée fait partie du contrôle : une skill ajoutée qui parle du front
#: doit rejoindre cette liste, et le premier test échoue si l'une disparaît.
SKILLS_FRONT = ("svelte-patterns", "ux-patterns")

#: Une ligne qui porte l'un de ces mots parle du PASSÉ : le nom qu'elle cite a
#: le droit de ne plus exister, et c'est même le but.
MARQUEURS_HISTORIQUE = (
    #  ⚠️ « n'existe pas » autant que « n'existe plus » : une skill qui CORRIGE
    #  une mention morte écrit souvent la première forme — « cette ligne nommait
    #  X, qui n'existe pas ». Le marqueur ne reconnaissait que la seconde, et le
    #  contrôle accusait la correction elle-même.
    "supprim",
    "retir",
    "n'existe plus",
    "nexiste plus",
    "n'existe pas",
    "nexiste pas",
    "remplac",
    "renomm",
    "disparu",
    "avant le",
    "jusqu'au",
    "jusquau",
    "périmé",
    "perime",
    "ne porte plus",
    "cessé",
    "cesse de",
    "obsolèt",
    "obsolet",
    "plus aucun",
)


def _lignes_vivantes(skill: str):
    """(numéro, ligne) des lignes qui ne parlent pas du passé."""
    chemin = _SKILLS / skill / "SKILL.md"
    for numero, ligne in enumerate(chemin.read_text(encoding="utf-8").split("\n"), 1):
        minuscule = ligne.lower()
        if any(marqueur in minuscule for marqueur in MARQUEURS_HISTORIQUE):
            continue
        yield numero, ligne


def _composants_existants() -> set[str]:
    return {p.name for p in (_FRONT / "src").rglob("*.svelte")}


def _scripts_npm() -> set[str]:
    paquet = json.loads((_FRONT / "package.json").read_text(encoding="utf-8"))
    return set(paquet.get("scripts", {}))


def test_la_portee_du_controle_est_intacte():
    """Cas zéro : une skill absente, et le contrôle ne vérifie plus rien."""
    for skill in SKILLS_FRONT:
        assert (_SKILLS / skill / "SKILL.md").exists(), (
            f"{skill}/SKILL.md est introuvable — le contrôle a perdu sa portée"
        )
    composants = _composants_existants()
    assert len(composants) > 50, (
        f"seulement {len(composants)} composant(s) trouvé(s) : le scan ne voit "
        "probablement pas `front/src`"
    )
    assert _scripts_npm(), "aucun script npm lu"


def test_aucun_composant_cite_n_a_disparu():
    """Le défaut exact : `PhotosUpload.svelte` n'existe pas."""
    existants = _composants_existants()
    fautes = []
    for skill in SKILLS_FRONT:
        for numero, ligne in _lignes_vivantes(skill):
            for nom in re.findall(r"\b([A-Z][A-Za-z0-9]*\.svelte)\b", ligne):
                if nom not in existants:
                    fautes.append(f"  {skill}:{numero} — {nom}")

    assert not fautes, (
        "Ces skills renvoient vers des composants qui n'existent pas :\n"
        + "\n".join(fautes)
        + "\n\n"
        "Une skill est lue AVANT d'écrire : un nom mort présenté comme vivant "
        "fait recréer le motif qu'il désignait (`standards/02` §5 — c'est ainsi "
        "que `renderContent` est né, #429).\n"
        "Si la mention est historique, la ligne doit le dire (« remplacé par… », "
        "« supprimé le… ») : le contrôle ignore alors la ligne, et le lecteur "
        "sait à quoi s'en tenir."
    )


def test_aucun_linter_cite_n_existe_plus():
    """Une skill qui nomme un `lint:*` absent envoie lancer une commande morte."""
    scripts = _scripts_npm()
    fautes = []
    for skill in SKILLS_FRONT:
        for numero, ligne in _lignes_vivantes(skill):
            for nom in re.findall(r"\blint:([a-z0-9-]+)\b", ligne):
                if f"lint:{nom}" not in scripts:
                    fautes.append(f"  {skill}:{numero} — lint:{nom}")

    assert not fautes, (
        "Ces skills nomment des contrôles qui n'existent pas dans "
        "`front/package.json` :\n" + "\n".join(fautes) + "\n\n"
        "Un garde-fou cité mais absent est pire qu'un garde-fou absent : il fait "
        "croire que la règle est tenue."
    )


def test_aucun_module_de_lib_cite_n_a_disparu():
    """`$lib/x.ts` doit exister : une skill ne renvoie pas vers un chemin mort."""
    fautes = []
    for skill in SKILLS_FRONT:
        for numero, ligne in _lignes_vivantes(skill):
            for chemin in re.findall(r"\$lib/([a-z0-9_/-]+\.ts)\b", ligne):
                if not (_FRONT / "src" / "lib" / chemin).exists():
                    fautes.append(f"  {skill}:{numero} — $lib/{chemin}")

    assert not fautes, "Ces skills renvoient vers des modules absents :\n" + "\n".join(fautes)
