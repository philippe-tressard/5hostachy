"""Exporter et réimporter une copropriété, dans un format NEUTRE et VÉRIFIÉ (#1749).

Lot P2-7 du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
§4.3 et §4.9). Un même outil, trois usages :

- **aujourd'hui** : prouver qu'une base se RESTAURE, au lieu de le supposer
  (`verifier_restauration`, bouton d'Administration › Maintenance) ;
- **demain** : faire changer la résidence de moteur de base, vers PostgreSQL
  (DI-7, #1759) — le format ne doit rien au moteur d'origine ;
- **ensuite** : rendre ses données à une copropriété qui part (réversibilité).

## Le format

Une archive `.tar.gz` :

| Chemin | Contenu |
|---|---|
| `manifeste.json` | version du format, révision Alembic, date, et pour CHAQUE table : colonnes, nombre de lignes, empreinte SHA-256 |
| `tables/<table>.jsonl` | une ligne JSON par enregistrement, valeurs neutres (`valeur_neutre`) |
| `fichiers/…` | les fichiers téléversés, avec leur empreinte dans le manifeste (si demandés) |

L'empreinte d'une table se calcule sur ses lignes NEUTRES, triées par clé
primaire : elle ne dépend ni du moteur, ni de l'ordre de lecture. C'est elle qui
rend l'import VÉRIFIÉ — après l'écriture, il relit la base cible, recalcule
chaque empreinte et REFUSE un écart (la transaction est annulée).

## Ce que l'outil ne fait pas, et le dit

- Une table présente en base mais absente des modèles (une table historique)
  n'est pas exportée : elle est NOMMÉE dans le manifeste (`ignorees`).
- 🔴 Règle d'or : l'export lit la base de l'APPLICATION dans le processus de
  l'API (l'endpoint), en une seule transaction de lecture — jamais depuis un
  processus tiers tant que l'API tourne (CLAUDE.md). L'import écrit dans une
  base CIBLE, jamais dans celle qui sert.

🔒 `tests/test_export_copropriete.py`.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import tarfile
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from uuid import UUID

from sqlalchemy import Date, DateTime, LargeBinary, Numeric, Time, inspect, select, text
from sqlmodel import SQLModel

from app.utils import horloge
import app.models.core  # noqa: F401 — enregistre TOUTES les tables (#1157)

FORMAT = 1


# ── Les valeurs neutres (PURES) ───────────────────────────────────────────────


def valeur_neutre(v):
    """Une valeur de base en JSON sans perte, identique quel que soit le moteur.

    Un type inconnu LÈVE : une valeur rendue au hasard ferait une empreinte fausse,
    et un export « réussi » qui ne se réimporte pas à l'identique.
    """
    if v is None or isinstance(v, (bool, int, str, float)):
        return v
    if isinstance(v, Enum):
        return v.name
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (date, time)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"$b64": base64.b64encode(bytes(v)).decode("ascii")}
    if isinstance(v, (dict, list)):
        return v
    raise TypeError(f"valeur de type {type(v).__name__} sans forme neutre déclarée")


def valeur_typee(colonne, v):
    """L'inverse de `valeur_neutre`, guidé par le TYPE de la colonne cible."""
    if v is None:
        return None
    if isinstance(v, dict) and set(v) == {"$b64"}:
        return base64.b64decode(v["$b64"])
    t = colonne.type
    if isinstance(t, DateTime):
        return datetime.fromisoformat(v)
    if isinstance(t, Date):
        return date.fromisoformat(v)
    if isinstance(t, Time):
        return time.fromisoformat(v)
    if isinstance(t, Numeric) and isinstance(v, str):
        return Decimal(v)
    if isinstance(t, LargeBinary) and isinstance(v, str):
        return base64.b64decode(v)
    return v


def ligne_neutre(ligne) -> dict:
    return {nom: valeur_neutre(v) for nom, v in ligne.items()}


def _cle_de_tri(table, ligne: dict):
    cles = [c.name for c in table.primary_key.columns] or sorted(ligne)
    return tuple((ligne[c] is None, str(ligne[c])) for c in cles)


