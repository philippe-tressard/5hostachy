"""
Règles de visibilité centralisées — source de vérité unique.

Toute logique de filtrage par rôle/périmètre/profil doit passer par ce module.
Ne jamais dupliquer ces règles dans les routers.

Règles métier appliquées :
  - CS et Admin voient toujours tout (pas de filtre).
  - Syndic : lecture seule sur tout (pas filtré ici — géré par les dépendances auth).
  - Mandataire : non géré ici (filtrage lot dans bailleur.py — périmètre trop spécifique).
  - Périmètre géographique : un nœud à portée globale (ou dont un ancêtre l'est) est
      visible par tous les résidents ; sinon, visible si le bâtiment du nœud — ou de
      son plus proche ancêtre qui en porte un — est celui de l'utilisateur.
      La liste des périmètres transverses n'est plus écrite ici : elle était en trois
      exemplaires (ici, `flux/evenements.py`, et le tableau de bord côté front) et
      c'est désormais le drapeau `portee_globale` de la table `perimetre`.
  - public_cible (publications) : résidents = tous ; copropriétaires = statut copropriétaire_* ;
      bailleurs = copropriétaire_bailleur uniquement ; locataires = statut locataire
      uniquement ; conseil_syndical = CS/admin uniquement.
      Si public_cible contient une valeur non reconnue ou non correspondante → non visible.
  - AG (événements) : visible uniquement par propriétaires, CS et admins.
  - Sondages : profils_autorises (CSV statuts) + batiments_ids (CSV ids bâtiments).
"""
from __future__ import annotations

import json
from typing import Optional

from app.models.core import (
    Document,
    Evenement,
    ProfilAccesDocument,
    Publication,
    RoleUtilisateur,
    Sondage,
    Ticket,
    TypeEvenement,
    Utilisateur,
)
from app.utils.mes_batiments import batiments_de_l_utilisateur
from app.utils.perimetres import a_portee_globale, batiments_cibles, parse_perimetres

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


def _codes_json_pour_acces(raw: Optional[str]) -> Optional[list[str]]:
    """Codes de périmètre d'un champ JSON, pour une **décision d'accès**.

    Distingue trois états là où `utils/perimetres.parse_json_perimetres` n'en
    distingue que deux, et la nuance est une nuance de sécurité :

    - champ absent ou vide → `[]`, c'est-à-dire « aucune restriction ». C'était
      déjà le comportement, et il est conservé ;
    - JSON valide → les codes ;
    - JSON **illisible** → `None`, et l'appelant refuse.

    Ce dernier cas est un changement assumé. Jusqu'ici, un `perimetre_cible`
    corrompu retombait sur `["résidence"]` : une donnée abîmée **élargissait** la
    visibilité au lieu de la restreindre. Pour un badge à l'écran ce repli est
    bienvenu (cf. `parse_json_perimetres`) ; pour décider qui a le droit de lire,
    il est exactement à l'envers.
    """
    if not raw:
        return []
    try:
        val = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None
    if not isinstance(val, (list, tuple)):
        return None
    return [str(v) for v in val]


# ── Règles géographiques ──────────────────────────────────────────────────────

