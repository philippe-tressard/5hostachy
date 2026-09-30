"""Les URL écrites dans les MODÈLES d'e-mail mènent quelque part.

## Le trou que ce test bouche (11/09/2026, demandé à l'écran)

`test_liens_front.py` vérifie les liens que le code Python **fabrique**
(`lien_element`, `lien=`, `lien_path=`). Il ne voit pas ceux qui sont écrits
**dans le HTML des modèles** — des chaînes de `app/seed/emails/*.py` que rien ne
relisait. C'est par là qu'est passé le défaut signalé : un bouton « Consulter le
ticket » pointant sur `https://5hostachy.fr//tickets/34`, **404**.

La cause de celui-là était ailleurs (`site_url` non normalisé, cf.
`test_base_site.py`) — mais personne ne pouvait le savoir, puisque **aucun
contrôle ne regardait les liens des e-mails**. Un e-mail part chez le syndic, un
prestataire, un résident : c'est le seul endroit du produit où un lien mort ne se
corrige pas après coup.

## Ce qu'il vérifie, et pourquoi chaque règle

| Règle | Ce qu'elle évite |
|---|---|
| le lien est **absolu** | un `/tickets/34` dans un e-mail n'ouvre rien : il n'y a pas de page courante |
| pas de **double barre** | exactement le 404 signalé |
| le chemin **existe côté front** | le défaut de 2026-07 (`/documents`), qui n'a jamais existé — tenu par `test_liens_front.py::test_les_liens_ecrits_dans_les_modeles_email_existent`, qui lit les mêmes liens dans les modèles rendus |
| pas de **domaine en dur** | une adresse figée survit au changement de nom de domaine, et pointe alors chez quelqu'un d'autre |

⚠️ Une variable de lien (`{{ reponse.lien }}`) est **déclarée** avec l'endroit qui
la remplit. Le test ne peut pas la suivre tout seul — mais il peut exiger qu'elle
soit nommée, et qu'à cet endroit-là une URL absolue soit construite. Une variable
non déclarée échoue : c'est la seule façon d'empêcher qu'un futur modèle emporte
un chemin nu sans que personne le voie.

Chaque règle est UN contrôle qui balaie tous les liens et nomme tous ses écarts
d'un coup — pas un test par lien, qui s'arrêterait sur le premier cas et
noierait le rapport sous soixante lignes vertes.
"""

from __future__ import annotations

import pathlib
import re

SEED = pathlib.Path(__file__).resolve().parents[1] / "app" / "seed" / "emails"
APP = pathlib.Path(__file__).resolve().parents[1] / "app"

HREF = re.compile(r'href="([^"]*)"')

#: 🔴 **Depuis la factorisation du 15/09/2026 (#959), les liens ne sont plus
#: tous écrits dans le HTML** : `fragments.bouton(href, libellé)` compose l'ancre,
#: et le modèle lui passe l'adresse. Un contrôle qui ne lirait que `href="…"`
#: verrait donc de moins en moins de choses, jusqu'à ne plus rien mesurer.
#:
#: ⚠️ C'est le cas zéro (`test_il_y_a_bien_des_liens_a_verifier`) qui l'a
#: attrapé, et c'est exactement ce pour quoi il existe : la factorisation n'a
#: pas cassé un test, elle a déplacé ce qu'il fallait lire.
APPEL_BOUTON = re.compile(r'\bbouton\(\s*["\']([^"\']+)["\']')

#: Le `href` de `fragments.bouton()` lui-même : un TROU de f-string, pas un lien.
#: L'appelant le remplit, et c'est lui qu'on vérifie.
PARAMETRE = "{href}"

#: Le préfixe qui rend une URL absolue dans un modèle.
BASE = "{{ app.url }}"

#: Les variables de lien employées sans `{{ app.url }}`, et le fichier qui les
#: remplit — il DOIT y construire une URL absolue.
#:
#: 🔴 Déclarer ne suffit pas : `test_les_variables_de_lien_sont_ABSOLUES` ouvre
#: chacun de ces fichiers et exige qu'une base de site y soit concaténée. Sans
#: cela, cette table serait une liste de dérogations, c'est-à-dire un endroit où
#: ranger les défauts.
VARIABLES_ABSOLUES = {
    "{{ lien }}": "routers/auth.py",
    "{{ idee.lien }}": "utils/reponses.py",
    "{{ reponse.lien }}": "utils/reponses.py",
}


