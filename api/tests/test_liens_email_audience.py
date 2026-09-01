"""Un lien d'e-mail qui MÈNE quelque part peut rester MORT pour son destinataire.

`test_liens_front.py` relie les deux moitiés d'un lien : l'API l'émet, le front
doit avoir la page. Ce fichier-ci pose la question d'après, et c'est une autre
question — d'où un fichier à part plutôt que soixante lignes de plus là-bas :

> la page existe, mais celui qui REÇOIT le message peut-il l'ouvrir ?

Un modèle d'e-mail ne connaît pas ses destinataires : ils sont choisis au point
d'appel, et le même modèle sert souvent plusieurs audiences.
"""
import pathlib
import re

import pytest

_API_DIR = pathlib.Path(__file__).resolve().parents[1]
_RACINE = _API_DIR.parent
_ROUTES = _RACINE / "front" / "src" / "routes"


# ── Un lien qui MÈNE quelque part peut rester MORT pour son destinataire ──────
#
# POURQUOI (01/09/2026, #480) : le modèle d'e-mail `annonce_hall` finissait par un
# bouton « Voir l'historique des annonces » vers `/espace-cs?onglet=annonces-hall`.
# La page existe — les tests ci-dessus étaient donc verts — mais le front y pose une
# garde : `if (!$isCS) goto('/tableau-de-bord')`. Tant que ce courriel n'allait qu'au
# conseil syndical, personne ne pouvait le voir. En ouvrant le canal « syndic », le
# même bouton s'est mis à renvoyer la moitié de ses destinataires au tableau de bord.
#
# La leçon est celle des liens front⇄API, d'un cran plus loin : vérifier que la page
# existe ne suffit pas, il faut que le DESTINATAIRE puisse l'ouvrir. Et c'est
# précisément ce qu'un e-mail ne peut pas savoir : il part à une liste, la garde
# s'applique à chacun.

_MOTIF_HREF_MODELE = re.compile(r"""href=["']\{\{ app\.url \}\}(/[^"'{]*)""")

#: Routes que le front REFUSE à qui n'a pas le rôle, en redirigeant ailleurs.
#: Détectées, pas recopiées — une liste tenue à la main se périmerait à la
#: première garde ajoutée, et c'est le lien nouvellement mort qu'on cherche.
_MOTIF_GARDE = re.compile(r"if\s*\(!\$is[A-Za-z]+\)\s*\{?\s*(?:\r?\n\s*)?goto\(")


def _routes_gardees() -> set[str]:
    """{'/espace-cs', …} — les pages qui redirigent qui n'a pas le rôle."""
    gardees: set[str] = set()
    for page in _ROUTES.rglob("+page.svelte"):
        if not _MOTIF_GARDE.search(page.read_text(encoding="utf-8-sig")):
            continue
        # `(app)/espace-cs/+page.svelte` → `/espace-cs` : les groupes SvelteKit
        # sont transparents dans l'URL, comme dans `_resoudre` plus haut.
        segments = [
            s for s in page.relative_to(_ROUTES).parent.parts
            if not (s.startswith("(") and s.endswith(")"))
        ]
        gardees.add("/" + "/".join(segments))
    return gardees


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_aucun_modele_email_ne_vise_une_route_reservee():
    """Un bouton d'e-mail doit s'ouvrir pour TOUS ceux qui reçoivent le message.

    Un modèle d'e-mail ne connaît pas ses destinataires — ils sont choisis au point
    d'appel, et le même modèle sert souvent plusieurs audiences (le CS et le syndic
    pour l'annonce de hall). Viser une page réservée à l'une d'elles est donc un
    défaut par construction, pas un cas particulier à arbitrer.

    Le remède appliqué à `annonce_hall` : pointer l'OBJET (l'actualité d'origine),
    et n'afficher le bouton que lorsqu'il y en a un. Un lien vers un objet vaut pour
    tout le monde ; un lien vers un écran d'administration ne vaut que pour ses
    administrateurs.
    """
    gardees = _routes_gardees()
    assert gardees, (
        "aucune garde de rôle détectée dans front/src/routes — le motif a dû "
        "changer de forme, et ce test ne mesure plus rien (INCONNU, pas OK)"
    )

    fautifs: list[str] = []
    dossier = _API_DIR / "app" / "seed" / "emails"
    for chemin in sorted(dossier.glob("*.py")):
        for lien in _MOTIF_HREF_MODELE.findall(chemin.read_text(encoding="utf-8-sig")):
            base = lien.split("?")[0].split("#")[0].rstrip("/")
            if base in gardees:
                fautifs.append(f"{chemin.relative_to(_RACINE)} → {lien}")

    assert not fautifs, (
        "modèle(s) d'e-mail visant une page que le front réserve à un rôle — "
        "leurs destinataires sans ce rôle seront redirigés :\n  "
        + "\n  ".join(fautifs)
    )
