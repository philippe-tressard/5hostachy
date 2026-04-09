"""
Service d'auto-match déclenché à l'activation d'un utilisateur.

Appelé depuis :
  - admin.py  : traiter_compte (action="valider")
  - auth.py   : register (si inscription directement active — futur)

Pour chaque nouveau user, passe en revue les 3 files d'import staging
(lots, TC, vigik) et tente de lier automatiquement les lignes en attente
dont le nom correspond à ce user.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Optional

from sqlmodel import Session, select


# ── Types copropriétaires (pour propagation conjoint) ────────────────────────

_TYPES_COPROPRIETAIRES = {"propriétaire", "bailleur", "mandataire"}


def _lot_coproprio_ids(lot_id: int | None, session: Session) -> set[int]:
    """Retourne les user_ids des copropriétaires d'un lot."""
    if not lot_id:
        return set()
    from app.models.core import UserLot
    user_lots = session.exec(
        select(UserLot).where(UserLot.lot_id == lot_id, UserLot.actif == True)
    ).all()
    return {
        ul.user_id for ul in user_lots
        if (ul.type_lien.value if hasattr(ul.type_lien, "value") else str(ul.type_lien))
        in _TYPES_COPROPRIETAIRES
    }


def _all_coproprio_ids(user_id: int, session: Session) -> set[int]:
    """Retourne tous les user_ids qui partagent au moins un lot avec user_id."""
    from app.models.core import UserLot
    # Lots de cet utilisateur
    my_lots = session.exec(
        select(UserLot).where(UserLot.user_id == user_id, UserLot.actif == True)
    ).all()
    lot_ids = {
        ul.lot_id for ul in my_lots
        if (ul.type_lien.value if hasattr(ul.type_lien, "value") else str(ul.type_lien))
        in _TYPES_COPROPRIETAIRES
    }
    if not lot_ids:
        return set()
    # Tous les copropriétaires sur ces lots
    co_owners = session.exec(
        select(UserLot).where(
            UserLot.lot_id.in_(list(lot_ids)),  # type: ignore
            UserLot.actif == True,
        )
    ).all()
    return {
        ul.user_id for ul in co_owners
        if (ul.type_lien.value if hasattr(ul.type_lien, "value") else str(ul.type_lien))
        in _TYPES_COPROPRIETAIRES
    }


def _create_user_telecommandes(tc, session: Session) -> None:
    """Crée les UserTelecommande pour le détenteur + tous les copropriétaires partagés."""
    from app.models.core import UserTelecommande
    user_ids = {tc.user_id}
    user_ids |= _lot_coproprio_ids(tc.lot_id, session)
    user_ids |= _all_coproprio_ids(tc.user_id, session)
    for uid in user_ids:
        existing = session.exec(
            select(UserTelecommande).where(
                UserTelecommande.user_id == uid,
                UserTelecommande.telecommande_id == tc.id,
            )
        ).first()
        if not existing:
            session.add(UserTelecommande(user_id=uid, telecommande_id=tc.id))


def _create_user_vigiks(vigik, session: Session) -> None:
    """Crée les UserVigik pour le détenteur + tous les copropriétaires partagés."""
    from app.models.core import UserVigik
    user_ids = {vigik.user_id}
    user_ids |= _lot_coproprio_ids(vigik.lot_id, session)
    user_ids |= _all_coproprio_ids(vigik.user_id, session)
    for uid in user_ids:
        existing = session.exec(
            select(UserVigik).where(
                UserVigik.user_id == uid,
                UserVigik.vigik_id == vigik.id,
            )
        ).first()
        if not existing:
            session.add(UserVigik(user_id=uid, vigik_id=vigik.id))


# ── Normalisation ────────────────────────────────────────────────────────────