def perimetre_visible(
    perimetres: list[str], user: Utilisateur, *, ouvert_a_la_copropriete: bool = False
) -> bool:
    """
    Retourne True si le périmètre de l'item est accessible à l'utilisateur.

    - CS / Admin : toujours True.
    - Nœud à portée globale, ou dont un ancêtre l'est : True pour tout résident.
    - `ouvert_a_la_copropriete` : les contenus dont le bâtiment ne restreint plus
      la lecture — actualités et tickets (#339). Voir ci-dessous.
    - Sinon : True si le bâtiment du nœud (ou du plus proche ancêtre qui en porte
      un) est celui de l'utilisateur.
    - Liste vide : aucune restriction → True.

    ## `ouvert_a_la_copropriete` — ce que ce paramètre ouvre, et ce qu'il n'ouvre pas

    Il vaut **False par défaut**, et c'est le point important : le comportement
    d'hier reste celui de tout ce qui ne demande pas explicitement l'ouverture.
    Documents, sondages et événements d'AG ne la demandent pas, et leur accès est
    donc rigoureusement inchangé.

    Ce paramètre élargit l'axe **bâtiment**, jamais l'axe **public**. Cette
    fonction est combinée en ET avec `public_cible` (résidents, copropriétaires,
    bailleurs, locataires, CS), avec `ProfilAccesDocument` et avec les règles
    mandataire de `routers/bailleur.py` : l'ouvrir ne peut donc rien débloquer
    pour quelqu'un que ces règles refusent. Contrainte posée par l'utilisateur le
    14/08/2026 — *une agence, un bailleur ou un mandataire qui n'avaient pas de
    visibilité n'en gagnent aucune* — et vérifiée couple par couple dans
    `tests/test_visibilite_ouverte.py`.

    - Code introuvable : n'accorde **rien**. Un nœud supprimé, un arbre vidé ou une
      table illisible ne peuvent pas justifier un accès — ils ne permettent pas de
      décider, et un contrôle qui ne peut pas s'exécuter ne renvoie jamais OK
      (`standards/04`). La première écriture de cette fonction court-circuitait à
      `True` quand l'arbre était vide : `tests/test_documents_acces.py` l'a
      attrapée, une pièce jointe ciblée sur un autre bâtiment devenant lisible dès
      que la table manquait.

    L'ordre des tests reproduit exactement celui de la règle précédente, qui
    comparait des chaînes : `api/tests/test_perimetres_arbre.py` rejoue l'ancienne
    implémentation contre celle-ci sur tous les couples (périmètre × utilisateur)
    et exige des verdicts identiques.
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True
    if not perimetres:
        return True
    if a_portee_globale(perimetres):
        return True

    if ouvert_a_la_copropriete:
        if not getattr(user, "restreindre_a_mes_batiments", False):
            return True
        #  L'utilisateur s'est restreint LUI-MÊME. On prend alors ses bâtiments au
        #  sens large — rattachement et lots —, parce qu'il s'agit de lui montrer
        #  les siens, pas de lui accorder quoi que ce soit : cette liste ne sert
        #  qu'ici, et seulement pour montrer MOINS.
        miens = batiments_de_l_utilisateur(user)
        if not miens:
            #  Cas zéro : rien de connu, donc rien à restreindre. Renvoyer False
            #  laisserait un fil vide à qui a simplement coché une case.
            return True
        return bool(miens & batiments_cibles(perimetres))

    if user.batiment_id is None:
        #  Pas de bâtiment assigné → accès résidence entière par défaut.
        #  ⚠️ Repli permissif **conservé volontairement** : le corriger changerait
        #  qui voit quoi aujourd'hui, ce qui n'est pas l'objet de ce lot. Il est
        #  épinglé par un test pour qu'il ne bouge pas par accident, et suivi à part.
        return True
    return user.batiment_id in batiments_cibles(perimetres)


# ── Règles publication ────────────────────────────────────────────────────────

def publication_visible(pub: Publication, user: Utilisateur) -> bool:
    """
    Retourne True si l'utilisateur peut voir cette publication.

    Vérifie deux dimensions indépendantes :
      1. Périmètre géographique (perimetre_cible)
      2. Public cible (public_cible) : résidents | copropriétaires | locataires | conseil_syndical
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True

    # 1. Périmètre géographique
    perims = _codes_json_pour_acces(pub.perimetre_cible)
    if perims is None:
        #  Ciblage illisible : on refuse. Le CS et l'admin sont déjà sortis plus
        #  haut et gardent donc l'accès nécessaire pour corriger la publication.
        return False
    #  `ouvert_a_la_copropriete` : une actualité ciblée sur un autre bâtiment reste
    #  lisible (#339). La vie d'une copropriété se passe rarement dans un seul
    #  bâtiment — un chantier, une coupure, une réunion concernent souvent sans
    #  être « chez soi ». Le résident qui préfère l'ancien fonctionnement coche
    #  « n'afficher que mes bâtiments » dans son profil.
    #
    #  ⚠️ Ce n'est QUE l'axe bâtiment. Le public cible ci-dessous n'est pas touché,
    #  et c'est lui qui protège : une agence, un bailleur non résident ou un
    #  mandataire qui ne voyaient pas cette publication ne la voient pas davantage.
    if not perimetre_visible(perims, user, ouvert_a_la_copropriete=True):
        return False

    # 2. Public cible
    public = _parse_json_list(pub.public_cible, ["résidents"])
    if not public:
        return True  # aucune restriction explicite
    if "résidents" in public:
        return True
    statut = user.statut.value if user.statut is not None else ""
    if "copropriétaires" in public and statut.startswith("copropriétaire_"):
        return True
    if "locataires" in public and statut == "locataire":
        return True
    #  « Bailleurs » vise les copropriétaires qui LOUENT leur lot, et eux seuls.
    #  `copropriétaires` ci-dessus les inclut déjà — il couvre les deux statuts
    #  `copropriétaire_*` — mais rien ne permettait de s'adresser à eux SANS
    #  toucher les copropriétaires occupants, alors que tout un pan du produit
    #  leur est propre (baux, remise d'objets, accès confiés aux locataires).
    #  Ajout purement additif : une valeur inconnue tombait déjà sur le `return
    #  False` final, donc aucune publication existante ne change de public.
    if "bailleurs" in public and statut == "copropriétaire_bailleur":
        return True
    # Valeur non reconnue ou accès restreint (ex: conseil_syndical) → non visible
    return False


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
    if profils and (user.statut is None or user.statut.value not in profils):
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

    #  `parse_perimetres` porte le repli : un événement sans périmètre désigne le
    #  nœud racine à portée globale, désigné par les données et non par une chaîne
    #  « résidence » écrite ici — une autre copropriété peut l'avoir renommé.
    return perimetre_visible(parse_perimetres(ev.perimetre), user)


