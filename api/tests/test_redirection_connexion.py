"""Garde-fou préventif : un lien partagé doit survivre à l'écran de connexion.

POURQUOI (26/07/2026) : `https://5hostachy.fr/actualites#pub-22` envoyé à un résident
sans session ouverte l'amenait sur l'écran de connexion, puis — une fois connecté —
sur le tableau de bord. Le lien reçu était perdu, à lui de retrouver l'actualité. Le
problème s'aggravait avec les ancres ajoutées en v2.25.0 : plus un lien est précis,
plus le perdre coûte cher.

Ces contrôles sont volontairement mécaniques : ils vérifient le CÂBLAGE, qui est ce
qui se défait en silence (un `goto('/tableau-de-bord')` remis en dur au détour d'une
modification, et la destination retombe dans l'oubli sans qu'aucun test ne bronche).
La protection contre l'« open redirect » est vérifiée ici sur le code source, faute
de lanceur de tests JavaScript dans le projet (cf. `front/scripts/check-dates.mjs`,
même contrainte).
"""
import pathlib

import pytest

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_FRONT = _RACINE / "front" / "src"
_MODULE = _FRONT / "lib" / "redirection.ts"
_GARDE = _FRONT / "routes" / "(app)" / "+layout.svelte"
_CONNEXION = _FRONT / "routes" / "auth" / "connexion" / "+page.svelte"

pytestmark = pytest.mark.skipif(not _FRONT.is_dir(), reason="front/ absent de ce checkout")


def _lire(chemin: pathlib.Path) -> str:
    assert chemin.exists(), f"{chemin.relative_to(_RACINE)} est introuvable"
    return chemin.read_text(encoding="utf-8-sig")


def test_la_garde_d_authentification_emporte_la_page_demandee():
    """Rediriger vers `/auth/connexion` nu, c'est perdre la destination."""
    garde = _lire(_GARDE)
    assert "urlDeConnexion(" in garde, (
        "front/src/routes/(app)/+layout.svelte doit rediriger via `urlDeConnexion()` "
        "pour conserver la page demandée (fragment compris)."
    )
    assert "goto('/auth/connexion')" not in garde, (
        "redirection en dur vers /auth/connexion : la destination initiale est perdue."
    )


def test_l_ecran_de_connexion_revient_sur_la_destination():
    """Après connexion, retour sur la cible — pas systématiquement le tableau de bord."""
    connexion = _lire(_CONNEXION)
    assert "destinationApresConnexion()" in connexion, (
        "front/src/routes/auth/connexion/+page.svelte doit utiliser "
        "`destinationApresConnexion()` après une connexion réussie."
    )
    assert "goto('/tableau-de-bord')" not in connexion, (
        "destination en dur après connexion : le `?next=` du lien partagé est ignoré."
    )


def test_la_destination_ne_peut_pas_pointer_hors_du_site():
    """`?next=` non filtré = écran de connexion transformé en tremplin (open redirect).

    Les trois pièges à couvrir : `//exemple.fr` et `/\\exemple.fr`, que les navigateurs
    résolvent en URL absolue malgré le `/` initial, et une cible `/auth/…` qui
    boucle sur l'écran de connexion.
    """
    module = _lire(_MODULE)
    assert "estCibleInterne" in module, "la validation de la cible a disparu"
    assert r"/^\/(?![/\\])/" in module, (
        "le filtre des cibles doit refuser `//` et `/\\` (URL absolues déguisées) — "
        "sans quoi la page de connexion redirige vers n'importe quel site."
    )
    assert "'/auth/'" in module, "une cible /auth/… boucle : elle doit être refusée"
    for appelant in (_GARDE, _CONNEXION):
        assert "$lib/redirection" in _lire(appelant), (
            f"{appelant.name} n'utilise plus le module de redirection commun"
        )
