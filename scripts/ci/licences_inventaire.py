"""Collecte des licences tierces — npm par les verrous, Python par les métadonnées.

Rend des listes de `{"nom", "licence", "portee"}` triées par nom. Une source
qui ne peut pas être lue lève `Inconnu` : le contrôle rend alors INCONNU,
jamais un vert sur ce qu'il n'a pas lu (`standards/04` §1).
"""

from __future__ import annotations

import json
import pathlib

from licences_spdx import licence_python

#  L'environnement de l'IMAGE de l'API (`api/Dockerfile`, python:3.12 sur un
#  Raspberry Pi) — pas celui du poste qui lance le contrôle. Évaluer les
#  marqueurs ici, c'est inventorier ce qui part en production : `uvloop` en
#  fait partie, `colorama` (Windows) non.
ENVIRONNEMENT_IMAGE = {
    "implementation_name": "cpython",
    "os_name": "posix",
    "platform_machine": "aarch64",
    "platform_python_implementation": "CPython",
    "platform_system": "Linux",
    "python_full_version": "3.12.0",
    "python_version": "3.12",
    "sys_platform": "linux",
}


class Inconnu(Exception):
    """La source n'a pas pu être mesurée."""


def _trier(paquets: dict[tuple[str, str], set[str]]) -> list[dict]:
    return [
        {"nom": nom, "licence": licence, "portee": ", ".join(sorted(portees))}
        for (nom, licence), portees in sorted(paquets.items())
    ]


def paquets_npm(verrou: pathlib.Path) -> list[dict]:
    """Chaque entrée de `package-lock.json` (v2+), avec la licence qu'il porte."""
    try:
        donnees = json.loads(verrou.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Inconnu(f"{verrou.name} illisible ({e})") from e
    entrees = donnees.get("packages")
    if donnees.get("lockfileVersion", 0) < 2 or not isinstance(entrees, dict):
        raise Inconnu(f"{verrou.name} : format de verrou sans section `packages`")
    paquets: dict[tuple[str, str], set[str]] = {}
    for cle, entree in entrees.items():
        if not cle or entree.get("link"):
            continue  # la racine du projet, ou un lien vers une entrée déjà listée
        nom = entree.get("name") or cle.rsplit("node_modules/", 1)[-1]
        licence = entree.get("license")
        if not isinstance(licence, str) or not licence.strip():
            licence = "NON DÉCLARÉE"
        portee = "devDependencies" if entree.get("dev") else "dependencies"
        if entree.get("optional") or entree.get("devOptional"):
            portee += " (optionnel)"
        paquets.setdefault((nom, licence.strip()), set()).add(portee)
    return _trier(paquets)


def _exigences(fichier: pathlib.Path) -> list[str]:
    try:
        lignes = fichier.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise Inconnu(f"{fichier.name} illisible ({e})") from e
    exigences = []
    for ligne in lignes:
        ligne = ligne.split("#", 1)[0].strip()
        if not ligne:
            continue
        if ligne.startswith("-"):
            raise Inconnu(f"{fichier.name} : option `{ligne}` non prise en charge")
        exigences.append(ligne)
    return exigences


def paquets_python(fichier: pathlib.Path) -> tuple[list[dict], list[str], list[str]]:
    """(paquets, réserves sur le jugement, réserves sur le document) — le graphe
    des distributions installées, depuis les exigences de production. `portee`
    vaut `directe` pour une ligne du fichier, `transitive` sinon.

    Une distribution ABSENTE ne lève pas : les autres restent jugées, et la
    réserve est rendue — l'appelant en fait un INCONNU. Une transitive absente
    (`uvloop` sur un poste Windows) ne touche que le jugement : le document ne
    fige que les directes. Une directe absente, ou installée dans une autre
    version que celle épinglée, touche les deux : sa métadonnée ne serait pas
    celle de l'image.
    """
    try:
        import importlib.metadata as md

        from packaging.requirements import Requirement
        from packaging.utils import canonicalize_name
    except ImportError as e:
        raise Inconnu(f"module `packaging` absent ({e})") from e

    directes = [Requirement(e) for e in _exigences(fichier)]
    noms_directs = {canonicalize_name(r.name) for r in directes}
    document: list[str] = []
    for r in directes:
        try:
            version = md.version(r.name)
        except md.PackageNotFoundError:
            document.append(f"{r.name} (directe) non installée ici")
            continue
        if r.specifier and not r.specifier.contains(version, prereleases=True):
            document.append(f"{r.name} installée en {version}, épinglée {r.specifier}")
    politique = list(document)

    extras_vus: dict[str, set[str]] = {}
    absentes: list[str] = []
    pile = list(directes)
    while pile:
        exigence = pile.pop()
        nom = canonicalize_name(exigence.name)
        demandes = set(exigence.extras)
        if nom in extras_vus and demandes <= extras_vus[nom]:
            continue
        extras_vus[nom] = extras_vus.get(nom, set()) | demandes
        try:
            dist = md.distribution(exigence.name)
        except md.PackageNotFoundError:
            absentes.append(nom)
            continue
        for texte in dist.requires or []:
            dependance = Requirement(texte)
            contextes = extras_vus[nom] or {""}
            if dependance.marker and not any(
                dependance.marker.evaluate({**ENVIRONNEMENT_IMAGE, "extra": x}) for x in contextes
            ):
                continue
            pile.append(dependance)
    transitives = sorted(set(absentes) - noms_directs)
    if transitives:
        politique.append(f"transitive(s) non installée(s) ici : {', '.join(transitives)}")
    paquets: dict[tuple[str, str], set[str]] = {}
    for nom in extras_vus:
        if nom in absentes:
            continue
        meta = md.metadata(nom)
        licence, _source = licence_python(
            meta.get("License-Expression"), meta.get("License"), meta.get_all("Classifier") or []
        )
        portee = "directe" if nom in noms_directs else "transitive"
        paquets.setdefault((nom, licence), set()).add(portee)
    return _trier(paquets), politique, document
