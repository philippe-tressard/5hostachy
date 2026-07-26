"""Garde-fou préventif : tout lien fabriqué par l'API doit exister côté front.

POURQUOI (26/07/2026) : le fil d'activité du tableau de bord renvoyait vers
`/documents` pour un nouveau document (« Voir → ») et pour un diagnostic. Cette route
n'a **jamais existé** dans `front/src/routes/` — il n'y a pas de page « tous les
documents », chaque document s'affiche là où il est rattaché. Résultat : un **404**
en pleine page, signalé par l'utilisateur depuis un PV d'AG.

Rien ne pouvait l'attraper : côté API c'est une chaîne de caractères, côté front une
route absente, et les deux moitiés ne se rencontrent qu'au clic. Les notifications
fabriquent des liens de la même façon (`lien=`, `lien_path=`) dans une dizaine de
routers — la même faute de frappe y produirait le même 404, dans un e-mail cette fois.

Ce test relie les deux moitiés : il extrait tous les liens émis par l'API et vérifie
qu'une page les sert réellement, en tenant compte des groupes SvelteKit — `(app)` est
transparent dans l'URL — et des segments dynamiques (`/tickets/{id}` → `[id]`).
"""
import pathlib
import re

import pytest

_API_DIR = pathlib.Path(__file__).resolve().parents[1]
_RACINE = _API_DIR.parent
_ROUTES = _RACINE / "front" / "src" / "routes"

# `lien="/x"`, `lien=f"/x/{y}"`, `lien_path="/x"` — les liens vers le front.
_MOTIF_LIEN = re.compile(r"""lien(?:_path)?\s*=\s*f?["'](/[^"']*)["']""")


def _liens_de_l_api() -> dict[str, list[str]]:
    """{lien: [fichiers qui l'émettent]} sur tout `api/app/`."""
    trouves: dict[str, list[str]] = {}
    for chemin in sorted((_API_DIR / "app").rglob("*.py")):
        for lien in _MOTIF_LIEN.findall(chemin.read_text(encoding="utf-8-sig")):
            trouves.setdefault(lien, []).append(str(chemin.relative_to(_RACINE)))
    return trouves


def _resoudre(base: pathlib.Path, segments: list[str]) -> bool:
    """Une page SvelteKit sert-elle ce chemin depuis `base` ?"""
    if not segments:
        return (base / "+page.svelte").exists()

    seg, reste = segments[0], segments[1:]
    if not base.is_dir():
        return False
    sous_dossiers = [d for d in base.iterdir() if d.is_dir()]

    # Les groupes `(app)`, `(marketing)`… n'apparaissent pas dans l'URL : on traverse.
    for groupe in (d for d in sous_dossiers if d.name.startswith("(")):
        if _resoudre(groupe, segments):
            return True

    if seg.startswith("{"):  # segment dynamique d'une f-string → `[id]`, `[slug]`…
        candidats = [d for d in sous_dossiers if d.name.startswith("[")]
    else:
        candidats = [d for d in sous_dossiers if d.name == seg]

    return any(_resoudre(c, reste) for c in candidats)


def _page_existe(lien: str) -> bool:
    chemin = lien.split("#")[0].split("?")[0]
    segments = [s for s in chemin.strip("/").split("/") if s]
    return _resoudre(_ROUTES, segments)


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_tous_les_liens_emis_par_l_api_existent_cote_front():
    """Un lien vers une route inexistante = 404 pour l'utilisateur, sans autre signal."""
    casses = []
    for lien, fichiers in sorted(_liens_de_l_api().items()):
        if not _page_existe(lien):
            casses.append(f"  {lien}  ← {', '.join(sorted(set(fichiers)))}")

    assert not casses, (
        "Ces liens émis par l'API ne correspondent à aucune page du front — "
        "l'utilisateur qui clique reçoit un 404 :\n" + "\n".join(casses)
    )


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_les_pages_de_documents_du_fil_existent():
    """La table catégorie → page du fil d'activité doit pointer sur des pages réelles.

    C'est le remplacement de `/documents` : chaque catégorie exposée renvoie vers la
    page qui l'affiche vraiment (`/residence` pour les plans, le règlement et les PV
    d'AG). Les catégories absentes de la table ne sont affichées nulle part et ne
    reçoivent donc AUCUN lien — c'est délibéré, pas un oubli.
    """
    from app.routers.flux import _PAGE_PAR_CATEGORIE_DOCUMENT

    assert _PAGE_PAR_CATEGORIE_DOCUMENT, "la table des pages de documents est vide"
    casses = [
        f"  {code} → {page}"
        for code, page in sorted(_PAGE_PAR_CATEGORIE_DOCUMENT.items())
        if not _page_existe(page)
    ]
    assert not casses, (
        "Le fil d'activité renverrait vers des pages inexistantes :\n" + "\n".join(casses)
    )
