"""Les fichiers de gouvernance disent la vérité sur la licence (#1033).

## Pourquoi ce contrôle — 🔴 RANG 1 (`standards/14`)

`CONTRIBUTING.md` promettait, en toutes lettres et depuis l'origine du dépôt, que
« *contributions will be licensed under the MIT License* ». Le dépôt est sous
**Licence 5Hostachy** — source-available, clauses commerciales, non reconnue OSI.
Un contributeur qui s'y fiait cédait son travail sous une attente **inverse** de
la licence réelle.

Ce n'était pas une faute d'inattention isolée : rien, nulle part, ne confrontait
le nom de licence écrit dans les fichiers publics à celui que le dépôt accorde.
`reuse lint` vérifie que chaque fichier **porte** une licence, jamais que les
textes publics **nomment** la bonne.

## Ce que le contrôle confronte

| Source de vérité | Ce qu'elle porte |
|---|---|
| `REUSE.toml` | l'identifiant SPDX réellement accordé (`LicenseRef-5Hostachy`) |
| `LICENSES/<identifiant>.txt` | le texte, exigé par REUSE à cet emplacement |
| `LICENSE`, `LICENSE-5Hostachy.md` | le même texte, aux deux noms qu'exigent GitHub et `NOTICE.md` §2 |

Le nom de la licence n'est **pas écrit ici** : il est dérivé de `REUSE.toml`.
Un nom recopié dans un test diverge le jour où la licence change, et le contrôle
défendrait alors l'ancienne (`standards/13` §1).

## Les trois copies du texte, et pourquoi elles restent

Le texte de licence existe en **trois exemplaires identiques**. C'est une
duplication, et elle est **imposée de l'extérieur** : GitHub ne reconnaît que
`LICENSE`, REUSE n'accepte que `LICENSES/<SPDX>.txt`, et `NOTICE.md` §2 fait de
la conservation de `LICENSE-5Hostachy.md` une obligation de la licence elle-même.
Aucun des trois ne peut partir sans casser quelque chose.

Ce qui peut être supprimé, ce n'est pas la copie — c'est la **divergence** :
`test_les_trois_copies_de_la_licence_sont_identiques` échoue à l'octet près. Une
licence modifiée à deux endroits sur trois est exactement le défaut que
`REUSE.toml` avait déjà connu avec ses douze motifs (#774).

## Français exclusif

`CONTRIBUTING.md` et `SECURITY.md` étaient intégralement en anglais alors que la
consigne du poste est « français exclusif », et que `README.md`, `NOTICE.md` et
`LICENSE` le respectaient. La règle n'avait aucun garde-fou : elle tenait sur
l'attention de qui écrivait.

Le contrôle ne juge pas une langue — il compte des mots **exclusivement**
anglais, hors blocs de code, liens et URL. Calibré avant d'être écrit : 0
occurrence sur les trois fichiers français, 33 et 23 sur les deux anglais.
"""

from __future__ import annotations

import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]

#: Les fichiers publics qui *parlent* de la licence et de la méthode du projet.
#: `LICENSE` en fait partie : c'est lui qui nomme sa propre nature.
GOUVERNANCE = ("README.md", "CONTRIBUTING.md", "SECURITY.md", "NOTICE.md", "LICENSE")

#: Les licences qu'un fichier de gouvernance ne peut pas promettre, puisque le
#: dépôt ne les accorde pas.
#:
#: `AGPL` n'y est pas, et c'est voulu : la Licence 5Hostachy se déclare
#: *fondée sur les principes de l'AGPLv3* et dit explicitement ne pas lui être
#: compatible. La citer est exact ; promettre MIT ne l'était pas.
#:
#: ⚠️ **Aucune exception n'est déclarée ici, parce qu'aucune ne sert
#: aujourd'hui** : le jour où `NOTICE.md` devra nommer la licence d'une
#: dépendance tierce embarquée, ce test échouera — et l'exception s'écrira
#: alors, avec sa raison et sa date (`standards/05` §2). Une exception posée à
#: vide ne protège rien et fait croire à une décision (`CLAUDE.md`, exceptions
#: XSS).
LICENCES_NON_ACCORDEES = (
    "MIT",
    "Apache",
    "BSD",
    "ISC",
    "LGPL",
    "MPL",
    "Unlicense",
    "WTFPL",
    "CC0",
    "Creative Commons",
)

#: Mots dont aucun n'a de sens en français. Ils ne mesurent pas un style : leur
#: présence dit qu'une phrase entière est en anglais.
MOTS_ANGLAIS = (
    r"\b(the|you|your|this|these|with|will|and|for|from|that|are|have|our"
    r"|use|using|when|where|which|please)\b"
)


def _lire(chemin: str) -> str:
    fichier = _RACINE / chemin
    assert fichier.exists(), (
        f"{chemin} introuvable — le contrôle a perdu sa portée, "
        "il ne devient pas vert pour autant (`standards/04` §1)"
    )
    return fichier.read_text(encoding="utf-8")