# ── Règle AG (helper rapide) ──────────────────────────────────────────────────

def can_see_ag(user: Utilisateur) -> bool:
    """True si l'utilisateur peut voir les événements AG."""
    return user.has_role(
        RoleUtilisateur.propriétaire,
        RoleUtilisateur.conseil_syndical,
        RoleUtilisateur.admin,
    )

# \u2500\u2500 R\u00e8gles ticket \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n
def ticket_visible(ticket: Ticket, user: Utilisateur) -> bool:
    """
    Retourne True si l'utilisateur peut voir ce ticket.

    - CS / Admin : toujours True.
    - Auteur du ticket (auteur_id == user.id).
    - R\u00e9sident inscrit pour le compte duquel le ticket a \u00e9t\u00e9 saisi
      (saisi_pour_user_id == user.id).
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True
    if ticket.auteur_id == user.id:
        return True
    if ticket.saisi_pour_user_id is not None and ticket.saisi_pour_user_id == user.id:
        return True
    return False

# ── Règles document ───────────────────────────────────────────────────────────

def document_visible(user: Utilisateur, doc: Document, session) -> bool:
    """Retourne True si l'utilisateur a le droit de lire ce document.

    Algorithme d'accès en 5 étapes (specs modele-donnees.md). Un document tire sa
    protection soit de l'objet qui le porte (contrat, actualité), soit de son profil
    d'accès de catégorie — jamais des deux, jamais d'aucun.

    Cette règle vivait dans `routers/documents.py`, et `flux.py` l'importait depuis
    ce router. Une règle de sécurité hors du module central, c'est une règle qu'un
    durcissement ultérieur peut manquer : c'est exactement ce qui est arrivé aux
    pièces jointes d'actualité, autorisées sans consulter l'actualité porteuse
    (cf. `tests/test_documents_acces.py`). Elle est ici, avec les autres.

    `session` n'est typé que par usage (`.get`) pour ne pas faire dépendre ce module
    de SQLModel : seuls `Publication` et `ProfilAccesDocument` sont chargés.
    """
    # Admin et CS voient tout
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True

    # Documents liés à un contrat (sans catégorie) : CS/admin uniquement
    if doc.contrat_id and not doc.categorie_id:
        return False

    # Pièce jointe d'actualité : elle suit EXACTEMENT la visibilité de son actualité.
    # Un document n'a pas de ciblage propre (ni `public_cible`, ni `perimetre_cible`) ;
    # sa seule protection légitime est celle de la publication qui le porte.
    if doc.publication_id and not doc.categorie_id:
        pub = session.get(Publication, doc.publication_id)
        # Publication introuvable → on refuse : aucune règle à appliquer.
        # Brouillon → rien n'est publié, la pièce jointe non plus (CS/admin sont
        # déjà sortis plus haut et gardent l'accès à leurs brouillons).
        if not pub or pub.brouillon:
            return False
        return publication_visible(pub, user)

    profil_id = doc.profil_acces_override_id or doc.categorie.profil_acces_id
    profil: ProfilAccesDocument = session.get(ProfilAccesDocument, profil_id)
    if not profil:
        return False

    # Vérifier le rôle (supporte valeurs de rôles ET de statuts pour compatibilité)
    roles_autorises = json.loads(profil.roles_autorises)
    user_idents = set(user.roles) | {user.statut.value}
    if not any(r in roles_autorises for r in user_idents):
        return False

    # Vérifier le périmètre
    if doc.perimetre == "bâtiment" and doc.batiment_id:
        user_batiments = {
            ul.lot.batiment_id for ul in user.user_lots if ul.actif and ul.lot
        }
        if doc.batiment_id not in user_batiments:
            return False

    if doc.perimetre == "lot" and doc.lot_id:
        user_lots = {ul.lot_id for ul in user.user_lots if ul.actif}
        if doc.lot_id not in user_lots:
            return False

    return True
