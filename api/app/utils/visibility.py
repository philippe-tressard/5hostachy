"""
Règles de visibilité centralisées — source de vérité unique.

Toute logique de filtrage par rôle/périmètre/profil doit passer par ce module.
Ne jamais dupliquer ces règles dans les routers.

Règles métier appliquées :
  - CS et Admin voient toujours tout (pas de filtre).
  - Syndic : lecture seule sur tout (pas filtré ici — géré par les dépendances auth).
  - Mandataire : non géré ici (filtrage lot dans bailleur.py — périmètre trop spécifique).
  - Périmètre géographique : résidence/parking/cave/aful = visible par tous résidents ;
      bat:N visible uniquement si user.batiment_id == N.
  - public_cible (publications) : résidents = tous ; copropriétaires = statut copropriétaire_* ;
      locataires = statut locataire uniquement.
  - AG (événements) : visible uniquement par propriétaires, CS et admins.
  - Sondages : profils_autorises (CSV statuts) + batiments_ids (CSV ids bâtiments).
"""
from __future__ import annotations

import json
from typing import Optional

from app.models.core import (
    Evenement,
    Publication,
    RoleUtilisateur,
    Sondage,
    TypeEvenement,
    Utilisateur,
)

# ── Périmètres "résidence entière" (visibles par tous les résidents) ──────────
SCOPES_RESIDENCE = frozenset({"résidence", "parking", "cave", "aful"})


# ── Parseurs internes ─────────────────────────────────────────────────────────

def _parse_json_list(raw: Optional[str], default: list[str]) -> list[str]:
    """Parse un champ JSON stocké en base (ex: '["bat:1","bat:3"]')."""
    if not raw:
        return default
    try:
        val = json.loads(raw) if isinstance(raw, str) else raw
        return list(val) if isinstance(val, (list, tuple)) else default
    except Exception:
        return default


def _parse_csv(raw: Optional[str]) -> list[str]:
    """Parse un champ CSV (ex: 'bat:1,résidence')."""
    if not raw:
        return []
    return [v.strip() for v in raw.split(",") if v.strip()]


# ── Règles géographiques ──────────────────────────────────────────────────────

def perimetre_visible(perimetres: list[str], user: Utilisateur) -> bool:
    """
    Retourne True si le périmètre de l'item est accessible à l'utilisateur.

    - CS / Admin : toujours True.
    - Périmètre résidence/parking/cave/aful : True pour tout résident.
    - Périmètre bat:N : True uniquement si user.batiment_id == N.
    - Liste vide : considérée comme 'résidence' → True.
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True
    if not perimetres:
        return True
    perims_lower = {p.lower() for p in perimetres}
    if perims_lower & SCOPES_RESIDENCE:
        return True
    if user.batiment_id is None:
        # Pas de bâtiment assigné → accès résidence entière par défaut
        return True
    return f"bat:{user.batiment_id}" in perims_lower


# ── Règles publication ────────────────────────────────────────────────────────

def publication_visible(pub: Publication, user: Utilisateur) -> bool:
    """
    Retourne True si l'utilisateur peut voir cette publication.

    Vérifie deux dimensions indépendantes :
      1. Périmètre géographique (perimetre_cible)
      2. Public cible (public_cible) : résidents | copropriétaires | locataires
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True

    # 1. Périmètre géographique
    perims = _parse_json_list(pub.perimetre_cible, ["résidence"])
    if not perimetre_visible(perims, user):
        return False

    # 2. Public cible
    public = _parse_json_list(pub.public_cible, ["résidents"])
    if "résidents" in public:
        return True
    statut = str(user.statut or "")
    if "copropriétaires" in public:
        return statut.startswith("copropriétaire_")
    if "locataires" in public:
        return statut == "locataire"
    # public_cible vide ou valeur inconnue → visible par tous
    return True


# ── Règles sondage ────────────────────────────────────────────────────────────

def sondage_accessible(sondage: Sondage, user: Utilisateur) -> bool:
    """
    Retourne True si l'utilisateur peut voir/voter à ce sondage.

    - CS / Admin : toujours True.
    - profils_autorises (CSV de StatutUtilisateur) : vide = tous les profils.
    - batiments_ids (CSV d'ids) : vide = toute la résidence.
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True
    profils = _parse_csv(sondage.profils_autorises)
    if profils and (user.statut is None or str(user.statut) not in profils):
        return False
    batiments = _parse_csv(sondage.batiments_ids)
    if batiments and (user.batiment_id is None or str(user.batiment_id) not in batiments):
        return False
    return True


# ── Règles événement ──────────────────────────────────────────────────────────

def evenement_visible(ev: Evenement, user: Utilisateur) -> bool:
    """
    Retourne True si l'utilisateur peut voir cet événement.

    - AG invisible pour les locataires, mandataires, syndics et aidants.
    - maintenance_recurrente invisible pour tous (usage interne uniquement).
    - Périmètre géographique (champ CSV ev.perimetre).
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        # CS/Admin voient tout sauf maintenance_recurrente (usage interne)
        if ev.type == TypeEvenement.maintenance_recurrente:
            return False
        return True

    if ev.type == TypeEvenement.maintenance_recurrente:
        return False

    if ev.type == TypeEvenement.ag:
        if not user.has_role(RoleUtilisateur.propriétaire):
            return False

    perims = _parse_csv(ev.perimetre) if ev.perimetre else ["résidence"]
    return perimetre_visible(perims, user)


# ── Règle AG (helper rapide) ──────────────────────────────────────────────────

def can_see_ag(user: Utilisateur) -> bool:
    """True si l'utilisateur peut voir les événements AG."""
    return user.has_role(
        RoleUtilisateur.propriétaire,
        RoleUtilisateur.conseil_syndical,
        RoleUtilisateur.admin,
    )