def _prose_seule(texte: str) -> str:
    """Le texte sans ce qui n'est pas de la prose : code, URL — **pas** les libellés.

    Un bloc ```bash``, un `cp .env.example .env` ou un `example.com` ne sont pas
    de l'anglais — ce sont des identifiants techniques, que la consigne laisse
    tels quels.

    🔴 Le libellé d'un lien markdown est de la prose, et de la prose lue. Une
    première version de cette fonction jetait `[texte](url)` en entier : le
    « MIT » de `[MIT License](LICENSE)` disparaissait donc **avant** le
    contrôle, qui passait au vert sur le défaut même qu'il devait attraper. Le
    cas zéro l'a montré — c'est pour ça qu'on l'écrit d'abord
    (`standards/04` §2).
    """
    texte = re.sub(r"```.*?```", " ", texte, flags=re.S)
    texte = re.sub(r"`[^`]*`", " ", texte)
    texte = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", texte)
    texte = re.sub(r"https?://\S+", " ", texte)
    return texte


def identifiant_spdx_accorde() -> str:
    """L'identifiant que le dépôt accorde réellement, lu dans `REUSE.toml`."""
    reuse = _lire("REUSE.toml")
    trouve = re.search(r'SPDX-License-Identifier\s*=\s*"([^"]+)"', reuse)
    assert trouve, (
        "REUSE.toml ne déclare aucun SPDX-License-Identifier : "
        "la licence accordée par le dépôt n'est plus lisible nulle part"
    )
    return trouve.group(1)


def nom_lisible_de_la_licence() -> str:
    """« Licence 5Hostachy » — le titre du texte de licence, pas une constante."""
    premiere_ligne = _lire("LICENSE").splitlines()[0]
    return premiere_ligne.lstrip("# ").strip()


def test_aucun_fichier_public_ne_promet_une_licence_non_accordee():
    """Le défaut exact du 19/09/2026 : « MIT » dans `CONTRIBUTING.md`."""
    fautes = []
    for nom in GOUVERNANCE:
        prose = _prose_seule(_lire(nom))
        for licence in LICENCES_NON_ACCORDEES:
            for trouve in re.finditer(rf"\b{re.escape(licence)}\b", prose, re.I):
                debut = max(0, trouve.start() - 60)
                fautes.append(f"  {nom} : …{prose[debut : trouve.end() + 40].strip()}…")

    assert not fautes, (
        "Un fichier public nomme une licence que le dépôt n'accorde pas "
        f"(il accorde « {nom_lisible_de_la_licence()} », "
        f"SPDX {identifiant_spdx_accorde()}) :\n" + "\n".join(fautes)
    )


def test_contributing_nomme_la_licence_reelle_et_son_fichier():
    """Ne pas promettre MIT ne suffit pas : il faut dire ce qui s'applique."""
    contributing = _lire("CONTRIBUTING.md")
    nom = nom_lisible_de_la_licence()
    assert nom in contributing, (
        f"CONTRIBUTING.md ne nomme pas « {nom} » : un contributeur ne peut pas "
        "savoir sous quelle licence son travail est versé"
    )

    liens = re.findall(r"\]\(([^)]*LICENSE[^)]*)\)", contributing)
    assert liens, "CONTRIBUTING.md ne renvoie vers aucun fichier de licence"
    for lien in liens:
        cible = _RACINE / lien.split("#")[0]
        assert cible.exists(), f"CONTRIBUTING.md renvoie vers « {lien} », qui n'existe pas"


def test_les_trois_copies_de_la_licence_sont_identiques():
    """Trois noms imposés de l'extérieur, un seul texte — vérifié à l'octet."""
    spdx = identifiant_spdx_accorde()
    copies = ("LICENSE", "LICENSE-5Hostachy.md", f"LICENSES/{spdx}.txt")
    contenus = {nom: (_RACINE / nom).read_bytes() for nom in copies}

    for nom in copies:
        assert (_RACINE / nom).exists(), (
            f"{nom} a disparu. Les trois noms sont imposés : GitHub ne lit que "
            "LICENSE, REUSE que LICENSES/<SPDX>.txt, et NOTICE.md §2 fait de "
            "LICENSE-5Hostachy.md une obligation de la licence elle-même"
        )

    reference = contenus["LICENSE"]
    divergentes = [nom for nom, octets in contenus.items() if octets != reference]
    assert not divergentes, (
        "Le texte de licence diverge entre ses copies : "
        f"{', '.join(divergentes)} ≠ LICENSE. La licence a été modifiée à un "
        "endroit sur trois — c'est le défaut que REUSE.toml a déjà connu (#774)."
    )


def test_la_gouvernance_est_redigee_en_francais():
    """« Français exclusif » n'avait aucun garde-fou avant le 19/09/2026."""
    fautes = {}
    for nom in GOUVERNANCE:
        mots = re.findall(MOTS_ANGLAIS, _prose_seule(_lire(nom)), re.I)
        if mots:
            fautes[nom] = sorted({mot.lower() for mot in mots})

    assert not fautes, (
        "Des fichiers de gouvernance sont rédigés en anglais, alors que le "
        "projet est intégralement en français :\n"
        + "\n".join(f"  {nom} : {', '.join(mots)}" for nom, mots in fautes.items())
    )
