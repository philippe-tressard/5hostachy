"""Visibilité par entité — publication, sondage, événement, ticket.

⚠️ Fragment de `app/utils/visibility/` — **la règle reste unique**, elle a seulement
cessé de tenir dans un seul fichier (#547, 20/08/2026). Le paquet expose la même
surface qu'avant : `from app.utils.visibility import …` ne change pas d'une ligne
pour ses seize importateurs.

Le découpage suit une couture réelle, pas la ligne où le compteur a dépassé :
`socle` porte les deux primitives que tout le reste compose (géographie et public
visé), `objets` les règles par entité, `documents` l'algorithme d'accès en cinq
étapes — le seul qui interroge la base, et le seul adossé à un modèle de profil
d'accès.
"""
from __future__ import annotations

from datetime import datetime

from app.models.core import (
    Evenement,
    Publication,
    RoleUtilisateur,
    Sondage,
    Ticket,
    TypeEvenement,
    Utilisateur,
)
from app.utils.perimetres import parse_perimetres

#  ⚠️ `_codes_json_pour_acces` est privé au paquet, pas au fichier : c'est le
#  parseur commun des listes de codes (« qui est visé »), et deux fragments le
#  composent. Le découpage a coupé cette dépendance au premier essai — 56 tests
#  sont tombés d'un coup sur un `NameError`, ce qui est la bonne façon d'échouer.
from .socle import _codes_json_pour_acces, perimetre_visible, public_cible_visible

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
    #
    #  `confidentiel` (#347) ne fait que **refermer** cette ouverture-là, et rien
    #  d'autre : il n'existe pas de seconde règle d'accès pour les actualités
    #  confidentielles — c'est le paramètre à sa valeur par défaut, c'est-à-dire
    #  le comportement d'avant #339. Une règle à part aurait dû être maintenue en
    #  parallèle de celle-ci, et c'est ainsi que deux règles divergent.
    if not perimetre_visible(
        perims, user, ouvert_a_la_copropriete=not pub.confidentiel
    ):
        return False

    # 2. Public cible — règle partagée avec les sondages, voir plus haut.
    return public_cible_visible(pub.public_cible, user)


# ── Règles sondage ────────────────────────────────────────────────────────────

def sondage_clos(sondage: Sondage, maintenant: datetime) -> bool:
    """Ce sondage est-il terminé — de force, ou parce que l'échéance est passée ?

    Les DEUX voies comptent, et c'est tout l'intérêt d'une écriture unique : la
    même expression était recopiée quatre fois côté API (fiche du sondage, vote,
    modification, fil d'activité) et une cinquième côté front (`estCloture`).
    Le compteur du tableau de bord, lui, ne regardait que `cloture_forcee` — il
    annonçait donc « actifs » des sondages que tous les autres écrans donnaient
    pour clos, jusqu'à ce que quelqu'un pense à cliquer sur « clôturer ». Deux
    définitions coexistaient, et c'est la plus permissive qui alimentait la
    pastille (#399).

    `maintenant` est passé en paramètre, jamais lu ici : le fil calcule son
    instant une fois par requête (`ContexteFlux.now`) et douze rubriques qui
    appelleraient `utcnow()` chacune ne dateraient plus la même clôture.
    """
    return bool(
        sondage.cloture_forcee
        or (sondage.cloture_le is not None and sondage.cloture_le < maintenant)
    )


def resultats_sondage_visibles(resultats_publics: bool, cloture: bool) -> bool:
    """Les décomptes de ce sondage peuvent-ils quitter le serveur ?

    `resultats_publics` signifie « visibles **avant** la clôture » : une fois le
    sondage clos, ils le sont dans tous les cas.

    ⚠️ Cette règle décide de ce que l'API **envoie**, pas de ce que le front
    affiche. Jusqu'au 17/08/2026 elle n'existait pas : `GET /sondages/{id}`
    renvoyait `nb_votes` et les réponses en texte libre sans aucune condition, et
    seul le front tentait de les masquer. Décocher la case ne cachait donc rien —
    les résultats restaient lisibles dans la réponse réseau par tout destinataire
    avant son vote, alors que la case existe précisément pour qu'un vote en cours
    n'influence pas les suivants (#397).

    L'audience, elle, n'est PAS gérée ici : c'est celle du sondage, décidée par
    `sondage_accessible` (périmètre + public cible). Cette fonction ne répond
    qu'à la question du calendrier — avant ou après la clôture.

    Aucune exception pour l'auteur ni pour le conseil syndical : ils sont donc
    aveugles à la participation jusqu'à la clôture quand la case est décochée.
    C'est ce que l'option promet littéralement, et le défaut le plus sûr pour
    l'intégrité du vote — à rouvrir si l'usage montre que c'est trop strict.
    """
    return bool(resultats_publics or cloture)


def sondage_accessible(sondage: Sondage, user: Utilisateur) -> bool:
    """
    Retourne True si l'utilisateur peut voir/voter à ce sondage.

    - CS / Admin : toujours True.
    - `perimetre_cible` (JSON de codes) : vide = aucune restriction géographique.
    - `public_cible` (JSON de codes) : vide = tous les profils.

    C'est **exactement** la règle des publications, à une exception près et elle
    est délibérée : `ouvert_a_la_copropriete` reste à sa valeur par défaut, donc
    faux. Une actualité ciblée sur un bâtiment reste lisible de toute la
    copropriété (#339) parce qu'elle informe ; un sondage, lui, fait **voter** —
    l'ouvrir changerait qui pèse sur le résultat. L'accès d'un sondage ciblé sur
    un bâtiment est donc rigoureusement celui d'avant l'unification.
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True
    perims = _codes_json_pour_acces(sondage.perimetre_cible)
    if perims is None:
        #  Ciblage illisible : on refuse. Un contrôle qui ne peut pas s'exécuter
        #  ne renvoie jamais OK (`standards/04`), et le CS est déjà sorti plus
        #  haut — il garde donc de quoi corriger le sondage.
        return False
    if not perimetre_visible(perims, user):
        return False
    return public_cible_visible(sondage.public_cible, user)


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

# ── Règles ticket ─────────────────────────────────────────────────────────────
def ticket_visible(ticket: Ticket, user: Utilisateur) -> bool:
    """
    Retourne True si l'utilisateur peut voir ce ticket.

    - CS / Admin : toujours True.
    - Auteur du ticket (auteur_id == user.id).
    - Résident inscrit pour le compte duquel le ticket a été saisi
      (saisi_pour_user_id == user.id).
    """
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True
    if ticket.auteur_id == user.id:
        return True
    if ticket.saisi_pour_user_id is not None and ticket.saisi_pour_user_id == user.id:
        return True
    return False
