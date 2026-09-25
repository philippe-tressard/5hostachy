"""Garde-fou préventif : cohérence de la documentation livrée.

Ce que l'on peut vérifier mécaniquement l'est ici. Ce qui relève du jugement
(« le manuel décrit-il encore fidèlement l'application ? ») reste une étape du
pré-check MEP — cf. l'étape 0 bis, point 0e, de `.claude/skills/mep-precheck`.

POURQUOI : la synchronisation du manuel entre `docs/` et `front/static/` était une
simple case à cocher dans la checklist avant commit. Elle a tenu jusqu'ici, mais une
case à cocher ne résiste pas à une session pressée : le manuel servi aux résidents
aurait divergé de la source sans que rien ne le signale. Les badges du README ont
connu la dérive inverse, réelle celle-là : le badge Python annonçait 3.10+ alors que
l'image de production tourne en 3.12 (corrigé le 26/07/2026).
"""

import pathlib
import re

_API_DIR = pathlib.Path(__file__).resolve().parents[1]
_RACINE = _API_DIR.parent

#: 🔴 UN SEUL manuel depuis le 02/09/2026 (#651). La « version 1 page » a été
#: supprimée sur arbitrage : *« le manuel utilisateur en 1 page est à supprimer ;
#: le manuel utilisateur suffit »*. Deux documents décrivant le même produit
#: divergent au premier écran qui change — et c'est le plus court, donc le moins
#: relu, qui restait en arrière.
_MANUELS = ("manuel-utilisateur.html",)


def test_manuels_synchronises_docs_et_static():
    """`docs/` est la source, `front/static/` la copie servie : identiques.

    Divergence → les résidents lisent une version périmée. Remédiation :
    `Copy-Item docs/<fichier> front/static/<fichier>` (ou `cp` sous Linux).
    """
    divergents = []
    for nom in _MANUELS:
        src = _RACINE / "docs" / nom
        pub = _RACINE / "front" / "static" / nom
        if not src.exists() or not pub.exists():
            divergents.append(f"{nom} : absent ({'docs' if not src.exists() else 'front/static'})")
            continue
        if src.read_bytes() != pub.read_bytes():
            divergents.append(
                f"{nom} : docs/ ({src.stat().st_size} o) != front/static/ ({pub.stat().st_size} o)"
            )
    assert not divergents, (
        "Manuel utilisateur désynchronisé — la version servie aux résidents diffère "
        "de la source :\n" + "\n".join(f"  {d}" for d in divergents)
    )


#: Le numéro du manuel s'écrit à DEUX endroits : le badge de l'en-tête et le pied
#: de page. La v2.50.0 a livré « Version 1.78 » en tête et « v1.76 » au pied, et
#: rien ne l'a vu (#1306) — la consigne de bumper les deux existait déjà.
_VERSION_BADGE = re.compile(r'class="topbar-badge">Version (\d+\.\d+)\b')
_VERSION_PIED = re.compile(r"Manuel utilisateur v(\d+\.\d+)\b")


def versions_du_manuel(html: str) -> tuple[list[str], list[str]]:
    """Les numéros lus dans le badge et dans le pied de page, dans cet ordre."""
    return _VERSION_BADGE.findall(html), _VERSION_PIED.findall(html)


def test_badge_et_pied_du_manuel_portent_la_meme_version():
    """Un numéro illisible échoue aussi : une liste vide n'est pas un accord."""
    for nom in _MANUELS:
        html = (_RACINE / "docs" / nom).read_text(encoding="utf-8")
        badge, pied = versions_du_manuel(html)
        assert len(badge) == 1 and len(pied) == 1, (
            f"{nom} : badge {badge}, pied {pied} — un numéro, et un seul, à chaque endroit"
        )
        assert badge == pied, (
            f"{nom} : le badge dit {badge[0]}, le pied de page {pied[0]} — bumper les deux"
        )


