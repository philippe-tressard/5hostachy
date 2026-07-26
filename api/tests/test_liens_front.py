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
import types

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


def _page_du_lien(lien: str) -> pathlib.Path | None:
    """Fichier `+page.svelte` qui sert ce lien (pour inspecter ancres et onglets)."""
    segments = [s for s in lien.split("#")[0].split("?")[0].strip("/").split("/") if s]

    def descendre(base: pathlib.Path, restants: list[str]) -> pathlib.Path | None:
        if not restants:
            page = base / "+page.svelte"
            return page if page.exists() else None
        seg, suite = restants[0], restants[1:]
        if not base.is_dir():
            return None
        sous = [d for d in base.iterdir() if d.is_dir()]
        for groupe in (d for d in sous if d.name.startswith("(")):
            trouve = descendre(groupe, restants)
            if trouve:
                return trouve
        cibles = (
            [d for d in sous if d.name.startswith("[")]
            if seg.startswith("{")
            else [d for d in sous if d.name == seg]
        )
        for c in cibles:
            trouve = descendre(c, suite)
            if trouve:
                return trouve
        return None

    return descendre(_ROUTES, segments)


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_les_ancres_des_liens_sont_produites_par_la_page_visee():
    """`#doc-42` n'a de sens que si la page pose `id="doc-{…}"` sur ses éléments.

    Une ancre qui ne correspond à rien ne casse pas visiblement : le navigateur
    charge la page et ne bouge pas. L'utilisateur arrive en haut d'une longue liste
    et cherche lui-même — c'est ce que faisait « Voir l'annonce → », qui ouvrait la
    Communauté sur l'onglet Sondages (26/07/2026).
    """
    orphelines = []
    for lien, fichiers in sorted(_liens_de_l_api().items()):
        if "#" not in lien:
            continue
        ancre = lien.split("#", 1)[1]
        prefixe = ancre.split("-")[0]
        page = _page_du_lien(lien)
        if page is None:
            continue  # déjà couvert par le test précédent
        if f'id="{prefixe}-' not in page.read_text(encoding="utf-8-sig"):
            orphelines.append(
                f"  {lien}  ← {', '.join(sorted(set(fichiers)))}\n"
                f"      {page.relative_to(_RACINE)} ne pose aucun id=\"{prefixe}-…\""
            )

    assert not orphelines, (
        "Ces ancres ne correspondent à aucun élément de la page visée — le lien "
        "ouvre la bonne page mais ne montre pas l'élément :\n" + "\n".join(orphelines)
    )


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_les_onglets_des_liens_existent_dans_la_page_visee():
    """`?onglet=annonces` doit correspondre à un onglet réellement déclaré.

    Les pages à onglets listent leurs valeurs dans une constante `ONGLETS` (voir
    `$lib/deepLink.ts`) : c'est cette liste que le lien doit viser. Une valeur
    inconnue est ignorée en silence et l'utilisateur reste sur l'onglet par défaut,
    exactement le symptôme d'origine.
    """
    inconnus = []
    for lien, fichiers in sorted(_liens_de_l_api().items()):
        m = re.search(r"[?&]onglet=([^&#]+)", lien)
        if not m:
            continue
        onglet = m.group(1)
        page = _page_du_lien(lien)
        if page is None:
            continue
        contenu = page.read_text(encoding="utf-8-sig")
        declares = re.search(r"const ONGLETS = \[([^\]]+)\]", contenu)
        valeurs = re.findall(r"'([^']+)'", declares.group(1)) if declares else []
        if onglet not in valeurs:
            inconnus.append(
                f"  {lien}  ← {', '.join(sorted(set(fichiers)))}\n"
                f"      {page.relative_to(_RACINE)} déclare {valeurs or 'aucun onglet'}"
            )

    assert not inconnus, (
        "Ces liens visent un onglet qui n'existe pas : la page s'ouvrira sur son "
        "onglet par défaut, sans le contenu attendu :\n" + "\n".join(inconnus)
    )


class _FauxUser:
    def __init__(self, cs: bool):
        self._cs = cs

    def has_role(self, *_roles):
        return self._cs


class _FauxSession:
    """`session.get(ContratEntretien, id)` — seul appel fait par `_lien_document`."""

    def __init__(self, prestataire_id: int | None = 7):
        self._prestataire_id = prestataire_id

    def get(self, _modele, _id):
        return (
            types.SimpleNamespace(prestataire_id=self._prestataire_id)
            if self._prestataire_id is not None
            else None
        )


def _faux_document(**champs):
    base = dict(id=42, publication_id=None, contrat_id=None, categorie=None)
    base.update(champs)
    return types.SimpleNamespace(**base)


def test_chaque_document_pointe_vers_l_endroit_ou_il_est_affiche():
    """La table de correspondance, testée sans base : c'est elle qui a produit le 404.

    Chaque cas correspond à un endroit réel de l'interface — pièce jointe d'actualité,
    fiche prestataire, section de /residence — ou à l'absence assumée de lien quand la
    catégorie n'est affichée nulle part.
    """
    from app.routers.flux import _lien_document

    cs, resident = _FauxUser(cs=True), _FauxUser(cs=False)
    categorie = lambda code: types.SimpleNamespace(code=code)  # noqa: E731

    cas = [
        (_faux_document(publication_id=3), resident, "/actualites#pub-3"),
        (_faux_document(contrat_id=9), cs, "/prestataires#presta-7"),
        # Page réservée au CS/admin : un résident n'a rien à y faire, même s'il a le
        # droit de lire le document.
        (_faux_document(contrat_id=9), resident, None),
        (_faux_document(categorie=categorie("pv_ag")), resident, "/residence#doc-42"),
        (_faux_document(categorie=categorie("plan_residence")), resident, "/residence#doc-42"),
        # Catégorie affichée nulle part → aucun lien, délibérément.
        (_faux_document(categorie=categorie("fiche_synthetique")), resident, None),
        (_faux_document(), resident, None),
    ]
    for doc, user, attendu in cas:
        assert _lien_document(doc, user, _FauxSession()) == attendu, (
            f"document {doc} pour un {'CS' if user.has_role() else 'résident'}"
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