def _norm(s: Optional[str]) -> str:
    if not s:
        return ""
    # Normalise pour comparaison robuste : accents, casse, ponctuation, espaces.
    s = s.strip().casefold()
    s = "".join(
        c for c in unicodedata.normalize("NFKD", s)
        if unicodedata.category(c) != "Mn"
    )
    # Uniformise apostrophes/traits d'union/ponctuation en séparateurs neutres.
    s = re.sub(r"[^0-9a-z]+", " ", s)
    return " ".join(s.split())


def _split_name_candidates(raw_name: Optional[str]) -> list[str]:
    """Découpe une cellule de noms potentiellement multi-occupants en candidats."""
    if not raw_name:
        return []
    raw = str(raw_name).strip()
    if not raw:
        return []
    # Séparateurs rencontrés dans les imports : ';', '/', '|', '&', '+', ' ET ', ' OU '.
    parts = re.split(r"\s*(?:;|/|\||&|\+)\s*|\s+(?:et|ou)\s+", raw, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p and p.strip()]


def _tokens(s: Optional[str]) -> list[str]:
    """Retourne les tokens significatifs (>3 car) d'une chaîne normalisée."""
    return [t for t in _norm(s).split() if len(t) > 3]


def _user_keys(nom: str, prenom: str) -> set[str]:
    """Ensemble des clés de recherche pour un user.

    N'inclut PAS le prénom seul ni les tokens individuels du nom
    pour éviter les faux positifs (ex. prénom commun "PHILIPPE"
    qui matcherait un autre copropriétaire homonyme de prénom).

    Clés générées :
      - NOM complet normalisé (ex. "de la fontaine" ou "dupont")
      - NOM PRENOM et PRENOM NOM
      - Variantes compactes (sans espaces) des combinaisons
    """
    n = _norm(nom)
    p = _norm(prenom)
    keys = set()
    if n:
        keys.add(n)
        keys.add(n.replace(" ", ""))
        # PAS de tokens individuels du nom — trop de faux positifs
    # PAS de prénom seul — "philippe" matcherait tout le monde
    if n and p:
        keys.add(f"{n} {p}")
        keys.add(f"{p} {n}")
        keys.add(f"{n}{p}".replace(" ", ""))
        keys.add(f"{p}{n}".replace(" ", ""))
    return keys


def _statut_to_type_lien(statut) -> str:
    """Mappe le statut d'un utilisateur vers le type_lien dans LotImport."""
    _MAP = {
        "copropriétaire_résident": "propriétaire",
        "copropriétaire_bailleur": "bailleur",
        "mandataire": "mandataire",
        "locataire": "locataire",
    }
    val = statut.value if hasattr(statut, "value") else str(statut)
    return _MAP.get(val, "propriétaire")


def count_lots_for_user(nom: str, prenom: str, session: Session) -> int:
    """Dry-run : compte les LotImport dont le nom_coproprietaire correspond à ce user.
    Inclut tous les statuts pour donner un aperçu global (même 'resolu')."""
    from app.models.core import LotImport, StatutLotImport
    keys = _user_keys(nom, prenom)
    imports = session.exec(
        select(LotImport).where(
            LotImport.statut.in_([
                StatutLotImport.en_attente,
                StatutLotImport.utilisateur_lie,
                StatutLotImport.lot_lie,
                StatutLotImport.resolu,
            ])
        )
    ).all()
    count = 0
    for imp in imports:
        if not imp.nom_coproprietaire:
            continue
        for nom_brut in _split_name_candidates(imp.nom_coproprietaire):
            if _matches_user(nom_brut.strip(), keys):
                count += 1
                break
    return count


