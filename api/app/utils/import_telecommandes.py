"""
Utilitaire d'import des télécommandes depuis un fichier Excel (.xlsx).

Structure attendue du fichier (première ligne = en-tête ignorée) :
  Colonne A : nom du copropriétaire (requis)
  Colonne B : nom du locataire (optionnel)
  Colonne C : référence de la télécommande (optionnel sur quelques lignes spéciales)

Usage depuis le conteneur :
  docker compose exec api python -c "
  from app.utils.import_telecommandes import importer_depuis_fichier
  importer_depuis_fichier('/chemin/vers/fichier.xlsx')
  "
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

#  La mécanique d'un import (ouverture du classeur, transaction, normalisation)
#  vit dans `import_xlsx` : elle était écrite à l'identique dans les trois modules.
#  Ce qui reste ici est la seule chose qui leur soit propre — comment lire les
#  colonnes. `normaliser` est ré-exporté : `acces.py` et `auto_match_service.py`
#  l'importent depuis ce module.
from app.utils.import_xlsx import (  # noqa: F401  (ré-export de `normaliser`)
    importer_bytes,
    importer_fichier,
    normaliser,
)

from app.models.core import StatutImport, TelecommandeImport


# ── Noms à ignorer automatiquement (accès non-résidents) ──────────────────
_NOMS_IGNORES = {
    "PARKINGS PUBLIQUES",
    "0. ACCES MAIRIE",
    "ATPE",
    "CDE 22/06/2023",
    "- CDE 02/07/2024",
}




def importer_depuis_bytes(
    contenu: bytes,
    session: Session,
    remplacer: bool = False,
) -> dict:
    """Import depuis des octets en mémoire (téléversement HTTP)."""
    return importer_bytes(contenu, session, remplacer, _traiter_rows)


def importer_depuis_fichier(chemin: str, remplacer: bool = False) -> dict:
    """Importe les télécommandes depuis un xlsx (script en ligne de commande).

    Rend un dict aux clés ``importes``, ``ignores``, ``doublons``, ``erreurs``.
    """
    return importer_fichier(chemin, remplacer, _traiter_rows)


def _traiter_rows(rows: list, session: Session, remplacer: bool) -> dict:
    """Traite les lignes du classeur et insère les TelecommandeImport."""
    data_rows = rows[1:]  # ignorer l'en-tête
    stats: dict = {"importes": 0, "ignores": 0, "doublons": 0, "erreurs": []}

    if remplacer:
        existants = session.exec(
            select(TelecommandeImport).where(
                TelecommandeImport.statut == StatutImport.en_attente
            )
        ).all()
        for e in existants:
            session.delete(e)
        session.flush()

    for i, row in enumerate(data_rows, start=2):
        nom_prop_raw  = str(row[0]).strip() if row[0] else None
        nom_loc_raw   = str(row[1]).strip() if row[1] else None
        reference_raw = str(row[2]).strip() if row[2] else None

        if not nom_prop_raw:
            continue

        nom_prop_norm = normaliser(nom_prop_raw)

        if nom_prop_norm in _NOMS_IGNORES:
            stats["ignores"] += 1
            _creer_import(
                session, nom_prop_raw, nom_loc_raw, reference_raw,
                statut=StatutImport.ignore,
                notes_admin=f"Ignoré automatiquement (hors résidents) — ligne Excel {i}",
            )
            continue

        if nom_loc_raw and normaliser(nom_loc_raw) == nom_prop_norm:
            nom_loc_raw = None  # proprio-occupant

        if reference_raw:
            doublon = session.exec(
                select(TelecommandeImport).where(
                    TelecommandeImport.nom_proprietaire == nom_prop_raw,
                    TelecommandeImport.reference == reference_raw,
                )
            ).first()
            if doublon:
                stats["doublons"] += 1
                continue

        _creer_import(session, nom_prop_raw, nom_loc_raw, reference_raw)
        stats["importes"] += 1

    return stats


def _creer_import(
    session: Session,
    nom_proprietaire: str,
    nom_locataire: Optional[str],
    reference: Optional[str],
    statut: StatutImport = StatutImport.en_attente,
    notes_admin: Optional[str] = None,
) -> TelecommandeImport:
    record = TelecommandeImport(
        nom_proprietaire=nom_proprietaire,
        nom_locataire=nom_locataire or None,
        reference=reference or None,
        statut=statut,
        notes_admin=notes_admin,
        importe_le=datetime.utcnow(),
    )
    session.add(record)
    return record
