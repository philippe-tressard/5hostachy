"""Le nom et l'adresse du site se lisent à UN endroit (18/09/2026, #779).

## Ce que ce contrôle protège

`config_site` lisait les clés `site_nom` / `site_url` depuis
`routers/tickets/commun.py` — chez un appelant, et dans le module d'un domaine
qui n'a rien à voir avec la configuration. Deux conséquences, toutes deux
observées :

- `main.py` l'importait **au milieu d'une fonction**, pour éviter le cycle que
  provoquerait un import de routeur depuis le démarrage ;
- **huit autres endroits** relisaient le couple eux-mêmes — `routers/auth.py`
  deux fois, `auth_mot_de_passe`, `documents`, `publications/courriels` deux
  fois, `health_monitor`, `annonces_hall` — et l'une de ces copies avait dérivé :
  elle rendait `""` là où l'originale rend `None`.

C'est `standards/02` §4 sexies : une règle rangée chez un appelant oblige le
suivant à un détour ou à une copie. Le corps vit désormais dans
`utils/config_site`, que personne n'a de raison d'éviter.

## 🔴 La portée est la NOTION, pas la table

Lire `ConfigSite` est banal : quinze modules le font pour les réglages SMTP,
WhatsApp ou LLM, et c'est leur droit. Ce qui s'écrit à un endroit est la lecture
du **couple** `site_nom` / `site_url` — le nom et l'adresse de la résidence, qui
alimentent chaque courriel et chaque document. Une portée qui viserait la table
crierait sur du légitime, et serait désarmée dans la semaine
(`standards/04` §40).
"""
from __future__ import annotations

import pathlib

RACINE = pathlib.Path(__file__).resolve().parents[1] / "app"
SOURCE = "utils/config_site.py"

#: Les deux clés qui, ENSEMBLE, désignent la lecture mutualisée.
COUPLE = ("site_nom", "site_url")


def _fichiers() -> list[pathlib.Path]:
    return [p for p in RACINE.rglob("*.py") if "__pycache__" not in p.parts]


def _lecteurs() -> dict[str, list[int]]:
    """Les modules qui lisent le couple eux-mêmes — hors source, hors prose."""
    trouves: dict[str, list[int]] = {}
    for chemin in _fichiers():
        rel = chemin.relative_to(RACINE).as_posix()
        if rel == SOURCE:
            continue
        lignes = [
            n + 1
            for n, ligne in enumerate(chemin.read_text(encoding="utf-8").split(chr(10)))
            if "ConfigSite" in ligne
            and all(cle in ligne for cle in COUPLE)
            and not ligne.lstrip().startswith(("#", "*"))
        ]
        if lignes:
            trouves[rel] = lignes
    return trouves


def test_cas_zero_la_source_nomme_bien_les_deux_cles():
    """Sans quoi le motif ne reconnaîtrait plus rien, et ne refuserait plus rien."""
    source = (RACINE / SOURCE).read_text(encoding="utf-8")
    assert all(cle in source for cle in COUPLE), (
        f"`{SOURCE}` ne nomme plus les deux clés : ce contrôle ne reconnaît plus "
        "la lecture qu'il protège."
    )
    assert len(_fichiers()) > 50, "le parcours ne décrit plus `app/`"


def test_personne_ne_RECOPIE_la_lecture_du_couple():
    """🔴 Aucune exception, et c'est délibéré.

    Ce contrôle est posé APRÈS que le compte soit tombé à zéro — huit recopies
    converties dans le même lot. Il n'a donc rien à tolérer. Le jour où une
    exception paraîtra nécessaire, la vraie question sera : que manque-t-il à
    `config_site` ? Elle accepte déjà des clés SUPPLÉMENTAIRES, ce qui a suffi
    aux deux lecteurs qui demandaient le couple ET d'autres clés.
    """
    fautifs = _lecteurs()
    assert not fautifs, (
        f"Ces modules relisent `site_nom` / `site_url` eux-mêmes : {fautifs}. "
        "Employer `config_site(session)` de `app.utils.config_site` — et "
        "`config_site(session, \"autre_cle\")` si d'autres clés sont nécessaires."
    )


def test_la_lecture_partagee_rend_bien_les_deux_cles():
    """Le fait, pas la forme : la fonction lit ce qu'elle promet.

    Un contrôle qui n'interdirait que la recopie resterait vert si la source
    cessait de rendre l'une des deux clés — et chaque appelant retomberait alors
    sur le repli de `nom_site` / `base_site`, sans que rien ne le dise.
    """
    from sqlmodel import Session, SQLModel, create_engine

    from app.models.core import ConfigSite
    from app.utils.config_site import config_site, contexte_site

    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as session:
        session.add(ConfigSite(cle="site_nom", valeur="Résidence 5 Hostachy"))
        session.add(ConfigSite(cle="site_url", valeur="https://5hostachy.fr"))
        session.add(ConfigSite(cle="autre", valeur="ignorée"))
        session.commit()

        cfg = config_site(session)
        assert cfg == {
            "site_nom": "Résidence 5 Hostachy",
            "site_url": "https://5hostachy.fr",
        }, cfg

        #  Les clés supplémentaires arrivent EN PLUS, jamais à la place.
        elargi = config_site(session, "autre")
        assert elargi["autre"] == "ignorée"
        assert elargi["site_nom"] == "Résidence 5 Hostachy"

        ctx = contexte_site(cfg)
        assert ctx["residence"]["nom"] == "Résidence 5 Hostachy"
        assert ctx["app"]["url"].startswith("https://5hostachy.fr")