def _matches_user(raw_name: str, user_keys: set[str]) -> bool:
    """True si le nom brut de l'Excel correspond au user.

    Stratégies (du plus strict au plus souple) :
      1. Nom complet normalisé exact (ex. "dupont jean")
      2. Variante compacte sans espaces (ex. "dupontjean")
      3. Bigrammes consécutifs pour noms avec bruit (ex. "M. DUPONT JEAN")
      4. Chaque mot significatif (>3 car) testé contre les clés NOM
         (gère "M. DUPONT" → "dupont", mais aussi "ALIF MASSON" → "masson")
         user_keys ne contient PAS le prénom seul → pas de faux positif.
    """
    for part in _split_name_candidates(raw_name):
        norm = _norm(part)
        if not norm:
            continue
        if norm in user_keys:
            return True
        compact = norm.replace(" ", "")
        if compact and compact in user_keys:
            return True
        # Bigrammes pour capter "NOM PRENOM" avec ponctuation/titres bruitées
        words = [w for w in norm.split() if len(w) > 2]
        for i in range(len(words) - 1):
            if f"{words[i]} {words[i + 1]}" in user_keys:
                return True
        # Tenter chaque mot significatif individuellement contre les clés NOM.
        # user_keys ne contient PAS le prénom seul → pas de faux positif
        # sur un prénom commun. Permet de matcher "ALIF MASSON" → user "Christophe MASSON"
        # via la clé NOM "masson".
        for w in words:
            if len(w) > 3 and w in user_keys:
                return True
    return False


# ── Auto-match TC ─────────────────────────────────────────────────────────────

def _auto_match_tc(user, session: Session) -> int:
    from datetime import datetime
    from app.models.core import (
        TelecommandeImport, StatutImport, UserLot,
        Telecommande, StatutAcces,
    )
    keys = _user_keys(user.nom, user.prenom)
    imports = session.exec(
        select(TelecommandeImport).where(
            TelecommandeImport.statut.in_([
                StatutImport.en_attente,
                StatutImport.proprietaire_lie,
            ])
        )
    ).all()

    matched = 0
    for imp in imports:
        changed = False
        if not imp.user_proprietaire_id and imp.nom_proprietaire:
            if _matches_user(imp.nom_proprietaire, keys):
                imp.user_proprietaire_id = user.id
                changed = True
        if not imp.user_locataire_id and imp.nom_locataire:
            if _matches_user(imp.nom_locataire, keys):
                imp.user_locataire_id = user.id
                changed = True
        # Auto-link lot via UserLot si proprio connu et 1 seul lot
        if changed and imp.user_proprietaire_id and not imp.lot_id:
            user_lots = session.exec(
                select(UserLot).where(
                    UserLot.user_id == imp.user_proprietaire_id,
                    UserLot.actif == True,
                )
            ).all()
            if len(user_lots) == 1:
                imp.lot_id = user_lots[0].lot_id
        if changed:
            if imp.user_proprietaire_id:
                imp.statut = StatutImport.proprietaire_lie
            # Auto-résolution : créer la Telecommande si proprio lié + référence
            if imp.user_proprietaire_id and imp.reference:
                holder_id = (
                    imp.user_locataire_id
                    if (imp.chez_locataire and imp.user_locataire_id)
                    else imp.user_proprietaire_id
                )
                tc = Telecommande(
                    code=imp.reference,
                    lot_id=imp.lot_id or None,
                    user_id=holder_id,
                    chez_locataire=imp.chez_locataire and bool(imp.user_locataire_id),
                    statut=StatutAcces.actif,
                )
                session.add(tc)
                session.flush()
                # Associer les copropriétaires du lot
                _create_user_telecommandes(tc, session)
                imp.statut = StatutImport.resolu
                imp.telecommande_id = tc.id
                imp.resolu_le = datetime.utcnow()
            session.add(imp)
            matched += 1
    return matched


# ── Auto-match Vigik ──────────────────────────────────────────────────────────