def test_badge_python_du_readme_suit_l_image_de_production():
    """Le badge Python du README doit refléter `api/Dockerfile`.

    Le badge annonçait « 3.10+ » alors que l'image est en 3.12 : une information
    d'installation fausse pour tout contributeur.
    """
    dockerfile = (_API_DIR / "Dockerfile").read_text(encoding="utf-8-sig")
    m = re.search(r"^FROM python:(\d+\.\d+)", dockerfile, re.MULTILINE)
    assert m, "version Python introuvable dans api/Dockerfile"
    version = m.group(1)

    readme = (_RACINE / "README.md").read_text(encoding="utf-8-sig")
    badge = re.search(r"badge/python-([0-9.+]+)-", readme)
    assert badge, "badge Python introuvable dans README.md"
    assert badge.group(1).rstrip("+") == version, (
        f"Badge Python du README = {badge.group(1)!r} mais l'image de production est "
        f"en {version} (api/Dockerfile)"
    )


def test_badge_node_du_readme_suit_la_ci():
    """Le badge Node doit refléter la version utilisée par la CI."""
    ci = (_RACINE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8-sig")
    m = re.search(r"node-version:\s*['\"]?(\d+)", ci)
    assert m, "node-version introuvable dans ci.yml"
    version = m.group(1)

    readme = (_RACINE / "README.md").read_text(encoding="utf-8-sig")
    badge = re.search(r"badge/node-(\d+)", readme)
    assert badge, "badge Node introuvable dans README.md"
    assert badge.group(1) == version, (
        f"Badge Node du README = {badge.group(1)} mais la CI utilise Node {version}"
    )


def test_readme_expose_un_badge_ci():
    """Un dépôt qui a une CI doit l'afficher : c'est le premier signal de santé."""
    readme = (_RACINE / "README.md").read_text(encoding="utf-8-sig")
    assert "workflows/ci.yml/badge.svg" in readme, "README.md n'expose pas le badge de la CI"


def test_ancrage_du_controle_p3_reste_valide():
    """Le contrôle P3 du post-check MEP repose sur le NOM du paquet front.

    P3 lit la version réellement servie dans le bundle public, en s'ancrant sur
    `"hostachy-front"` — Vite intègre `front/package.json` dans le chunk du layout
    `(app)`, et le nom précède immédiatement la version. Cet ancrage a été choisi
    parce qu'il survit à la minification, contrairement aux noms de variables.

    Renommer le paquet casserait P3 **en silence** : le contrôle rendrait
    « INCONNU » à chaque MEP, et personne ne saurait que c'est l'ancrage, pas le
    déploiement, qui est en cause. Corollaire de la règle 1 du pré-check — un
    contrôle qui ne peut plus mesurer doit être réparé, pas subi.

    L'ancienne commande P3 (`curl / | grep`) ne pouvait pas fonctionner du tout :
    la racine redirige vers /auth/connexion. Corrigé le 03/08/2026.
    """
    import json

    nom = json.loads((_RACINE / "front" / "package.json").read_text(encoding="utf-8"))["name"]
    skill = (_RACINE / ".claude" / "skills" / "mep-precheck" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert f'"{nom}"' in skill, (
        f"Le paquet front s'appelle « {nom} », mais le contrôle P3 de "
        "mep-precheck/SKILL.md s'ancre sur un autre nom : il rendra INCONNU à "
        "chaque MEP. Mettre l'ancrage à jour."
    )
    # Le contrôle doit rester capable de dire qu'il n'a pas pu mesurer.
    assert "INCONNU" in skill, "P3 ne prévoit plus de sortie INCONNU"


#: Les nombres qu'une consigne écrit en lettres devant une liste.
_NOMBRES_EN_LETTRES = {"deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6}


def _etape_0_bis(skill: str) -> tuple[int | None, list[str]]:
    """Le compte annoncé par l'étape 0 bis, et les lignes de son tableau."""
    m = re.search(r"^## Étape 0 bis.*?(?=^## )", skill, re.MULTILINE | re.DOTALL)
    assert m, "section « Étape 0 bis » introuvable dans mep-precheck/SKILL.md"
    section = m.group(0)
    annonce = re.search(r"\*\*(\w+)\*\* exigences", section)
    compte = _NOMBRES_EN_LETTRES.get(annonce.group(1).lower()) if annonce else None
    lignes = re.findall(r"^\| (0[a-z]) \| \*\*([^*|—]+)", section, re.MULTILINE)
    return compte, [f"{code} {nom.split(',')[0].strip()}" for code, nom in lignes]


def test_etape_0_bis_annonce_autant_d_exigences_qu_elle_en_tabule():
    """Le nombre écrit en tête de l'étape 0 bis = les lignes de son tableau (#122).

    Il a divergé DEUX fois : « deux » au-dessus d'un tableau de trois, corrigé le
    21/09/2026, puis revenu dans la copie du même tableau que portait la fin du
    fichier (v2.19.0). Un audit de doublons par date et chiffre ne le voyait pas.
    """
    skill = (_RACINE / ".claude" / "skills" / "mep-precheck" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    compte, lignes = _etape_0_bis(skill)
    assert compte is not None, (
        "l'étape 0 bis n'annonce plus son nombre d'exigences en « **N** exigences »"
    )
    assert compte == len(lignes), (
        f"L'étape 0 bis annonce {compte} exigences mais en tabule {len(lignes)} ({', '.join(lignes)})."
    )


def test_etape_0_bis_n_est_tabulee_qu_une_fois():
    """Les exigences 0c–0e ne s'écrivent qu'au tableau de l'étape 0 bis (#122).

    La seconde copie, en fin de fichier, portait d'autres outils dans sa colonne
    « Automatisé par » et un autre compte en titre : deux tableaux pour une liste.
    """
    skill = (_RACINE / ".claude" / "skills" / "mep-precheck" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    _, lignes = _etape_0_bis(skill)
    assert lignes, "le tableau de l'étape 0 bis est vide ou illisible"
    for ligne in lignes:
        code, nom = ligne.split(" ", 1)
        # Le code seul ne suffit pas : les points 0a–0d du script réemploient
        # « 0c » et « 0d » pour autre chose. C'est l'exigence qui ne se recopie pas.
        n = len(re.findall(rf"^\| {code} \| \*\*{re.escape(nom)}", skill, re.MULTILINE))
        assert n == 1, (
            f"l'exigence « {ligne} » est tabulée {n} fois dans mep-precheck/SKILL.md — un seul tableau"
        )


def test_blame_ignore_revs_ne_nomme_que_des_commits_de_l_historique():
    """`.git-blame-ignore-revs` : SHA complets, et présents dans l'historique.

    Le premier candidat (`d665b62`, `ruff format` sur api/, #1261) n'existait déjà
    plus quand on a voulu l'y ajouter : la MEP l'avait squashé dans v2.49.0 avec
    d'autres lots, puis `dev` avait été réaligné sur `main`. Un SHA absent de
    l'historique n'ignore rien — et le fichier laisserait croire le contraire.
    Règle d'entrée : `mep-precheck`, piège 4.

    L'appartenance ne se vérifie que sur un clone COMPLET : la CI clone en
    profondeur 1. Le test le dit alors (skip motivé), il ne conclut pas au vert.
    """
    import subprocess

    fichier = _RACINE / ".git-blame-ignore-revs"
    assert fichier.exists(), (
        "`.git-blame-ignore-revs` a disparu — setup.sh et CONTRIBUTING.md l'arment"
    )
    shas = [
        ligne.strip()
        for ligne in fichier.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.lstrip().startswith("#")
    ]
    mal_formes = [s for s in shas if not re.fullmatch(r"[0-9a-f]{40}", s)]
    assert not mal_formes, f"SHA complets (40 caractères) exigés : {mal_formes}"
    if not shas:
        return

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(_RACINE), *args], capture_output=True, text=True)

    peu_profond = git("rev-parse", "--is-shallow-repository")
    if peu_profond.returncode != 0 or peu_profond.stdout.strip() != "false":
        import pytest

        pytest.skip(
            "INCONNU : clone partiel ou sans git — l'appartenance à l'historique n'est pas mesurable ici"
        )
    absents = [s for s in shas if git("merge-base", "--is-ancestor", s, "HEAD").returncode != 0]
    assert not absents, (
        f"Ces commits ne sont pas dans l'historique de HEAD : {absents}. "
        "Un reformatage squashé avec d'autres lots n'a plus de SHA propre (mep-precheck, piège 4)."
    )
