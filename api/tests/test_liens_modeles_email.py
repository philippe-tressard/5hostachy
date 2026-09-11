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
| le chemin **existe côté front** | le défaut de 2026-07 (`/documents`), qui n'a jamais existé |
| pas de **domaine en dur** | une adresse figée survit au changement de nom de domaine, et pointe alors chez quelqu'un d'autre |

⚠️ Une variable de lien (`{{ reponse.lien }}`) est **déclarée** avec l'endroit qui
la remplit. Le test ne peut pas la suivre tout seul — mais il peut exiger qu'elle
soit nommée, et qu'à cet endroit-là une URL absolue soit construite. Une variable
non déclarée échoue : c'est la seule façon d'empêcher qu'un futur modèle emporte
un chemin nu sans que personne le voie.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from tests.aides_routes_front import _page_existe

SEED = pathlib.Path(__file__).resolve().parents[1] / "app" / "seed" / "emails"
APP = pathlib.Path(__file__).resolve().parents[1] / "app"

HREF = re.compile(r'href="([^"]*)"')

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

#: Les chemins littéraux qu'on ne peut pas confronter au front tels quels, avec
#: leur motif. `?onglet=` n'est PAS une forme périmée pour `/admin` : ses onglets
#: n'ont pas de route dédiée (vérifié en production le 11/09/2026 —
#: `/admin/import_tc` rend 404, `/admin?onglet=import_tc` rend 200).
CHEMINS_TOLERES = {
    "/admin?onglet=import_tc": "les onglets d'administration n'ont pas de route dédiée",
    "/admin?onglet=audit_lots": "idem",
}


def _liens_des_modeles() -> list[tuple[str, str]]:
    """Tous les `href` des modèles, avec le fichier qui les porte."""
    trouves = []
    for f in sorted(SEED.glob("*.py")):
        for lien in HREF.findall(f.read_text(encoding="utf-8")):
            trouves.append((f.name, lien.strip()))
    return trouves


def test_il_y_a_bien_des_liens_a_verifier():
    """⚠️ Le cas zéro (`standards/04` §2). Si l'extraction cesse de fonctionner —
    les modèles déplacés, le HTML réécrit autrement —, tous les contrôles de ce
    fichier passeraient au vert en ne mesurant rien."""
    liens = _liens_des_modeles()
    assert len(liens) >= 15, f"seulement {len(liens)} lien(s) extraits — l'extraction est cassée"


@pytest.mark.parametrize("fichier, lien", _liens_des_modeles())
def test_chaque_lien_de_modele_est_absolu(fichier, lien):
    """Un chemin nu dans un e-mail n'ouvre rien : il n'y a pas de page courante."""
    if lien.startswith("mailto:"):
        return
    if lien.startswith(BASE):
        return
    assert lien in VARIABLES_ABSOLUES, (
        f"{fichier} : « {lien} » n'est ni préfixé par `{BASE}` ni déclaré dans "
        "VARIABLES_ABSOLUES avec le fichier qui le remplit"
    )


@pytest.mark.parametrize("fichier, lien", _liens_des_modeles())
def test_aucun_lien_ne_porte_de_double_barre(fichier, lien):
    """Le défaut signalé : `{{ app.url }}` vaut déjà `https://…` sans barre
    finale (`utils/liens.base_site`) ; en écrire une seconde ici la ramènerait."""
    apres = lien[len(BASE) :] if lien.startswith(BASE) else lien
    assert not apres.startswith("//"), f"{fichier} : « {lien} » — double barre"
    assert "//" not in apres, f"{fichier} : « {lien} » — double barre dans le chemin"


@pytest.mark.parametrize("fichier, lien", _liens_des_modeles())
def test_aucun_domaine_ecrit_en_dur(fichier, lien):
    """Une adresse figée survit au changement de nom de domaine, et pointe alors
    chez quelqu'un d'autre — un e-mail déjà parti ne se corrige pas."""
    if lien.startswith("mailto:"):
        return
    assert not re.match(r"https?://", lien), (
        f"{fichier} : « {lien} » écrit un domaine en dur — employer `{BASE}`"
    )


def test_chaque_chemin_litteral_existe_cote_front():
    """Le défaut de juillet 2026 : `/documents`, une route qui n'a jamais existé,
    et un 404 en pleine page signalé depuis un PV d'AG."""
    manquants = []
    for fichier, lien in _liens_des_modeles():
        if not lien.startswith(BASE):
            continue
        chemin = lien[len(BASE) :]
        if not chemin or chemin in CHEMINS_TOLERES:
            continue
        #  Un chemin qui porte une variable Jinja ne se confronte pas tel quel :
        #  c'est `test_liens_front.py` qui vérifie ce que le code y met.
        if "{{" in chemin:
            continue
        sans_ancre = chemin.split("#", 1)[0].split("?", 1)[0]
        if not _page_existe(sans_ancre):
            manquants.append(f"{fichier} : {chemin}")
    assert not manquants, "Chemin servi par aucune page du front :\n  " + "\n  ".join(manquants)


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


def test_les_tolerances_de_chemin_servent_TOUTES():
    """Une tolérance reconduite « au cas où » masque la prochaine vraie erreur."""
    ecrits = {lien[len(BASE) :] for _, lien in _liens_des_modeles() if lien.startswith(BASE)}
    inutiles = [c for c in CHEMINS_TOLERES if c not in ecrits]
    assert not inutiles, "Tolérances périmées : " + ", ".join(inutiles)