def _auto_match_vigik(user, session: Session) -> int:
    from datetime import datetime
    from app.models.core import VigikImport, StatutImport, UserLot, Vigik, StatutAcces
    from app.utils.import_vigiks import _build_lot_index, normaliser as _norm_vigik
    keys = _user_keys(user.nom, user.prenom)
    imports = session.exec(
        select(VigikImport).where(
            VigikImport.statut.in_([
                StatutImport.en_attente,
                StatutImport.proprietaire_lie,
            ])
        )
    ).all()
    lot_index = _build_lot_index(session)

    matched = 0
    for imp in imports:
        changed = False
        if not imp.user_proprietaire_id and imp.nom_proprietaire:
            if _matches_user(imp.nom_proprietaire, keys):
                imp.user_proprietaire_id = user.id
                changed = True
        if not imp.user_locataire_id and imp.nom_locataire:
            if _matches_user(imp.nom_locataire, keys):
                imp.user_locataire_id = user.id
                changed = True
        # Résolution lot via colonnes brutes
        if not imp.lot_id and imp.batiment_raw and imp.appartement_raw:
            key = (_norm_vigik(imp.batiment_raw), _norm_vigik(imp.appartement_raw))
            lot_id = lot_index.get(key)
            if lot_id:
                imp.lot_id = lot_id
                changed = True
        # Auto-link lot via UserLot
        if changed and imp.user_proprietaire_id and not imp.lot_id:
            user_lots = session.exec(
                select(UserLot).where(
                    UserLot.user_id == imp.user_proprietaire_id,
                    UserLot.actif == True,
                )
            ).all()
            if len(user_lots) == 1:
                imp.lot_id = user_lots[0].lot_id
        if changed:
            if imp.user_proprietaire_id:
                imp.statut = StatutImport.proprietaire_lie
            # Auto-résolution : créer le Vigik si proprio lié + code
            if imp.user_proprietaire_id and imp.code:
                holder_id = (
                    imp.user_locataire_id
                    if (imp.chez_locataire and imp.user_locataire_id)
                    else imp.user_proprietaire_id
                )
                vigik = Vigik(
                    code=imp.code,
                    lot_id=imp.lot_id or None,
                    user_id=holder_id,
                    statut=StatutAcces.actif,
                )
                session.add(vigik)
                session.flush()
                # Associer les copropriétaires du lot
                _create_user_vigiks(vigik, session)
                imp.statut = StatutImport.resolu
                imp.vigik_id = vigik.id
                imp.resolu_le = datetime.utcnow()
            session.add(imp)
            matched += 1
    return matched


# ── Auto-match Lots ───────────────────────────────────────────────────────────

def _auto_match_lots(user, session: Session) -> int:
    from app.models.core import LotImport, StatutLotImport, UserLot, TypeLien

    def _tl(s: str) -> TypeLien:
        try:
            return TypeLien(s)
        except ValueError:
            return TypeLien.propriétaire

    keys = _user_keys(user.nom, user.prenom)

    # Passe 1 : imports en attente / utilisateur_lie / lot_lie → ajouter à utilisateurs_json
    imports = session.exec(
        select(LotImport).where(
            LotImport.statut.in_([
                StatutLotImport.en_attente,
                StatutLotImport.utilisateur_lie,
                StatutLotImport.lot_lie,       # lot connu mais user pas encore matché
            ])
        )
    ).all()

    matched = 0
    for imp in imports:
        if not imp.nom_coproprietaire:
            continue
        # Décomposer les noms potentiellement multiples (couples, séparateurs divers).
        noms = _split_name_candidates(imp.nom_coproprietaire)
        current_users: list[dict] = json.loads(imp.utilisateurs_json or "[]")
        existing_ids = {e["user_id"] for e in current_users}
        added = False
        type_lien = _statut_to_type_lien(user.statut)
        for nom in noms:
            if user.id in existing_ids:
                continue
            if _matches_user(nom, keys):
                current_users.append({"user_id": user.id, "type_lien": type_lien})
                existing_ids.add(user.id)
                added = True
        if added:
            imp.utilisateurs_json = json.dumps(current_users, ensure_ascii=False)
            if imp.lot_id:
                imp.statut = StatutLotImport.lot_lie
            else:
                imp.statut = StatutLotImport.utilisateur_lie
            session.add(imp)
            matched += 1

    # Passe 2 : imports déjà résolu (lot_id connu) où ce user n'est pas encore lié.
    # Cas typique : import résolu sans occupant, user inscrit après coup.
    # → ajouter à utilisateurs_json ET créer UserLot directement.
    imports_resolu = session.exec(
        select(LotImport).where(
            LotImport.statut == StatutLotImport.resolu,
            LotImport.lot_id.is_not(None),  # type: ignore
        )
    ).all()

    TYPES_COPROPRIETAIRES = {"propriétaire", "bailleur", "mandataire"}
    type_lien = _statut_to_type_lien(user.statut)

    for imp in imports_resolu:
        if not imp.nom_coproprietaire or type_lien not in TYPES_COPROPRIETAIRES:
            continue
        noms = _split_name_candidates(imp.nom_coproprietaire)
        if not any(_matches_user(nom, keys) for nom in noms):
            continue
        # Vérifier d'abord si le UserLot existe réellement en base
        # (utilisateurs_json peut contenir l'user_id sans UserLot correspondant
        #  si supprimer_user_lot a été appelé avant le fix du nettoyage json).
        existing_ul = session.exec(
            select(UserLot).where(UserLot.user_id == user.id, UserLot.lot_id == imp.lot_id)
        ).first()
        if existing_ul:
            continue  # déjà lié correctement
        # Créer le UserLot manquant
        session.add(UserLot(user_id=user.id, lot_id=imp.lot_id, type_lien=_tl(type_lien), actif=True))
        # Synchroniser utilisateurs_json si l'entry est absente
        current_users = json.loads(imp.utilisateurs_json or "[]")
        existing_ids = {e["user_id"] for e in current_users}
        if user.id not in existing_ids:
            current_users.append({"user_id": user.id, "type_lien": type_lien})
            imp.utilisateurs_json = json.dumps(current_users, ensure_ascii=False)
            session.add(imp)
        matched += 1

    return matched