def empreinte_table(table, lignes: list[dict]) -> str:
    """PURE. SHA-256 des lignes neutres triées par clé primaire, colonnes triées."""
    h = hashlib.sha256()
    for ligne in sorted(lignes, key=lambda li: _cle_de_tri(table, li)):
        h.update(
            json.dumps(ligne, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        )
        h.update(b"\n")
    return h.hexdigest()


# ── La lecture d'une base ─────────────────────────────────────────────────────


def tables() -> list:
    """Les tables des modèles, dans l'ordre des clés étrangères (parents d'abord)."""
    return list(SQLModel.metadata.sorted_tables)


def lire(connexion) -> tuple[dict[str, list[dict]], list[str], str | None]:
    """Toutes les tables (lignes neutres), les tables ignorées, la révision Alembic."""
    presentes = set(inspect(connexion).get_table_names())
    contenu = {
        t.name: [ligne_neutre(li) for li in connexion.execute(select(t)).mappings()]
        for t in tables()
        if t.name in presentes
    }
    connues = {t.name for t in tables()} | {"alembic_version"}
    ignorees = sorted(presentes - connues)
    revision = None
    if "alembic_version" in presentes:
        revision = connexion.execute(text("SELECT version_num FROM alembic_version")).scalar()
    return contenu, ignorees, revision


def manifeste_de(contenu: dict[str, list[dict]], ignorees: list[str], revision) -> dict:
    par_nom = {t.name: t for t in tables()}
    return {
        "format": FORMAT,
        "revision": revision,
        "cree_le": horloge.maintenant().isoformat(timespec="seconds"),  # UTC
        "ignorees": ignorees,
        "tables": {
            nom: {
                "colonnes": sorted(c.name for c in par_nom[nom].columns),
                "lignes": len(lignes),
                "empreinte": empreinte_table(par_nom[nom], lignes),
            }
            for nom, lignes in contenu.items()
        },
    }


# ── L'export ──────────────────────────────────────────────────────────────────


def _ajouter(archive: tarfile.TarFile, chemin: str, donnees: bytes) -> None:
    info = tarfile.TarInfo(chemin)
    info.size = len(donnees)
    archive.addfile(info, io.BytesIO(donnees))


def exporter(moteur, sortie: Path, *, fichiers: Path | None = None) -> dict:
    """Écrit l'archive ; rend son manifeste. Une seule transaction de lecture."""
    with moteur.connect() as connexion, connexion.begin():
        contenu, ignorees, revision = lire(connexion)
    manifeste = manifeste_de(contenu, ignorees, revision)
    inventaire = []
    with tarfile.open(sortie, "w:gz") as archive:
        for nom, lignes in contenu.items():
            corps = "".join(
                json.dumps(li, ensure_ascii=False, separators=(",", ":")) + "\n" for li in lignes
            )
            _ajouter(archive, f"tables/{nom}.jsonl", corps.encode())
        if fichiers is not None and fichiers.is_dir():
            for chemin in sorted(p for p in fichiers.rglob("*") if p.is_file()):
                rel = chemin.relative_to(fichiers).as_posix()
                donnees = chemin.read_bytes()
                inventaire.append(
                    {
                        "chemin": rel,
                        "octets": len(donnees),
                        "sha256": hashlib.sha256(donnees).hexdigest(),
                    }
                )
                _ajouter(archive, f"fichiers/{rel}", donnees)
        manifeste["fichiers"] = inventaire
        _ajouter(
            archive, "manifeste.json", json.dumps(manifeste, ensure_ascii=False, indent=1).encode()
        )
    return manifeste


# ── L'import, vérifié ─────────────────────────────────────────────────────────


class ImportRefuse(Exception):
    """La base cible ne porte pas EXACTEMENT ce que l'archive annonce."""


@dataclass
class Bilan:
    tables: int = 0
    lignes: int = 0
    fichiers: int = 0
    ecarts: list[str] = field(default_factory=list)


def _recaler_sequences(connexion) -> None:
    """PostgreSQL : après des identifiants écrits à la main, la séquence repart après eux."""
    if connexion.dialect.name != "postgresql":
        return
    for t in tables():
        cles = list(t.primary_key.columns)
        if (
            len(cles) == 1
            and cles[0].autoincrement in (True, "auto")
            and str(cles[0].type) == "INTEGER"
        ):
            connexion.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{t.name}', '{cles[0].name}'), "  # noqa: S608 — identifiants des modèles
                    f"COALESCE((SELECT MAX({cles[0].name}) FROM {t.name}), 0) + 1, false)"
                )
            )


