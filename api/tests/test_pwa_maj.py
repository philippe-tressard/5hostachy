"""Garde-fou préventif : le client doit apprendre qu'une nouvelle version existe.

POURQUOI (26/07/2026) : le front est une PWA dont le service worker met l'app shell
en cache et ne cherche une mise à jour qu'au chargement de la page. Un onglet resté
ouvert sert donc indéfiniment la version qu'il a chargée. Le jour de la MEP v2.23.0
— un correctif de sécurité — le footer d'un onglet ouvert annonçait encore
`v2.22.8-050e91c` une heure après le déploiement : ce n'était pas un affichage
trompeur, c'était l'ancien code qui tournait toujours.

Trois pièces rendent ce cas visible et corrigeable, et aucune n'est visible sans
rouvrir le fichier concerné — donc chacune est testée ici plutôt que confiée à une
consigne :

1. le service worker attend au lieu de prendre la main (sinon la page se recharge
   d'elle-même, formulaire en cours compris) ;
2. le bandeau est monté dans le layout racine (sinon personne n'est averti) ;
3. un contrôle périodique interroge le serveur (sinon l'onglet ouvert ne cherche
   jamais, et 1 et 2 ne se déclenchent pas).

Le test lit `front/` depuis `api/tests/` comme le fait déjà `test_documentation.py` :
la CI n'exécute pytest qu'ici, et un contrôle sans exécution est un contrôle absent.
"""
import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_VITE_CONFIG = _RACINE / "front" / "vite.config.ts"
_LAYOUT_RACINE = _RACINE / "front" / "src" / "routes" / "+layout.svelte"
_COMPOSANT = _RACINE / "front" / "src" / "lib" / "components" / "MajDisponible.svelte"


def _lire(chemin: pathlib.Path) -> str:
    assert chemin.exists(), f"{chemin.relative_to(_RACINE)} est introuvable"
    return chemin.read_text(encoding="utf-8-sig")


def test_le_service_worker_attend_au_lieu_de_recharger_seul():
    """`registerType: 'prompt'` — jamais `autoUpdate`.

    En `autoUpdate`, workbox pose `skipWaiting` + `clientsClaim` : la page se
    recharge sans prévenir dès qu'une version est trouvée, et une saisie en cours
    est perdue. Le rechargement doit rester une décision de l'utilisateur.
    """
    config = _lire(_VITE_CONFIG)
    assert re.search(r"registerType:\s*'prompt'", config), (
        "vite.config.ts : `registerType` doit valoir 'prompt' — en 'autoUpdate' le "
        "rechargement est imposé à l'utilisateur, formulaire en cours compris."
    )


def test_le_service_worker_est_enregistre_en_url_absolue():
    """`base` et `scope` explicites — sinon l'enregistrement échoue hors racine.

    Sans eux, `vite-plugin-pwa` hérite du `base` de Vite (vide sous SvelteKit) et
    génère `new Workbox('./sw.js', { scope: './' })` : depuis `/auth/connexion`, le
    navigateur demande `/auth/sw.js` et reçoit un 404. Constaté en production le
    26/07/2026 (v2.24.0) — plus aucun service worker enregistré, en silence.

    Le contrôle décisif porte sur le bundle construit (`npm run lint:sw`) ; celui-ci
    vérifie qu'il est toujours branché dans la CI et que l'intention reste écrite.
    """
    config = _lire(_VITE_CONFIG)
    assert re.search(r"base:\s*'/'", config) and re.search(r"scope:\s*'/'", config), (
        "vite.config.ts : VitePWA doit fixer `base: '/'` et `scope: '/'`, sinon "
        "l'enregistrement du service worker échoue en 404 hors de la racine."
    )
    ci = _lire(_RACINE / ".github" / "workflows" / "ci.yml")
    assert "lint:sw" in ci, (
        "ci.yml n'exécute plus `npm run lint:sw` : le seul contrôle qui inspecte "
        "l'artefact livré est débranché."
    )


def test_le_bandeau_de_mise_a_jour_est_monte_dans_le_layout_racine():
    """Monté à la racine : le bandeau doit couvrir aussi l'écran de connexion.

    Placé dans `(app)/+layout.svelte`, il ne s'afficherait que pour les pages
    authentifiées — or une version périmée l'est pour tout le monde.
    """
    layout = _lire(_LAYOUT_RACINE)
    assert "MajDisponible" in layout, (
        "front/src/routes/+layout.svelte ne monte pas <MajDisponible /> : plus rien "
        "n'avertit l'utilisateur qu'une nouvelle version est déployée."
    )
    _lire(_COMPOSANT)  # le composant lui-même doit exister


def test_une_verification_periodique_cherche_les_nouvelles_versions():
    """Sans contrôle actif, un onglet ouvert ne découvre jamais la mise à jour.

    C'est exactement le cas constaté : l'onglet ne redemandait rien au serveur, donc
    ni le service worker ni le bandeau n'avaient de raison de se déclencher.
    """
    composant = _lire(_COMPOSANT)
    assert "setInterval" in composant and "registration.update()" in composant, (
        "MajDisponible.svelte ne contrôle plus périodiquement l'arrivée d'une "
        "nouvelle version (setInterval + registration.update())."
    )
    assert "visibilitychange" in composant, (
        "MajDisponible.svelte ne contrôle plus au retour sur l'onglet — c'est le cas "
        "principal : un onglet laissé ouvert en arrière-plan toute la nuit."
    )
    assert "onNeedRefresh" in composant, (
        "MajDisponible.svelte n'écoute plus `onNeedRefresh` : le bandeau ne "
        "s'afficherait jamais."
    )