def _is_coproprietaire(user) -> bool:
    """True si ce user est copropriétaire/bailleur/mandataire (doit être résolu automatiquement)."""
    TYPES = {"copropriétaire_résident", "copropriétaire_bailleur", "mandataire"}
    val = user.statut.value if hasattr(user.statut, "value") else str(user.statut)
    return val in TYPES


# ── Auto-résolution lots pour un utilisateur ─────────────────────────────────

def _auto_resoudre_lots_pour_utilisateur(user, session: Session) -> int:
    """Résout les LotImport où ce user est lié (copropriétaire/bailleur/mandataire).
    Crée les UserLot correspondants. Ne pas appeler pour les locataires.
    Ne committe pas — l'appelant doit faire session.commit()."""
    import unicodedata as _ud
    from datetime import datetime
    from app.models.core import (
        LotImport, StatutLotImport, Lot, UserLot, TypeLot, TypeLien, Utilisateur,
    )

    def _tl(s: str) -> TypeLien:
        try:
            return TypeLien(s)
        except ValueError:
            return TypeLien.propriétaire

    _TYPE_PARKING = {"PS"}
    _TYPE_CAVE = {"CA"}
    _ETAGE_MAP = {"RDC": 0, "1ER": 1, "1SS": -1, "2EME": 2, "2SS": -2,
                  "3EME": 3, "3SS": -3, "4EME": 4, "5EME": 5}

    def _norm2(s):
        if not s:
            return ""
        s = s.strip().upper()
        s = "".join(c for c in _ud.normalize("NFD", s) if _ud.category(c) != "Mn")
        return " ".join(s.split())

    def _lot_type(type_raw):
        t = _norm2(type_raw)
        if t in _TYPE_PARKING:
            return TypeLot.parking, None
        if t in _TYPE_CAVE:
            return TypeLot.cave, None
        type_app = t if t not in ("AP", "DIV", "LC", "") else None
        return TypeLot.appartement, type_app

    def _etage(etage_raw):
        return _ETAGE_MAP.get(_norm2(etage_raw)) if etage_raw else None

    TYPES_COPROPRIETAIRES = {"propriétaire", "bailleur", "mandataire"}

    imports = session.exec(
        select(LotImport).where(
            LotImport.statut.in_([StatutLotImport.utilisateur_lie, StatutLotImport.lot_lie])
        )
    ).all()

    resolus = 0
    for imp in imports:
        users = json.loads(imp.utilisateurs_json or "[]")
        # Ce user doit être dans la liste avec un rôle copropriétaire
        user_entry = next(
            (u for u in users if u.get("user_id") == user.id
             and u.get("type_lien", "propriétaire") in TYPES_COPROPRIETAIRES),
            None,
        )
        if not user_entry:
            continue
        # Si un locataire est lié à cet import, ne pas auto-résoudre (supervision manuelle)
        # Note : avec le type_lien correct, cela ne bloque plus les bailleurs entre eux
        # → skip uniquement si le SEUL occupant non-copropriétaire est un locataire (edge case)
        # On ne bloque plus : la boucle UserLot ci-dessous filtre les locataires elle-même
        # Trouver / créer le lot
        lot = session.get(Lot, imp.lot_id) if imp.lot_id else None
        if not lot:
            if imp.batiment_id:
                lot = session.exec(
                    select(Lot).where(Lot.batiment_id == imp.batiment_id, Lot.numero == imp.numero)
                ).first()
            else:
                # Parking : chercher parmi les lots sans bâtiment
                lot = session.exec(
                    select(Lot).where(Lot.batiment_id.is_(None), Lot.numero == imp.numero)  # type: ignore
                ).first()
        if not lot:
            # Créer le lot (parking autorisé avec batiment_id=None)
            lot_type, type_app = _lot_type(imp.type_raw)
            lot = Lot(
                batiment_id=imp.batiment_id,  # None pour parking
                numero=imp.numero,
                type=lot_type,
                type_appartement=type_app,
                etage=_etage(imp.etage_raw),
            )
            session.add(lot)
            session.flush()
        imp.lot_id = lot.id
        # Créer les UserLot pour les occupants copropriétaires/bailleurs/mandataires
        # Les locataires ne sont pas auto-résolus (workflow manuel)
        noms_import = _split_name_candidates(imp.nom_coproprietaire or "")
        for entry in users:
            uid = entry.get("user_id")
            tl_raw = entry.get("type_lien", "propriétaire")
            if not uid:
                continue
            if tl_raw not in TYPES_COPROPRIETAIRES:
                continue  # Locataires exclus de la résolution automatique
            existing = session.exec(
                select(UserLot).where(UserLot.user_id == uid, UserLot.lot_id == lot.id)
            ).first()
            # Garde-fou anti-pollution: revalider le nom utilisateur contre la ligne import.
            # Empêche qu'une ancienne entrée erronée dans utilisateurs_json crée un UserLot.
            linked_user = session.get(Utilisateur, uid)
            if not linked_user:
                continue
            if noms_import:
                linked_keys = _user_keys(linked_user.nom, linked_user.prenom)
                if not any(_matches_user(nom_brut, linked_keys) for nom_brut in noms_import):
                    if existing:
                        session.delete(existing)
                    continue
            tl = _tl(tl_raw)
            if not existing:
                session.add(UserLot(user_id=uid, lot_id=lot.id, type_lien=tl, actif=True))
        imp.statut = StatutLotImport.resolu
        imp.resolu_le = datetime.utcnow()
        session.add(imp)
        resolus += 1
    return resolus