def _liens_des_modeles() -> list[tuple[str, str]]:
    """Toutes les adresses des modèles, avec le fichier qui les porte.

    **Deux sources**, depuis que la mise en forme est factorisée :

    1. les `href="…"` encore écrits dans le HTML d'un modèle ;
    2. l'adresse passée à `fragments.bouton(…)`, qui compose l'ancre.

    Le paramètre `{href}` de `bouton()` lui-même est exclu : c'est un trou de
    f-string, et le lien réel est celui que l'appelant y met.
    """
    trouves = []
    for f in sorted(SEED.glob("*.py")):
        src = f.read_text(encoding="utf-8")
        for lien in HREF.findall(src):
            lien = lien.strip()
            if lien == PARAMETRE:
                continue
            trouves.append((f.name, lien))
        for lien in APPEL_BOUTON.findall(src):
            trouves.append((f.name, lien.strip()))
    return trouves


def test_il_y_a_bien_des_liens_a_verifier():
    """⚠️ Le cas zéro (`standards/04` §2). Si l'extraction cesse de fonctionner —
    les modèles déplacés, le HTML réécrit autrement —, tous les contrôles de ce
    fichier passeraient au vert en ne mesurant rien."""
    liens = _liens_des_modeles()
    assert len(liens) >= 15, f"seulement {len(liens)} lien(s) extraits — l'extraction est cassée"


def test_chaque_lien_de_modele_est_absolu():
    """Un chemin nu dans un e-mail n'ouvre rien : il n'y a pas de page courante."""
    fautifs = [
        f"  {fichier} : « {lien} »"
        for fichier, lien in _liens_des_modeles()
        if not lien.startswith(("mailto:", BASE)) and lien not in VARIABLES_ABSOLUES
    ]
    assert not fautifs, (
        f"Liens ni préfixés par `{BASE}` ni déclarés dans VARIABLES_ABSOLUES avec le "
        "fichier qui les remplit :\n" + "\n".join(fautifs)
    )


def test_aucun_lien_ne_porte_de_double_barre():
    """Le défaut signalé : `{{ app.url }}` vaut déjà `https://…` sans barre
    finale (`utils/liens.base_site`) ; en écrire une seconde ici la ramènerait."""
    fautifs = []
    for fichier, lien in _liens_des_modeles():
        apres = lien[len(BASE) :] if lien.startswith(BASE) else lien
        if "//" in apres:
            fautifs.append(f"  {fichier} : « {lien} »")
    assert not fautifs, "Double barre dans le chemin :\n" + "\n".join(fautifs)


def test_aucun_domaine_ecrit_en_dur():
    """Une adresse figée survit au changement de nom de domaine, et pointe alors
    chez quelqu'un d'autre — un e-mail déjà parti ne se corrige pas."""
    fautifs = [
        f"  {fichier} : « {lien} »"
        for fichier, lien in _liens_des_modeles()
        if re.match(r"https?://", lien)
    ]
    assert not fautifs, f"Domaine écrit en dur — employer `{BASE}` :\n" + "\n".join(fautifs)


def test_les_variables_de_lien_sont_ABSOLUES_a_leur_point_d_appel():
    """🔴 Déclarer une variable ne la rend pas absolue. On ouvre le fichier qui
    la remplit et on exige qu'une base de site y soit concaténée."""
    fautifs = []
    for variable, fichier in VARIABLES_ABSOLUES.items():
        f = APP / fichier
        if not f.exists():
            fautifs.append(f"{variable} → {fichier} : le fichier a disparu")
            continue
        src = f.read_text(encoding="utf-8")
        if "base_site(" not in src and "_site_url(" not in src:
            fautifs.append(
                f"{variable} → {fichier} : aucune base de site n'y est construite, "
                "le lien partirait en chemin nu"
            )
    assert not fautifs, "Variables de lien non absolues :\n  " + "\n  ".join(fautifs)