def importer(archive_chemin: Path, moteur, *, fichiers: Path | None = None) -> Bilan:
    """Écrit l'archive dans une base CIBLE au schéma posé et vide, puis la VÉRIFIE.

    Tout écart lève `ImportRefuse`, et la transaction est annulée : la base cible
    reste vide plutôt que fausse.
    """
    with tarfile.open(archive_chemin, "r:gz") as archive:
        manifeste = json.loads(archive.extractfile("manifeste.json").read())
        if manifeste.get("format") != FORMAT:
            raise ImportRefuse(f"format {manifeste.get('format')} inconnu (attendu {FORMAT})")
        par_nom = {t.name: t for t in tables()}
        inconnues = sorted(set(manifeste["tables"]) - set(par_nom))
        if inconnues:
            raise ImportRefuse(f"tables absentes des modèles de ce code : {inconnues}")
        bilan = Bilan()
        with moteur.connect() as connexion, connexion.begin():
            for t in tables():
                if t.name not in manifeste["tables"]:
                    continue
                lignes = [
                    json.loads(li)
                    for li in archive.extractfile(f"tables/{t.name}.jsonl")
                    .read()
                    .decode()
                    .splitlines()
                ]
                if lignes:
                    colonnes = {c.name: c for c in t.columns}
                    connexion.execute(
                        t.insert(),
                        [{k: valeur_typee(colonnes[k], v) for k, v in li.items()} for li in lignes],
                    )
                bilan.tables += 1
                bilan.lignes += len(lignes)
            _recaler_sequences(connexion)
            relu, _ignorees, _rev = lire(connexion)
            for nom, attendu in manifeste["tables"].items():
                obtenu = relu.get(nom, [])
                if len(obtenu) != attendu["lignes"]:
                    bilan.ecarts.append(
                        f"{nom} : {len(obtenu)} ligne(s), l'archive en annonce {attendu['lignes']}"
                    )
                elif empreinte_table(par_nom[nom], obtenu) != attendu["empreinte"]:
                    bilan.ecarts.append(f"{nom} : contenu différent de l'archive (empreinte)")
            if bilan.ecarts:
                raise ImportRefuse("; ".join(bilan.ecarts))
        if fichiers is not None:
            for f in manifeste.get("fichiers", []):
                donnees = archive.extractfile(f"fichiers/{f['chemin']}").read()
                if hashlib.sha256(donnees).hexdigest() != f["sha256"]:
                    raise ImportRefuse(f"fichier {f['chemin']} altéré dans l'archive")
                cible = fichiers / f["chemin"]
                cible.parent.mkdir(parents=True, exist_ok=True)
                cible.write_bytes(donnees)
                bilan.fichiers += 1
    return bilan


def verifier_restauration(moteur_source, dossier: Path) -> tuple[dict, Bilan]:
    """Exporte la base (sans fichiers) puis la réimporte dans une base neuve et jetable.

    Rend le manifeste et le bilan. Une base qui ne se restaure pas lève
    `ImportRefuse` : c'est précisément ce que ce geste doit dire.
    """
    from app.dialecte import moteur_jetable

    archive = dossier / "verification.tar.gz"
    cible = dossier / "verification.db"
    manifeste = exporter(moteur_source, archive)
    moteur_cible = moteur_jetable(cible)
    try:
        SQLModel.metadata.create_all(moteur_cible)
        bilan = importer(archive, moteur_cible)
    finally:
        moteur_cible.dispose()
        for f in (archive, cible):
            if f.exists():
                os.remove(f)
    return manifeste, bilan


# ── En ligne de commande : l'IMPORT dans une base cible (DI-7) ────────────────
#
#     python -m app.utils.export_copropriete importer <archive> <url-cible> [<dossier-fichiers>]
#
#  Pour le passage à PostgreSQL (DI-7, #1759) : la cible est une base NEUVE, au
#  schéma posé. 🔴 Jamais la base qui sert : l'export, lui, ne se lance que par
#  l'administration, dans le processus de l'API (règle d'or).
if __name__ == "__main__":
    import sys

    from sqlmodel import create_engine

    if len(sys.argv) < 4 or sys.argv[1] != "importer":
        sys.exit(
            "usage : python -m app.utils.export_copropriete importer <archive> <url-cible> [<fichiers>]"
        )
    _cible = create_engine(sys.argv[3])
    SQLModel.metadata.create_all(_cible)
    try:
        _bilan = importer(
            Path(sys.argv[2]), _cible, fichiers=Path(sys.argv[4]) if len(sys.argv) > 4 else None
        )
    except ImportRefuse as _refus:
        sys.exit(f"IMPORT REFUSÉ : {_refus}")
    print(
        f"Importé et vérifié : {_bilan.tables} tables, {_bilan.lignes} lignes, {_bilan.fichiers} fichiers."
    )