# ── Auto-liaison annuaire CS / Syndic ──────────────────────────────────────

def _auto_link_annuaire(user, session: Session) -> dict:
    """Lie ce user aux membres CS et Syndic dont le NOM correspond (NFD, insensible casse).
    Ne committe pas — l'appelant doit faire session.commit()."""
    from app.models.core import MembreCS, MembreSyndic

    user_nom_norm = _norm(user.nom)
    if not user_nom_norm:
        return {"cs": 0, "syndic": 0}

    cs_linked = 0
    for membre in session.exec(select(MembreCS)).all():
        if membre.user_id:
            continue
        if membre.nom and _norm(membre.nom) == user_nom_norm:
            membre.user_id = user.id
            session.add(membre)
            cs_linked += 1

    syndic_linked = 0
    for membre in session.exec(select(MembreSyndic)).all():
        if membre.user_id:
            continue
        if membre.nom and _norm(membre.nom) == user_nom_norm:
            membre.user_id = user.id
            session.add(membre)
            syndic_linked += 1

    return {"cs": cs_linked, "syndic": syndic_linked}


# ── Point d'entrée principal ──────────────────────────────────────────────────

def auto_match_pour_utilisateur(user, session: Session) -> dict:
    """
    Lance l'auto-match sur les 3 systèmes d'import pour un utilisateur donné,
    puis résout automatiquement les LotImport copropriétaires reconnus.

    Ordre critique :
      1. lots      → lie le user aux LotImport (crée utilisateurs_json)
      2. resoudre  → crée les UserLot (lots résolus en DB)
      3. tc        → auto-link lot via UserLot (SEULEMENT si propriétaire a des lots)
      4. vigik     → auto-link lot via UserLot (SEULEMENT si propriétaire a des lots)
      5. baux      → lie le locataire aux baux créés par email (si locataire)

    RÈGLE CRITIQUE pour propriétaires/bailleures :
      - Si lots_resolus = 0 ET c'est un copropriétaire/bailleur/mandataire
      - ALORS tc et vigik ne seront pas traités (0 affectation)

    Ne committe pas — l'appelant doit faire session.commit().
    """
    from app.models.core import StatutUtilisateur
    
    lots         = _auto_match_lots(user, session)
    # Flush pour que les nouveaux statuts soient visibles dans _auto_resoudre
    session.flush()
    lots_resolus = _auto_resoudre_lots_pour_utilisateur(user, session)
    # Flush pour que les UserLot soient visibles dans TC/Vigik
    session.flush()
    
    # Déterminer si c'est un copropriétaire et vérifier s'il y a des lots résolus
    user_statut = user.statut.value if hasattr(user.statut, "value") else str(user.statut)
    is_coproprietaire = user_statut in {
        StatutUtilisateur.copropriétaire_résident.value,
        StatutUtilisateur.copropriétaire_bailleur.value,
        StatutUtilisateur.mandataire.value
    }
    
    # RÈGLE : Pour les propriétaires, TC/Vigik ne sont traités que si lots ont réussi
    if is_coproprietaire and lots_resolus == 0:
        tc = 0
        vigik = 0
    else:
        tc      = _auto_match_tc(user, session)
        vigik   = _auto_match_vigik(user, session)
    
    baux    = _auto_match_baux_locataire(user, session)
    annuaire = _auto_link_annuaire(user, session)
    return {
        "lots": lots,
        "lots_resolus": lots_resolus,
        "tc": tc,
        "vigik": vigik,
        "baux": baux,
        "annuaire_cs": annuaire["cs"],
        "annuaire_syndic": annuaire["syndic"],
        "total": lots + tc + vigik + baux + annuaire["cs"] + annuaire["syndic"],
    }


# ── Auto-liaison bail par email (locataires) ─────────────────────────────────

def _auto_match_baux_locataire(user, session: Session) -> int:
    """Lie ce user comme locataire sur les baux créés avec son email.
    Ne committe pas — l'appelant doit faire session.commit()."""
    from app.models.core import LocationBail, StatutBail, StatutUtilisateur

    # Uniquement pour les locataires
    val = user.statut.value if hasattr(user.statut, "value") else str(user.statut)
    if val != StatutUtilisateur.locataire.value:
        return 0

    if not user.email:
        return 0

    baux = session.exec(
        select(LocationBail).where(
            LocationBail.locataire_email == user.email.lower().strip(),
            LocationBail.locataire_id.is_(None),  # type: ignore
            LocationBail.statut != StatutBail.termine,
        )
    ).all()

    matched = 0
    for bail in baux:
        bail.locataire_id = user.id
        session.add(bail)
        matched += 1
    return matched
