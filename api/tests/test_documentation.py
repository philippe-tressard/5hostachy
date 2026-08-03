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

_MANUELS = ("manuel-utilisateur.html", "manuel-utilisateur-1-page.html")


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
    assert "workflows/ci.yml/badge.svg" in readme, (
        "README.md n'expose pas le badge de la CI"
    )


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
    skill = (_RACINE / ".claude" / "skills" / "mep-precheck" / "SKILL.md").read_text(encoding="utf-8")

    assert f'"{nom}"' in skill, (
        f"Le paquet front s'appelle « {nom} », mais le contrôle P3 de "
        "mep-precheck/SKILL.md s'ancre sur un autre nom : il rendra INCONNU à "
        "chaque MEP. Mettre l'ancrage à jour."
    )
    # Le contrôle doit rester capable de dire qu'il n'a pas pu mesurer.
    assert "INCONNU" in skill, "P3 ne prévoit plus de sortie INCONNU"
