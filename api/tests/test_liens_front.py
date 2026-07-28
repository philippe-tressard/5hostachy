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

MISE À JOUR (28/07/2026) : les liens vers un élément précis ne sont plus des f-strings
éparpillées, ils sortent tous de la table `EMPLACEMENTS` (`app/utils/liens.py`). Ce
fichier vérifie donc la table elle-même, ligne par ligne — page, onglet, ancre — en
plus des liens encore écrits à la main. Il gagne au passage le contrôle qui manquait :
**l'ancre doit être rendue par l'onglet que le lien sélectionne**. C'est précisément ce
qui a échappé aux trois tests précédents avec `/prestataires#presta-23` : la page
existait, l'ancre existait, aucun `?onglet=` n'était présent — donc rien à valider — et
la fiche restait invisible derrière l'onglet « Prestations ponctuelles ».
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


def _liens_de_la_table() -> dict[str, list[str]]:
    """{lien: [source]} pour chaque ligne de `EMPLACEMENTS`, avec un id d'exemple."""
    from app.utils.liens import EMPLACEMENTS, lien_element

    return {
        lien_element(prefixe, 1): ["api/app/utils/liens.py (EMPLACEMENTS)"]
        for prefixe in EMPLACEMENTS
    }


def _liens_de_l_api() -> dict[str, list[str]]:
    """{lien: [fichiers qui l'émettent]} — table centrale + littéraux restants."""
    trouves: dict[str, list[str]] = {k: list(v) for k, v in _liens_de_la_table().items()}
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


def page_element(prefixe: str) -> str:
    """Raccourci de lecture vers la table centrale."""
    from app.utils.liens import EMPLACEMENTS

    return EMPLACEMENTS[prefixe][0]


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


# Les pages à onglets branchent leur contenu sur `onglet === '…'` ou `activeTab === '…'`.
_MOTIF_BRANCHE_ONGLET = re.compile(r"(?:onglet|activeTab)\s*===\s*'([\w]+)'")


def _segments_par_onglet(contenu: str) -> dict[str, str]:
    """{onglet: portion(s) du fichier rendue(s) sous cet onglet}.

    Découpage volontairement grossier : chaque marqueur `onglet === 'x'` ouvre une
    portion qui court jusqu'au marqueur suivant. Une page déclare plusieurs fois le
    même onglet (bouton d'en-tête, onglet de la barre, bloc de contenu) → on
    concatène toutes ses portions. Suffisant pour répondre à la seule question
    posée : « cet onglet rend-il, quelque part, un `id="prefixe-…"` ? »
    """
    marqueurs = list(_MOTIF_BRANCHE_ONGLET.finditer(contenu))
    segments: dict[str, str] = {}
    for i, m in enumerate(marqueurs):
        fin = marqueurs[i + 1].start() if i + 1 < len(marqueurs) else len(contenu)
        segments[m.group(1)] = segments.get(m.group(1), "") + contenu[m.start():fin]
    return segments


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_l_ancre_est_rendue_par_l_onglet_que_le_lien_selectionne():
    """Le contrôle manquant : viser la bonne page ET le bon onglet.

    `/prestataires#presta-23` (28/07/2026) passait les trois tests précédents — page
    existante, ancre existante, aucun `?onglet=` à valider — et déposait pourtant
    l'utilisateur sur « Prestations ponctuelles », où aucun élément ne porte cet id.
    L'ancre ne désignait rien de rendu : le navigateur restait immobile, la fiche
    introuvable.

    Ici on relie les deux : pour chaque ligne de `EMPLACEMENTS`, l'onglet déclaré doit
    être celui dont le balisage produit réellement l'ancre.
    """
    from app.utils.liens import EMPLACEMENTS, lien_element

    ecarts = []
    for prefixe, (page, onglet) in sorted(EMPLACEMENTS.items()):
        fichier = _page_du_lien(page)
        if fichier is None:
            continue  # déjà couvert par le test des pages
        contenu = fichier.read_text(encoding="utf-8-sig")
        segments = _segments_par_onglet(contenu)
        ancre = f'id="{prefixe}-'

        if onglet is None:
            # Page sans onglets : l'ancre doit exister, et la page ne doit pas être
            # devenue une page à onglets sans que la table le sache.
            if segments and ancre in contenu:
                ecarts.append(
                    f"  {prefixe} → {page} : la page a désormais des onglets "
                    f"({', '.join(sorted(segments))}) mais EMPLACEMENTS n'en déclare "
                    f"aucun — le lien s'ouvrira sur l'onglet par défaut"
                )
            continue

        if onglet not in segments:
            ecarts.append(
                f"  {prefixe} → {lien_element(prefixe, 1)} : "
                f"{fichier.relative_to(_RACINE)} ne connaît pas l'onglet '{onglet}' "
                f"(onglets trouvés : {', '.join(sorted(segments)) or 'aucun'})"
            )
        elif ancre not in segments[onglet]:
            rendu_par = [o for o, seg in segments.items() if ancre in seg]
            ecarts.append(
                f"  {prefixe} → {lien_element(prefixe, 1)} : l'onglet '{onglet}' ne "
                f"rend aucun {ancre}…\" — "
                + (f"c'est l'onglet '{rendu_par[0]}' qui le rend"
                   if rendu_par else "aucun onglet ne le rend")
            )

    assert not ecarts, (
        "Ces liens ouvrent la bonne page mais un onglet où l'élément visé n'existe "
        "pas — l'utilisateur arrive et ne voit rien :\n" + "\n".join(ecarts)
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
        # L'onglet fait partie du lien : /prestataires s'ouvre sur « Prestations
        # ponctuelles », la fiche vit sous « Prestataires ».
        (_faux_document(contrat_id=9), cs, "/prestataires?onglet=prestataires#presta-7"),
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
def test_les_categories_de_documents_du_fil_mènent_quelque_part():
    """Les catégories que le fil accepte de lier doivent aboutir sur une page réelle.

    C'est le remplacement de `/documents` : les documents liables (plans, règlement,
    PV d'AG) s'affichent tous dans /residence, page et onglet décidés une seule fois
    par `EMPLACEMENTS["doc"]`. Les catégories absentes de cet ensemble ne sont
    affichées nulle part et ne reçoivent AUCUN lien — c'est délibéré, pas un oubli.
    """
    from app.routers.flux import _CATEGORIES_DOCUMENT_AVEC_LIEN

    assert _CATEGORIES_DOCUMENT_AVEC_LIEN, "aucune catégorie de document n'est liable"
    assert _page_existe(page_element("doc")), (
        f"le fil renverrait les documents vers {page_element('doc')}, page inexistante"
    )
